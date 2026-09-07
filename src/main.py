"""Entry point for the polite scraper — FlyRank A9."""

import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError, HttpUrl

USER_AGENT = "polite-scraper/1.0 (+https://github.com/Adithyaa-06/polite-scraper)"
TIMEOUT_SECONDS = 10
CACHE_DIR = "cache"
OUTPUT_DIR = "output"
DELAY_SECONDS = 0.5
RETRY_WAIT_SECONDS = 2

BASE_URL = "https://books.toscrape.com"
CATALOGUE_URL = f"{BASE_URL}/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

RATING_WORDS = {"One", "Two", "Three", "Four", "Five"}

# Set to True to inject one deliberately broken URL, per the Stage 5
# checkpoint. Leave False for a normal run.
INJECT_FAKE_URL_FOR_TESTING = False

# Simple run-scoped counter for cache hits, incremented inside fetch_page.
# Reset at the start of each run in __main__.
_cache_hit_count = 0


class BookRecord(BaseModel):
    """The clean, validated shape of one book record."""
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str | None = None
    description: str | None = None
    source_page: HttpUrl
    fetched_at: str


class FetchFailed(Exception):
    """Raised when a page could not be fetched after retries.

    Carries the HTTP status code (or None for connection/timeout errors)
    so the caller can log a useful reason without re-inspecting requests
    exceptions.
    """
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def fetch_page(url: str, cache_filename: str) -> tuple[str, bool]:
    """Fetch a page politely, using the cache if we already have it.

    Retries once on a timeout or a 5xx server error, after a short wait.
    Does NOT retry on 404 (the page does not exist) or 403 (the site said
    no) — retrying either of those only pesters the server for no gain.

    Returns (html, was_cached). Raises FetchFailed if the page could not
    be retrieved after the retry.
    """
    global _cache_hit_count

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, cache_filename)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT: {cache_filename} ({len(html)} bytes)")
        _cache_hit_count += 1
        return html, True

    headers = {"User-Agent": USER_AGENT}
    last_error: FetchFailed | None = None

    for attempt in (1, 2):
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            last_error = FetchFailed(f"timeout fetching {url}", status_code=None)
            if attempt == 1:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            raise last_error

        if response.status_code == 200:
            response.encoding = "utf-8"
            html = response.text
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"FETCH: {cache_filename} ({len(html)} bytes)")
            return html, False

        if response.status_code in (404, 403):
            # Permanent failures — asking again will not help.
            raise FetchFailed(
                f"{url} returned {response.status_code}", status_code=response.status_code
            )

        if response.status_code >= 500:
            last_error = FetchFailed(
                f"{url} returned {response.status_code}", status_code=response.status_code
            )
            if attempt == 1:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            raise last_error

        raise FetchFailed(
            f"{url} returned unexpected status {response.status_code}",
            status_code=response.status_code,
        )

    raise last_error


def discover_catalogue_pages():
    """Walk the catalogue's own 'next' links, up to MAX_CATALOGUE_PAGES.

    Returns a list of (book_url, source_page_url) tuples, de-duplicated
    by book_url, in first-seen order.
    """
    book_entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    current_url = CATALOGUE_URL
    pages_visited = 0

    for page_num in range(1, MAX_CATALOGUE_PAGES + 1):
        cache_filename = f"catalogue-page-{page_num}.html"
        html, was_cached = fetch_page(current_url, cache_filename)
        pages_visited += 1

        if not was_cached:
            time.sleep(DELAY_SECONDS)

        soup = BeautifulSoup(html, "html.parser")

        for article in soup.select("article.product_pod"):
            link = article.select_one("h3 a")
            if link and link.get("href"):
                absolute_url = urljoin(current_url, link["href"])
                if absolute_url not in seen:
                    seen.add(absolute_url)
                    book_entries.append((absolute_url, current_url))

        next_link = soup.select_one("li.next a")
        if not next_link or page_num == MAX_CATALOGUE_PAGES:
            break
        current_url = urljoin(current_url, next_link["href"])

    if INJECT_FAKE_URL_FOR_TESTING:
        fake_url = urljoin(BASE_URL, "catalogue/this-book-does-not-exist_0000/index.html")
        book_entries.append((fake_url, CATALOGUE_URL))

    return book_entries, pages_visited


def cache_filename_for_book(book_url: str) -> str:
    """Derive a stable cache filename from a book's slug, e.g.
    'a-light-in-the-attic_1000' -> 'book-a-light-in-the-attic_1000.html'."""
    slug = book_url.rstrip("/").split("/")[-2]
    return f"book-{slug}.html"


def parse_price_gbp(price_text: str) -> float:
    """Turn '£51.77' into 51.77."""
    cleaned = re.sub(r"[^0-9.]", "", price_text)
    return float(cleaned)


def extract_raw_record(book_url: str, source_page: str) -> dict:
    """Fetch one book detail page and pull out the raw record fields.

    May raise FetchFailed — the caller is responsible for catching it
    and logging the page as failed rather than crashing the whole run.
    """
    cache_filename = cache_filename_for_book(book_url)
    html, was_cached = fetch_page(book_url, cache_filename)

    if not was_cached:
        time.sleep(DELAY_SECONDS)

    soup = BeautifulSoup(html, "html.parser")
    product_main = soup.select_one("div.product_main")

    title = product_main.select_one("h1").get_text(strip=True) if product_main else None

    price_el = product_main.select_one("p.price_color") if product_main else None
    price_text = price_el.get_text(strip=True) if price_el else None

    availability_el = product_main.select_one("p.availability") if product_main else None
    availability_text = availability_el.get_text(strip=True) if availability_el else None

    rating_text = None
    if product_main:
        star_p = product_main.select_one("p.star-rating")
        if star_p:
            classes = star_p.get("class", [])
            rating_text = next((c for c in classes if c in RATING_WORDS), None)

    description_el = soup.select_one("#product_description ~ p")
    description = description_el.get_text(strip=True) if description_el else None

    return {
        "title": title,
        "product_url": book_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def clean_and_validate(raw: dict) -> tuple[BookRecord | None, str | None]:
    """Attempt to turn a raw record into a validated BookRecord.

    Returns (record, None) on success, or (None, reason) on failure.
    """
    try:
        price_gbp = parse_price_gbp(raw["price_text"]) if raw["price_text"] else None
        if price_gbp is None:
            return None, "missing or unparsable price_text"

        record = BookRecord(
            title=raw["title"],
            product_url=raw["product_url"],
            price_text=raw["price_text"],
            price_gbp=price_gbp,
            availability_text=raw["availability_text"],
            rating_text=raw["rating_text"],
            description=raw["description"],
            source_page=raw["source_page"],
            fetched_at=raw["fetched_at"],
        )
        return record, None
    except (ValidationError, ValueError, TypeError, KeyError) as e:
        return None, str(e)


if __name__ == "__main__":
    _cache_hit_count = 0

    run_started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()

    pages_fetched = 0
    failed_pages = 0
    valid_records: list[dict] = []
    errors: list[dict] = []
    seen_urls: set[str] = set()

    entries, catalogue_pages_visited = discover_catalogue_pages()
    pages_fetched += catalogue_pages_visited
    print(f"catalogue_pages={catalogue_pages_visited}")
    print(f"discovered={len(entries)}")
    print(f"unique_urls={len(set(u for u, _ in entries))}")

    for book_url, source_page in entries:
        try:
            raw = extract_raw_record(book_url, source_page)
        except FetchFailed as e:
            failed_pages += 1
            errors.append({"product_url": book_url, "reason": str(e)})
            continue

        pages_fetched += 1
        record, reason = clean_and_validate(raw)

        if record is None:
            errors.append({"product_url": book_url, "reason": reason})
            continue

        canonical_url = str(record.product_url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        valid_records.append(record.model_dump(mode="json"))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, "books.json"), "w", encoding="utf-8") as f:
        json.dump(valid_records, f, indent=2, ensure_ascii=False)

    with open(os.path.join(OUTPUT_DIR, "errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, indent=2, ensure_ascii=False)

    duration_seconds = round(time.monotonic() - start_time, 3)

    run_report = {
        "start_time": run_started_at.isoformat(),
        "duration_seconds": duration_seconds,
        "pages_fetched": pages_fetched,
        "cache_hits": _cache_hit_count,
        "valid_records": len(valid_records),
        "invalid_records": len(errors),
        "failed_pages": failed_pages,
    }
    with open(os.path.join(OUTPUT_DIR, "run-report.json"), "w", encoding="utf-8") as f:
        json.dump(run_report, f, indent=2)

    print(f"valid_records={len(valid_records)}")
    print(f"invalid_records={len(errors)}")
    print(f"failed_pages={failed_pages}")
    print("run_report:", run_report)
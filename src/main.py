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

BASE_URL = "https://books.toscrape.com"
CATALOGUE_URL = f"{BASE_URL}/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

RATING_WORDS = {"One", "Two", "Three", "Four", "Five"}


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


def fetch_page(url: str, cache_filename: str) -> tuple[str, bool]:
    """Fetch a page politely, using the cache if we already have it.

    Returns (html, was_cached). Prints FETCH on a real network request,
    CACHE HIT when reading from disk instead.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, cache_filename)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT: {cache_filename} ({len(html)} bytes)")
        return html, True

    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)

    if response.status_code != 200:
        raise RuntimeError(f"FETCH FAILED: {url} returned status {response.status_code}")

    response.encoding = "utf-8"
    html = response.text
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"FETCH: {cache_filename} ({len(html)} bytes)")
    return html, False


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

    return book_entries, pages_visited


def cache_filename_for_book(book_url: str) -> str:
    """Derive a stable cache filename from a book's slug, e.g.
    'a-light-in-the-attic_1000' -> 'book-a-light-in-the-attic_1000.html'."""
    slug = book_url.rstrip("/").split("/")[-2]
    return f"book-{slug}.html"


def parse_price_gbp(price_text: str) -> float:
    """Turn '£51.77' into 51.77. Strips any non-numeric characters except
    the decimal point, since the currency symbol (and any stray encoding
    artifacts) should never reach the numeric value."""
    cleaned = re.sub(r"[^0-9.]", "", price_text)
    return float(cleaned)


def extract_raw_record(book_url: str, source_page: str) -> dict:
    """Fetch one book detail page and pull out the raw record fields."""
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

    Returns (record, None) on success, or (None, reason) on failure —
    never both, never neither.
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
    entries, pages = discover_catalogue_pages()
    print(f"catalogue_pages={pages}")
    print(f"discovered={len(entries)}")
    print(f"unique_urls={len(set(u for u, _ in entries))}")

    valid_records: list[dict] = []
    errors: list[dict] = []
    seen_urls: set[str] = set()

    for book_url, source_page in entries:
        raw = extract_raw_record(book_url, source_page)
        record, reason = clean_and_validate(raw)

        if record is None:
            errors.append({"product_url": book_url, "reason": reason})
            continue

        # Canonical identity: the absolute product_url. Skip if we've
        # already stored this exact URL (idempotency at the record level).
        canonical_url = str(record.product_url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        # model_dump(mode="json") turns HttpUrl objects back into plain
        # strings so json.dump doesn't choke on a non-serializable type.
        valid_records.append(record.model_dump(mode="json"))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, "books.json"), "w", encoding="utf-8") as f:
        json.dump(valid_records, f, indent=2, ensure_ascii=False)

    with open(os.path.join(OUTPUT_DIR, "errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, indent=2, ensure_ascii=False)

    print(f"detail_pages={len(entries)}")
    print(f"valid_records={len(valid_records)}")
    print(f"invalid_records={len(errors)}")
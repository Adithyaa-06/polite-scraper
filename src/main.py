"""Entry point for the polite scraper — FlyRank A9."""

import os
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

USER_AGENT = "polite-scraper/1.0 (+https://github.com/Adithyaa-06/polite-scraper)"
TIMEOUT_SECONDS = 10
CACHE_DIR = "cache"
DELAY_SECONDS = 0.5

BASE_URL = "https://books.toscrape.com"
CATALOGUE_URL = f"{BASE_URL}/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

RATING_WORDS = {"One", "Two", "Three", "Four", "Five"}


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

    # Force UTF-8 decoding explicitly — requests sometimes guesses the wrong
    # encoding when a site's headers don't declare it clearly, which was
    # showing up as mojibake (Â£ instead of £) in price_text.
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


def extract_book_record(book_url: str, source_page: str) -> dict:
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


if __name__ == "__main__":
    entries, pages = discover_catalogue_pages()
    print(f"catalogue_pages={pages}")
    print(f"discovered={len(entries)}")
    print(f"unique_urls={len(set(u for u, _ in entries))}")

    records = []
    for book_url, source_page in entries:
        record = extract_book_record(book_url, source_page)
        records.append(record)

    print(f"detail_pages={len(records)}")
    print("--- sample record ---")
    print(records[0])
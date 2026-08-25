"""Entry point for the polite scraper — FlyRank A9."""

import os
import time
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

    html = response.text
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"FETCH: {cache_filename} ({len(html)} bytes)")
    return html, False


def discover_catalogue_pages():
    """Walk the catalogue's own 'next' links, up to MAX_CATALOGUE_PAGES.

    Returns (book_urls, pages_visited) where book_urls is a de-duplicated
    list of absolute book detail-page URLs, in first-seen order.
    """
    book_urls: list[str] = []
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

        # Every book on the page lives in an <article class="product_pod">,
        # with its link in the <h3><a href="..."> inside it.
        for article in soup.select("article.product_pod"):
            link = article.select_one("h3 a")
            if link and link.get("href"):
                absolute_url = urljoin(current_url, link["href"])
                if absolute_url not in seen:
                    seen.add(absolute_url)
                    book_urls.append(absolute_url)

        # Follow the site's own "next" link rather than hardcoding page URLs.
        next_link = soup.select_one("li.next a")
        if not next_link or page_num == MAX_CATALOGUE_PAGES:
            break
        current_url = urljoin(current_url, next_link["href"])

    return book_urls, pages_visited


if __name__ == "__main__":
    urls, pages = discover_catalogue_pages()
    print(f"catalogue_pages={pages}")
    print(f"discovered={len(urls)}")
    print(f"unique_urls={len(set(urls))}")
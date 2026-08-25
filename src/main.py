"""Entry point for the polite scraper — FlyRank A9."""

import os
import requests

USER_AGENT = "polite-scraper/1.0 (+https://github.com/Adithyaa-06/polite-scraper)"
TIMEOUT_SECONDS = 10
CACHE_DIR = "cache"

BASE_URL = "https://books.toscrape.com"
CATALOGUE_PAGE_1_URL = f"{BASE_URL}/catalogue/page-1.html"


def fetch_page(url: str, cache_filename: str) -> str:
    """Fetch a page politely, using the cache if we already have it.

    Returns the page's HTML as a string. Prints FETCH on a real network
    request, CACHE HIT when reading from disk instead.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, cache_filename)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT: {cache_filename} ({len(html)} bytes)")
        return html

    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)

    if response.status_code != 200:
        raise RuntimeError(f"FETCH FAILED: {url} returned status {response.status_code}")

    html = response.text
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"FETCH: {cache_filename} ({len(html)} bytes)")
    return html


if __name__ == "__main__":
    fetch_page(CATALOGUE_PAGE_1_URL, "catalogue-page-1.html")
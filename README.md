# Polite Scraper — FlyRank A9

A small, polite scraping pipeline for [Books to Scrape](https://books.toscrape.com), a public sandbox built specifically for practicing web scraping. It downloads the first 3 catalogue pages, visits all 60 book detail pages, cleans and validates the data, survives a broken page without crashing, and writes an honest report of what happened on every run.

## Target classification

**Site:** [books.toscrape.com](https://books.toscrape.com)

**Why this site is appropriate to scrape:** the site's own homepage carries the tagline *"We love being scraped!"* and displays a banner stating: *"Warning! This is a demo website for web scraping purposes. Prices and ratings here were randomly assigned and have no real meaning."* It is a sandbox explicitly built for practicing scraping.

**Scope:** the first 3 catalogue pages only (`page-1.html` through `page-3.html`), and the 60 individual book detail pages linked from them.

**robots.txt check:** requested `https://books.toscrape.com/robots.txt` once — it returns `404 Not Found`. No robots file found. (A missing file is not permission on its own — it's simply absent. Permission here comes from the site's own explicit statement above, not from robots.txt.)

**Data collected:** book title, product URL, price, availability, star rating, description, and provenance (source catalogue page + fetch timestamp) — all publicly visible on the page, nothing behind a login.

I will not reuse this code on another site without checking its rules and terms first.

## Setup & run

Requires Python 3.10+.

```bash
git clone https://github.com/Adithyaa-06/polite-scraper.git
cd polite-scraper
python -m venv .venv
.venv\Scripts\activate        # on Windows; use `source .venv/bin/activate` on macOS/Linux
python -m pip install -r requirements.txt
python src/main.py
```

Output lands in `output/books.json`, `output/errors.json`, and `output/run-report.json`. Raw HTML is cached under `cache/` (git-ignored) — a second run reads from cache instead of re-fetching, and finishes in well under a second.

## Record schema

Every validated record in `output/books.json` has this shape:

| Field | Type | Notes |
|---|---|---|
| `title` | string | Required |
| `product_url` | string (URL) | Required — the canonical identity of the record |
| `price_text` | string | Required — original text as shown on the page, e.g. `"£51.77"` |
| `price_gbp` | number | Required — `price_text` parsed into a float, e.g. `51.77` |
| `availability_text` | string | Required, e.g. `"In stock (22 available)"` |
| `rating_text` | string or null | Optional — one of `One`/`Two`/`Three`/`Four`/`Five` |
| `description` | string or null | Optional — `null` when the page has none, never invented |
| `source_page` | string (URL) | Required — which catalogue page this book was discovered on |
| `fetched_at` | string (ISO 8601) | Required — UTC timestamp of when the page was fetched |

Records that fail validation are written to `output/errors.json` instead, each with the URL and the reason, and never appear in `books.json`.

## Politeness rules

- **User-agent:** every real request sends `polite-scraper/1.0 (+https://github.com/Adithyaa-06/polite-scraper)`, identifying the scraper and linking back to this repo.
- **Timeout:** every request gives up after 10 seconds rather than hanging indefinitely.
- **Delay:** at least 0.5 seconds between real (non-cached) requests to the site.
- **Cache:** every fetched page is saved to `cache/` and read from there on subsequent runs, so the site is only ever asked once per page during development.
- **Retries:** a timeout or a 5xx server error is retried once after a short wait. A 404 or 403 is never retried — the page either doesn't exist or the site has said no, and asking again would only be pestering it.

## Why this assignment needed no browser

The data (title, price, availability, rating, description) is present directly in the HTML the server sends on first request — a browser would only add the cost of rendering JavaScript that isn't needed to reach it.

## Sample run report

A real `output/run-report.json` from an actual run, including one deliberately broken URL to prove the pipeline survives a bad page:

```json
{
  "start_time": "2026-09-07T04:33:09.982379+00:00",
  "duration_seconds": 2.375,
  "pages_fetched": 63,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 1,
  "failed_pages": 1
}
```

The corresponding `output/errors.json` entry for that run:

```json
[
  {
    "product_url": "https://books.toscrape.com/catalogue/this-book-does-not-exist_0000/index.html",
    "reason": "https://books.toscrape.com/catalogue/this-book-does-not-exist_0000/index.html returned 404"
  }
]
```

A normal run (no injected failure) produces `failed_pages: 0` and exactly 60 valid records, both on a fresh run and on a rerun — the pipeline is idempotent.

## Ethics note

This scraper only touches a site that explicitly invites scraping for practice. In general: check for an official API before scraping anything; never bypass a login, paywall, or an explicit block; collect only the data actually needed, not everything reachable; and identify yourself honestly in every request rather than hiding who is asking.

## Known limitation

The scraper currently assumes a stable page structure (fixed CSS selectors for price, availability, rating, and description). If Books to Scrape ever changes its HTML layout, extraction would silently start failing validation rather than adapting — this trades robustness against site changes for simplicity, which is an acceptable tradeoff for a practice sandbox that isn't expected to change.
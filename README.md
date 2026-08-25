# polite-scraper
## Target classification

**Site:** [books.toscrape.com](https://books.toscrape.com)

**Why this site is appropriate to scrape:** the site's own homepage carries the tagline *"We love being scraped!"* and displays a banner stating: *"Warning! This is a demo website for web scraping purposes. Prices and ratings here were randomly assigned and have no real meaning."* It is a sandbox explicitly built for practicing scraping.

**Scope:** the first 3 catalogue pages only (`page-1.html` through `page-3.html`), and the ~60 individual book detail pages linked from them.

**robots.txt check:** requested `https://books.toscrape.com/robots.txt` once — it returns `404 Not Found`. No robots file found. (A missing file is not permission on its own — it's simply absent. Permission here comes from the site's own explicit statement above, not from robots.txt.)

**Data collected:** book title, product URL, price, availability, star rating, description, and provenance (source catalogue page + fetch timestamp) — all publicly visible on the page, nothing behind a login.

I will not reuse this code on another site without checking its rules and terms first.
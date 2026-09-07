import json

with open("output/books.json", encoding="utf-8") as f:
    books = json.load(f)

print("count:", len(books))
print("all numeric price_gbp:", all(isinstance(b["price_gbp"], (int, float)) for b in books))
print("all https urls:", all(b["product_url"].startswith("https://") for b in books))
print(books[0])
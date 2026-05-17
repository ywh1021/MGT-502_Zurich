"""
Enrich missing Author fields using Google Books API.
Reads API keys from api.env (one key per line: GOOGLE_BOOKS_KEY_N=...).
Rotates between keys to maximise daily quota. Resumes from existing output.
Saves progress every 100 books.

Result: filled 1,267 missing authors over 2 days (17.4% → 9.1% missing).
"""
import time
import requests
import pandas as pd
import os

KEYS = []
for line in open("api.env").read().strip().split("\n"):
    if "=" in line:
        KEYS.append(line.split("=", 1)[1].strip())
print(f"Loaded {len(KEYS)} API keys")

INPUT_PATH  = "data/items.csv"
OUTPUT_PATH = "data/augmented/items_enriched.csv"
SAVE_EVERY  = 100
SLEEP       = 0.1

def query_google_books(isbn: str, key: str) -> str | None:
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&key={key}&maxResults=1"
        r = requests.get(url, timeout=8)
        if r.status_code == 429:
            return "QUOTA"
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        info = items[0].get("volumeInfo", {})
        authors = info.get("authors", [])
        return ", ".join(authors[:2]) if authors else None
    except Exception:
        return None

def extract_first_isbn(isbn_field) -> str | None:
    if pd.isna(isbn_field):
        return None
    parts = [p.strip() for p in str(isbn_field).split(";")]
    for p in parts:
        if len(p) == 13 and p.isdigit():
            return p
    return parts[0] if parts else None

# Load data
books = pd.read_csv(INPUT_PATH)

# Resume from existing output
if os.path.exists(OUTPUT_PATH):
    enriched = pd.read_csv(OUTPUT_PATH)
    print(f"Resuming from {OUTPUT_PATH}")
else:
    enriched = books.copy()

missing = enriched[enriched['Author'].isna()].copy()
print(f"Missing Author: {len(missing)} | Using {len(KEYS)} API keys")

filled = 0
key_idx = 0
quota_exhausted = [False] * len(KEYS)

for idx, (row_idx, row) in enumerate(missing.iterrows()):
    isbn = extract_first_isbn(row['ISBN Valid'])
    if not isbn:
        continue

    # Try current key, rotate if quota hit
    for attempt in range(len(KEYS)):
        ki = (key_idx + attempt) % len(KEYS)
        if quota_exhausted[ki]:
            continue
        result = query_google_books(isbn, KEYS[ki])
        if result == "QUOTA":
            print(f"  Key {ki+1} quota exhausted, switching...")
            quota_exhausted[ki] = True
            continue
        if result:
            enriched.at[row_idx, 'Author'] = result
            filled += 1
            key_idx = (ki + 1) % len(KEYS)  # rotate
        break

    if all(quota_exhausted):
        print("Both API keys exhausted. Stopping.")
        break

    if (idx + 1) % 50 == 0:
        print(f"  [{idx+1}/{len(missing)}] filled: {filled}")

    if (idx + 1) % SAVE_EVERY == 0:
        enriched.to_csv(OUTPUT_PATH, index=False)
        print(f"  → Saved ({filled} new authors)")

    time.sleep(SLEEP)

os.makedirs("data/augmented", exist_ok=True)
enriched.to_csv(OUTPUT_PATH, index=False)
still_missing = enriched['Author'].isna().sum()
print(f"\nDone! Filled {filled} new authors.")
print(f"Still missing: {still_missing} ({100*still_missing/len(enriched):.1f}%)")

"""
Enrichment via BnF (Bibliothèque nationale de France) SRU API.
Free, no rate limit, excellent French book coverage.
Fills missing Author and Subjects in data/items_enriched.csv.
"""
import pandas as pd, requests, time, re
import xml.etree.ElementTree as ET

NS = {'srw': 'http://www.loc.gov/zing/srw/',
      'mxc': 'info:lc/xmlns/marcxchange-v2'}

def clean_subject(raw):
    """Remove RAMEAU numeric codes and trailing 'rameau' keyword."""
    raw = re.sub(r'\b\d{8,}\b', '', raw)   # remove 8+ digit codes
    raw = re.sub(r'\brameau\b', '', raw, flags=re.I)
    raw = re.sub(r'\s+', ' ', raw).strip(' ;,')
    return raw

def fetch_bnf(row):
    isbn = str(row['ISBN Valid']).split(';')[0].strip()
    title = str(row['Title']).strip()

    query = f'bib.isbn+adj+"{isbn}"' if isbn not in ('nan', '') else f'bib.title+adj+"{title[:40]}"'
    url = (f'https://catalogue.bnf.fr/api/SRU?version=1.2'
           f'&operation=searchRetrieve&query={query}'
           f'&recordSchema=unimarcxchange&maximumRecords=1')
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return None, None
        root = ET.fromstring(r.text)
        records = root.findall('.//mxc:record', NS)
        if not records: return None, None
        rec = records[0]

        author, subjects = None, []
        for df in rec.findall('mxc:datafield', NS):
            tag = df.get('tag', '')
            # Author: tags 700 / 701 / 702
            if tag in ('700', '701', '702') and not author:
                parts = [sf.text for sf in df.findall('mxc:subfield', NS)
                         if sf.get('code') in ('a', 'b', 'f') and sf.text]
                if parts: author = ' '.join(parts).strip(' ,.')
            # Subjects: 600-608 (RAMEAU)
            if tag.isdigit() and 600 <= int(tag) <= 608:
                parts = [sf.text for sf in df.findall('mxc:subfield', NS)
                         if sf.get('code') in ('a', 'x', 'y', 'z') and sf.text]
                if parts:
                    subj = clean_subject(' '.join(parts))
                    if subj: subjects.append(subj)

        return author or None, '; '.join(subjects[:8]) or None
    except:
        return None, None

# ==========================================
print("Loading data...")
import os
src = "data/items_enriched.csv" if os.path.exists("data/items_enriched.csv") else "data/items.csv"
books = pd.read_csv(src)
books['Author']   = books['Author'].fillna('')
books['Subjects'] = books['Subjects'].fillna('')

missing = books[(books['Author'] == '') | (books['Subjects'] == '')].copy()
print(f"Книг с пропусками: {len(missing)} (Author={( books['Author']=='').sum()}, Subjects={(books['Subjects']=='').sum()})")

filled_a = filled_s = 0
count = 0
total = len(missing)

print("Starting BnF enrichment (no rate limit)...\n")
for index, row in missing.iterrows():
    new_author, new_subjects = fetch_bnf(row)

    if new_author and row['Author'] == '':
        books.at[index, 'Author'] = new_author
        filled_a += 1
    if new_subjects and row['Subjects'] == '':
        books.at[index, 'Subjects'] = new_subjects
        filled_s += 1

    count += 1
    if count % 50 == 0:
        books.to_csv("data/items_enriched.csv", index=False)
        print(f"  [{count}/{total}] Author заполнен: {filled_a}, Subjects: {filled_s}")

    time.sleep(0.3)  # BnF не имеет жёсткого лимита, но будем вежливы

books.to_csv("data/items_enriched.csv", index=False)
print(f"\n{'='*50}")
print(f"BnF обогащение завершено:")
print(f"  Author заполнен:   {filled_a} книг")
print(f"  Subjects заполнен: {filled_s} книг")
print(f"  Хит-рейт Author:   {100*filled_a/max(total,1):.1f}%")
print(f"  Хит-рейт Subjects: {100*filled_s/max(total,1):.1f}%")
print(f"Сохранено в data/items_enriched.csv")

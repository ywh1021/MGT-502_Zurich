"""
Classify French books into book_type and scientific discipline using
Anthropic's Message Batches API with Claude Haiku 4.5.

Usage:
    1. Set environment variable: export ANTHROPIC_API_KEY=your_key_here
    2. Edit INPUT_CSV and OUTPUT_CSV paths below
    3. Run: python classify_books.py submit       # submits batch
       Then: python classify_books.py poll <batch_id>   # check status
       Then: python classify_books.py fetch <batch_id>  # download results

Input CSV columns expected:
    Title, Author, ISBN Valid, Publisher, Subjects, i

Output CSV columns:
    i, Title, book_type, discipline, confidence
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import anthropic

# ---------- Configuration ----------
INPUT_CSV = "book_sample.csv"
OUTPUT_CSV = "books_classified.csv"
REQUESTS_JSONL = "batch_requests.jsonl"      # for inspection/debugging
RESULTS_JSONL = "batch_results.jsonl"        # raw API output
BATCH_ID_FILE = "batch_id.txt"               # persists the batch ID

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 200  # JSON response with 4 fields; cap keeps cost predictable

# ---------- Closed vocabularies (must match prompt) ----------
BOOK_TYPES = [
    "academic", "popular_science", "reference", "fiction", "comics",
    "non_fiction_general", "practical", "children", "other",
]

DISCIPLINES = [
    "mathematics", "physics", "chemistry", "biology", "medicine_health",
    "computer_science", "engineering_technology", "earth_sciences",
    "astronomy_space", "environmental_sciences", "agriculture_food_sciences",
    "history", "geography", "philosophy", "religion_theology", "psychology",
    "sociology", "anthropology_ethnology", "economics_management",
    "political_science", "law", "education_sciences", "linguistics",
    "literature_studies", "arts_art_history", "library_information_science",
    "communication_media_studies", "interdisciplinary", "other",
    "not_applicable",
]

CONFIDENCES = ["high", "medium", "low"]

TOPICS = [
    "travel",
    "cooking_food",
    "health_wellness",
    "parenting_family",
    "personal_development",
    "relationships",
    "home_garden",
    "crafts_hobbies",
    "sports_fitness",
    "career_business",
    "finance_money",
    "spirituality",
    "biography_memoir",
    "current_affairs_politics",
    "true_crime",
    "nature_animals",
    "art_culture",
    "science_technology",     # popular science without a specific discipline
    "history_civilization",   # popular history without an academic angle
    "education_learning",     # parenting/teaching guides, study skills
    "language_learning",
    "religion_practice",      # devotional, not theology
    "games_entertainment",
    "food_drink_culture",     # gastronomy, wine, regional cuisine
    "other",
    "not_applicable",
]

# Used when a request fails or its response cannot be parsed.
DEFAULT_CLASSIFICATION = {
    "book_type": "other",
    "discipline": "not_applicable",
    "topic": "not_applicable",
    "confidence": "low",
}

# ---------- Prompt ----------
SYSTEM_PROMPT = f"""You are a library cataloging expert specializing in French-language books.

You classify books into four fields. You MUST output ONLY a JSON object with exactly these four keys: "book_type", "discipline", "topic", "confidence". No prose, no explanation, no markdown, no code fences.

================================================================
FIELD 1 — book_type (pick exactly one)
================================================================
- academic: scholarly works (research monographs, university textbooks, peer-reviewed essays, conference proceedings, theses, scientific reference works for specialists). Conceptual or theoretical framing ("penser", "pour une pédagogie de", "concepts et outils", "perspectives", "approches").
- popular_science: science or knowledge books written for general audiences (vulgarisation scientifique).
- reference: dictionaries, encyclopedias, classification systems, professional manuals, technical guides aimed at specialists.
- fiction: novels (roman), short stories (nouvelles), poetry (poésie), drama (théâtre), plays.
- comics: bandes dessinées, graphic novels, manga — regardless of whether the topic is serious (climate, economics, autobiography) or entertainment.
- non_fiction_general: biographies, memoirs, journalism, essays for general audiences, autobiography in prose form, personal accounts (récits personnels). When subjects mention an academic field (e.g. "Sociologie") BUT also include "[Récits personnels]" or essayistic framing, choose non_fiction_general, not academic.
- practical: cookbooks, self-help, how-to guides, hobby books, travel guides ("Guides touristiques"), parenting guides, professional toolkits. Strong signals: "guide pratique", "boîte à outils", "100 idées", "comment faire", "Guides pratiques" in subjects.
- children: children's and youth literature (littérature jeunesse).
- other: anything that does not fit the categories above.

DISAMBIGUATION — academic vs practical for education books:
- Title contains "guide pratique", "boîte à outils", "100 idées pour", "comment", numbered tips → practical
- Title is conceptual/theoretical ("penser", "pour une pédagogie de", "concepts", "approches", "perspectives") → academic
- When in doubt and the publisher is academic-leaning (PUF, La Découverte for scholarly series, ESF, Presses universitaires) → academic
- When in doubt and the publisher specializes in practical guides (Dunod's "Boîte à outils" series, Eyrolles practical, Tom Pousse) → practical

DISAMBIGUATION — children's literature detection:
The "dès X ans" or "à partir de X ans" pattern (where X is a number) is a strong signal for children's literature in French publishing. When you see this pattern, choose book_type = children regardless of whether the book looks like a guide, story, or activity book. Examples:
- "guide illustré ... dès 7 ans" → children (NOT practical)
- "histoires ... à partir de 5 ans" → children (NOT fiction)
- "découvre la science ... dès 8 ans" → children (NOT popular_science)
Other children's signals: "littérature jeunesse" in subjects, "album jeunesse", age ranges like "6-9 ans", publishers exclusively dedicated to children (École des loisirs, Père Castor).

DISAMBIGUATION — art books, photography monographs, exhibition catalogs:
Art monographs, photography books, and museum/exhibition catalogs (livres d'art, beaux livres, catalogues d'exposition, monographies d'artistes) → book_type = reference + discipline = arts_art_history. They function as reference works in the art world even when they contain primarily images. Examples:
- A photographer's published photo collection → reference + arts_art_history
- An artist monograph → reference + arts_art_history
- An exhibition catalog → reference + arts_art_history
Use non_fiction_general only when the book is genuinely a biographical or essayistic prose work ABOUT an artist (not a collection of their work).

================================================================
FIELD 2 — discipline (pick exactly one)
================================================================
Populate ONLY for academic, popular_science, and reference book_types. For all other book_types, use "not_applicable".

Disciplines: {", ".join(d for d in DISCIPLINES if d != "not_applicable")}, not_applicable

Notes:
- "interdisciplinary" only when a book genuinely spans 3+ fields with no dominant one
- "education_sciences" covers pedagogy, didactics, teaching methods (academic study of education)
- "library_information_science" covers cataloging, classification, documentation
- "literature_studies" is the academic study of literature, NOT literature itself (which goes in fiction)
- "history" includes history of any topic; "arts_art_history" takes art history
- "linguistics" covers language sciences, including didactique des langues
- "medicine_health" covers clinical medicine, public health, nursing — the scholarly side
- "religion_theology" is the scholarly study of religion; devotional books go to non_fiction_general/practical with topic "religion_practice"

================================================================
FIELD 3 — topic (pick exactly one)
================================================================
Topic captures what the book is ABOUT in everyday terms. Rules by book_type:

- For fiction, children, other: use "not_applicable"
- For academic: use "not_applicable" (the discipline already captures the subject)
- For popular_science, reference: use "not_applicable" UNLESS the book has a clear everyday topic better captured here (rare — usually leave as not_applicable)
- For non_fiction_general, practical, comics: ALWAYS pick a specific topic when one fits

Topics: {", ".join(t for t in TOPICS if t not in ("other", "not_applicable"))}, other, not_applicable

Notes on topics:
- "travel": travel guides, city guides, country guides ("Guides touristiques et de visite")
- "cooking_food": cookbooks, recipe collections (cuisine practical) — use "food_drink_culture" for gastronomy/wine essays
- "parenting_family": child-rearing guides, family relationships, special-needs parenting
- "education_learning": teaching guides for educators/parents, study skills, training toolkits — use this for practical pedagogy books
- "personal_development": self-help, personal essays on life choices ("Vieille fille : une proposition"), introspection
- "current_affairs_politics": political commentary, current events, policy debates including economics-as-current-affairs (e.g. "Le mirage de la croissance verte")
- "nature_animals": environment, ecology, climate, wildlife, animals — use this for climate/ecology-themed comics/essays
- "biography_memoir": prose biographies and memoirs (autobiographical comics also use this topic, with book_type=comics)
- "history_civilization": popular history books not framed as academic
- "art_culture": general books on art, music, cinema for non-specialists
- "religion_practice": devotional, prayer, religious life (not academic theology)
- "career_business": professional development, management for practitioners
- "finance_money": personal finance, investing for general readers
- "science_technology": DEFAULT topic for popular-science or educational content covering ANY scientific discipline — chemistry, biology, physics, mathematics, immunology, anatomy, computer science, engineering, etc. Use this consistently rather than reaching for narrower topics. Examples: "La chimie en BD", "Les brigades immunitaires" (manga about cells), a popularization comic about black holes, an illustrated guide to coding for kids — all use "science_technology". Reserve "health_wellness" for self-care, mental health, fitness, diet, and personal-health practical content (NOT for content that happens to involve medicine/biology). Reserve "nature_animals" for ecology, environment, and wildlife content specifically.

================================================================
FIELD 4 — confidence (pick exactly one)
================================================================
- high: title and/or subjects clearly indicate the classification
- medium: classification is reasonable but title is somewhat ambiguous
- low: minimal information; classification is a best guess

================================================================
OUTPUT FORMAT (strict)
================================================================
{{"book_type": "...", "discipline": "...", "topic": "...", "confidence": "..."}}

Output ONLY this JSON object. Nothing else."""


def build_user_message(title: str, author: str, publisher: str, subjects: str) -> str:
    """Build the per-book user message."""
    parts = [f"Title: {title.strip()}"]
    if author and author.strip():
        parts.append(f"Author: {author.strip()}")
    if publisher and publisher.strip():
        parts.append(f"Publisher: {publisher.strip()}")
    if subjects and subjects.strip():
        parts.append(f"Subjects: {subjects.strip()}")
    return "\n".join(parts)


# ---------- Step 1: Build batch requests file ----------
def build_requests(input_csv: str, output_jsonl: str) -> int:
    """Read input CSV and write a JSONL file of batch requests."""
    count = 0
    with open(input_csv, "r", encoding="utf-8", newline="") as f_in, \
         open(output_jsonl, "w", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            book_id = row.get("i", "").strip()
            if not book_id:
                continue
            user_msg = build_user_message(
                title=row.get("Title", ""),
                author=row.get("Author", ""),
                publisher=row.get("Publisher", ""),
                subjects=row.get("Subjects", ""),
            )
            request = {
                "custom_id": f"book_{book_id}",
                "params": {
                    "model": MODEL,
                    "max_tokens": MAX_TOKENS,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_msg}],
                },
            }
            f_out.write(json.dumps(request, ensure_ascii=False) + "\n")
            count += 1
    return count


# ---------- Step 2: Submit the batch ----------
def submit_batch(requests_jsonl: str) -> str:
    """Submit batch and return batch_id."""
    client = anthropic.Anthropic()
    requests = []
    with open(requests_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            requests.append({
                "custom_id": obj["custom_id"],
                "params": obj["params"],
            })

    print(f"Submitting batch with {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)
    batch_id = batch.id
    Path(BATCH_ID_FILE).write_text(batch_id)
    print(f"Batch submitted. ID: {batch_id}")
    print(f"Status: {batch.processing_status}")
    print(f"Saved batch ID to {BATCH_ID_FILE}")
    return batch_id


# ---------- Step 3: Poll status ----------
def poll_batch(batch_id: str) -> dict:
    """Check batch status. Returns dict with status info."""
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(batch_id)
    counts = batch.request_counts
    info = {
        "id": batch.id,
        "status": batch.processing_status,
        "processing": counts.processing,
        "succeeded": counts.succeeded,
        "errored": counts.errored,
        "canceled": counts.canceled,
        "expired": counts.expired,
        "results_url": batch.results_url,
    }
    print(json.dumps(info, indent=2, default=str))
    return info


# ---------- Step 4: Fetch and parse results ----------
def parse_response(text: str) -> dict:
    """Parse the model's JSON response defensively."""
    # Strip code fences if any slipped through
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    # Find first { and last } as a final safeguard
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1:
        t = t[start:end + 1]
    return json.loads(t)


def validate_classification(obj: dict) -> dict:
    """Ensure values are in our closed vocabularies; coerce to safe defaults if not.

    Cross-field rules enforced here (the prompt asks the model to follow them,
    but we enforce them defensively in code):
      - discipline is populated only for academic / popular_science / reference;
        all other book_types force discipline = not_applicable.
      - topic is not_applicable for fiction, children, other, and academic.
      - For popular_science and reference, topic defaults to not_applicable
        unless the model picked a specific topic (we trust the model here).
      - For non_fiction_general, practical, comics: topic should be specific;
        if model returned not_applicable, we leave it (low signal) rather
        than guess.
    """
    book_type = obj.get("book_type", "other")
    discipline = obj.get("discipline", "not_applicable")
    topic = obj.get("topic", "not_applicable")
    confidence = obj.get("confidence", "low")

    if book_type not in BOOK_TYPES:
        book_type = "other"
    if discipline not in DISCIPLINES:
        discipline = "other"
    if topic not in TOPICS:
        topic = "other"
    if confidence not in CONFIDENCES:
        confidence = "low"

    # Enforce: only scholarly book_types get a real discipline.
    knowledge_types = {"academic", "popular_science", "reference"}
    if book_type not in knowledge_types:
        discipline = "not_applicable"

    # Enforce: topic is not_applicable for fiction, children, other, academic.
    no_topic_types = {"fiction", "children", "other", "academic"}
    if book_type in no_topic_types:
        topic = "not_applicable"

    return {
        "book_type": book_type,
        "discipline": discipline,
        "topic": topic,
        "confidence": confidence,
    }


def fetch_results(batch_id: str, input_csv: str, results_jsonl: str, output_csv: str):
    """Stream results from the batch and write the final CSV."""
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(batch_id)

    if batch.processing_status != "ended":
        print(f"Batch is not finished. Current status: {batch.processing_status}")
        sys.exit(1)

    # Build a lookup: book_id -> Title (for the output CSV)
    titles_by_id = {}
    with open(input_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            book_id = row.get("i", "").strip()
            if book_id:
                titles_by_id[book_id] = row.get("Title", "")

    # Stream raw results to a JSONL file (useful for debugging) and parse them
    classifications = {}  # book_id -> {book_type, discipline, confidence}
    errors = []

    with open(results_jsonl, "w", encoding="utf-8") as f_raw:
        for result in client.messages.batches.results(batch_id):
            f_raw.write(json.dumps(result.model_dump(), default=str, ensure_ascii=False) + "\n")

            custom_id = result.custom_id
            book_id = custom_id.replace("book_", "", 1)

            if result.result.type != "succeeded":
                errors.append({
                    "book_id": book_id,
                    "error_type": result.result.type,
                    "detail": str(result.result),
                })
                classifications[book_id] = dict(DEFAULT_CLASSIFICATION)
                continue

            try:
                text_blocks = [
                    b.text for b in result.result.message.content
                    if getattr(b, "type", None) == "text"
                ]
                full_text = "".join(text_blocks)
                parsed = parse_response(full_text)
                classifications[book_id] = validate_classification(parsed)
            except Exception as e:
                errors.append({"book_id": book_id, "parse_error": str(e)})
                classifications[book_id] = dict(DEFAULT_CLASSIFICATION)

    # Write final CSV in original order
    with open(input_csv, "r", encoding="utf-8", newline="") as f_in, \
         open(output_csv, "w", encoding="utf-8", newline="") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(
            f_out,
            fieldnames=["i", "Title", "book_type", "discipline", "topic", "confidence"],
        )
        writer.writeheader()
        for row in reader:
            book_id = row.get("i", "").strip()
            if not book_id:
                continue
            cls = classifications.get(book_id, dict(DEFAULT_CLASSIFICATION))
            writer.writerow({
                "i": book_id,
                "Title": row.get("Title", ""),
                "book_type": cls["book_type"],
                "discipline": cls["discipline"],
                "topic": cls["topic"],
                "confidence": cls["confidence"],
            })

    print(f"Wrote {len(classifications)} classifications to {output_csv}")
    if errors:
        print(f"Encountered {len(errors)} errors. First 5:")
        for e in errors[:5]:
            print(f"  {e}")
        with open("classification_errors.json", "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
        print("Full error list saved to classification_errors.json")


# ---------- CLI ----------
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "build":
        n = build_requests(INPUT_CSV, REQUESTS_JSONL)
        print(f"Built {n} requests in {REQUESTS_JSONL}")

    elif cmd == "submit":
        # Build then submit
        n = build_requests(INPUT_CSV, REQUESTS_JSONL)
        print(f"Built {n} requests")
        submit_batch(REQUESTS_JSONL)

    elif cmd == "poll":
        batch_id = sys.argv[2] if len(sys.argv) > 2 else Path(BATCH_ID_FILE).read_text().strip()
        poll_batch(batch_id)

    elif cmd == "fetch":
        batch_id = sys.argv[2] if len(sys.argv) > 2 else Path(BATCH_ID_FILE).read_text().strip()
        fetch_results(batch_id, INPUT_CSV, RESULTS_JSONL, OUTPUT_CSV)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
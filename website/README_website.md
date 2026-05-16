# Book Recommender — local web app

A 3-step wizard that lets you browse books by category, tick a few you've read, and get hybrid recommendations. Wraps the recommender in [`inference.py`](backend/inference.py) with a FastAPI backend and a Vite + React frontend.

## Running

Two terminals.

**Terminal 1 — backend** (port 8001), run from repo root:
```bash
.venv/bin/uvicorn website.backend.main:app --port 8001
```
Cold start fits the model (~5 s on this dataset) and writes `website/backend/cache/model.pkl` (~1.5 GB). Subsequent starts unpickle in ~3 s. The cache auto-invalidates when any of `interactions_train.csv`, `items.csv`, or `books_classified.csv` changes (mtime check).

**Terminal 2 — frontend** (port 5180):
```bash
cd website/frontend && npm install   # first time only
npm run dev
```
Open <http://127.0.0.1:5180/>.

To force a refit, delete `website/backend/cache/model.pkl`.

## Architecture

```
┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│  React wizard        │      │  FastAPI             │      │  inference.py    │
│  (Vite, port 5180)   │ ───► │  (uvicorn, 8001)     │ ───► │  (untouched)         │
│                      │      │                      │      │                      │
│  CategoryPicker  ──┐ │      │  /api/categories     │      │  load_data           │
│  SubcategoryPicker │ │ /api │  /api/subcategories  │      │  fit                 │
│  BookPicker      ──┤ │ ───► │  /api/books          │      │  recommend_for_user  │
│  Recommendations   │ │      │  /api/recommend      │      │                      │
└──────────────────────┘      └──────────────────────┘      └──────────────────────┘
       proxy /api → 8001              loads at startup,            cosine sims +
       (vite.config.ts)               pickles to cache             TF-IDF content
                                                                   blend
```

### Data flow

1. **Startup**: `model_service.load_or_fit()` either unpickles a cached `FittedModel` + book/item maps, or calls `inference.load_data` + `fit` and persists the result. A `catalog` DataFrame (one row per item, indexed by remapped `book_id`) is built from `books_classified.csv` joined with title/author and per-item interaction counts.

2. **Browse**: `/api/categories` lists 7 visible `book_type`s (hides `reference`/`other`) with a per-type **axis** = `"discipline"`, `"topic"`, or `"none"`. The axis is whichever classification field has more non-`not_applicable` rows. Academic → `discipline`; comics/practical/etc. → `topic`; fiction/children → `none` (skip subcategory step). `/api/subcategories` and `/api/books` filter the catalog accordingly, sorted by popularity.

3. **Recommend**: the UI sends back original book `i` values from `items.csv`. `model_service.recommend()` translates them via `book_map` to remapped indices, builds a 0/1 cold-start `user_vector` of length `n_items`, and calls `inference.recommend_for_user`. The returned indices are reverse-translated by looking up the catalog (indexed by remapped `book_id`).

### Why a disk cache

The expensive step is `fit`: building 7838×7838 user-similarity and 15109×15109 item-similarity cosine matrices (~1.5 GB combined). Fitting takes a few seconds; loading the pickle is faster, and avoids re-paying the cost on every reload during dev. Cache key = mtime tuple of the three CSVs, embedded in the pickle.

### Why two ports + Vite proxy

The frontend uses relative URLs (`/api/...`). Vite proxies them to the FastAPI process. This keeps the browser on a single origin (no CORS preflights) and lets you run the backend on a different port from the frontend without coupling them.

## Layout

```
.
├── inference.py            # the recommender — untouched
├── items.csv                   # (Title, Author, Subjects, ...)
├── interactions_train.csv      # (user, item, timestamp)
├── books_classified.csv        # (book_type, discipline, topic) per item
├── backend/
│   ├── main.py                 # FastAPI app, lifespan, CORS, routes
│   ├── model_service.py        # load_or_fit, build_catalog, recommend
│   ├── schemas.py              # Pydantic request/response models
│   └── cache/model.pkl         # gitignored, written on first run
└── frontend/
    ├── vite.config.ts          # proxy /api → 127.0.0.1:8001, port 5180
    └── src/
        ├── App.tsx             # wizard state machine
        ├── api.ts              # typed fetch wrappers
        ├── types.ts
        └── components/         # CategoryPicker, SubcategoryPicker, BookPicker, Recommendations
```

## API reference

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | `{status, n_items, n_users}`; gates the UI until the model is loaded. |
| GET | `/api/categories` | Returns 7 `book_type`s with `{value, label, count, axis}`. |
| GET | `/api/subcategories?book_type=` | Returns `{axis, subcategories: [{value, label, count}]}`. Empty when `axis="none"`. |
| GET | `/api/books?book_type=&subcategory=&limit=50` | Popular books in the area, sorted by interaction count. |
| POST | `/api/recommend` | Body `{read_book_ids: [int, ...]}` (≥1). Returns 10 ranked recommendations. |

`k=10` and `content_w=0.15` are hardcoded server-side, matching the recommender's defaults.

## Hardcoded knobs

- Hidden book_types: `reference`, `other`. Edit `HIDDEN_BOOK_TYPES` in [backend/model_service.py](backend/model_service.py).
- Top recommendations per call: 10. Content weight: 0.15. Edit the call to `recommend_for_user` in `recommend()`.
- Books per browse page: 50. Configurable via the `limit` query param (1–200).

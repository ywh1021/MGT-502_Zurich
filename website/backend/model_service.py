"""Recommender state, lazy fit + disk cache, and request-time helpers."""

from __future__ import annotations

import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_PATH = Path(__file__).resolve().parent / "cache" / "model.pkl"
INTERACTIONS_CSV = ROOT / "data" / "interactions_train.csv"
ITEMS_CSV = ROOT / "data" / "items.csv"
CLASSIFIED_CSV = ROOT / "data" / "augmented" / "books_classified.csv"

from .inference import (
    FittedModel,
    build_interaction_matrix,
    fit,
    load_data,
    recommend_for_user,
)

HIDDEN_BOOK_TYPES = {"reference", "other"}
PICKLE_VERSION = 1


@dataclass
class RecommenderState:
    model: FittedModel
    books: pd.DataFrame
    book_map: dict[int, int]
    catalog: pd.DataFrame  # indexed by book_id
    n_items: int
    n_users: int


def _csv_signature() -> tuple:
    return tuple(p.stat().st_mtime_ns for p in (INTERACTIONS_CSV, ITEMS_CSV, CLASSIFIED_CSV))


def _build_catalog(books: pd.DataFrame, book_map: dict, interactions: pd.DataFrame) -> pd.DataFrame:
    classified = pd.read_csv(CLASSIFIED_CSV)
    classified = classified[classified["i"].isin(book_map)].copy()
    classified["book_id"] = classified["i"].map(book_map)

    popularity = (
        interactions.groupby("book_id").size().rename("popularity").reset_index()
    )

    catalog = (
        classified[["i", "book_id", "book_type", "discipline", "topic"]]
        .merge(books[["book_id", "Title", "Author", "Subjects"]], on="book_id", how="left")
        .merge(popularity, on="book_id", how="left")
    )
    catalog["popularity"] = catalog["popularity"].fillna(0).astype(int)
    catalog["Title"] = catalog["Title"].fillna("")
    catalog["Author"] = catalog["Author"].fillna("")
    catalog["Subjects"] = catalog["Subjects"].fillna("")
    return catalog.set_index("book_id")


def _fit_fresh() -> tuple[FittedModel, pd.DataFrame, dict, pd.DataFrame]:
    print("[model_service] Loading data + fitting model (cold start)...", flush=True)
    t0 = time.time()
    interactions, books, aligned_tfidf, _user_map, book_map = load_data(
        str(INTERACTIONS_CSV), str(ITEMS_CSV)
    )
    n_users = int(interactions["user_id"].max()) + 1
    n_items = len(book_map)
    train_matrix = build_interaction_matrix(interactions, n_users, n_items)
    model = fit(train_matrix, aligned_tfidf)
    catalog = _build_catalog(books, book_map, interactions)
    print(f"[model_service] Fit done in {time.time() - t0:.1f}s "
          f"(users={n_users}, items={n_items}).", flush=True)
    return model, books, book_map, catalog


def _save_cache(model: FittedModel, books: pd.DataFrame, book_map: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PICKLE_VERSION,
        "csv_signature": _csv_signature(),
        "train_matrix": model.train_matrix,
        "aligned_tfidf": model.aligned_tfidf,
        "user_similarity": model.user_similarity,
        "item_similarity": model.item_similarity,
        "books_records": books.to_dict("records"),
        "book_map": book_map,
    }
    print(f"[model_service] Writing cache to {CACHE_PATH} ...", flush=True)
    t0 = time.time()
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"[model_service] Cache written in {time.time() - t0:.1f}s.", flush=True)


def _try_load_cache() -> tuple[FittedModel, pd.DataFrame, dict] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH, "rb") as f:
            payload = pickle.load(f)
    except Exception as e:
        print(f"[model_service] Cache unreadable ({e}); refitting.", flush=True)
        return None
    if payload.get("version") != PICKLE_VERSION:
        print("[model_service] Cache version mismatch; refitting.", flush=True)
        return None
    if tuple(payload.get("csv_signature", ())) != _csv_signature():
        print("[model_service] CSV mtimes changed; refitting.", flush=True)
        return None
    model = FittedModel(
        train_matrix=payload["train_matrix"],
        aligned_tfidf=payload["aligned_tfidf"],
        user_similarity=payload["user_similarity"],
        item_similarity=payload["item_similarity"],
    )
    books = pd.DataFrame(payload["books_records"])
    book_map = payload["book_map"]
    return model, books, book_map


def load_or_fit() -> RecommenderState:
    cached = _try_load_cache()
    if cached is not None:
        print("[model_service] Loaded model from cache.", flush=True)
        model, books, book_map = cached
        # Catalog still depends on interactions (popularity); rebuild from CSV.
        interactions = pd.read_csv(INTERACTIONS_CSV).rename(
            columns={"u": "user_id", "i": "book_id", "t": "timestamp"}
        )
        interactions["user_id"] = interactions["user_id"].map(
            {orig: new for new, orig in enumerate(interactions["user_id"].unique())}
        )
        interactions["book_id"] = interactions["book_id"].map(book_map)
        interactions = interactions.dropna(subset=["book_id"])
        interactions["book_id"] = interactions["book_id"].astype(int)
        catalog = _build_catalog(books, book_map, interactions)
    else:
        model, books, book_map, catalog = _fit_fresh()
        _save_cache(model, books, book_map)

    n_items = model.train_matrix.shape[1]
    n_users = model.train_matrix.shape[0]
    return RecommenderState(
        model=model,
        books=books,
        book_map=book_map,
        catalog=catalog,
        n_items=n_items,
        n_users=n_users,
    )


# ─── Request-time helpers ───────────────────────────────────────────────────


_LABEL_OVERRIDES: dict[str, str] = {
    "arts_art_history": "Arts",
    "non_fiction_general": "Non-Fiction",
    "popular_science": "Popular Science",
    "library_information_science": "Library & Info Science",
    "communication_media_studies": "Media Studies",
    "agriculture_food_sciences": "Agriculture & Food",
    "engineering_technology": "Engineering & Tech",
    "astronomy_space": "Astronomy & Space",
    "medicine_health": "Medicine & Health",
    "economics_management": "Economics & Management",
    "anthropology_ethnology": "Anthropology & Ethnology",
    "earth_sciences": "Earth Sciences",
}

def _label(value: str) -> str:
    return _LABEL_OVERRIDES.get(value, value.replace("_", " ").title())


def categories(state: RecommenderState) -> list[dict]:
    cat = state.catalog
    rows = []
    for bt, group in cat.groupby("book_type"):
        if bt in HIDDEN_BOOK_TYPES:
            continue
        n_disc = int((group["discipline"] != "not_applicable").sum())
        n_topic = int((group["topic"] != "not_applicable").sum())
        if n_disc > n_topic:
            axis = "discipline"
        elif n_topic > 0:
            axis = "topic"
        else:
            axis = "none"
        rows.append({
            "value": bt,
            "label": _label(bt),
            "count": int(len(group)),
            "axis": axis,
        })
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def _axis_for(state: RecommenderState, book_type: str) -> str:
    for c in categories(state):
        if c["value"] == book_type:
            return c["axis"]
    return "none"


def subcategories(state: RecommenderState, book_type: str) -> dict:
    axis = _axis_for(state, book_type)
    if axis == "none":
        return {"book_type": book_type, "axis": axis, "subcategories": []}
    sub = state.catalog[state.catalog["book_type"] == book_type]
    sub = sub[sub[axis] != "not_applicable"]
    counts = sub.groupby(axis).size().sort_values(ascending=False)
    items = [
        {"value": str(v), "label": _label(str(v)), "count": int(c)}
        for v, c in counts.items()
    ]
    return {"book_type": book_type, "axis": axis, "subcategories": items}


def books_in(state: RecommenderState, book_type: str, subcategory: str | None, limit: int) -> list[dict]:
    df = state.catalog[state.catalog["book_type"] == book_type]
    if subcategory:
        axis = _axis_for(state, book_type)
        if axis in ("discipline", "topic"):
            df = df[df[axis] == subcategory]
    df = df.sort_values(["popularity", "i"], ascending=[False, True]).head(limit)
    return [
        {
            "id": int(row["i"]),
            "title": str(row["Title"]),
            "author": str(row["Author"]),
            "subjects": str(row["Subjects"]),
            "popularity": int(row["popularity"]),
        }
        for _, row in df.iterrows()
    ]


def recommend_existing_user(
    state: RecommenderState, user_id: int, k: int = 10, content_w: float = 0.15
) -> list[dict]:
    if user_id < 0 or user_id >= state.n_users:
        raise ValueError(f"User ID must be between 0 and {state.n_users - 1}.")
    v = np.asarray(state.model.train_matrix[user_id], dtype=np.float32).flatten()
    if v.sum() == 0:
        raise ValueError(f"User {user_id} has no recorded interactions.")
    top = recommend_for_user(v, state.model, k=k, content_w=content_w, exclude_seen=True)
    rows = state.catalog.loc[top].reset_index()
    out = []
    for rank, (_, row) in enumerate(rows.iterrows(), start=1):
        out.append({
            "id": int(row["i"]),
            "rank": rank,
            "title": str(row["Title"]),
            "author": str(row["Author"]),
            "subjects": str(row["Subjects"]),
            "book_type": str(row["book_type"]),
            "discipline": str(row["discipline"]),
            "topic": str(row["topic"]),
        })
    return out


def search_books(state: RecommenderState, q: str, limit: int = 10) -> list[dict]:
    q_lower = q.lower().strip()
    if not q_lower:
        return []
    cat = state.catalog
    mask = (
        cat["Title"].str.lower().str.contains(q_lower, na=False, regex=False)
        | cat["Author"].str.lower().str.contains(q_lower, na=False, regex=False)
    )
    df = cat[mask].sort_values("popularity", ascending=False).head(limit)
    return [
        {
            "id": int(row["i"]),
            "title": str(row["Title"]),
            "author": str(row["Author"]),
            "subjects": str(row["Subjects"]),
            "popularity": int(row["popularity"]),
        }
        for _, row in df.iterrows()
    ]


def recommend(
    state: RecommenderState,
    read_book_ids: list[int],
    liked_ids: list[int] | None = None,
    disliked_ids: list[int] | None = None,
    k: int = 10,
    content_w: float = 0.15,
) -> list[dict]:
    # Profile = original reads + liked recommendations
    profile_ids = list(read_book_ids) + list(liked_ids or [])
    remapped = [state.book_map[i] for i in profile_ids if i in state.book_map]
    if not remapped:
        raise ValueError("no recognized books in read_book_ids")
    v = np.zeros(state.n_items, dtype=np.float32)
    v[remapped] = 1.0

    # Fetch extra results so we can filter out disliked books
    disliked_remapped = {state.book_map[i] for i in (disliked_ids or []) if i in state.book_map}
    fetch_k = k + len(disliked_remapped)
    top_all = recommend_for_user(v, state.model, k=fetch_k, content_w=content_w, exclude_seen=True)
    top = [t for t in top_all if t not in disliked_remapped][:k]
    rows = state.catalog.loc[top].reset_index()
    out = []
    for rank, (_, row) in enumerate(rows.iterrows(), start=1):
        out.append({
            "id": int(row["i"]),
            "rank": rank,
            "title": str(row["Title"]),
            "author": str(row["Author"]),
            "subjects": str(row["Subjects"]),
            "book_type": str(row["book_type"]),
            "discipline": str(row["discipline"]),
            "topic": str(row["topic"]),
        })
    return out

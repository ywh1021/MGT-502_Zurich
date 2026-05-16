"""
Model 7: CF (time-decay, sign-preserving log) + Content (count-weighted TF-IDF)
         + Popularity + Graph RWR (alpha=0.7, 15 iter)

Final blend: normalize(0.8 * normalize(0.75*CF + 0.20*Content + 0.05*Pop) + 0.2*Graph)
Kaggle score: 0.1739 (Precision@10)
"""
from __future__ import annotations
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse import csr_matrix, diags, bmat
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

EPS = 1e-9


# ─── Data ────────────────────────────────────────────────────────────────────

def load_data(interactions_path: str, items_path: str, tfidf_kwargs=None):
    """Load interactions + items, remap ids, build aligned TF-IDF.

    Returns:
        interactions: DataFrame with user_id, book_id, timestamp (remapped).
        books: DataFrame with book_id column added.
        aligned_tfidf: sparse (n_items, n_features) — row i ↔ book_id i.
        user_map, book_map: original_id → new_id dicts.
    """
    interactions = pd.read_csv(interactions_path).rename(
        columns={"u": "user_id", "i": "book_id", "t": "timestamp"}
    )
    user_map = {o: n for n, o in enumerate(interactions["user_id"].unique())}
    book_map = {o: n for n, o in enumerate(interactions["book_id"].unique())}
    interactions["user_id"] = interactions["user_id"].map(user_map)
    interactions["book_id"] = interactions["book_id"].map(book_map)

    n_items = len(book_map)
    books = pd.read_csv(items_path)
    for col in ("Title", "Author", "Subjects", "Publisher"):
        books[col] = books[col].fillna("")

    # Author×2, Subjects×2 — same as Model 7
    books["content"] = (
        books["Title"] + " " + books["Author"] + " " + books["Author"] + " " +
        books["Subjects"] + " " + books["Subjects"] + " " + books["Publisher"]
    )
    books = books[books["i"].isin(book_map)].copy()
    books["book_id"] = books["i"].map(book_map)

    tfidf = TfidfVectorizer(
        **(tfidf_kwargs or dict(max_features=10000, strip_accents="unicode", min_df=2))
    )
    tfidf_matrix = tfidf.fit_transform(books["content"])
    aligned_tfidf = _align_tfidf(tfidf_matrix, books["book_id"].values, n_items)

    return interactions, books, aligned_tfidf, user_map, book_map


def _align_tfidf(tfidf_matrix, book_ids, n_items):
    src = np.arange(len(book_ids))
    perm = sp.csr_matrix(
        (np.ones_like(src, dtype=np.float32), (book_ids, src)),
        shape=(n_items, len(book_ids)),
    )
    return (perm @ tfidf_matrix).tocsr()


def build_interaction_matrix(df, n_users, n_items):
    matrix = np.zeros((n_users, n_items), dtype=np.float32)
    matrix[df["user_id"].values, df["book_id"].values] = 1.0
    return matrix


# ─── Normalisation ───────────────────────────────────────────────────────────

def _norm(x):
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo + EPS)

def _norm1d(x):
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo + EPS)

def _sln(x):
    return _norm(np.log1p(np.abs(x)) * np.sign(x))


# ─── Graph RWR ───────────────────────────────────────────────────────────────

def _build_graph(binary_mat, n_users, n_items, alpha=0.7, n_iter=15):
    R = csr_matrix(binary_mat)
    adj = bmat([[csr_matrix((n_users, n_users)), R],
                [R.T, csr_matrix((n_items, n_items))]], format="csr")
    rs = np.array(adj.sum(axis=1)).flatten(); rs[rs == 0] = 1
    T = diags(1.0 / rs).dot(adj)
    n_total = n_users + n_items
    scores = np.zeros((n_users, n_items), dtype=np.float32)
    for bs in range(0, n_users, 200):
        be = min(bs + 200, n_users)
        p = np.zeros((n_total, be - bs), dtype=np.float32)
        for i, u in enumerate(range(bs, be)): p[u, i] = 1.0
        r = p.copy()
        for _ in range(n_iter): r = alpha * T.dot(r) + (1 - alpha) * p
        scores[bs:be] = r[n_users:].T
    return _norm(scores)


# ─── Model ───────────────────────────────────────────────────────────────────

@dataclass
class FittedModel:
    train_matrix: np.ndarray       # (n_users, n_items) time-decay weighted
    aligned_tfidf: sp.csr_matrix   # (n_items, n_features)
    user_similarity: np.ndarray    # (n_users, n_users) cosine
    item_similarity: np.ndarray    # (n_items, n_items) cosine
    graph_scores: np.ndarray       # (n_users, n_items) RWR — precomputed
    pop_scores: np.ndarray         # (n_items,) log-normalized popularity


def fit(train_matrix: np.ndarray, aligned_tfidf: sp.csr_matrix,
        train_df: pd.DataFrame | None = None) -> FittedModel:
    """Fit Model 7: compute CF similarities, graph RWR, and popularity."""
    n_users, n_items = train_matrix.shape

    print("[inference] Computing user similarity...", flush=True)
    user_sim = cosine_similarity(train_matrix)

    print("[inference] Computing item similarity...", flush=True)
    item_sim = cosine_similarity(train_matrix.T)

    print("[inference] Computing Graph RWR...", flush=True)
    binary = (train_matrix > 0).astype(np.float32)
    graph = _build_graph(binary, n_users, n_items)

    pop = _norm1d(np.log1p(binary.sum(axis=0)))

    return FittedModel(
        train_matrix=train_matrix,
        aligned_tfidf=aligned_tfidf,
        user_similarity=user_sim,
        item_similarity=item_sim,
        graph_scores=graph,
        pop_scores=pop,
    )


# ─── Scoring ─────────────────────────────────────────────────────────────────

def recommend_for_user(
    user_vector: np.ndarray,
    model: FittedModel,
    k: int = 10,
    content_w: float = 0.20,
    exclude_seen: bool = True,
) -> np.ndarray:
    """Top-k recommendations for a single user vector (Model 7 architecture).

    Graph scores are interpolated from training users weighted by cosine similarity.
    """
    uv = np.asarray(user_vector, dtype=np.float32).ravel()
    n_items = model.train_matrix.shape[1]
    assert uv.shape[0] == n_items

    # ── CF (sign-preserving log) ──────────────────────────────────────────
    sims = cosine_similarity(uv.reshape(1, -1), model.train_matrix).ravel()
    user_pred = sims @ model.train_matrix / (np.abs(sims).sum() + EPS)
    item_pred = (uv @ model.item_similarity) / (model.item_similarity.sum(axis=0) + EPS)
    cf = (0.45 * _norm1d(np.log1p(np.abs(user_pred)) * np.sign(user_pred)) +
          0.55 * _norm1d(np.log1p(np.abs(item_pred)) * np.sign(item_pred)))

    # ── Content (count-weighted profile) ─────────────────────────────────
    n_read = float(uv.sum()) + EPS
    profile = np.asarray(uv.reshape(1, -1) @ model.aligned_tfidf, dtype=np.float32) / n_read
    content = _norm1d(np.log1p(cosine_similarity(profile, model.aligned_tfidf).ravel()))

    # ── Popularity ────────────────────────────────────────────────────────
    pop = model.pop_scores

    # ── Graph (interpolated) ──────────────────────────────────────────────
    graph = (sims @ model.graph_scores) / (np.abs(sims).sum() + EPS)
    graph = _norm1d(graph)

    # ── Final blend (Model 7) ─────────────────────────────────────────────
    current = _norm1d(0.75 * cf + 0.20 * content + 0.05 * pop)
    scores  = _norm1d(0.8 * current + 0.2 * graph)

    if exclude_seen:
        scores = scores.copy()
        scores[uv > 0] = -np.inf

    k = min(k, scores.size)
    top = np.argpartition(-scores, k - 1)[:k]
    return top[np.argsort(-scores[top])]

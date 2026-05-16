"""Hybrid (CF + content) recommender — original recipe.

Cleaned-up, vectorized version of the original cross-validation script. The
per-user content-scoring loop is replaced by a single matmul; precision@k is
vectorized via argpartition.

Public entry points:
    load_data            — fetch interactions/items, remap ids, build aligned TF-IDF
    fit                  — precompute user/item similarities for a train matrix
    score_all_users      — full (n_users, n_items) hybrid score matrix
    recommend_for_user   — top-k recommendations from a single user vector
    evaluate_cv          — temporal K-fold CV sweeping content weights
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


INTERACTIONS_URL = (
    "https://raw.githubusercontent.com/MiraFedo/Machine-Learning-/main/interactions_train.csv"
)
ITEMS_URL = "https://raw.githubusercontent.com/MiraFedo/Machine-Learning-/main/items.csv"

EPS = 1e-9
USER_CF_WEIGHT = 0.7  # weight on user-CF inside the CF blend (item-CF gets 1 - this)

# Time-aware blend defaults — found by grid search in experiments_time.py.
# 3-way blend (legacy CF+content, recency-weighted popularity, time-decayed
# reborrow) on the 80/20 temporal holdout: P@10 0.0581 → 0.0613 (+5.5%).
DEFAULT_REBO_W = 0.55
DEFAULT_POP_W = 0.05
DEFAULT_LEGACY_W = 1.0 - DEFAULT_REBO_W - DEFAULT_POP_W   # 0.40
DEFAULT_REBO_MU = 60.0       # days since last borrow at which reborrow is most likely
DEFAULT_REBO_SIGMA = 30.0    # spread of the reborrow window
DEFAULT_REBO_ALPHA = 1.0     # exponent on the user's prior borrow count
DEFAULT_POP_TAU = 365.0      # days; near-flat decay (all-time popularity won the sweep)


# ─── Data ───────────────────────────────────────────────────────────────────

def load_data(interactions_url=INTERACTIONS_URL, items_url=ITEMS_URL, tfidf_kwargs=None):
    """Load interactions + items, remap ids to dense [0, n) ranges, build TF-IDF.

    Returns:
        interactions: DataFrame with columns user_id, book_id, timestamp (ids remapped).
        books: DataFrame filtered to ids present in interactions, with a `book_id` column.
        aligned_tfidf: sparse (n_items, n_features) matrix where row i ↔ book_id i.
        user_map, book_map: original_id → new_id dicts.
    """
    interactions = pd.read_csv(interactions_url).rename(
        columns={"u": "user_id", "i": "book_id", "t": "timestamp"}
    )
    user_map = {orig: new for new, orig in enumerate(interactions["user_id"].unique())}
    book_map = {orig: new for new, orig in enumerate(interactions["book_id"].unique())}
    interactions["user_id"] = interactions["user_id"].map(user_map)
    interactions["book_id"] = interactions["book_id"].map(book_map)

    n_items = len(book_map)

    books = pd.read_csv(items_url)
    for col in ("Author", "Subjects", "Publisher", "Title"):
        books[col] = books[col].fillna("")
    # Subjects doubled to up-weight that signal — original recipe.
    books["content"] = (
        books["Title"] + " " + books["Author"] + " "
        + books["Subjects"] + " " + books["Subjects"] + " "
        + books["Publisher"]
    )
    books = books[books["i"].isin(book_map)].copy()
    books["book_id"] = books["i"].map(book_map)

    tfidf = TfidfVectorizer(
        **(tfidf_kwargs or dict(max_features=10000, stop_words=None,
                                strip_accents="unicode", min_df=2))
    )
    tfidf_matrix = tfidf.fit_transform(books["content"])
    aligned_tfidf = _align_tfidf(tfidf_matrix, books["book_id"].values, n_items)

    return interactions, books, aligned_tfidf, user_map, book_map


def _align_tfidf(tfidf_matrix, book_ids, n_items):
    """Permute tfidf rows so row i ↔ book_id i. Items without metadata are zero rows."""
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


def add_temporal_folds(df, k_folds):
    """Split each user's interactions into k_folds time-ordered chunks."""
    df = df.sort_values(["user_id", "timestamp"]).copy()
    df["fold"] = df.groupby("user_id")["timestamp"].transform(
        lambda x: pd.qcut(x.rank(method="first"), k_folds, labels=False)
    )
    return df


# ─── Score primitives ───────────────────────────────────────────────────────

def normalize(matrix):
    """Min-max normalize using global min/max (matches the original recipe).

    Per-user ranking is preserved, but the relative scale between blended
    matrices (cf vs content) is anchored to the global ranges so the blend
    weight `content_w` has a comparable meaning across runs.
    """
    lo, hi = matrix.min(), matrix.max()
    return (matrix - lo) / (hi - lo + EPS)


def user_cf_scores(interactions, user_similarity):
    """User-based CF: each user's score = similarity-weighted average of all
    users' histories."""
    return user_similarity @ interactions / (
        np.abs(user_similarity).sum(axis=1, keepdims=True) + EPS
    )


def item_cf_scores(interactions, item_similarity):
    """Item-based CF. Equivalent to interactions @ item_similarity since
    cosine similarity is symmetric — sum(axis=0) == sum(axis=1)."""
    return interactions @ item_similarity / (item_similarity.sum(axis=0) + EPS)


def content_scores(interactions, aligned_tfidf):
    """Vectorized content-based scoring.

    User profile = mean of TF-IDF rows for read books; final score = cosine
    similarity of that profile vs every item. One matmul builds every user
    profile, one cosine_similarity scores every (user, item) pair.
    """
    n_read = interactions.sum(axis=1, keepdims=True) + EPS
    user_profiles = np.asarray(interactions @ aligned_tfidf) / n_read
    return cosine_similarity(user_profiles, aligned_tfidf)


# ─── Time-aware components ──────────────────────────────────────────────────

def recency_weighted_pop(train_df, n_items, tau_days=DEFAULT_POP_TAU,
                         t_max=None):
    """Per-item recency-weighted popularity: pop[i] = Σ exp(-(t_max - t_j)/τ).

    Returns a 1-D vector of length n_items, min-max normalized to [0, 1] so it
    can be blended directly with row-normalized score matrices.
    """
    ts = train_df["timestamp"].to_numpy()
    if t_max is None:
        t_max = ts.max()
    delta_days = (t_max - ts) / 86400.0
    weights = np.exp(-delta_days / tau_days).astype(np.float32)
    pop = np.zeros(n_items, dtype=np.float32)
    np.add.at(pop, train_df["book_id"].to_numpy(), weights)
    lo, hi = pop.min(), pop.max()
    return (pop - lo) / (hi - lo + EPS)


def reborrow_score(train_df, n_users, n_items,
                   mu=DEFAULT_REBO_MU, sigma=DEFAULT_REBO_SIGMA,
                   alpha=DEFAULT_REBO_ALPHA, t_max=None):
    """Per-(user, item) reborrow score. Non-zero only on (u, i) pairs the user
    has touched at least once in train.

        gap_days   = (t_max - last_borrow_t[u, i]) / 86400
        score[u,i] = prior_count[u, i] ** α  *  exp(-(gap - μ)² / 2σ²)

    The gaussian decay (peaking at μ days stale) beat both monotone exp decay
    and a flat seen-item bonus on the temporal holdout (experiments_time.py).
    Returns a row-normalized (n_users, n_items) float32 matrix.
    """
    ts = train_df["timestamp"].to_numpy()
    if t_max is None:
        t_max = ts.max()
    g = train_df.groupby(["user_id", "book_id"])
    pair = g["timestamp"].max().reset_index(name="last_t")
    pair["n"] = g.size().values
    gap_days = (t_max - pair["last_t"].to_numpy()) / 86400.0
    decay = np.exp(-((gap_days - mu) ** 2) / (2 * sigma ** 2)).astype(np.float32)
    val = (pair["n"].to_numpy().astype(np.float32) ** alpha) * decay
    out = np.zeros((n_users, n_items), dtype=np.float32)
    out[pair["user_id"].to_numpy(), pair["book_id"].to_numpy()] = val
    row_max = out.max(axis=1, keepdims=True)
    return out / (row_max + EPS)


# ─── Model ──────────────────────────────────────────────────────────────────

@dataclass
class FittedModel:
    """Cached training inputs and similarity matrices."""
    train_matrix: np.ndarray         # (n_users, n_items)
    aligned_tfidf: sp.csr_matrix     # (n_items, n_features)
    user_similarity: np.ndarray      # (n_users, n_users)
    item_similarity: np.ndarray      # (n_items, n_items)
    rwpop: np.ndarray = None         # (n_items,) — None if no train_df at fit time
    rebo: np.ndarray = None          # (n_users, n_items) — None likewise


def fit(train_matrix, aligned_tfidf, train_df=None):
    """Fit the recommender. If `train_df` (with user_id, book_id, timestamp
    columns) is supplied, also precompute the recency-weighted popularity and
    time-decayed reborrow components used by score_all_users."""
    rwpop, rebo = None, None
    if train_df is not None:
        n_users, n_items = train_matrix.shape
        rwpop = recency_weighted_pop(train_df, n_items)
        rebo = reborrow_score(train_df, n_users, n_items)
    return FittedModel(
        train_matrix=train_matrix,
        aligned_tfidf=aligned_tfidf,
        user_similarity=cosine_similarity(train_matrix),
        item_similarity=cosine_similarity(train_matrix.T),
        rwpop=rwpop,
        rebo=rebo,
    )


def hybrid_components(model):
    """Return (cf, content) — the row-blended CF score and the content score.
    Caller blends them with content_w."""
    user_pred = user_cf_scores(model.train_matrix, model.user_similarity)
    item_pred = item_cf_scores(model.train_matrix, model.item_similarity)
    cf = USER_CF_WEIGHT * normalize(user_pred) + (1 - USER_CF_WEIGHT) * normalize(item_pred)
    content = content_scores(model.train_matrix, model.aligned_tfidf)
    return cf, content


def _row_normalize(matrix):
    row_min = matrix.min(axis=1, keepdims=True)
    row_max = matrix.max(axis=1, keepdims=True)
    return (matrix - row_min) / (row_max - row_min + EPS)


def score_all_users(model, content_w=0.15,
                    rebo_w=DEFAULT_REBO_W, pop_w=DEFAULT_POP_W):
    """Full (n_users, n_items) hybrid score matrix.

    When the model was fit with a `train_df`, the score is a 3-way blend:
        legacy_w * normalize(CF + content) + rebo_w * rebo + pop_w * rwpop
    where legacy_w = 1 - rebo_w - pop_w. Falls back to the original CF+content
    blend when the time-aware components are absent (backwards-compatible with
    callers like the FastAPI backend that fit without timestamps).
    """
    cf, content = hybrid_components(model)
    legacy = (1 - content_w) * normalize(cf) + content_w * normalize(content)
    if model.rebo is None and model.rwpop is None:
        return legacy
    legacy_w = max(0.0, 1.0 - rebo_w - pop_w)
    out = legacy_w * _row_normalize(legacy)
    if model.rebo is not None and rebo_w > 0:
        out = out + rebo_w * model.rebo
    if model.rwpop is not None and pop_w > 0:
        out = out + pop_w * model.rwpop
    return out


def recommend_for_user(user_vector, model, k=10, content_w=0.15, exclude_seen=True):
    """Top-k recommendations for a single user vector.

    Works for users not present in the training set — the user's similarity
    to every training user is computed on the fly. For training users you can
    pass `model.train_matrix[user_id]` directly.

    Note: each component is min-max normalized using its own (1D) range here,
    not the global range used in batch scoring. Per-user rankings are
    unaffected, but the cf/content blend may differ slightly from the row of
    `score_all_users` for the same user.

    Args:
        user_vector: 1D array of length n_items — 1 for read, 0 otherwise.
        model: FittedModel from `fit`.
        k: number of recommendations to return.
        content_w: weight on content score in the hybrid blend (cf weight = 1 - this).
        exclude_seen: drop items already in user_vector.

    Returns:
        np.ndarray of length min(k, n_items) — book indices ordered by descending score.
    """
    user_vector = np.asarray(user_vector, dtype=np.float32).reshape(-1)
    n_items = model.train_matrix.shape[1]
    if user_vector.shape[0] != n_items:
        raise ValueError(f"user_vector length {user_vector.shape[0]} != n_items {n_items}")

    # User-CF: similarity to every training user, then weighted-average their histories.
    sims = cosine_similarity(user_vector.reshape(1, -1), model.train_matrix).ravel()
    user_pred = (sims @ model.train_matrix) / (np.abs(sims).sum() + EPS)

    # Item-CF
    item_pred = (user_vector @ model.item_similarity) / (model.item_similarity.sum(axis=0) + EPS)

    cf = USER_CF_WEIGHT * normalize(user_pred) + (1 - USER_CF_WEIGHT) * normalize(item_pred)

    # Content: mean TF-IDF profile vs all items.
    n_read = float(user_vector.sum()) + EPS
    user_profile = np.asarray(user_vector.reshape(1, -1) @ model.aligned_tfidf) / n_read
    content = cosine_similarity(user_profile, model.aligned_tfidf).ravel()

    scores = (1 - content_w) * normalize(cf) + content_w * normalize(content)

    if exclude_seen:
        scores = scores.copy()
        scores[user_vector > 0] = -np.inf

    k = min(k, scores.size)
    top = np.argpartition(-scores, kth=k - 1)[:k]
    return top[np.argsort(-scores[top])]


# ─── Evaluation ─────────────────────────────────────────────────────────────

def precision_recall_at_k(prediction, ground_truth, k=10):
    """Vectorized precision@k / recall@k averaged across users."""
    k = min(k, prediction.shape[1])
    top_k = np.argpartition(-prediction, kth=k - 1, axis=1)[:, :k]
    rows = np.arange(prediction.shape[0])[:, None]
    relevant = ground_truth[rows, top_k].sum(axis=1).astype(np.float64)
    totals = ground_truth.sum(axis=1)

    precision = (relevant / k).mean()
    recall_per_user = np.divide(
        relevant, totals,
        out=np.zeros_like(relevant, dtype=np.float64),
        where=totals > 0,
    )
    return precision, recall_per_user.mean()


def evaluate_cv(interactions, aligned_tfidf, n_users, n_items,
                k_folds=5, k=10, content_weights=(0.05, 0.10, 0.15, 0.20, 0.25)):
    """Temporal K-fold CV. For each fold, fit once and sweep content_w."""
    interactions = add_temporal_folds(interactions, k_folds)
    scores_per_w = {w: [] for w in content_weights}

    for fold in range(k_folds):
        print(f"\n── Fold {fold + 1}/{k_folds} ──")
        train_df = interactions[interactions["fold"] != fold]
        test_df = interactions[interactions["fold"] == fold]

        train_matrix = build_interaction_matrix(train_df, n_users, n_items)
        test_matrix = build_interaction_matrix(test_df, n_users, n_items)

        model = fit(train_matrix, aligned_tfidf)
        cf, content = hybrid_components(model)
        cf_n, content_n = normalize(cf), normalize(content)

        for w in content_weights:
            hybrid = (1 - w) * cf_n + w * content_n
            precision, _ = precision_recall_at_k(hybrid, test_matrix, k=k)
            scores_per_w[w].append(precision)
            print(f"  content_w={w:.2f} | P@{k}: {precision:.4f}")

    return scores_per_w


# ─── Submission ─────────────────────────────────────────────────────────────

def write_submission(scores, user_map, book_map, k=10, out_path="submission.csv"):
    """Top-k items per user → CSV in sample_submission.csv format.

    The submission expects ORIGINAL `u`/`i` values, not the densified indices
    used internally. No exclusion of seen items: ~19% of held-out pairs are
    re-borrows, and the time-decayed reborrow component is meant to surface
    them.
    """
    n_users = scores.shape[0]
    inv_user = np.empty(n_users, dtype=np.int64)
    for orig, new in user_map.items():
        inv_user[new] = orig
    inv_book = np.empty(scores.shape[1], dtype=np.int64)
    for orig, new in book_map.items():
        inv_book[new] = orig

    rows = []
    for u in range(n_users):
        topk_unsorted = np.argpartition(-scores[u], k)[:k]
        topk = topk_unsorted[np.argsort(-scores[u, topk_unsorted])]
        rows.append((int(inv_user[u]), " ".join(str(i) for i in inv_book[topk])))
    rows.sort(key=lambda r: r[0])
    df = pd.DataFrame(rows, columns=["user_id", "recommendation"])
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    return df


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    interactions, _, aligned_tfidf, user_map, book_map = load_data()
    n_users, n_items = len(user_map), len(book_map)
    print(f"Users: {n_users}, Items: {n_items}, TF-IDF: {aligned_tfidf.shape}")

    print("\nFitting on full train (with time-aware components)...")
    train_matrix = build_interaction_matrix(interactions, n_users, n_items)
    model = fit(train_matrix, aligned_tfidf, train_df=interactions)

    scores = score_all_users(model)
    print(f"  blend: legacy={DEFAULT_LEGACY_W:.2f}  "
          f"pop={DEFAULT_POP_W:.2f}  rebo={DEFAULT_REBO_W:.2f}")

    write_submission(scores, user_map, book_map, k=10, out_path="submission.csv")


if __name__ == "__main__":
    main()

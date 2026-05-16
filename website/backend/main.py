from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import model_service
from .schemas import (
    BooksResp,
    CategoriesResp,
    HealthResp,
    RecommendReq,
    RecommendResp,
    SearchResp,
    SubcategoriesResp,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.recommender = model_service.load_or_fit()
    yield


app = FastAPI(title="Book Recommender", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5180",
        "http://127.0.0.1:5180",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResp)
def health():
    state = app.state.recommender
    return HealthResp(status="ok", n_items=state.n_items, n_users=state.n_users)


@app.get("/api/categories", response_model=CategoriesResp)
def categories():
    return CategoriesResp(book_types=model_service.categories(app.state.recommender))


@app.get("/api/subcategories", response_model=SubcategoriesResp)
def subcategories(book_type: str = Query(..., min_length=1)):
    payload = model_service.subcategories(app.state.recommender, book_type)
    return SubcategoriesResp(**payload)


@app.get("/api/recommend/user/{user_id}", response_model=RecommendResp)
def recommend_existing(user_id: int):
    try:
        recs = model_service.recommend_existing_user(app.state.recommender, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RecommendResp(recommendations=recs)


@app.get("/api/search", response_model=SearchResp)
def search(q: str = Query(""), limit: int = Query(10, ge=1, le=50)):
    return SearchResp(books=model_service.search_books(app.state.recommender, q, limit))


@app.get("/api/books", response_model=BooksResp)
def books(
    book_type: str = Query(..., min_length=1),
    subcategory: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    return BooksResp(
        books=model_service.books_in(app.state.recommender, book_type, subcategory, limit)
    )


@app.post("/api/recommend", response_model=RecommendResp)
def recommend(req: RecommendReq):
    try:
        recs = model_service.recommend(
            app.state.recommender,
            req.read_book_ids,
            liked_ids=req.liked_ids,
            disliked_ids=req.disliked_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RecommendResp(recommendations=recs)

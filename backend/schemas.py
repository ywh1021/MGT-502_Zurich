from pydantic import BaseModel, Field


class HealthResp(BaseModel):
    status: str
    n_items: int
    n_users: int


class BookType(BaseModel):
    value: str
    label: str
    count: int
    axis: str  # "discipline" | "topic" | "none"


class CategoriesResp(BaseModel):
    book_types: list[BookType]


class Subcategory(BaseModel):
    value: str
    label: str
    count: int


class SubcategoriesResp(BaseModel):
    book_type: str
    axis: str
    subcategories: list[Subcategory]


class Book(BaseModel):
    id: int
    title: str
    author: str
    subjects: str
    popularity: int


class BooksResp(BaseModel):
    books: list[Book]


class RecommendReq(BaseModel):
    read_book_ids: list[int] = Field(..., min_length=1)


class Recommendation(BaseModel):
    id: int
    rank: int
    title: str
    author: str
    subjects: str
    book_type: str
    discipline: str
    topic: str


class RecommendResp(BaseModel):
    recommendations: list[Recommendation]

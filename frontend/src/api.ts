import type {
  BooksResp,
  CategoriesResp,
  HealthResp,
  RecommendResp,
  SearchResp,
  SubcategoriesResp,
} from "./types";

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export function getHealth() {
  return getJson<HealthResp>("/api/health");
}

export function getCategories() {
  return getJson<CategoriesResp>("/api/categories");
}

export function searchBooks(q: string, limit = 10) {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return getJson<SearchResp>(`/api/search?${params}`);
}

export function getSubcategories(bookType: string) {
  return getJson<SubcategoriesResp>(
    `/api/subcategories?book_type=${encodeURIComponent(bookType)}`,
  );
}

export function getBooks(bookType: string, subcategory?: string, limit = 50) {
  const params = new URLSearchParams({ book_type: bookType, limit: String(limit) });
  if (subcategory) params.set("subcategory", subcategory);
  return getJson<BooksResp>(`/api/books?${params}`);
}

export async function getRecommendForUser(userId: number): Promise<RecommendResp> {
  return getJson<RecommendResp>(`/api/recommend/user/${userId}`);
}

export async function postRecommend(
  readBookIds: number[],
  likedIds: number[] = [],
  dislikedIds: number[] = [],
): Promise<RecommendResp> {
  const r = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      read_book_ids: readBookIds,
      liked_ids: likedIds,
      disliked_ids: dislikedIds,
    }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json();
}

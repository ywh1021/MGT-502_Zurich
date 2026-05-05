import type {
  BooksResp,
  CategoriesResp,
  RecommendResp,
  SubcategoriesResp,
} from "./types";

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export function getCategories() {
  return getJson<CategoriesResp>("/api/categories");
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

export async function postRecommend(readBookIds: number[]): Promise<RecommendResp> {
  const r = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ read_book_ids: readBookIds }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json();
}

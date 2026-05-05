export type Axis = "discipline" | "topic" | "none";

export interface BookType {
  value: string;
  label: string;
  count: number;
  axis: Axis;
}

export interface Subcategory {
  value: string;
  label: string;
  count: number;
}

export interface Book {
  id: number;
  title: string;
  author: string;
  subjects: string;
  popularity: number;
}

export interface Recommendation {
  id: number;
  rank: number;
  title: string;
  author: string;
  subjects: string;
  book_type: string;
  discipline: string;
  topic: string;
}

export interface CategoriesResp {
  book_types: BookType[];
}
export interface SubcategoriesResp {
  book_type: string;
  axis: Axis;
  subcategories: Subcategory[];
}
export interface BooksResp {
  books: Book[];
}
export interface RecommendResp {
  recommendations: Recommendation[];
}

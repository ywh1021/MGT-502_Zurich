import { useEffect, useState } from "react";
import { getCategories } from "../api";
import type { BookType } from "../types";

interface Props {
  onPick: (bt: BookType) => void;
}

export function CategoryPicker({ onPick }: Props) {
  const [bookTypes, setBookTypes] = useState<BookType[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCategories()
      .then((r) => setBookTypes(r.book_types))
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!bookTypes) return <div className="loading">Loading categories…</div>;

  return (
    <>
      <p className="subtitle">What kind of books are you in the mood for?</p>
      <div className="grid">
        {bookTypes.map((bt) => (
          <button key={bt.value} className="tile" onClick={() => onPick(bt)}>
            <div className="tile-label">{bt.label}</div>
            <div className="tile-count">{bt.count.toLocaleString()} books</div>
          </button>
        ))}
      </div>
    </>
  );
}

import { useEffect, useState } from "react";
import { getCategories } from "../api";
import type { BookType } from "../types";

interface Props {
  onConfirm: (categories: BookType[]) => void;
}

export function CategoryPicker({ onConfirm }: Props) {
  const [bookTypes, setBookTypes] = useState<BookType[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCategories()
      .then((r) => setBookTypes(r.book_types))
      .catch((e) => setError(String(e)));
  }, []);

  function toggle(value: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  if (error) return <div className="error">{error}</div>;
  if (!bookTypes) return <div className="loading">Loading categories…</div>;

  const selectedTypes = bookTypes.filter((bt) => selected.has(bt.value));

  return (
    <>
      <p className="subtitle">Choose one or more categories you're interested in.</p>
      <div className="grid">
        {bookTypes.map((bt) => {
          const isSel = selected.has(bt.value);
          return (
            <button
              key={bt.value}
              className={"tile" + (isSel ? " selected" : "")}
              onClick={() => toggle(bt.value)}
            >
              <div className="tile-label">{bt.label}</div>
              <div className="tile-count">{bt.count.toLocaleString()} books</div>
            </button>
          );
        })}
      </div>
      <div className="actions">
        <span style={{ color: "#555", fontSize: "13px", flex: 1 }}>
          {selected.size === 0
            ? "Select at least one category"
            : `${selected.size} categor${selected.size === 1 ? "y" : "ies"} selected`}
        </span>
        <button
          className="btn primary"
          disabled={selected.size === 0}
          onClick={() => onConfirm(selectedTypes)}
        >
          Next →
        </button>
      </div>
    </>
  );
}

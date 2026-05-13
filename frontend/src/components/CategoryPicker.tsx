import { useEffect, useState } from "react";
import { getCategories } from "../api";
import type { BookType } from "../types";

interface Props {
  onConfirm: (categories: BookType[]) => void;
}

const COLORS: Record<string, string> = {
  academic: "#7c5cdb",
  fiction: "#c45db3",
  non_fiction: "#4a7eff",
  children: "#4abe8a",
  young_adult: "#e05ca0",
  comics: "#ff8c42",
  practical: "#4ab8d0",
};
const FALLBACK = ["#7c5cdb", "#c45db3", "#4a7eff", "#4abe8a", "#ff8c42", "#4ab8d0", "#e05ca0"];

function BookIcon({ color }: { color: string }) {
  return (
    <svg width="40" height="50" viewBox="0 0 40 50" fill="none" aria-hidden>
      <rect x="5" y="0" width="30" height="44" rx="3" fill={color} opacity="0.25" />
      <rect x="5" y="0" width="7" height="44" rx="2" fill={color} opacity="0.5" />
      <rect x="14" y="0" width="21" height="44" rx="2" fill={color} opacity="0.8" />
      <rect x="18" y="13" width="13" height="2" rx="1" fill="white" opacity="0.5" />
      <rect x="18" y="18" width="9" height="2" rx="1" fill="white" opacity="0.3" />
    </svg>
  );
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
        {bookTypes.map((bt, i) => {
          const isSel = selected.has(bt.value);
          const color = COLORS[bt.value] ?? FALLBACK[i % FALLBACK.length];
          return (
            <button
              key={bt.value}
              className={"tile" + (isSel ? " selected" : "")}
              onClick={() => toggle(bt.value)}
            >
              <div className="tile-icon">
                <BookIcon color={color} />
              </div>
              <div className="tile-label">{bt.label}</div>
              <div className="tile-count">{bt.count.toLocaleString()} books</div>
            </button>
          );
        })}
      </div>
      <div className="actions">
        <span style={{ color: "var(--text-muted)", fontSize: "13px", flex: 1 }}>
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

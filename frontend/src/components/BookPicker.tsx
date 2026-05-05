import { useEffect, useMemo, useState } from "react";
import { getBooks, postRecommend } from "../api";
import type { Book, Recommendation } from "../types";

interface Props {
  bookType: string;
  subcategory?: string;
  onRecommendations: (recs: Recommendation[]) => void;
  onBack: () => void;
}

export function BookPicker({ bookType, subcategory, onRecommendations, onBack }: Props) {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getBooks(bookType, subcategory, 50)
      .then((r) => setBooks(r.books))
      .catch((e) => setError(String(e)));
  }, [bookType, subcategory]);

  const filtered = useMemo(() => {
    if (!books) return [];
    const q = search.trim().toLowerCase();
    if (!q) return books;
    return books.filter(
      (b) =>
        b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q),
    );
  }, [books, search]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const r = await postRecommend([...selected]);
      onRecommendations(r.recommendations);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (error) return <div className="error">{error}</div>;
  if (!books) return <div className="loading">Loading books…</div>;

  return (
    <>
      <p className="subtitle">
        Tick the books you've read. We'll recommend similar ones.
      </p>
      <input
        className="search"
        type="search"
        placeholder="Filter by title or author…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="book-list">
        {filtered.map((b) => {
          const isSel = selected.has(b.id);
          return (
            <label
              key={b.id}
              className={"book-row" + (isSel ? " selected" : "")}
            >
              <input
                type="checkbox"
                checked={isSel}
                onChange={() => toggle(b.id)}
              />
              <div className="meta">
                <div className="title">{b.title}</div>
                {b.author && <div className="author">{b.author}</div>}
              </div>
              <div className="pop">{b.popularity}×</div>
            </label>
          );
        })}
        {filtered.length === 0 && (
          <div className="loading">No books match that filter.</div>
        )}
      </div>
      <div className="actions">
        <button className="btn" onClick={onBack} disabled={submitting}>
          ← Back
        </button>
        <span className="selection-count">{selected.size} selected</span>
        <button
          className="btn primary"
          onClick={submit}
          disabled={selected.size === 0 || submitting}
        >
          {submitting ? "Thinking…" : "Get recommendations →"}
        </button>
      </div>
    </>
  );
}

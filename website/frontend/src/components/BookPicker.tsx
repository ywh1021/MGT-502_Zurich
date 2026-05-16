import { useEffect, useMemo, useRef, useState } from "react";
import { getBooks, postRecommend } from "../api";
import type { Book, Recommendation } from "../types";

interface Selection {
  book_type: string;
  subcategory?: string;
}

interface Props {
  selections: Selection[];
  allowEmpty?: boolean;
  onRecommendations: (recs: Recommendation[], profileIds: number[]) => void;
  onBack: () => void;
}

export function BookPicker({ selections, allowEmpty, onRecommendations, onBack }: Props) {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    Promise.all(selections.map((s) => getBooks(s.book_type, s.subcategory, 50)))
      .then((results) => {
        const byId = new Map<number, Book>();
        for (const r of results) {
          for (const b of r.books) {
            if (!byId.has(b.id)) byId.set(b.id, b);
          }
        }
        const merged = [...byId.values()].sort((a, b) => b.popularity - a.popularity);
        setBooks(merged);
      })
      .catch((e) => setError(String(e)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    if (!books) return [];
    const q = search.trim().toLowerCase();
    if (!q) return books;
    return books.filter(
      (b) =>
        b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q),
    );
  }, [books, search]);

  const suggestions = useMemo(() => {
    if (!search.trim() || search.trim().length < 2) return [];
    return filtered.slice(0, 8);
  }, [filtered, search]);

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
      const ids =
        selected.size > 0
          ? [...selected]
          : (books ?? []).slice(0, 5).map((b) => b.id);
      const r = await postRecommend(ids);
      onRecommendations(r.recommendations, ids);
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
        {allowEmpty
          ? "Tick any books you recognise — or just skip ahead and we'll use the most popular ones."
          : "Tick the books you've read — we'll use these to recommend similar ones."}
      </p>
      <div className="search-wrap" ref={wrapRef}>
        <input
          className="search"
          type="search"
          placeholder="Filter by title or author…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setDropdownOpen(true); }}
          onFocus={() => suggestions.length > 0 && setDropdownOpen(true)}
        />
        {dropdownOpen && suggestions.length > 0 && (
          <div className="search-dropdown">
            {suggestions.map((b) => (
              <button
                key={b.id}
                className="search-result"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { toggle(b.id); setSearch(""); setDropdownOpen(false); }}
              >
                <div className="meta">
                  <div className="title">{b.title}</div>
                  {b.author && <div className="author">{b.author}</div>}
                </div>
                <span className="search-add">{selected.has(b.id) ? "✓" : "+"}</span>
              </button>
            ))}
          </div>
        )}
      </div>
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
          disabled={(!allowEmpty && selected.size === 0) || submitting}
        >
          {submitting
            ? "Thinking…"
            : selected.size === 0 && allowEmpty
            ? "Recommend based on my genres →"
            : "Get recommendations →"}
        </button>
      </div>
    </>
  );
}

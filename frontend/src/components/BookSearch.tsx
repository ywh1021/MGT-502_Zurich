import { useEffect, useRef, useState } from "react";
import { postRecommend, searchBooks } from "../api";
import type { Book, Recommendation } from "../types";

interface Props {
  onRecommendations: (recs: Recommendation[], profileIds: number[]) => void;
  onBack: () => void;
}

export function BookSearch({ onRecommendations, onBack }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Book[]>([]);
  const [reads, setReads] = useState<Book[]>([]);
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Debounced search
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const r = await searchBooks(query, 8);
        const readIds = new Set(reads.map((b) => b.id));
        setResults(r.books.filter((b) => !readIds.has(b.id)));
        setOpen(true);
      } catch {
        // silently ignore search errors
      } finally {
        setSearching(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [query, reads]);

  function addBook(book: Book) {
    setReads((prev) => [...prev, book]);
    setQuery("");
    setResults([]);
    setOpen(false);
  }

  function removeBook(id: number) {
    setReads((prev) => prev.filter((b) => b.id !== id));
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const ids = reads.map((b) => b.id);
      const r = await postRecommend(ids);
      onRecommendations(r.recommendations, ids);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <p className="subtitle">
        Type a title or author — Marguerite will find matching books.
      </p>

      <div className="search-wrap" ref={wrapRef}>
        <input
          className="search"
          type="search"
          placeholder="e.g. Harry Potter, Tolstoy, Dune…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          autoFocus
        />
        {open && results.length > 0 && (
          <div className="search-dropdown">
            {results.map((b) => (
              <button
                key={b.id}
                className="search-result"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => addBook(b)}
              >
                <div className="meta">
                  <div className="title">{b.title}</div>
                  {b.author && <div className="author">{b.author}</div>}
                </div>
                <span className="search-add">+</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {!searching && query.trim().length >= 2 && results.length === 0 && open && (
        <div className="search-hint">No matches — try a different title or author.</div>
      )}
      {searching && <div className="search-hint">Searching…</div>}

      {reads.length > 0 && (
        <div className="reads-section">
          <div className="reads-label">Your reads — {reads.length} book{reads.length !== 1 ? "s" : ""}</div>
          <div className="reads-chips">
            {reads.map((b) => (
              <div key={b.id} className="read-chip">
                <span>{b.title}</span>
                <button className="read-chip-remove" onClick={() => removeBook(b.id)}>
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div className="actions">
        <button className="btn" onClick={onBack} disabled={submitting}>
          ← Back
        </button>
        <button
          className="btn primary"
          style={{ marginLeft: "auto" }}
          disabled={reads.length === 0 || submitting}
          onClick={submit}
        >
          {submitting ? "Thinking…" : `What should I read next? →`}
        </button>
      </div>
    </>
  );
}

import { useEffect, useState } from "react";
import { getSubcategories } from "../api";
import type { Subcategory } from "../types";

interface Props {
  bookType: string;
  axisLabel: string; // "discipline" | "topic"
  onPick: (sub: Subcategory) => void;
  onBack: () => void;
}

export function SubcategoryPicker({ bookType, axisLabel, onPick, onBack }: Props) {
  const [subs, setSubs] = useState<Subcategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSubcategories(bookType)
      .then((r) => setSubs(r.subcategories))
      .catch((e) => setError(String(e)));
  }, [bookType]);

  if (error) return <div className="error">{error}</div>;
  if (!subs) return <div className="loading">Loading {axisLabel}s…</div>;

  return (
    <>
      <p className="subtitle">Pick a {axisLabel} you're interested in.</p>
      <div className="grid">
        {subs.map((s) => (
          <button key={s.value} className="tile" onClick={() => onPick(s)}>
            <div className="tile-label">{s.label}</div>
            <div className="tile-count">{s.count.toLocaleString()} books</div>
          </button>
        ))}
      </div>
      <div className="actions">
        <button className="btn" onClick={onBack}>← Back</button>
      </div>
    </>
  );
}

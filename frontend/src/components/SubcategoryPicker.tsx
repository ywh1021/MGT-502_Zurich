import { useEffect, useState } from "react";
import { getSubcategories } from "../api";
import type { BookType, Subcategory } from "../types";

interface Props {
  categories: BookType[];
  onConfirm: (subcategoryMap: Map<string, string[]>) => void;
  onBack: () => void;
}

export function SubcategoryPicker({ categories, onConfirm, onBack }: Props) {
  const [subsMap, setSubsMap] = useState<Map<string, Subcategory[]> | null>(null);
  const [selectedMap, setSelectedMap] = useState<Map<string, Set<string>>>(new Map());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all(categories.map((cat) => getSubcategories(cat.value)))
      .then((results) => {
        const map = new Map<string, Subcategory[]>();
        results.forEach((r, i) => {
          map.set(categories[i].value, r.subcategories);
        });
        setSubsMap(map);
      })
      .catch((e) => setError(String(e)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(bookType: string, value: string) {
    setSelectedMap((prev) => {
      const next = new Map(prev);
      const set = new Set(next.get(bookType) ?? []);
      if (set.has(value)) set.delete(value);
      else set.add(value);
      next.set(bookType, set);
      return next;
    });
  }

  function confirm() {
    const result = new Map<string, string[]>();
    for (const [bookType, set] of selectedMap) {
      result.set(bookType, [...set]);
    }
    onConfirm(result);
  }

  if (error) return <div className="error">{error}</div>;
  if (!subsMap) return <div className="loading">Loading topics…</div>;

  return (
    <>
      <p className="subtitle">
        Narrow down by topic or discipline — or skip straight to books.
      </p>
      {categories.map((cat) => {
        const subs = subsMap.get(cat.value) ?? [];
        const selectedSet = selectedMap.get(cat.value) ?? new Set<string>();
        const axisLabel = cat.axis === "discipline" ? "discipline" : "topic";
        return (
          <div key={cat.value} className="sub-group">
            <div className="sub-group-label">
              {cat.label}
              <span className="sub-group-axis"> — pick a {axisLabel}</span>
            </div>
            <div className="grid">
              {subs.map((s) => {
                const isSel = selectedSet.has(s.value);
                return (
                  <button
                    key={s.value}
                    className={"tile" + (isSel ? " selected" : "")}
                    onClick={() => toggle(cat.value, s.value)}
                  >
                    <div className="tile-label">{s.label}</div>
                    <div className="tile-count">{s.count.toLocaleString()} books</div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="actions">
        <button className="btn" onClick={onBack}>
          ← Back
        </button>
        <button className="btn primary" style={{ marginLeft: "auto" }} onClick={confirm}>
          Show books →
        </button>
      </div>
    </>
  );
}

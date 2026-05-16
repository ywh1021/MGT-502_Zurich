import { useState } from "react";
import { getRecommendForUser, getHealth } from "../api";
import type { Recommendation } from "../types";
import { useEffect } from "react";

interface Props {
  onRecommendations: (recs: Recommendation[]) => void;
  onBack: () => void;
}

export function UserIdEntry({ onRecommendations, onBack }: Props) {
  const [value, setValue] = useState("");
  const [maxId, setMaxId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setMaxId(h.n_users - 1))
      .catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const id = parseInt(value.trim(), 10);
    if (isNaN(id)) {
      setError("Please enter a valid number.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await getRecommendForUser(id);
      onRecommendations(r.recommendations);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg.includes("404") ? "This ID wasn't found — double-check and try again." : msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <p className="subtitle">
        Enter your reader ID and Marguerite will pull up your history instantly.
      </p>

      <form onSubmit={submit} style={{ maxWidth: 360 }}>
        <label className="id-label">
          Your reader ID
          {maxId !== null && (
            <span className="id-range"> (0 – {maxId.toLocaleString()})</span>
          )}
        </label>
        <div className="id-row">
          <input
            className="id-input"
            type="number"
            min={0}
            max={maxId ?? undefined}
            placeholder="e.g. 4821"
            value={value}
            onChange={(e) => { setValue(e.target.value); setError(null); }}
            autoFocus
          />
          <button
            className="btn primary"
            type="submit"
            disabled={value.trim() === "" || loading}
          >
            {loading ? "Looking up…" : "Go →"}
          </button>
        </div>
        {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
      </form>

      <div className="actions" style={{ marginTop: 32 }}>
        <button className="btn" onClick={onBack}>← Back</button>
      </div>
    </>
  );
}

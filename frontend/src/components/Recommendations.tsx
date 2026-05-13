import { useState } from "react";
import { postRecommend } from "../api";
import type { Recommendation } from "../types";

interface Props {
  recs: Recommendation[];
  profileIds: number[];
  onStartOver: () => void;
  onBack: () => void;
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function chipsFor(r: Recommendation): string[] {
  const chips: string[] = [r.book_type.replace(/_/g, " ")];
  if (r.discipline && r.discipline !== "not_applicable")
    chips.push(r.discipline.replace(/_/g, " "));
  if (r.topic && r.topic !== "not_applicable")
    chips.push(r.topic.replace(/_/g, " "));
  return chips;
}

export function Recommendations({ recs: initialRecs, profileIds, onStartOver, onBack }: Props) {
  const [recs, setRecs] = useState(initialRecs);
  const [liked, setLiked] = useState<Set<number>>(new Set());
  const [disliked, setDisliked] = useState<Set<number>>(new Set());
  const [allLiked, setAllLiked] = useState<Set<number>>(new Set());
  const [allDisliked, setAllDisliked] = useState<Set<number>>(new Set());
  const [round, setRound] = useState(1);
  const [refining, setRefining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleLiked(id: number) {
    setLiked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        setDisliked((d) => { const nd = new Set(d); nd.delete(id); return nd; });
      }
      return next;
    });
  }

  function toggleDisliked(id: number) {
    setDisliked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        setLiked((l) => { const nl = new Set(l); nl.delete(id); return nl; });
      }
      return next;
    });
  }

  async function refine() {
    setRefining(true);
    setError(null);
    try {
      const newAllLiked = new Set([...allLiked, ...liked]);
      const newAllDisliked = new Set([...allDisliked, ...disliked]);
      const r = await postRecommend(
        profileIds,
        [...newAllLiked],
        [...newAllDisliked],
      );
      setRecs(r.recommendations);
      setAllLiked(newAllLiked);
      setAllDisliked(newAllDisliked);
      setLiked(new Set());
      setDisliked(new Set());
      setRound((n) => n + 1);
    } catch (e) {
      setError(String(e));
    } finally {
      setRefining(false);
    }
  }

  const hasNewRatings = liked.size > 0 || disliked.size > 0;
  const canRefine = hasNewRatings && (profileIds.length > 0 || allLiked.size + liked.size > 0);

  return (
    <>
      <div className="recs-header">
        <p className="subtitle" style={{ margin: 0 }}>
          {round === 1
            ? `Top ${recs.length} picks for you.`
            : `Round ${round} — refined based on your feedback.`}
        </p>
        {round > 1 && (
          <span className="round-badge">Round {round}</span>
        )}
      </div>

      <p className="feedback-hint">
        👍 like a book to refine your taste · 👎 dislike to skip similar ones
      </p>

      <div className="recs">
        {recs.map((r) => {
          const isLiked = liked.has(r.id);
          const isDisliked = disliked.has(r.id);
          return (
            <div
              key={r.id}
              className={
                "rec" +
                (isLiked ? " rec-liked" : "") +
                (isDisliked ? " rec-disliked" : "")
              }
            >
              <div className="rank">{r.rank}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="title">{r.title}</div>
                {r.author && <div className="author">{r.author}</div>}
                {r.subjects && (
                  <div className="subjects">{truncate(r.subjects, 120)}</div>
                )}
                <div className="chips">
                  {chipsFor(r).map((c) => (
                    <span key={c} className="chip">{c}</span>
                  ))}
                </div>
              </div>
              <div className="rec-feedback">
                <button
                  className={"feedback-btn" + (isLiked ? " active-like" : "")}
                  onClick={() => toggleLiked(r.id)}
                  title="I'd like to read this"
                >👍</button>
                <button
                  className={"feedback-btn" + (isDisliked ? " active-dislike" : "")}
                  onClick={() => toggleDisliked(r.id)}
                  title="Not interested"
                >👎</button>
              </div>
            </div>
          );
        })}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="actions">
        <button className="btn" onClick={onBack} disabled={refining}>← Back</button>
        <button className="btn" onClick={onStartOver} disabled={refining}>Start over</button>
        <button
          className="btn primary"
          style={{ marginLeft: "auto" }}
          onClick={refine}
          disabled={!canRefine || refining}
          title={!canRefine ? "Rate at least one book to refine" : ""}
        >
          {refining ? "Updating…" : `Refine with feedback →`}
        </button>
      </div>
    </>
  );
}

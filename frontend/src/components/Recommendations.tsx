import type { Recommendation } from "../types";

interface Props {
  recs: Recommendation[];
  onStartOver: () => void;
  onBack: () => void;
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function chipsFor(r: Recommendation): string[] {
  const chips: string[] = [r.book_type.replace(/_/g, " ")];
  if (r.discipline && r.discipline !== "not_applicable") {
    chips.push(r.discipline.replace(/_/g, " "));
  }
  if (r.topic && r.topic !== "not_applicable") {
    chips.push(r.topic.replace(/_/g, " "));
  }
  return chips;
}

export function Recommendations({ recs, onStartOver, onBack }: Props) {
  return (
    <>
      <p className="subtitle">Top {recs.length} recommendations for you.</p>
      <div className="recs">
        {recs.map((r) => (
          <div key={r.id} className="rec">
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
          </div>
        ))}
      </div>
      <div className="actions">
        <button className="btn" onClick={onBack}>← Pick different books</button>
        <button className="btn primary" onClick={onStartOver}>Start over</button>
      </div>
    </>
  );
}

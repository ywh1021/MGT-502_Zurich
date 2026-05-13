import { useEffect, useState } from "react";
import { getHealth } from "../api";
import librarian from "../assets/librarian.png";
import cat from "../assets/cat.png";

interface Props {
  onSearch: () => void;
  onGenre: () => void;
  onUserId: () => void;
}

export function HomePage({ onSearch, onGenre, onUserId }: Props) {
  const [stats, setStats] = useState<{ n_items: number; n_users: number } | null>(null);

  useEffect(() => {
    getHealth().then(setStats).catch(() => {});
  }, []);

  return (
    <>
      {/* Hero — text + Marguerite on the left, cat far right */}
      <div className="hero">
        <div className="hero-text">
          <div className="hero-eyebrow">Library Recommendation System</div>
          <h1 className="hero-title">
            ask
            <span className="hero-title-accent">Marguerite</span>
          </h1>
          {stats && (
            <p className="hero-stats">
              <b>{stats.n_items.toLocaleString()}</b> books ·{" "}
              <b>{stats.n_users.toLocaleString()}</b> readers
            </p>
          )}
          <div className="hero-librarian">
            <img src={cat} alt="" />
          </div>
        </div>
        <div className="hero-image">
          <img src={librarian} alt="Marguerite the librarian" />
        </div>
      </div>

      {/* Path selection */}
      <div className="path-intro">
        <p className="path-quote">Let's find your next favorite book!</p>
        <p className="path-prompt">How should we start?</p>
      </div>
      <div className="path-grid">
        <button className="path-card" onClick={onSearch}>
          <div className="path-icon">📖</div>
          <div className="path-title">I love these…</div>
          <div className="path-desc">
            Name a few books you've enjoyed, and I'll find something similar.
          </div>
          <div className="path-arrow">→</div>
        </button>
        <button className="path-card" onClick={onGenre}>
          <div className="path-icon">✨</div>
          <div className="path-title">Surprise me!</div>
          <div className="path-desc">
            Pick a genre, and let's see what's popular.
          </div>
          <div className="path-arrow">→</div>
        </button>
        <button className="path-card" onClick={onUserId}>
          <div className="path-icon">👋</div>
          <div className="path-title">Welcome back</div>
          <div className="path-desc">
            Enter your Reader ID to get picks based on your history.
          </div>
          <div className="path-arrow">→</div>
        </button>
      </div>
    </>
  );
}

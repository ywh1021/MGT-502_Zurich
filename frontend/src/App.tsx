import { useState } from "react";
import { CategoryPicker } from "./components/CategoryPicker";
import { SubcategoryPicker } from "./components/SubcategoryPicker";
import { BookPicker } from "./components/BookPicker";
import { Recommendations } from "./components/Recommendations";
import type { BookType, Recommendation, Subcategory } from "./types";

type Step = "category" | "subcategory" | "books" | "recommendations";

export default function App() {
  const [step, setStep] = useState<Step>("category");
  const [bookType, setBookType] = useState<BookType | null>(null);
  const [sub, setSub] = useState<Subcategory | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);

  function pickCategory(bt: BookType) {
    setBookType(bt);
    setSub(null);
    setStep(bt.axis === "none" ? "books" : "subcategory");
  }

  function pickSubcategory(s: Subcategory) {
    setSub(s);
    setStep("books");
  }

  function startOver() {
    setBookType(null);
    setSub(null);
    setRecs([]);
    setStep("category");
  }

  return (
    <div className="app">
      <h1>Book recommender</h1>
      {step !== "category" && (
        <div className="crumbs">
          <span
            style={{ cursor: "pointer", textDecoration: "underline" }}
            onClick={startOver}
          >
            All categories
          </span>
          {bookType && (
            <>
              <span className="sep">›</span>
              <strong>{bookType.label}</strong>
            </>
          )}
          {sub && (
            <>
              <span className="sep">›</span>
              <strong>{sub.label}</strong>
            </>
          )}
        </div>
      )}

      {step === "category" && <CategoryPicker onPick={pickCategory} />}

      {step === "subcategory" && bookType && (
        <SubcategoryPicker
          bookType={bookType.value}
          axisLabel={bookType.axis === "discipline" ? "discipline" : "topic"}
          onPick={pickSubcategory}
          onBack={() => setStep("category")}
        />
      )}

      {step === "books" && bookType && (
        <BookPicker
          bookType={bookType.value}
          subcategory={sub?.value}
          onRecommendations={(r) => {
            setRecs(r);
            setStep("recommendations");
          }}
          onBack={() =>
            setStep(bookType.axis === "none" ? "category" : "subcategory")
          }
        />
      )}

      {step === "recommendations" && (
        <Recommendations
          recs={recs}
          onStartOver={startOver}
          onBack={() => setStep("books")}
        />
      )}
    </div>
  );
}

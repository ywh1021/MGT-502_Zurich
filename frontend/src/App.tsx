import { useMemo, useState } from "react";
import { CategoryPicker } from "./components/CategoryPicker";
import { SubcategoryPicker } from "./components/SubcategoryPicker";
import { BookPicker } from "./components/BookPicker";
import { Recommendations } from "./components/Recommendations";
import type { BookType, Recommendation } from "./types";

type Step = "category" | "subcategory" | "books" | "recommendations";

export default function App() {
  const [step, setStep] = useState<Step>("category");
  const [selectedCategories, setSelectedCategories] = useState<BookType[]>([]);
  const [subcategoryMap, setSubcategoryMap] = useState<Map<string, string[]>>(new Map());
  const [recs, setRecs] = useState<Recommendation[]>([]);

  const categoriesWithSubs = useMemo(
    () => selectedCategories.filter((c) => c.axis !== "none"),
    [selectedCategories],
  );

  const bookSelections = useMemo(() => {
    const result: { book_type: string; subcategory?: string }[] = [];
    for (const cat of selectedCategories) {
      if (cat.axis === "none") {
        result.push({ book_type: cat.value });
      } else {
        const subs = subcategoryMap.get(cat.value) ?? [];
        if (subs.length === 0) {
          result.push({ book_type: cat.value });
        } else {
          for (const sub of subs) {
            result.push({ book_type: cat.value, subcategory: sub });
          }
        }
      }
    }
    return result;
  }, [selectedCategories, subcategoryMap]);

  function confirmCategories(cats: BookType[]) {
    setSelectedCategories(cats);
    setSubcategoryMap(new Map());
    setStep(cats.some((c) => c.axis !== "none") ? "subcategory" : "books");
  }

  function confirmSubcategories(map: Map<string, string[]>) {
    setSubcategoryMap(map);
    setStep("books");
  }

  function startOver() {
    setSelectedCategories([]);
    setSubcategoryMap(new Map());
    setRecs([]);
    setStep("category");
  }

  const categoryLabels = selectedCategories.map((c) => c.label).join(", ");

  return (
    <div className="app">
      <h1>Book recommender</h1>
      {step !== "category" && (
        <div className="crumbs">
          <span
            style={{ cursor: "pointer", textDecoration: "underline" }}
            onClick={startOver}
          >
            ← Start over
          </span>
          {categoryLabels && (
            <>
              <span className="sep">·</span>
              <span>{categoryLabels}</span>
            </>
          )}
        </div>
      )}

      {step === "category" && <CategoryPicker onConfirm={confirmCategories} />}

      {step === "subcategory" && (
        <SubcategoryPicker
          categories={categoriesWithSubs}
          onConfirm={confirmSubcategories}
          onBack={() => setStep("category")}
        />
      )}

      {step === "books" && (
        <BookPicker
          selections={bookSelections}
          onRecommendations={(r) => {
            setRecs(r);
            setStep("recommendations");
          }}
          onBack={() =>
            setStep(categoriesWithSubs.length > 0 ? "subcategory" : "category")
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

import { useMemo, useState } from "react";
import { HomePage } from "./components/HomePage";
import { BookSearch } from "./components/BookSearch";
import { UserIdEntry } from "./components/UserIdEntry";
import { CategoryPicker } from "./components/CategoryPicker";
import { SubcategoryPicker } from "./components/SubcategoryPicker";
import { BookPicker } from "./components/BookPicker";
import { Recommendations } from "./components/Recommendations";
import type { BookType, Recommendation } from "./types";

type Step =
  | "home"
  | "search"
  | "user-id"
  | "genre-category"
  | "genre-subcategory"
  | "genre-books"
  | "recommendations";

export default function App() {
  const [step, setStep] = useState<Step>("home");
  const [selectedCategories, setSelectedCategories] = useState<BookType[]>([]);
  const [subcategoryMap, setSubcategoryMap] = useState<Map<string, string[]>>(new Map());
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [profileIds, setProfileIds] = useState<number[]>([]);
  const [prevStep, setPrevStep] = useState<Step>("home");

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

  function goHome() {
    setSelectedCategories([]);
    setSubcategoryMap(new Map());
    setRecs([]);
    setStep("home");
  }

  function confirmCategories(cats: BookType[]) {
    setSelectedCategories(cats);
    setSubcategoryMap(new Map());
    setStep(cats.some((c) => c.axis !== "none") ? "genre-subcategory" : "genre-books");
  }

  function confirmSubcategories(map: Map<string, string[]>) {
    setSubcategoryMap(map);
    setStep("genre-books");
  }

  function showRecs(r: Recommendation[], ids: number[] = []) {
    setPrevStep(step as Step);
    setProfileIds(ids);
    setRecs(r);
    setStep("recommendations");
  }

  const categoryLabels = selectedCategories.map((c) => c.label).join(", ");

  return (
    <div className="app">
      {/* Breadcrumb — hidden on home */}
      {step !== "home" && (
        <div className="crumbs">
          <button role="button" onClick={goHome}>← Home</button>
          {categoryLabels && (
            <>
              <span className="sep">›</span>
              <span>{categoryLabels}</span>
            </>
          )}
        </div>
      )}

      {step === "home" && (
        <HomePage
          onSearch={() => setStep("search")}
          onGenre={() => setStep("genre-category")}
          onUserId={() => setStep("user-id")}
        />
      )}

      {step === "search" && (
        <BookSearch onRecommendations={showRecs} onBack={goHome} />
      )}

      {step === "user-id" && (
        <UserIdEntry onRecommendations={showRecs} onBack={goHome} />
      )}

      {step === "genre-category" && (
        <CategoryPicker onConfirm={confirmCategories} />
      )}

      {step === "genre-subcategory" && (
        <SubcategoryPicker
          categories={categoriesWithSubs}
          onConfirm={confirmSubcategories}
          onBack={() => setStep("genre-category")}
        />
      )}

      {step === "genre-books" && (
        <BookPicker
          selections={bookSelections}
          allowEmpty
          onRecommendations={showRecs}
          onBack={() =>
            setStep(categoriesWithSubs.length > 0 ? "genre-subcategory" : "genre-category")
          }
        />
      )}

      {step === "recommendations" && (
        <Recommendations
          recs={recs}
          profileIds={profileIds}
          onStartOver={goHome}
          onBack={() => setStep(prevStep === "search" ? "search" : prevStep === "user-id" ? "user-id" : "genre-books")}
        />
      )}
    </div>
  );
}

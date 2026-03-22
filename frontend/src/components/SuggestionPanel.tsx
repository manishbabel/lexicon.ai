/**
 * Fixed 2x3 grid of suggestion slots — one per category.
 *
 * Cards are always visible. When a new suggestion arrives for a category,
 * it replaces the previous content in that slot. Empty slots show a
 * subtle placeholder.
 */

import type { Suggestion, SuggestionCategory } from "../lib/types";
import SuggestionCard from "./SuggestionCard";

const SLOT_ORDER: SuggestionCategory[] = [
  "term",
  "insight",
  "procon",
  "pattern",
  "question",
  "general",
];

export default function SuggestionPanel({
  suggestions,
}: {
  suggestions: Suggestion[];
}) {
  // For each category, pick the most recent suggestion
  const slotMap = new Map<SuggestionCategory, Suggestion>();
  for (const s of suggestions) {
    const existing = slotMap.get(s.category);
    if (!existing || s.timestamp > existing.timestamp) {
      slotMap.set(s.category, s);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 p-3">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2.5 h-full">
          {SLOT_ORDER.map((category) => (
            <SuggestionCard
              key={category}
              category={category}
              suggestion={slotMap.get(category) ?? null}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

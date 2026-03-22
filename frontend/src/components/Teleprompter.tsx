/**
 * Teleprompter — big colorful "say this NOW" banner.
 *
 * Extracts the most recent quoted sentence from suggestions
 * and displays it huge and colorful so the user can read it at a glance.
 */

import { motion, AnimatePresence } from "framer-motion";
import type { Suggestion, SuggestionCategory } from "../lib/types";

const CATEGORY_COLORS: Record<SuggestionCategory, { text: string; glow: string }> = {
  term:     { text: "text-term",     glow: "from-term/10 via-term/5 to-transparent" },
  insight:  { text: "text-insight",  glow: "from-insight/10 via-insight/5 to-transparent" },
  procon:   { text: "text-procon",   glow: "from-procon/10 via-procon/5 to-transparent" },
  pattern:  { text: "text-pattern",  glow: "from-pattern/10 via-pattern/5 to-transparent" },
  question: { text: "text-question", glow: "from-question/10 via-question/5 to-transparent" },
  general:  { text: "text-accent",   glow: "from-accent/10 via-accent/5 to-transparent" },
};

const CATEGORY_LABEL: Record<SuggestionCategory, string> = {
  term: "SAY THIS",
  insight: "KEY INSIGHT",
  procon: "CONSIDER",
  pattern: "PATTERN",
  question: "ASK THIS",
  general: "NOTE",
};

/** Extract quoted phrases from text */
function extractQuotes(text: string): string[] {
  const matches = text.match(/"([^"]{10,})"/g);
  return matches ? matches.map((m) => m.replace(/"/g, "")) : [];
}

/** Parse **bold** into colored elements */
function renderBold(text: string, colorClass: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className={`font-extrabold ${colorClass}`}>
        {part}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

interface TeleprompterProps {
  suggestions: Suggestion[];
}

export default function Teleprompter({ suggestions }: TeleprompterProps) {
  // Find the best "say this" text from recent suggestions
  const sorted = [...suggestions]
    .filter((s) => !s.streaming && s.body)
    .sort((a, b) => b.timestamp - a.timestamp);

  // Try to find a quoted sentence first (most actionable)
  let displayText = "";
  let category: SuggestionCategory = "general";

  for (const s of sorted) {
    const quotes = extractQuotes(s.body);
    if (quotes.length > 0) {
      displayText = quotes[0];
      category = s.category;
      break;
    }
  }

  // Fallback: first line of most recent suggestion
  if (!displayText && sorted.length > 0) {
    const latest = sorted[0];
    category = latest.category;
    const firstLine = latest.body.split("\n").find((l) => l.trim().length > 10);
    displayText = firstLine?.trim().replace(/^[▸•\-*]\s*/, "").slice(0, 150) || "";
  }

  const colors = CATEGORY_COLORS[category];
  const label = CATEGORY_LABEL[category];

  return (
    <div
      className={`shrink-0 border-b border-border bg-gradient-to-r ${colors.glow} w-full`}
    >
      <div className="px-8 py-6 text-center min-h-[100px] flex flex-col items-center justify-center">
        <AnimatePresence mode="wait">
          {displayText ? (
            <motion.div
              key={displayText.slice(0, 20)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35 }}
              className="flex flex-col items-center gap-3"
            >
              <span
                className={`text-[11px] font-black uppercase tracking-[0.25em] ${colors.text} opacity-60`}
              >
                {label}
              </span>
              <p className="text-3xl md:text-4xl leading-tight text-text font-bold tracking-tight max-w-4xl">
                {renderBold(`"${displayText}"`, colors.text)}
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="waiting"
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.25 }}
              className="flex flex-col items-center gap-2"
            >
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-text-3 animate-pulse" />
                <span className="w-2 h-2 rounded-full bg-text-3 animate-pulse [animation-delay:200ms]" />
                <span className="w-2 h-2 rounded-full bg-text-3 animate-pulse [animation-delay:400ms]" />
              </div>
              <span className="text-sm text-text-3 font-medium">Listening to conversation...</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/**
 * Fixed suggestion card slot — always visible, shows latest data for its category.
 *
 * Each card type has its own rendering:
 * - Term: bullet list of terms with sentences
 * - Insight: key point + say this
 * - Pro/Con: two columns (pro vs con)
 * - Pattern: ASCII diagram + pattern name
 * - Question: big question text
 */

import { motion, AnimatePresence } from "framer-motion";
import type { Suggestion, SuggestionCategory } from "../lib/types";

const CATEGORY_CONFIG: Record<
  SuggestionCategory,
  { label: string; icon: string; color: string; bg: string; border: string; cardBg: string }
> = {
  term: {
    label: "Terms You Can Use",
    icon: "A",
    color: "text-term",
    bg: "bg-term-muted",
    border: "border-term/30",
    cardBg: "bg-term-muted/20",
  },
  insight: {
    label: "Key Insight",
    icon: "!",
    color: "text-insight",
    bg: "bg-insight-muted",
    border: "border-insight/30",
    cardBg: "bg-insight-muted/20",
  },
  procon: {
    label: "Pro / Con",
    icon: "⇅",
    color: "text-procon",
    bg: "bg-procon-muted",
    border: "border-procon/30",
    cardBg: "bg-procon-muted/20",
  },
  pattern: {
    label: "Design Pattern",
    icon: "◇",
    color: "text-pattern",
    bg: "bg-pattern-muted",
    border: "border-pattern/30",
    cardBg: "bg-pattern-muted/20",
  },
  question: {
    label: "Ask This",
    icon: "?",
    color: "text-question",
    bg: "bg-question-muted",
    border: "border-question/30",
    cardBg: "bg-question-muted/20",
  },
  general: {
    label: "Note",
    icon: "●",
    color: "text-accent",
    bg: "bg-accent-muted",
    border: "border-accent/30",
    cardBg: "bg-accent-muted/20",
  },
};

/** Parse **bold** into colored elements */
function renderBold(text: string, colorClass: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className={`font-bold ${colorClass}`}>
        {part}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

/** Extract quoted sentences from text */
function extractQuotes(text: string): string[] {
  const matches = text.match(/"([^"]{8,})"/g);
  return matches ? matches.map((m) => m.replace(/"/g, "")) : [];
}

/** Remove quoted sentences from text so they don't duplicate the quote section */
function stripQuotes(text: string): string {
  return text.replace(/"[^"]{8,}"/g, "").replace(/\n{2,}/g, "\n").trim();
}

/** Extract code block (ASCII diagram) from text */
function extractDiagram(text: string): { diagram: string; rest: string } {
  const match = text.match(/```[\s\S]*?\n([\s\S]*?)```/);
  if (match) {
    const diagram = match[1].trim();
    const rest = text.replace(match[0], "").trim();
    return { diagram, rest };
  }
  // Also try lines with arrows/boxes (no fenced block)
  const lines = text.split("\n");
  const diagramLines: string[] = [];
  const restLines: string[] = [];
  for (const line of lines) {
    if (/[→←↑↓│┌┐└┘├┤┬┴─\[\]|>]/.test(line) && !line.startsWith('"')) {
      diagramLines.push(line);
    } else {
      restLines.push(line);
    }
  }
  if (diagramLines.length >= 2) {
    return { diagram: diagramLines.join("\n"), rest: restLines.join("\n").trim() };
  }
  return { diagram: "", rest: text };
}

/** Extract pro/con lines */
function extractProCon(text: string): { pros: string[]; cons: string[]; rest: string } {
  const pros: string[] = [];
  const cons: string[] = [];
  const rest: string[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (/^[✓✔+]/.test(trimmed) || /^pro:/i.test(trimmed)) {
      pros.push(trimmed.replace(/^[✓✔+]\s*/, "").replace(/^pro:\s*/i, ""));
    } else if (/^[✗✘✕×-]/.test(trimmed) || /^con:/i.test(trimmed)) {
      cons.push(trimmed.replace(/^[✗✘✕×-]\s*/, "").replace(/^con:\s*/i, ""));
    } else {
      rest.push(trimmed);
    }
  }
  return { pros, cons, rest: rest.filter(Boolean).join("\n") };
}

// ── Per-category renderers ──────────────────────────────────────

function TermContent({ body, color }: { body: string; color: string }) {
  // For terms, each line is like: ▸ **Term** — "sentence to say"
  // We keep the full line (term + quote together) since that's the format
  const lines = body.split("\n").filter((l) => l.trim());
  return (
    <div className="space-y-1.5">
      {lines.slice(0, 4).map((line, i) => {
        // Split line into term part and quote part
        const quoteMatch = line.match(/(.*?)['"](.{8,})['"](.*)/);
        if (quoteMatch) {
          const [, before, quote, after] = quoteMatch;
          return (
            <div key={i} className="text-sm leading-snug">
              <span className="text-text-2">{renderBold(before.trim(), color)}</span>
              <span className={`${color} font-semibold`}> "{quote}"</span>
              {after && <span className="text-text-3">{after}</span>}
            </div>
          );
        }
        return (
          <div key={i} className="text-sm text-text-2 leading-snug">
            {renderBold(line, color)}
          </div>
        );
      })}
    </div>
  );
}

function InsightContent({ body, color }: { body: string; color: string }) {
  const quotes = extractQuotes(body);
  const cleaned = stripQuotes(body);
  const lines = cleaned.split("\n").filter((l) => l.trim());
  return (
    <div>
      <p className="text-sm text-text-2 leading-relaxed line-clamp-3">
        {renderBold(lines.slice(0, 2).join(" "), color)}
      </p>
      {quotes[0] && (
        <p className={`text-sm ${color} font-semibold mt-2 leading-snug`}>
          "{quotes[0]}"
        </p>
      )}
    </div>
  );
}

function ProConContent({ body, color }: { body: string; color: string }) {
  const { pros, cons, rest } = extractProCon(body);
  const quotes = extractQuotes(rest);
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          {pros.map((p, i) => (
            <p key={i} className="text-term leading-snug">✓ {renderBold(p, "text-term")}</p>
          ))}
          {pros.length === 0 && <p className="text-text-3 opacity-40">—</p>}
        </div>
        <div>
          {cons.map((c, i) => (
            <p key={i} className="text-danger leading-snug">✗ {renderBold(c, "text-danger")}</p>
          ))}
          {cons.length === 0 && <p className="text-text-3 opacity-40">—</p>}
        </div>
      </div>
      {quotes[0] && (
        <p className={`text-xs ${color} font-semibold mt-2 leading-snug`}>
          "{quotes[0]}"
        </p>
      )}
    </div>
  );
}

function PatternContent({ body, color }: { body: string; color: string }) {
  const { diagram, rest } = extractDiagram(body);
  const quotes = extractQuotes(rest);
  const cleanRest = stripQuotes(rest);
  return (
    <div>
      {diagram && (
        <pre className={`text-[10px] leading-tight font-mono ${color} whitespace-pre overflow-x-auto mb-2 p-2 rounded-lg bg-bg/50`}>
          {diagram}
        </pre>
      )}
      <p className="text-xs text-text-2 leading-relaxed line-clamp-2">
        {renderBold(cleanRest.split("\n").filter((l) => l.trim()).slice(0, 2).join(" "), color)}
      </p>
      {quotes[0] && (
        <p className={`text-xs ${color} font-semibold mt-1.5 leading-snug`}>
          "{quotes[0]}"
        </p>
      )}
    </div>
  );
}

function QuestionContent({ body, color }: { body: string; color: string }) {
  const quotes = extractQuotes(body);
  const mainQuestion = quotes[0] || body.split("\n")[0]?.trim() || "";
  const cleaned = stripQuotes(body);
  const context = cleaned.split("\n").slice(1).filter((l) => l.trim()).join(" ").trim();
  return (
    <div>
      <p className={`text-base ${color} font-bold leading-snug`}>
        {mainQuestion.startsWith('"') ? mainQuestion : `"${mainQuestion}"`}
      </p>
      {context && (
        <p className="text-xs text-text-3 mt-1.5 leading-relaxed line-clamp-2">
          {renderBold(context.slice(0, 150), color)}
        </p>
      )}
    </div>
  );
}

function GeneralContent({ body, color }: { body: string; color: string }) {
  const quotes = extractQuotes(body);
  const cleaned = stripQuotes(body);
  return (
    <div>
      <p className="text-sm text-text-2 leading-relaxed line-clamp-3">
        {renderBold(cleaned.split("\n").slice(0, 3).join(" "), color)}
      </p>
      {quotes[0] && (
        <p className={`text-xs ${color} font-semibold mt-2`}>"{quotes[0]}"</p>
      )}
    </div>
  );
}

const CONTENT_RENDERERS: Record<SuggestionCategory, React.FC<{ body: string; color: string }>> = {
  term: TermContent,
  insight: InsightContent,
  procon: ProConContent,
  pattern: PatternContent,
  question: QuestionContent,
  general: GeneralContent,
};

// ── Main Component ──────────────────────────────────────────────

export default function SuggestionCard({
  category,
  suggestion,
}: {
  category: SuggestionCategory;
  suggestion: Suggestion | null;
}) {
  const cfg = CATEGORY_CONFIG[category];
  const ContentRenderer = CONTENT_RENDERERS[category];

  return (
    <div
      className={`rounded-xl border ${cfg.border} ${cfg.cardBg} px-4 py-3 flex flex-col transition-all min-h-0 overflow-hidden`}
    >
      {/* Category label */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold ${cfg.color} ${cfg.bg}`}
        >
          {cfg.icon}
        </span>
        <span
          className={`text-[10px] font-semibold uppercase tracking-wider ${cfg.color}`}
        >
          {cfg.label}
        </span>
        {suggestion?.streaming && (
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse ml-auto" />
        )}
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        {suggestion ? (
          <motion.div
            key={suggestion.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="flex-1 min-h-0 overflow-y-auto"
          >
            <ContentRenderer body={suggestion.body} color={cfg.color} />
          </motion.div>
        ) : (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.2 }}
            className="flex-1 flex items-center justify-center"
          >
            <span className="text-xs text-text-3">Waiting...</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

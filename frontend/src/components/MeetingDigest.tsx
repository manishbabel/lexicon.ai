import { motion } from "framer-motion";
import { Clock, FileText, RotateCcw } from "lucide-react";
import type { Suggestion, SuggestionCategory, MeetingState } from "../lib/types";

const CATEGORY_CONFIG: Record<
  SuggestionCategory,
  { label: string; color: string; bg: string; border: string }
> = {
  term: { label: "Terms", color: "text-term", bg: "bg-term-muted", border: "border-l-term" },
  insight: { label: "Insights", color: "text-insight", bg: "bg-insight-muted", border: "border-l-insight" },
  procon: { label: "Pros & Cons", color: "text-procon", bg: "bg-procon-muted", border: "border-l-procon" },
  pattern: { label: "Patterns", color: "text-pattern", bg: "bg-pattern-muted", border: "border-l-pattern" },
  question: { label: "Questions", color: "text-question", bg: "bg-question-muted", border: "border-l-question" },
  general: { label: "Notes", color: "text-accent", bg: "bg-accent-muted", border: "border-l-accent" },
};

const CATEGORY_ORDER: SuggestionCategory[] = ["term", "insight", "procon", "pattern", "question", "general"];

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatDate(timestamp: number | null): string {
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface Props {
  suggestions: Suggestion[];
  meeting: MeetingState;
  onNewMeeting: () => void;
}

export default function MeetingDigest({ suggestions, meeting, onNewMeeting }: Props) {
  const grouped = CATEGORY_ORDER.reduce<Partial<Record<SuggestionCategory, Suggestion[]>>>(
    (acc, cat) => {
      const items = suggestions.filter((s) => s.category === cat);
      if (items.length > 0) acc[cat] = items;
      return acc;
    },
    {},
  );

  const categoriesPresent = CATEGORY_ORDER.filter((c) => grouped[c]);

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="space-y-2"
        >
          <h1 className="text-2xl font-bold text-text">
            {meeting.title || "Meeting Digest"}
          </h1>
          <div className="flex items-center gap-4 text-sm text-text-3">
            {meeting.startedAt && (
              <span>{formatDate(meeting.startedAt)}</span>
            )}
            <span className="flex items-center gap-1.5">
              <Clock size={14} />
              {formatDuration(meeting.elapsed)}
            </span>
            <span className="flex items-center gap-1.5">
              <FileText size={14} />
              {suggestions.length} suggestion{suggestions.length !== 1 ? "s" : ""}
            </span>
          </div>
        </motion.div>

        {/* Stats pills */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1, ease: "easeOut" }}
          className="flex flex-wrap gap-2"
        >
          {categoriesPresent.map((cat) => {
            const cfg = CATEGORY_CONFIG[cat];
            const count = grouped[cat]!.length;
            return (
              <span
                key={cat}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${cfg.color} ${cfg.bg}`}
              >
                {cfg.label}
                <span className="opacity-70">{count}</span>
              </span>
            );
          })}
        </motion.div>

        {/* Grouped suggestions */}
        <div className="space-y-6">
          {categoriesPresent.map((cat, groupIdx) => {
            const cfg = CATEGORY_CONFIG[cat];
            const items = grouped[cat]!;
            return (
              <motion.section
                key={cat}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.15 + groupIdx * 0.07, ease: "easeOut" }}
              >
                <h2 className={`text-sm font-semibold uppercase tracking-wider ${cfg.color} mb-3`}>
                  {cfg.label}
                  <span className="text-text-3 ml-2 text-xs font-normal normal-case tracking-normal">
                    ({items.length})
                  </span>
                </h2>
                <div className="space-y-2">
                  {items.map((s) => (
                    <div
                      key={s.id}
                      className={`rounded-lg border-l-3 ${cfg.border} bg-surface px-4 py-3`}
                    >
                      <h3 className={`text-sm font-bold ${cfg.color} leading-snug`}>
                        {s.title}
                      </h3>
                      <p className="text-xs text-text-2 leading-relaxed mt-1 whitespace-pre-line">
                        {s.body}
                      </p>
                    </div>
                  ))}
                </div>
              </motion.section>
            );
          })}
        </div>

        {/* New Meeting button */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.4, ease: "easeOut" }}
          className="pt-4 pb-8"
        >
          <button
            onClick={onNewMeeting}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:brightness-110 transition-all cursor-pointer"
          >
            <RotateCcw size={15} />
            New Meeting
          </button>
        </motion.div>
      </div>
    </div>
  );
}

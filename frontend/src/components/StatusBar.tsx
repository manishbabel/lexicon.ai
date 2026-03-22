import { Mic, MicOff, User, Sparkles, AlertCircle } from "lucide-react";
import type { MeetingState } from "../lib/types";

interface StatusBarProps {
  meeting: MeetingState;
  persona: string;
  isListening: boolean;
  audioLevel?: number;
  audioError?: string | null;
}

/** 5-bar audio level visualizer shown next to the mic icon. */
function AudioLevelBars({ level, active }: { level: number; active: boolean }) {
  const BAR_COUNT = 5;
  // Each bar has a threshold — it "activates" when level exceeds it
  const thresholds = [0.05, 0.15, 0.3, 0.5, 0.7];

  return (
    <span className="inline-flex items-end gap-[2px] h-[10px] ml-0.5">
      {Array.from({ length: BAR_COUNT }, (_, i) => {
        const barActive = active && level > thresholds[i];
        // Height scales from 3px (min) to 10px (max)
        const minH = 3;
        const maxH = 10;
        const height = barActive
          ? Math.max(minH, Math.min(maxH, minH + (maxH - minH) * ((level - thresholds[i]) / (1 - thresholds[i]))))
          : minH;

        return (
          <span
            key={i}
            className="rounded-full transition-all duration-75"
            style={{
              width: 2,
              height: barActive ? height : minH,
              backgroundColor: barActive
                ? "var(--color-success, #22c55e)"
                : "var(--color-text-3, #6b7280)",
              opacity: barActive ? 1 : 0.4,
            }}
          />
        );
      })}
    </span>
  );
}

export default function StatusBar({ meeting, persona, isListening, audioLevel = 0, audioError }: StatusBarProps) {
  return (
    <footer className="flex items-center justify-between px-6 h-10 border-t border-border bg-surface/60 text-[11px] text-text-3 shrink-0">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          {isListening ? (
            <Mic size={11} className="text-success" />
          ) : (
            <MicOff size={11} />
          )}
          <AudioLevelBars level={audioLevel} active={isListening} />
          {isListening ? "Listening" : "Mic off"}
        </span>
        {audioError && (
          <span className="flex items-center gap-1 text-danger">
            <AlertCircle size={11} />
            {audioError}
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <User size={11} />
          {persona}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <Sparkles size={11} />
        {meeting.suggestionCount} suggestions
      </div>
    </footer>
  );
}

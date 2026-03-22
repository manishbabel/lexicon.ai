import { useRef, useEffect } from "react";
import { Mic } from "lucide-react";
import type { TranscriptEntry } from "../lib/types";

function timeStr(ts: number) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Entry({ entry }: { entry: TranscriptEntry }) {
  const isYou = entry.speaker.toLowerCase() === "you";

  return (
    <div className="flex gap-2.5 py-1.5">
      <span className="text-[10px] font-mono text-text-3 w-10 shrink-0 text-right pt-0.5">
        {timeStr(entry.timestamp)}
      </span>
      <div className="min-w-0">
        <span
          className={`text-[11px] font-medium ${isYou ? "text-accent" : "text-text-2"}`}
        >
          {entry.speaker}
        </span>
        <p className="text-xs leading-relaxed text-text-2 mt-0.5">
          {entry.text}
        </p>
      </div>
    </div>
  );
}

export default function Transcript({
  entries,
}: {
  entries: TranscriptEntry[];
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2.5 border-b border-border">
        <h2 className="text-xs font-medium text-text-3 uppercase tracking-widest">
          Transcript
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto px-4">
        {entries.map((e) => (
          <Entry key={e.id} entry={e} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 py-2 border-t border-border flex items-center gap-2">
        <div className="relative">
          <Mic size={12} className="text-success" />
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-success rounded-full animate-pulse" />
        </div>
        <span className="text-[10px] text-text-3">Listening</span>
        <div className="flex-1 flex items-center gap-0.5 ml-2">
          {Array.from({ length: 24 }).map((_, i) => (
            <div
              key={i}
              className="w-0.5 bg-text-3/30 rounded-full"
              style={{
                height: `${3 + Math.random() * 10}px`,
                opacity: 0.3 + Math.random() * 0.5,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

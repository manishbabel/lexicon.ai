import { useEffect, useRef, useState } from "react";
import { Bot, CornerDownLeft, User2 } from "lucide-react";
import type { AgentChatMessage, AgentTarget } from "../lib/types";

const AGENT_OPTIONS: Array<{ id: AgentTarget; label: string }> = [
  { id: "auto", label: "Auto Route" },
  { id: "ai-educator", label: "AI Educator" },
  { id: "software-engineer", label: "Software Engineer" },
  { id: "doctor", label: "Doctor" },
];

const AGENT_LABELS: Record<AgentChatMessage["agent"], string> = {
  auto: "Auto",
  "ai-educator": "AI Educator",
  "software-engineer": "Software Engineer",
  doctor: "Doctor",
  system: "System",
};

interface AgentChatPanelProps {
  messages: AgentChatMessage[];
  isResponding: boolean;
  onSend: (prompt: string, agent: AgentTarget) => void;
}

export default function AgentChatPanel({
  messages,
  isResponding,
  onSend,
}: AgentChatPanelProps) {
  const [draft, setDraft] = useState("");
  const [agent, setAgent] = useState<AgentTarget>("auto");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [isResponding, messages]);

  function submit() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    onSend(trimmed, agent);
    setDraft("");
  }

  return (
    <aside className="flex h-full min-h-0 flex-col bg-surface/70 backdrop-blur-sm">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-text">
              Ask Sub-Agent
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-text-3">
              Auto route sends education prompts to AI Educator and defaults other prompts to the best fit.
            </p>
          </div>
          <select
            value={agent}
            onChange={(e) => setAgent(e.target.value as AgentTarget)}
            className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-text outline-none"
          >
            {AGENT_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="rounded-2xl border border-dashed border-border bg-surface-2/50 p-4 text-sm text-text-3">
            Try: "Design a 6-week AI bootcamp for working adults" or "Turn this workshop into resume-ready projects."
          </div>
        )}

        {messages.map((message) => {
          const isUser = message.role === "user";
          return (
            <div
              key={message.id}
              className={`flex ${isUser ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[92%] rounded-2xl border px-3.5 py-3 ${
                  isUser
                    ? "border-accent/25 bg-accent-muted/20 text-text"
                    : "border-border bg-surface-2 text-text"
                }`}
              >
                <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-3">
                  {isUser ? <User2 size={12} /> : <Bot size={12} />}
                  <span>{isUser ? "You" : AGENT_LABELS[message.agent]}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-2">
                  {message.text}
                </p>
              </div>
            </div>
          );
        })}

        {isResponding && (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-border bg-surface-2 px-3.5 py-3 text-sm text-text-3">
              <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em]">
                <Bot size={12} />
                <span>Thinking</span>
              </div>
              <div className="flex gap-1">
                <span className="h-2 w-2 animate-pulse rounded-full bg-text-3" />
                <span className="h-2 w-2 animate-pulse rounded-full bg-text-3 [animation-delay:200ms]" />
                <span className="h-2 w-2 animate-pulse rounded-full bg-text-3 [animation-delay:400ms]" />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-border px-4 py-3">
        <div className="rounded-2xl border border-border bg-surface p-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={4}
            placeholder="Give a direct instruction to a sub-agent..."
            className="w-full resize-none bg-transparent px-2 py-1 text-sm leading-relaxed text-text outline-none placeholder:text-text-3"
          />
          <div className="mt-2 flex items-center justify-between gap-3 px-2 pb-1">
            <span className="text-[11px] text-text-3">
              Enter to send, Shift+Enter for newline
            </span>
            <button
              onClick={submit}
              disabled={!draft.trim() || isResponding}
              className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
              <CornerDownLeft size={12} />
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

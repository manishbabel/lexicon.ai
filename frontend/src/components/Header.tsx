import { useState, useRef, useEffect } from "react";
import { Play, Pause, Square, Clock, Settings, ChevronDown, Sun, Moon } from "lucide-react";
import type { MeetingState } from "../lib/types";
import type { Persona } from "../hooks/usePersona";
import { useTheme } from "../hooks/useTheme";

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

interface HeaderProps {
  meeting: MeetingState;
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
  onOpenSettings?: () => void;
  persona: Persona;
  availablePersonas: Persona[];
  onPersonaChange: (id: string) => void;
}

export default function Header({ meeting, onStart, onPause, onStop, onOpenSettings, persona, availablePersonas, onPersonaChange }: HeaderProps) {
  const isActive = meeting.status === "active";
  const isIdle = meeting.status === "idle" || meeting.status === "ended";
  const isPaused = meeting.status === "paused";
  const { theme, toggle: toggleTheme } = useTheme();
  const [personaOpen, setPersonaOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setPersonaOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="flex items-center justify-between px-6 h-14 border-b border-border bg-surface/80 backdrop-blur-sm shrink-0">
      <div className="flex items-center gap-3">
        <div
          className={`w-2 h-2 rounded-full ${
            isActive ? "bg-accent animate-pulse" : "bg-text-3/30"
          }`}
        />
        <span className="text-sm font-medium tracking-tight text-text">
          Lexicon
        </span>
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => isIdle && setPersonaOpen((o) => !o)}
            disabled={!isIdle}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border border-border transition-colors ${
              isIdle
                ? "text-text-2 hover:text-text hover:bg-surface-2 cursor-pointer"
                : "text-text-3/50 cursor-not-allowed"
            }`}
          >
            {persona.label}
            {isIdle && <ChevronDown size={12} className={`transition-transform ${personaOpen ? "rotate-180" : ""}`} />}
          </button>
          {personaOpen && (
            <div className="absolute top-full left-0 mt-1 py-1 min-w-40 rounded-lg border border-border bg-surface shadow-lg z-50">
              {availablePersonas.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    onPersonaChange(p.id);
                    setPersonaOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 text-xs transition-colors cursor-pointer ${
                    p.id === persona.id
                      ? "text-accent font-medium bg-surface-2"
                      : "text-text-2 hover:text-text hover:bg-surface-2"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {(isActive || isPaused) && (
          <span className="text-xs text-text-3 font-mono flex items-center gap-1.5">
            <Clock size={12} />
            {formatTime(meeting.elapsed)}
          </span>
        )}
        <span className="text-sm text-text-2 max-w-64 truncate">
          {meeting.title || "New Meeting"}
        </span>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-2 transition-colors cursor-pointer"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        </button>
        {onOpenSettings && isIdle && (
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-2 transition-colors cursor-pointer"
          >
            <Settings size={14} />
          </button>
        )}
        {isIdle && (
          <button
            onClick={onStart}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:bg-accent/90 transition-colors cursor-pointer"
          >
            Start Meeting
          </button>
        )}
        {isActive && (
          <>
            <button
              onClick={onPause}
              className="p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <Pause size={14} />
            </button>
            <button
              onClick={onStop}
              className="p-2 rounded-lg text-danger hover:text-danger hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <Square size={14} />
            </button>
          </>
        )}
        {isPaused && (
          <>
            <button
              onClick={onStart}
              className="p-2 rounded-lg text-text-3 hover:text-text hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <Play size={14} />
            </button>
            <button
              onClick={onStop}
              className="p-2 rounded-lg text-danger hover:text-danger hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <Square size={14} />
            </button>
          </>
        )}
      </div>
    </header>
  );
}

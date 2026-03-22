/**
 * Pre-meeting prep screen.
 *
 * User enters agenda, topics, attendees before starting.
 * Sends to gateway so the agent pre-loads relevant context.
 */

import { useState } from "react";
import { Loader2, CheckCircle2, Zap } from "lucide-react";
import type { MeetingPrepData } from "../lib/types";
import type { PrepResult } from "../hooks/useMeeting";

interface MeetingPrepProps {
  isPreparing: boolean;
  prepResult: PrepResult | null;
  onPrepare: (data: MeetingPrepData) => void;
  onStart: () => void;
}

export default function MeetingPrep({
  isPreparing,
  prepResult,
  onPrepare,
  onStart,
}: MeetingPrepProps) {
  const [title, setTitle] = useState("");
  const [agenda, setAgenda] = useState("");
  const [topicsInput, setTopicsInput] = useState("");
  const [attendeesInput, setAttendeesInput] = useState("");
  const [notes, setNotes] = useState("");

  function handlePrepare() {
    onPrepare({
      title,
      agenda,
      topics: topicsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      attendees: attendeesInput
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean),
      notes,
    });
  }

  return (
    <div className="flex-1 flex items-center justify-center px-6">
      <div className="w-full max-w-lg">
        <h1 className="text-2xl font-bold text-text tracking-tight mb-1">
          Meeting Prep
        </h1>
        <p className="text-sm text-text-3 mb-8">
          Give context so Lexicon is ready from minute one.
        </p>

        <div className="flex flex-col gap-4">
          {/* Title */}
          <div>
            <label className="text-xs font-medium text-text-2 mb-1.5 block">
              Meeting title
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="System Design Review"
              className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-3/50 focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          {/* Agenda */}
          <div>
            <label className="text-xs font-medium text-text-2 mb-1.5 block">
              Agenda
            </label>
            <textarea
              value={agenda}
              onChange={(e) => setAgenda(e.target.value)}
              placeholder="Discuss event sourcing vs CRUD for the ingestion pipeline..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-3/50 focus:outline-none focus:border-accent transition-colors resize-none"
            />
          </div>

          {/* Topics */}
          <div>
            <label className="text-xs font-medium text-text-2 mb-1.5 block">
              Topics
              <span className="text-text-3 font-normal ml-1">comma separated</span>
            </label>
            <input
              value={topicsInput}
              onChange={(e) => setTopicsInput(e.target.value)}
              placeholder="event sourcing, CQRS, schema migration"
              className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-3/50 focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          {/* Attendees */}
          <div>
            <label className="text-xs font-medium text-text-2 mb-1.5 block">
              Attendees
              <span className="text-text-3 font-normal ml-1">comma separated</span>
            </label>
            <input
              value={attendeesInput}
              onChange={(e) => setAttendeesInput(e.target.value)}
              placeholder="Priya, Alex, Jordan"
              className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-3/50 focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          {/* Notes */}
          <div>
            <label className="text-xs font-medium text-text-2 mb-1.5 block">
              Notes
              <span className="text-text-3 font-normal ml-1">optional</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Priya is skeptical about event sourcing, Alex prefers simpler approaches..."
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-sm text-text placeholder:text-text-3/50 focus:outline-none focus:border-accent transition-colors resize-none"
            />
          </div>
        </div>

        {/* Prep result */}
        {prepResult && (
          <div className="mt-6 px-4 py-3 rounded-lg bg-term-muted border border-term/20">
            <div className="flex items-center gap-2 mb-1.5">
              <CheckCircle2 size={14} className="text-term" />
              <span className="text-xs font-medium text-term">Ready</span>
            </div>
            <p className="text-xs text-text-2 leading-relaxed">
              {prepResult.summary ||
                `Loaded ${prepResult.termsLoaded} terms and ${prepResult.memoriesLoaded} memories.`}
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 mt-6">
          <button
            onClick={handlePrepare}
            disabled={isPreparing}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-surface-2 text-text hover:bg-surface-3 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-default"
          >
            {isPreparing ? (
              <span className="flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Preparing...
              </span>
            ) : (
              "Prepare"
            )}
          </button>

          <button
            onClick={onStart}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors cursor-pointer flex items-center gap-2"
          >
            <Zap size={14} />
            Start Meeting
          </button>
        </div>

        <p className="text-[10px] text-text-3 mt-3">
          You can skip prep and start directly — Lexicon adapts as the conversation flows.
        </p>
      </div>
    </div>
  );
}

/**
 * Orchestrator hook — ties WebSocket, audio capture, and UI state together.
 *
 * This is the single hook Meeting.tsx calls. It manages:
 * - Meeting lifecycle (start/pause/stop)
 * - Audio capture → Deepgram → transcript → gateway
 * - Incoming suggestions from gateway → UI state
 * - Elapsed time counter
 */

import { useState, useEffect, useRef, useCallback } from "react";
import type { MeetingState, Suggestion } from "../lib/types";
import type { Promptline, MeetingPrepData } from "../lib/types";
import type { AgentChatMessage, AgentTarget } from "../lib/types";
import type { WSMessage } from "../lib/wsClient";
import { useWS } from "../components/WebSocketProvider";
import { useAudioCapture } from "./useAudioCapture";

export interface PrepResult {
  termsLoaded: number;
  memoriesLoaded: number;
  summary: string;
}

export interface UseMeetingReturn {
  meeting: MeetingState;
  suggestions: Suggestion[];
  agentChat: AgentChatMessage[];
  promptlines: Promptline[];
  prepResult: PrepResult | null;
  wsStatus: string;
  audioError: string | null;
  isListening: boolean;
  audioLevel: number;
  isAgentResponding: boolean;
  prepare: (data: MeetingPrepData) => void;
  start: () => Promise<void>;
  pause: () => void;
  stop: () => void;
  sendAgentPrompt: (prompt: string, agent?: AgentTarget, context?: string) => void;
}

let suggestionCounter = 0;
let agentRequestCounter = 0;

export function useMeeting(): UseMeetingReturn {
  const ws = useWS();
  const audio = useAudioCapture();

  const [meeting, setMeeting] = useState<MeetingState>({
    status: "idle",
    title: "",
    startedAt: null,
    elapsed: 0,
    suggestionCount: 0,
    termsUsed: 0,
  });

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [agentChat, setAgentChat] = useState<AgentChatMessage[]>([]);
  const [promptlines, setPromptlines] = useState<Promptline[]>([]);
  const [prepResult, setPrepResult] = useState<PrepResult | null>(null);
  const [pendingAgentRequests, setPendingAgentRequests] = useState<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamingRef = useRef<Map<string, Suggestion>>(new Map());

  // ── Elapsed timer ──────────────────────────────────────────

  useEffect(() => {
    if (meeting.status === "active" && meeting.startedAt) {
      timerRef.current = setInterval(() => {
        setMeeting((prev) => ({
          ...prev,
          elapsed: Math.floor((Date.now() - (prev.startedAt ?? Date.now())) / 1000),
        }));
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [meeting.status, meeting.startedAt]);

  // ── Subscribe to server messages ───────────────────────────

  useEffect(() => {
    // Meeting state updates
    const unsubState = ws.on("meeting.state", (msg: WSMessage) => {
      const status = msg.status as string;
      setMeeting((prev) => ({
        ...prev,
        status: status as MeetingState["status"],
      }));
    });

    // Streaming suggestion deltas
    const unsubStream = ws.on("suggestion.stream", (msg: WSMessage) => {
      const id = msg.suggestion_id as string;
      const delta = (msg.delta as string) ?? "";
      const done = (msg.done as boolean) ?? false;
      const category = (msg.category as string) ?? "general";

      if (!streamingRef.current.has(id)) {
        // New suggestion — create it
        streamingRef.current.set(id, {
          id,
          category: category as Suggestion["category"],
          title: "",
          body: "",
          streaming: true,
          timestamp: Date.now(),
        });
      }

      const s = streamingRef.current.get(id)!;
      s.body += delta;
      // Update category as server refines it from accumulated text
      if (category && category !== "general") {
        s.category = category as Suggestion["category"];
      }

      if (done) {
        s.streaming = false;
        // Extract title from first line if not set
        if (!s.title && s.body) {
          const firstLine = s.body.split("\n")[0];
          s.title = firstLine.slice(0, 80);
          s.body = s.body.slice(firstLine.length).trim();
        }
        streamingRef.current.delete(id);
      }

      // Update suggestions state
      setSuggestions((prev) => {
        const idx = prev.findIndex((x) => x.id === id);
        const updated = idx >= 0 ? [...prev] : [...prev, { ...s }];
        if (idx >= 0) updated[idx] = { ...s };

        // Update suggestion count from the new array length
        setMeeting((m) => ({ ...m, suggestionCount: updated.length }));
        return updated;
      });
    });

    // Term suggestions (structured)
    const unsubTerm = ws.on("term.suggest", (msg: WSMessage) => {
      const suggestion: Suggestion = {
        id: (msg.term_id as string) ?? `term-${++suggestionCounter}`,
        category: "term",
        title: msg.term as string,
        body: msg.definition as string,
        sentence: msg.use_in_sentence as string | undefined,
        streaming: false,
        timestamp: Date.now(),
      };

      setSuggestions((prev) => [...prev, suggestion]);
    });

    // Meeting prepared response
    const unsubPrep = ws.on("meeting.prepared" as any, (msg: WSMessage) => {
      setPrepResult({
        termsLoaded: (msg.terms_loaded as number) ?? 0,
        memoriesLoaded: (msg.memories_loaded as number) ?? 0,
        summary: (msg.summary as string) ?? "",
      });
      setMeeting((prev) => ({ ...prev, status: "idle" }));
    });

    const unsubAgentReply = ws.on("agent.reply" as any, (msg: WSMessage) => {
      const requestId = (msg.request_id as string) ?? "";
      const routedAgent = ((msg.routed_agent as string) ?? "auto") as AgentTarget;
      const response = (msg.response as string) ?? "";

      setAgentChat((prev) => [
        ...prev,
        {
          id: `${requestId || `reply-${Date.now()}`}-assistant`,
          role: "assistant",
          text: response,
          agent: routedAgent,
          requestId,
        },
      ]);

      if (requestId) {
        setPendingAgentRequests((prev) => prev.filter((id) => id !== requestId));
      }
    });

    // Agent errors
    const unsubError = ws.on("error" as any, (msg: WSMessage) => {
      const detail = (msg.detail as string) ?? "Unknown error";
      console.error("[Lexicon] Agent error:", msg.code, detail);

      const code = (msg.code as string) ?? "";
      if (pendingAgentRequests.length > 0 && (
        code === "bad_agent_prompt" ||
        code === "no_orchestrator" ||
        code === "agent_error"
      )) {
        const requestId = pendingAgentRequests[0];
        setPendingAgentRequests((prev) => prev.filter((id) => id !== requestId));
        setAgentChat((prev) => [
          ...prev,
          {
            id: `${requestId}-error`,
            role: "assistant",
            text: detail,
            agent: "system",
            requestId,
          },
        ]);
      }
    });

    // Promptline updates
    const unsubPrompt = ws.on("*", (msg: WSMessage) => {
      if (msg.type === "promptline.update") {
        const lines = msg.lines as Promptline[] | undefined;
        if (lines) setPromptlines(lines);
      }
    });

    return () => {
      unsubState();
      unsubStream();
      unsubTerm();
      unsubPrep();
      unsubAgentReply();
      unsubError();
      unsubPrompt();
    };
  }, [pendingAgentRequests, ws]);

  // ── Meeting controls ───────────────────────────────────────

  const prepare = useCallback(
    (data: MeetingPrepData) => {
      ws.connect();
      setMeeting((prev) => ({
        ...prev,
        status: "preparing",
        title: data.title || prev.title,
      }));
      setPrepResult(null);

      setTimeout(() => {
        ws.send("meeting.prepare", {
          agenda: data.agenda,
          topics: data.topics,
          attendees: data.attendees,
          notes: data.notes,
        });
      }, 500);
    },
    [ws],
  );

  const start = useCallback(
    async () => {
      // 1. Fetch Deepgram key from backend
      let deepgramKey = "";
      try {
        const resp = await fetch("/api/deepgram-key");
        const data = await resp.json();
        deepgramKey = data.key || "";
      } catch {
        // Continue without audio if key fetch fails
      }

      // 2. Open WebSocket
      ws.connect();

      // 3. Update local state
      setMeeting((prev) => ({
        ...prev,
        status: "active",
        startedAt: Date.now(),
        elapsed: 0,
        title: prev.title || "Meeting",
      }));

      // 4. Send start command (small delay for WS to connect)
      setTimeout(() => {
        ws.send("meeting.control", { action: "start" });
      }, 500);

      // 5. Start audio capture → Deepgram → transcript → gateway
      if (deepgramKey) {
        await audio.start(deepgramKey, (result) => {
          if (result.isFinal) {
            ws.send("transcript.chunk", {
              text: result.text,
              is_final: true,
              speaker: result.speaker,
            });
          }
        });
      }
    },
    [ws, audio],
  );

  const pause = useCallback(() => {
    ws.send("meeting.control", { action: "pause" });
    audio.stop();
    setMeeting((prev) => ({ ...prev, status: "paused" }));
  }, [ws, audio]);

  const stop = useCallback(() => {
    audio.stop();
    ws.send("meeting.control", { action: "stop" });

    // Small delay to let the stop message send before disconnecting
    setTimeout(() => {
      ws.disconnect();
    }, 300);

    setMeeting((prev) => ({ ...prev, status: "ended" }));
  }, [ws, audio]);

  const sendAgentPrompt = useCallback(
    (prompt: string, agent: AgentTarget = "auto", context = "") => {
      const trimmed = prompt.trim();
      if (!trimmed) return;

      const requestId = `agent-${Date.now()}-${++agentRequestCounter}`;
      setAgentChat((prev) => [
        ...prev,
        {
          id: `${requestId}-user`,
          role: "user",
          text: trimmed,
          agent,
          requestId,
        },
      ]);
      setPendingAgentRequests((prev) => [...prev, requestId]);

      const send = () => {
        ws.send("agent.prompt", {
          request_id: requestId,
          prompt: trimmed,
          agent,
          context,
        });
      };

      if (ws.status !== "connected") {
        ws.connect();
        setTimeout(send, 400);
        return;
      }

      send();
    },
    [ws],
  );

  return {
    meeting,
    suggestions,
    agentChat,
    promptlines,
    prepResult,
    wsStatus: ws.status,
    audioError: audio.error,
    isListening: audio.isListening,
    audioLevel: audio.audioLevel,
    isAgentResponding: pendingAgentRequests.length > 0,
    prepare,
    start,
    pause,
    stop,
    sendAgentPrompt,
  };
}

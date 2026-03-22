export type SuggestionCategory =
  | "term"
  | "insight"
  | "procon"
  | "pattern"
  | "question"
  | "general";

export interface Suggestion {
  id: string;
  category: SuggestionCategory;
  title: string;
  body: string;
  sentence?: string;
  streaming: boolean;
  timestamp: number;
  feedback?: "up" | "down";
}

export type AgentTarget = "auto" | "software-engineer" | "ai-educator" | "doctor";

export interface AgentChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  agent: AgentTarget | "system";
  requestId?: string;
}

export interface TranscriptEntry {
  id: string;
  speaker: string;
  text: string;
  timestamp: number;
  isFinal: boolean;
}

export interface Promptline {
  id: string;
  text: string;
  context: string;
  active: boolean;
  used: boolean;
}

export interface MeetingPrepData {
  title: string;
  agenda: string;
  topics: string[];
  attendees: string[];
  notes: string;
}

export type MeetingStatus = "idle" | "preparing" | "active" | "paused" | "ended";

export interface MeetingState {
  status: MeetingStatus;
  title: string;
  startedAt: number | null;
  elapsed: number;
  suggestionCount: number;
  termsUsed: number;
}

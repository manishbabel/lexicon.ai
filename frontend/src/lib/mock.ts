import type { Suggestion, TranscriptEntry } from "./types";

let _id = 0;
const id = () => `mock-${++_id}`;

export const MOCK_TRANSCRIPT: TranscriptEntry[] = [
  {
    id: id(),
    speaker: "You",
    text: "So for the ingestion pipeline, I think we should consider event sourcing instead of the traditional CRUD approach.",
    timestamp: Date.now() - 180_000,
    isFinal: true,
  },
  {
    id: id(),
    speaker: "Priya",
    text: "That's interesting. How would we handle schema migrations with event sourcing though?",
    timestamp: Date.now() - 120_000,
    isFinal: true,
  },
  {
    id: id(),
    speaker: "You",
    text: "Good point. We'd need event versioning — maybe upcasters or a weak schema approach.",
    timestamp: Date.now() - 90_000,
    isFinal: true,
  },
  {
    id: id(),
    speaker: "Alex",
    text: "What about the read side? Do we need CQRS as well, or can we keep it simpler?",
    timestamp: Date.now() - 45_000,
    isFinal: true,
  },
  {
    id: id(),
    speaker: "You",
    text: "I think we could start with a single read model and add projections later if we need them.",
    timestamp: Date.now() - 15_000,
    isFinal: true,
  },
];

export interface Promptline {
  id: string;
  text: string; // with **bold** markers around key terms
  context: string; // why this line is suggested
  active: boolean;
  used: boolean;
}

export const MOCK_PROMPTLINES: Promptline[] = [
  {
    id: id(),
    text: "With **event sourcing**, every state change is stored as an **immutable event** — so we get a full **audit trail** for free.",
    context: "Responding to Priya's question",
    active: true,
    used: false,
  },
  {
    id: id(),
    text: "For **schema evolution**, we can use **upcasters** that transform old events to the new format on read — no need to migrate historical data.",
    context: "Addressing migration concern",
    active: false,
    used: false,
  },
  {
    id: id(),
    text: "We don't necessarily need full **CQRS** right away. We can start with a **single read model** and add **projections** when query patterns diverge.",
    context: "Answering Alex's CQRS question",
    active: false,
    used: false,
  },
  {
    id: id(),
    text: "The key advantage is **temporal queries** — we can reconstruct the system state at **any point in time**, which is critical for debugging production issues.",
    context: "Reinforcing the case for event sourcing",
    active: false,
    used: false,
  },
];

export const MOCK_SUGGESTIONS: Suggestion[] = [
  {
    id: id(),
    category: "term",
    title: "Event Sourcing",
    body: "Stores state changes as an immutable sequence of events rather than mutating current state directly. Enables complete audit trails and temporal queries.",
    sentence:
      "Event sourcing gives us a complete audit trail and lets us rebuild state at any point in time.",
    streaming: false,
    timestamp: Date.now() - 170_000,
  },
  {
    id: id(),
    category: "insight",
    title: "Event Versioning Strategies",
    body: "Three approaches when schemas evolve:\n\n1. Upcasters — transform old events to new format on read\n2. Weak schema — use flexible payloads (JSON) that tolerate missing fields\n3. Event migration — batch rewrite historical events (risky, use sparingly)",
    streaming: false,
    timestamp: Date.now() - 80_000,
  },
  {
    id: id(),
    category: "procon",
    title: "Event Sourcing vs CRUD",
    body: "Pros:\n• Full audit trail\n• Temporal queries\n• Natural fit for event-driven architectures\n\nCons:\n• Higher complexity\n• Event versioning overhead\n• Eventual consistency challenges",
    streaming: false,
    timestamp: Date.now() - 60_000,
  },
  {
    id: id(),
    category: "term",
    title: "CQRS",
    body: "Command Query Responsibility Segregation — separates read and write models. Write side optimized for consistency, read side optimized for query patterns.",
    sentence:
      "We could apply CQRS to separate our write-optimized event store from read-optimized query views.",
    streaming: false,
    timestamp: Date.now() - 40_000,
  },
  {
    id: id(),
    category: "question",
    title: "Ask about projections",
    body: "What's our strategy for replaying events if we need to add a new read model six months from now?",
    streaming: true,
    timestamp: Date.now() - 10_000,
  },
];

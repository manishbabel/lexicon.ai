/**
 * WebSocket client for Lexicon gateway.
 *
 * Opens a single connection per meeting. Sends/receives typed JSON messages.
 * Auto-reconnects on disconnect with exponential backoff.
 */

// ── Message types (mirrors gateway/protocol.py) ────────────────

export type ConnectionStatus = "disconnected" | "connecting" | "connected";

/** All message types the server can send us */
export type ServerMessageType =
  | "connected"
  | "suggestion.stream"
  | "term.suggest"
  | "transcript.ack"
  | "meeting.state"
  | "meeting.prepared"
  | "agent.reply"
  | "error";

/** All message types we can send to the server */
export type ClientMessageType =
  | "connect"
  | "transcript.chunk"
  | "persona.select"
  | "meeting.control"
  | "meeting.prepare"
  | "agent.prompt"
  | "memory.query"
  | "term.feedback";

export interface WSMessage {
  type: string;
  [key: string]: unknown;
}

type MessageHandler = (data: WSMessage) => void;
type StatusHandler = (status: ConnectionStatus) => void;

// ── Config ─────────────────────────────────────────────────────

const DEFAULT_URL = `ws://${window.location.hostname}:18800/ws`;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

// ── Client ─────────────────────────────────────────────────────

export interface WSClient {
  connect: (url?: string) => void;
  disconnect: () => void;
  send: (type: ClientMessageType, payload?: Record<string, unknown>) => void;
  on: (type: ServerMessageType | "*", handler: MessageHandler) => () => void;
  onStatus: (handler: StatusHandler) => () => void;
  status: () => ConnectionStatus;
}

export function createWSClient(): WSClient {
  let ws: WebSocket | null = null;
  let currentStatus: ConnectionStatus = "disconnected";
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let intentionalClose = false;
  let wsUrl = DEFAULT_URL;

  // Event listeners
  const messageHandlers = new Map<string, Set<MessageHandler>>();
  const statusHandlers = new Set<StatusHandler>();

  // ── Internal helpers ───────────────────────────────────────

  function setStatus(s: ConnectionStatus) {
    currentStatus = s;
    statusHandlers.forEach((h) => h(s));
  }

  function emit(msg: WSMessage) {
    // Specific type handlers
    const handlers = messageHandlers.get(msg.type);
    if (handlers) handlers.forEach((h) => h(msg));

    // Wildcard handlers
    const wildcard = messageHandlers.get("*");
    if (wildcard) wildcard.forEach((h) => h(msg));
  }

  function scheduleReconnect() {
    if (intentionalClose) return;

    const delay = Math.min(
      RECONNECT_BASE_MS * 2 ** reconnectAttempts,
      RECONNECT_MAX_MS,
    );
    reconnectAttempts++;

    reconnectTimer = setTimeout(() => {
      connect(wsUrl);
    }, delay);
  }

  // ── Public API ─────────────────────────────────────────────

  function connect(url?: string) {
    if (url) wsUrl = url;
    intentionalClose = false;

    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus("connecting");

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectAttempts = 0;
      setStatus("connected");

      // Send initial handshake
      send("connect", { persona: "software-engineer" });
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        emit(msg);
      } catch {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      ws = null;
      setStatus("disconnected");
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after this, which handles reconnect
    };
  }

  function disconnect() {
    intentionalClose = true;

    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    if (ws) {
      ws.close();
      ws = null;
    }

    setStatus("disconnected");
  }

  function send(type: ClientMessageType, payload: Record<string, unknown> = {}) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type, ...payload }));
  }

  function on(type: ServerMessageType | "*", handler: MessageHandler): () => void {
    if (!messageHandlers.has(type)) {
      messageHandlers.set(type, new Set());
    }
    messageHandlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      messageHandlers.get(type)?.delete(handler);
    };
  }

  function onStatus(handler: StatusHandler): () => void {
    statusHandlers.add(handler);
    return () => {
      statusHandlers.delete(handler);
    };
  }

  return {
    connect,
    disconnect,
    send,
    on,
    onStatus,
    status: () => currentStatus,
  };
}

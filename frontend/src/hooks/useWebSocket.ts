/**
 * React hook wrapping wsClient.ts.
 *
 * Creates a single WS client instance per component lifecycle.
 * Components get reactive connection status + send/subscribe API.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import {
  createWSClient,
  type WSClient,
  type ConnectionStatus,
  type WSMessage,
  type ServerMessageType,
  type ClientMessageType,
} from "../lib/wsClient";

export interface UseWebSocketReturn {
  status: ConnectionStatus;
  connect: (url?: string) => void;
  disconnect: () => void;
  send: (type: ClientMessageType, payload?: Record<string, unknown>) => void;
  on: (type: ServerMessageType | "*", handler: (data: WSMessage) => void) => () => void;
}

export function useWebSocket(): UseWebSocketReturn {
  const clientRef = useRef<WSClient | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");

  useEffect(() => {
    const client = createWSClient();
    clientRef.current = client;

    const unsub = client.onStatus(setStatus);

    return () => {
      unsub();
      client.disconnect();
      clientRef.current = null;
    };
  }, []);

  const connect = useCallback((url?: string) => {
    clientRef.current?.connect(url);
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  const send = useCallback(
    (type: ClientMessageType, payload?: Record<string, unknown>) => {
      clientRef.current?.send(type, payload);
    },
    [],
  );

  const on = useCallback(
    (type: ServerMessageType | "*", handler: (data: WSMessage) => void) => {
      return clientRef.current?.on(type, handler) ?? (() => {});
    },
    [],
  );

  return { status, connect, disconnect, send, on };
}

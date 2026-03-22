/**
 * React context provider for WebSocket access.
 *
 * Wrap your app (or Meeting page) with this. Any nested component
 * can then call useWS() to send messages or subscribe to events
 * without prop drilling.
 */

import { createContext, useContext, type ReactNode } from "react";
import { useWebSocket, type UseWebSocketReturn } from "../hooks/useWebSocket";

const WSContext = createContext<UseWebSocketReturn | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const ws = useWebSocket();
  return <WSContext.Provider value={ws}>{children}</WSContext.Provider>;
}

/**
 * Access the shared WebSocket client from any component.
 * Must be inside a <WebSocketProvider>.
 */
export function useWS(): UseWebSocketReturn {
  const ctx = useContext(WSContext);
  if (!ctx) {
    throw new Error("useWS() must be used within <WebSocketProvider>");
  }
  return ctx;
}

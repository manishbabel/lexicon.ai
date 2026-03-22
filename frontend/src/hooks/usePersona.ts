/**
 * Manages active persona and switching between personas.
 */

import { useState, useCallback, useEffect } from "react";
import { useWS } from "../components/WebSocketProvider";

export interface Persona {
  id: string;
  label: string;
}

const AVAILABLE_PERSONAS: Persona[] = [
  { id: "software-engineer", label: "Software Engineer" },
  { id: "ai-educator", label: "AI Educator" },
  { id: "doctor", label: "Doctor" },
  { id: "chief", label: "Chief" },
];

export interface UsePersonaReturn {
  persona: Persona;
  available: Persona[];
  switchPersona: (id: string) => void;
}

export function usePersona(): UsePersonaReturn {
  const ws = useWS();
  const [current, setCurrent] = useState<Persona>(AVAILABLE_PERSONAS[0]);

  // Listen for server-side persona confirmations
  useEffect(() => {
    const unsub = ws.on("connected", (msg) => {
      const id = msg.persona as string | undefined;
      if (id) {
        const match = AVAILABLE_PERSONAS.find((p) => p.id === id);
        if (match) setCurrent(match);
      }
    });
    return unsub;
  }, [ws]);

  const switchPersona = useCallback(
    (id: string) => {
      const match = AVAILABLE_PERSONAS.find((p) => p.id === id);
      if (!match) return;

      ws.send("persona.select", { persona: id });
      setCurrent(match);
    },
    [ws],
  );

  return {
    persona: current,
    available: AVAILABLE_PERSONAS,
    switchPersona,
  };
}

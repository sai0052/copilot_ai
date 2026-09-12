import { useEffect, useRef, useState } from "react";
import { apiBase } from "../services/api";
import type { AgentEvent } from "../types";

export function useAgentEvents(taskId: number | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setEvents([]);
    if (!taskId) {
      return;
    }
    const source = new EventSource(`${apiBase()}/api/agent/tasks/${taskId}/events`);
    sourceRef.current = source;
    source.onmessage = (message) => {
      try {
        const parsed = JSON.parse(message.data) as AgentEvent;
        setEvents((current) => [...current, parsed]);
      } catch {
        /* ignore malformed frames */
      }
    };
    source.onerror = () => {
      source.close();
    };
    return () => {
      source.close();
    };
  }, [taskId]);

  return events;
}

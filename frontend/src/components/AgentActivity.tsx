import type { AgentEvent } from "../types";

function tone(event: string): "ok" | "warn" | "bad" | "run" {
  if (
    event.includes("fail") ||
    event === "rate_limit_exhausted" ||
    event === "agent_cancelled" ||
    event === "agent_limit_reached" ||
    event === "limit_reached" ||
    event === "agent_timeout" ||
    event === "timeout_reached"
  ) {
    return "bad";
  }
  if (event.startsWith("rate_limit") || event.includes("retry") || event.includes("waiting")) return "warn";
  if (event.includes("complet") || event === "llm_retry_succeeded" || event === "agent_resumed") return "ok";
  return "run";
}

function looksTechnical(text: string | undefined): boolean {
  const value = (text || "").trim();
  return value.startsWith("{") || value.startsWith("[") || /"error"\s*:/.test(value);
}

export function activityLines(event: AgentEvent): { title: string; detail?: string } {
  const payload = event.payload || {};
  const wait = payload.wait_seconds;
  const waitLabel = typeof wait === "number" ? `Waiting ${Math.max(1, Math.round(Number(wait)))} seconds before retry...` : undefined;
  const attempt = payload.attempt;
  const maxAttempts = payload.max_attempts;

  switch (event.event) {
    case "rate_limit_reached":
      return { title: "Rate limit reached", detail: waitLabel || event.message };
    case "rate_limit_waiting":
      return { title: waitLabel || event.message || "Waiting before retry..." };
    case "llm_retrying":
      return {
        title: "Retrying LLM request",
        detail: typeof attempt === "number" && typeof maxAttempts === "number" ? `Attempt ${attempt}/${maxAttempts}` : event.message,
      };
    case "llm_retry_succeeded":
      return { title: "LLM request recovered" };
    case "rate_limit_exhausted":
      return { title: "LLM rate limit exceeded", detail: "Please wait and try again." };
    default:
      if (looksTechnical(event.message)) {
        return { title: "LLM request failed", detail: "See technical details" };
      }
      return { title: event.message };
  }
}

function mergeRateLimitEvents(events: AgentEvent[]): AgentEvent[] {
  const merged: AgentEvent[] = [];
  for (const event of events) {
    const previous = merged[merged.length - 1];
    if (event.event === "rate_limit_waiting" && previous?.event === "rate_limit_reached") {
      previous.payload = { ...(previous.payload || {}), ...(event.payload || {}) };
      if (!previous.message || previous.message === "Rate limit reached") {
        previous.message = event.message;
      }
      continue;
    }
    merged.push({ ...event, payload: { ...(event.payload || {}) } });
  }
  return merged;
}

export function AgentActivity({ events }: { events: AgentEvent[] }) {
  const waiting = events.some((item) => item.event === "rate_limit_waiting" || item.event === "llm_retrying");
  const resolved = events.some((item) =>
    ["llm_retry_succeeded", "rate_limit_exhausted", "agent_completed", "agent_failed", "agent_cancelled", "agent_limit_reached", "agent_timeout"].includes(
      item.event,
    ),
  );
  return (
    <section className="panel">
      <h2>Agent Activity</h2>
      {waiting && !resolved ? (
        <div className="retry-banner" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          Rate limited — waiting to retry. Cancel remains available.
        </div>
      ) : null}
      {events.length === 0 ? (
        <div className="empty">No Agent Activity Yet. Run an AI task to see activity here.</div>
      ) : (
        <ul className="activity">
          {mergeRateLimitEvents(events).map((event, index) => {
            const line = activityLines(event);
            const technical = looksTechnical(event.message) ? event.message : undefined;
            return (
              <li key={`${event.event}-${index}`}>
                <span className={`dot ${tone(event.event)}`} />
                <div>
                  <div>{line.title}</div>
                  {line.detail ? <div className="muted">{line.detail}</div> : null}
                  {technical ? (
                    <details className="muted">
                      <summary>Technical details</summary>
                      <pre>{technical}</pre>
                    </details>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

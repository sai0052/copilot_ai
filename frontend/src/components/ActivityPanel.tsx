import type { AgentEvent } from "../types";

interface Props {
  events: AgentEvent[];
  plan: unknown[];
  terminalLines: string[];
  changedFiles: string[];
}

export function ActivityPanel({ events, plan, terminalLines, changedFiles }: Props) {
  return (
    <section className="grid-2">
      <div className="card">
        <h2>Agent Activity</h2>
        <ul className="activity">
          {events.length === 0 ? <li className="muted">Waiting for the agent...</li> : null}
          {events.map((event, index) => (
            <li key={`${event.event}-${index}`}>
              <span className="dot" />
              {event.message}
            </li>
          ))}
        </ul>
      </div>
      <div className="card">
        <h2>Plan</h2>
        <ol>
          {plan.length === 0 ? <li className="muted">Plan appears after analysis.</li> : null}
          {plan.map((step, index) => {
            const item = step as { title?: string; detail?: string };
            return (
              <li key={index}>
                <strong>{item.title}</strong>
                <div className="muted">{item.detail}</div>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="card">
        <h2>Files Changed</h2>
        <ul>
          {changedFiles.length === 0 ? <li className="muted">No files changed yet.</li> : null}
          {changedFiles.map((file) => (
            <li key={file}>{file}</li>
          ))}
        </ul>
      </div>
      <div className="card">
        <h2>Terminal</h2>
        <pre className="terminal">{terminalLines.join("\n") || "$ waiting"}</pre>
      </div>
    </section>
  );
}

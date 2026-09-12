import type { AgentTask } from "../types";
import { formatDuration } from "../utils/format";

interface Props {
  task: AgentTask | null;
  onRollback: () => void;
  onViewDiff: () => void;
}

function resultCopy(status: string, summary?: string): { kind: "success" | "failed"; title: string } {
  const value = (status || "").toUpperCase();
  if (value === "SUCCESS") return { kind: "success", title: "Task completed successfully" };
  if (value === "CANCELLED") return { kind: "failed", title: "Task cancelled" };
  if (value === "LIMIT_REACHED") return { kind: "failed", title: "Task stopped — limit reached" };
  if (value === "TIMEOUT") return { kind: "failed", title: "Task stopped — timeout reached" };
  if (/rate limit/i.test(summary || "")) return { kind: "failed", title: "LLM rate limit exceeded. Please wait and try again." };
  return { kind: "failed", title: "Agent execution failed" };
}

export function FinalResult({ task, onRollback, onViewDiff }: Props) {
  const report = task?.report;
  if (!report) {
    return (
      <section className="panel">
        <h2>Final Result</h2>
        <p className="muted">{task ? `Status: ${task.status}` : "Run an agent task to see the report."}</p>
      </section>
    );
  }
  const copy = resultCopy(report.status, report.summary);
  return (
    <section className={`panel result ${copy.kind}`}>
      <div>
        <h2>Final Result</h2>
        <p>{copy.title}</p>
        <p>
          <span className="muted">Status:</span> {report.status.toUpperCase()}
        </p>
        <p>
          <span className="muted">Duration:</span> {formatDuration(report.duration_seconds)}
        </p>
        <p>
          <span className="muted">Iterations:</span> {report.iterations_used}
        </p>
        <p>
          <span className="muted">Tool rounds:</span> {report.tool_rounds ?? 0}
        </p>
        <p>
          <span className="muted">Files changed:</span> {report.files_changed.length}
          {report.files_changed.length ? ` (${report.files_changed.join(", ")})` : ""}
        </p>
        <p>
          <span className="muted">Tests:</span> {report.tests_passed} passed
          {report.tests_failed ? ` · ${report.tests_failed} failed` : ""}
          {report.tests_executed ? ` · ${report.tests_executed}` : ""}
        </p>
        <p>
          <span className="muted">Summary:</span> {report.summary}
        </p>
        {report.problem ? (
          <p>
            <span className="muted">Problem:</span> {report.problem}
          </p>
        ) : null}
        {report.root_cause ? (
          <p>
            <span className="muted">Root cause:</span> {report.root_cause}
          </p>
        ) : null}
        {report.fix ? (
          <p>
            <span className="muted">Fix:</span> Updated {report.fix}.
          </p>
        ) : null}
      </div>
      <div className="row">
        <button className="btn" onClick={onViewDiff}>
          View Diff
        </button>
        <button className="btn" onClick={onRollback}>
          Rollback
        </button>
      </div>
    </section>
  );
}

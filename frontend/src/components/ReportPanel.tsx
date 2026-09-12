import type { AgentTask } from "../types";

export function ReportPanel({ task }: { task: AgentTask | null }) {
  const report = task?.report;
  if (!report) {
    return (
      <section className="card">
        <h2>Final Result</h2>
        <p className="muted">{task ? `Status: ${task.status} · phase: ${task.phase}` : "Run an agent task to see the report."}</p>
      </section>
    );
  }
  return (
    <section className="card">
      <h2>Final Result</h2>
      <div className={`status ${report.status.toLowerCase()}`}>{report.status}</div>
      <p>{report.summary}</p>
      <p className="muted">
        Tests: {report.tests_passed} passed / {report.tests_failed} failed · Iterations: {report.iterations_used}
      </p>
      {report.warnings.length ? (
        <div>
          <h3>Warnings</h3>
          <ul>
            {report.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {report.review_findings.length ? (
        <div>
          <h3>Review findings</h3>
          <pre>{JSON.stringify(report.review_findings, null, 2)}</pre>
        </div>
      ) : null}
    </section>
  );
}

import { normalizePlanStatus, planProgress, type PlanStep } from "../utils/planState";

const MARK: Record<string, string> = {
  COMPLETED: "✓",
  RUNNING: "●",
  FAILED: "✗",
  CANCELLED: "✗",
  SKIPPED: "—",
  PENDING: "○",
};

export function AgentPlan({ plan }: { plan: PlanStep[] }) {
  const progress = planProgress(plan);
  return (
    <section className="panel">
      <h2>Plan</h2>
      {plan.length === 0 ? (
        <div className="empty">The execution plan will appear after analysis.</div>
      ) : (
        <>
          <p className="muted plan-progress">
            Plan Progress: {progress.completed} / {progress.total} completed
            {progress.total ? ` (${progress.percent}%)` : ""}
          </p>
          <ol className="plan">
            {plan.map((step, index) => {
              const status = normalizePlanStatus(step.status);
              const tone =
                status === "COMPLETED" ? "done" : status === "FAILED" || status === "CANCELLED" ? "fail" : status === "SKIPPED" ? "skip" : "run";
              return (
                <li key={step.id || index} className={`plan-step ${tone}`}>
                  <div className="plan-head">
                    <strong>
                      {MARK[status] || "○"} {step.title || `Step ${index + 1}`}
                    </strong>
                    <span className={`badge ${tone}`}>{status}</span>
                  </div>
                  {step.detail ? <div className="muted">{step.detail}</div> : null}
                  {status === "SKIPPED" && (step.kind === "commit" || /commit/i.test(step.title || "")) && !/optional commit/i.test(step.detail || "") ? (
                    <div className="muted">SKIPPED — Optional commit not requested</div>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}

export type PlanStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED" | "CANCELLED";

export interface PlanStep {
  id?: number;
  index?: number;
  title?: string;
  detail?: string;
  status?: string;
  kind?: string;
}

const ALIASES: Record<string, PlanStatus> = {
  pending: "PENDING",
  in_progress: "RUNNING",
  running: "RUNNING",
  done: "COMPLETED",
  complete: "COMPLETED",
  completed: "COMPLETED",
  failed: "FAILED",
  skipped: "SKIPPED",
  cancelled: "CANCELLED",
  canceled: "CANCELLED",
};

export function normalizePlanStatus(value: string | undefined | null): PlanStatus {
  const raw = (value || "PENDING").trim();
  return (ALIASES[raw.toLowerCase()] || raw.toUpperCase()) as PlanStatus;
}

export function derivePlan(events: Array<{ event: string; payload?: Record<string, unknown> }>, taskPlan?: PlanStep[] | null): PlanStep[] {
  let steps: PlanStep[] = Array.isArray(taskPlan) ? taskPlan.map((step) => ({ ...step })) : [];
  for (const event of events) {
    const payload = event.payload || {};
    if (Array.isArray(payload.plan) && payload.plan.length) {
      steps = payload.plan as PlanStep[];
      continue;
    }
    const stepId = Number(payload.step_id);
    const status = payload.status ? String(payload.status) : "";
    if (!stepId || !status) continue;
    steps = steps.map((step) =>
      Number(step.id || step.index) === stepId ? { ...step, status: normalizePlanStatus(status) } : step,
    );
  }
  return steps.map((step, index) => ({
    ...step,
    id: Number(step.id || step.index || index + 1),
    status: normalizePlanStatus(step.status),
  }));
}

export function planProgress(steps: PlanStep[]): { completed: number; total: number; percent: number } {
  const total = steps.length;
  const completed = steps.filter((step) => normalizePlanStatus(step.status) === "COMPLETED").length;
  return { completed, total, percent: total ? Math.round((completed / total) * 100) : 0 };
}

export const LAST_TASK_STORAGE_KEY = "codepilot.lastTaskId";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AgentPlan } from "../AgentPlan";
import { derivePlan } from "../../utils/planState";

afterEach(() => cleanup());

const steps = [
  { id: 1, title: "Inspect repository", detail: "Identify relevant files", status: "PENDING" },
  { id: 2, title: "Fix implementation", detail: "Correct apply_discount", status: "RUNNING" },
  { id: 3, title: "Add tests", detail: "Cover discounts", status: "COMPLETED" },
  { id: 4, title: "Run test suite", detail: "pytest", status: "FAILED" },
  { id: 5, title: "Commit changes", detail: "git commit", status: "SKIPPED" },
];

describe("AgentPlan", () => {
  it("renders pending, running, completed, failed, and skipped", () => {
    render(<AgentPlan plan={steps} />);
    expect(screen.getByText("PENDING")).toBeInTheDocument();
    expect(screen.getByText("RUNNING")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText("FAILED")).toBeInTheDocument();
    expect(screen.getByText("SKIPPED")).toBeInTheDocument();
    expect(screen.getByText(/Optional commit not requested/)).toBeInTheDocument();
    expect(screen.getByText(/Plan Progress: 1 \/ 5 completed/)).toBeInTheDocument();
  });

  it("updates when backend sends step events", () => {
    const plan = derivePlan(
      [
        {
          event: "plan_created",
          payload: { plan: [{ id: 1, title: "Inspect repository", status: "PENDING" }] },
        },
        { event: "plan_step_started", payload: { step_id: 1, status: "RUNNING" } },
        { event: "plan_step_completed", payload: { step_id: 1, status: "COMPLETED" } },
      ],
      [],
    );
    expect(plan[0].status).toBe("COMPLETED");
    const { rerender } = render(<AgentPlan plan={[{ id: 1, title: "Inspect repository", status: "PENDING" }]} />);
    rerender(<AgentPlan plan={plan} />);
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    expect(screen.queryByText("PENDING")).not.toBeInTheDocument();
  });

  it("keeps SUCCESS consistent with completed plan", () => {
    const plan = derivePlan(
      [
        {
          event: "plan_updated",
          payload: {
            plan: [
              { id: 1, title: "Inspect repository", status: "COMPLETED" },
              { id: 2, title: "Fix implementation", status: "COMPLETED" },
            ],
          },
        },
      ],
      [],
    );
    expect(plan.every((step) => step.status === "COMPLETED")).toBe(true);
  });

  it("restores final plan from stored task state after refresh", () => {
    const stored = [
      { id: 1, title: "Inspect repository", status: "COMPLETED" },
      { id: 2, title: "Commit changes", status: "SKIPPED" },
    ];
    const plan = derivePlan([], stored);
    expect(plan.map((step) => step.status)).toEqual(["COMPLETED", "SKIPPED"]);
  });
});

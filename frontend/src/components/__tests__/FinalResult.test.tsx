import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { FinalResult } from "../FinalResult";
import type { AgentTask } from "../../types";

afterEach(() => cleanup());

function task(status: string, extra: Partial<AgentTask["report"]> = {}): AgentTask {
  return {
    id: 1,
    project_id: 1,
    prompt: "Fix discount",
    mode: "implement",
    status: status.toLowerCase(),
    phase: "failed",
    iteration: 2,
    max_iterations: 5,
    report: {
      task: "Fix discount",
      status,
      summary: status === "LIMIT_REACHED" ? "Task stopped — tool-round limit reached" : "Fixed",
      files_changed: ["app/cart.py"],
      tests_executed: "pytest -q",
      tests_passed: 4,
      tests_failed: 0,
      commands_executed: ["pytest -q"],
      iterations_used: 2,
      tool_rounds: 10,
      duration_seconds: 12.4,
      decisions: [],
      warnings: [],
      review_findings: [],
      ...extra,
    },
  };
}

describe("FinalResult", () => {
  it("does not treat a tool-round limit as success", () => {
    render(<FinalResult task={task("LIMIT_REACHED")} onRollback={() => undefined} onViewDiff={() => undefined} />);
    expect(screen.getByText("Task stopped — limit reached")).toBeInTheDocument();
    expect(screen.queryByText("Task completed successfully")).not.toBeInTheDocument();
    expect(screen.getByText(/LIMIT_REACHED/)).toBeInTheDocument();
    expect(screen.getByText(/Tool rounds/)).toBeInTheDocument();
  });

  it("shows success metrics", () => {
    render(<FinalResult task={task("SUCCESS")} onRollback={() => undefined} onViewDiff={() => undefined} />);
    expect(screen.getByText("Task completed successfully")).toBeInTheDocument();
    expect(screen.getByText(/12\.4s/)).toBeInTheDocument();
  });

  it("shows rate-limit failure instead of success", () => {
    render(
      <FinalResult
        task={task("FAILED", { summary: "LLM rate limit reached. Please wait and try again.", tests_passed: 0, files_changed: [] })}
        onRollback={() => undefined}
        onViewDiff={() => undefined}
      />,
    );
    expect(screen.getByText("LLM rate limit exceeded. Please wait and try again.")).toBeInTheDocument();
    expect(screen.queryByText("Task completed successfully")).not.toBeInTheDocument();
    expect(screen.getByText(/FAILED/)).toBeInTheDocument();
  });
});

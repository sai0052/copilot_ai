import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TaskPanel } from "../TaskPanel";
import { TASK_TOO_SHORT, REPO_REQUIRED } from "../../utils/taskValidation";

afterEach(() => cleanup());

const base = {
  prompt: "Fix the discount calculation.",
  problemDescription: "",
  mode: "implement" as const,
  busy: false,
  hasProject: true,
  onPrompt: vi.fn(),
  onProblemDescription: vi.fn(),
  onMode: vi.fn(),
  onRun: vi.fn(),
  onCancel: vi.fn(),
};

describe("TaskPanel", () => {
  it("renders optional problem description and allows run without it", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    render(<TaskPanel {...base} onRun={onRun} />);
    expect(screen.getByLabelText("Problem description (optional)")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Describe the error or problem...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it.each(["", "   ", "a", "ab"])("disables Run Agent and shows inline error for %j", (prompt) => {
    const onRun = vi.fn();
    render(<TaskPanel {...base} prompt={prompt} onRun={onRun} />);
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeDisabled();
    expect(screen.getByText(`⚠ ${TASK_TOO_SHORT}`)).toBeInTheDocument();
  });

  it("enables Run Agent for a three-character task", () => {
    render(<TaskPanel {...base} prompt="abc" />);
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeEnabled();
    expect(screen.queryByText(`⚠ ${TASK_TOO_SHORT}`)).not.toBeInTheDocument();
  });

  it("does not call onRun when the task is invalid", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    render(<TaskPanel {...base} prompt="" onRun={onRun} />);
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(onRun).not.toHaveBeenCalled();
  });

  it("requires a selected repository", () => {
    const onRun = vi.fn();
    render(<TaskPanel {...base} hasProject={false} onRun={onRun} />);
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeDisabled();
    expect(screen.getByText(`⚠ ${REPO_REQUIRED}`)).toBeInTheDocument();
  });

  it("disables Run Agent while busy even with a valid task", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    render(<TaskPanel {...base} busy onRun={onRun} />);
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(onRun).not.toHaveBeenCalled();
  });

  it("keeps task and problem description values after a failed run", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    render(
      <TaskPanel
        {...base}
        prompt="Fix the discount calculation"
        problemDescription="10% of ₹53,000 is wrong"
        onRun={onRun}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(onRun).toHaveBeenCalled();
    expect(screen.getByLabelText("Task")).toHaveValue("Fix the discount calculation");
    expect(screen.getByLabelText("Problem description (optional)")).toHaveValue("10% of ₹53,000 is wrong");
  });

  it("does not submit twice while the first click is in flight", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    const { rerender } = render(<TaskPanel {...base} onRun={onRun} />);
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    rerender(<TaskPanel {...base} busy onRun={onRun} />);
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(onRun).toHaveBeenCalledTimes(1);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { startTask } from "../../services/api";
import { TASK_TOO_SHORT } from "../taskValidation";

describe("startTask request construction", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("does not POST when the task is empty", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(startTask(1, "", "implement")).rejects.toMatchObject({
      message: TASK_TOO_SHORT,
      field: "prompt",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends prompt and omits empty problem_description", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 9, prompt: "Fix the bug", status: "queued" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await startTask(3, "  Fix the bug  ", "implement", "   ");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      project_id: 3,
      prompt: "Fix the bug",
      mode: "implement",
    });
  });

  it("sends optional problem_description when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 9, prompt: "Fix the discount calculation", status: "queued" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await startTask(
      3,
      "Fix the discount calculation",
      "implement",
      "When I apply a 10% discount to ₹53,000, the result is incorrect.",
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      project_id: 3,
      prompt: "Fix the discount calculation",
      mode: "implement",
      problem_description: "When I apply a 10% discount to ₹53,000, the result is incorrect.",
    });
  });

  it("maps backend 422 to a clean field error", async () => {
    const payload = {
      error: "validation_error",
      field: "prompt",
      message: "Task must contain at least 3 characters.",
      detail: "Task must contain at least 3 characters.",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 422, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(startTask(1, "Fix the bug", "implement")).rejects.toMatchObject({
      message: TASK_TOO_SHORT,
      field: "prompt",
      status: 422,
    });
  });
});

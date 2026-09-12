import { describe, expect, it } from "vitest";
import {
  TASK_TOO_SHORT,
  REPO_REQUIRED,
  canRunAgent,
  createSubmitLock,
  isValidTaskPrompt,
  validateAgentSubmission,
  validateTaskPrompt,
} from "../taskValidation";
import { ApiError, friendlyError, parseHttpError } from "../errors";

describe("task prompt validation", () => {
  it.each(["", " ", "   ", "a", "ab", "  a  ", "  "])("rejects %j", (value) => {
    expect(isValidTaskPrompt(value)).toBe(false);
    const result = validateTaskPrompt(value);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toBe(TASK_TOO_SHORT);
      expect(result.field).toBe("prompt");
    }
  });

  it.each(["abc", "Fix the bug", "Add a health endpoint", "Review the authentication code"])(
    "accepts %j",
    (value) => {
      expect(isValidTaskPrompt(value)).toBe(true);
      const result = validateTaskPrompt(value);
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.prompt).toBe(value.trim());
    },
  );
});

describe("agent submission", () => {
  it("requires a repository", () => {
    const result = validateAgentSubmission({ prompt: "Fix the bug", hasProject: false });
    expect(result).toEqual({ ok: false, field: "repository", message: REPO_REQUIRED });
  });

  it("does not require a problem description", () => {
    const result = validateAgentSubmission({ prompt: "Fix the bug", hasProject: true });
    expect(result).toEqual({ ok: true, prompt: "Fix the bug" });
  });

  it("disables run for invalid or busy states", () => {
    expect(canRunAgent({ prompt: "", hasProject: true, busy: false })).toBe(false);
    expect(canRunAgent({ prompt: "Fix the bug", hasProject: false, busy: false })).toBe(false);
    expect(canRunAgent({ prompt: "Fix the bug", hasProject: true, busy: true })).toBe(false);
    expect(canRunAgent({ prompt: "Fix the bug", hasProject: true, busy: false })).toBe(true);
  });

  it("prevents overlapping submits", () => {
    const lock = createSubmitLock();
    expect(lock.tryAcquire()).toBe(true);
    expect(lock.tryAcquire()).toBe(false);
    lock.release();
    expect(lock.tryAcquire()).toBe(true);
  });
});

describe("API validation errors", () => {
  it("maps FastAPI 422 string_too_short to a clean prompt message", () => {
    const err = parseHttpError(
      422,
      "POST /api/agent/tasks",
      JSON.stringify({
        detail: [
          {
            type: "string_too_short",
            loc: ["body", "prompt"],
            msg: "String should have at least 3 characters",
            input: "",
            ctx: { min_length: 3 },
          },
        ],
      }),
    );
    expect(err).toBeInstanceOf(ApiError);
    expect(err.field).toBe("prompt");
    expect(err.message).toBe(TASK_TOO_SHORT);
    expect(friendlyError(err)).toBe(TASK_TOO_SHORT);
    expect(friendlyError(err)).not.toMatch(/string_too_short/);
  });
});

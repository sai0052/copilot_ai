export const TASK_MIN_LENGTH = 3;

export const TASK_TOO_SHORT = "Please enter a task with at least 3 characters.";
export const REPO_REQUIRED = "Please select a repository first.";

export type SubmissionField = "prompt" | "repository";

export type SubmissionResult =
  | { ok: true; prompt: string }
  | { ok: false; field: SubmissionField; message: string };

export function trimTaskPrompt(value: string): string {
  return (value ?? "").trim();
}

export function isValidTaskPrompt(value: string): boolean {
  return trimTaskPrompt(value).length >= TASK_MIN_LENGTH;
}

export function validateTaskPrompt(value: string): SubmissionResult {
  const prompt = trimTaskPrompt(value);
  if (prompt.length < TASK_MIN_LENGTH) {
    return { ok: false, field: "prompt", message: TASK_TOO_SHORT };
  }
  return { ok: true, prompt };
}

export function validateAgentSubmission(input: {
  prompt: string;
  hasProject: boolean;
}): SubmissionResult {
  if (!input.hasProject) {
    return { ok: false, field: "repository", message: REPO_REQUIRED };
  }
  return validateTaskPrompt(input.prompt);
}

export function canRunAgent(input: {
  prompt: string;
  hasProject: boolean;
  busy: boolean;
}): boolean {
  return !input.busy && input.hasProject && isValidTaskPrompt(input.prompt);
}

export function createSubmitLock(): {
  tryAcquire: () => boolean;
  release: () => void;
  isLocked: () => boolean;
} {
  let locked = false;
  return {
    tryAcquire: () => {
      if (locked) return false;
      locked = true;
      return true;
    },
    release: () => {
      locked = false;
    },
    isLocked: () => locked,
  };
}

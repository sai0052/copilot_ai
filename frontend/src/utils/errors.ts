import { TASK_TOO_SHORT } from "./taskValidation";

const MESSAGES: Array<{ test: RegExp; message: string }> = [
  { test: /folder selection was cancelled/i, message: "Folder selection was cancelled." },
  { test: /does not support direct folder|not supported here/i, message: "Direct folder selection is not supported here. Use the browser folder import or enter the repository path manually." },
  { test: /could not access the selected folder|cannot access this folder/i, message: "CodePilot could not access the selected folder." },
  { test: /no folder selected/i, message: "No folder selected." },
  { test: /could not be accessed/i, message: "Repository folder could not be accessed." },
  { test: /does not exist/i, message: "Repository path does not exist." },
  { test: /not a directory/i, message: "Repository path is not a directory." },
  { test: /no supported project files/i, message: "Repository contains no supported project files." },
  { test: /scan failed/i, message: "Repository scan failed." },
  { test: /too many files/i, message: "Project contains too many files." },
  { test: /exceeds size limit|too large/i, message: "Project is too large." },
  { test: /file exceeds size/i, message: "A file in this project exceeds the size limit." },
  { test: /unable to read|no files were provided/i, message: "Unable to read project." },
  { test: /unsupported project/i, message: "Unsupported project type." },
  { test: /rate limit/i, message: "Groq rate limit reached. Please wait and try again." },
  { test: /llm unavailable|api key/i, message: "LLM unavailable. Configure the server API key in .env and restart the backend." },
  { test: /agent execution failed|agent_failed/i, message: "Agent execution failed." },
  { test: /tests failed/i, message: "Tests failed." },
  { test: /path traversal|system director/i, message: "That folder cannot be imported for security reasons." },
];

export class ApiError extends Error {
  status: number;
  field?: string;
  code?: string;

  constructor(message: string, status: number, field?: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.field = field;
    this.code = code;
  }

  get isValidation(): boolean {
    return this.status === 400 || this.status === 422 || this.code === "validation_error";
  }
}

type ValidationBody = {
  detail?: unknown;
  error?: string;
  field?: string;
  message?: string;
};

export function parseHttpError(status: number, path: string, body: string): ApiError {
  let parsed: ValidationBody | null = null;
  try {
    parsed = JSON.parse(body) as ValidationBody;
  } catch {
    parsed = null;
  }
  const promptMessage = promptValidationMessage(parsed, body);
  if (promptMessage) {
    return new ApiError(promptMessage, status, "prompt", "validation_error");
  }
  if (parsed?.error === "validation_error" && parsed.message) {
    return new ApiError(parsed.message, status, parsed.field, "validation_error");
  }
  let detail = body.slice(0, 400);
  if (typeof parsed?.detail === "string") {
    detail = parsed.detail;
  } else if (parsed?.message) {
    detail = parsed.message;
  } else if (Array.isArray(parsed?.detail)) {
    detail = "Invalid request.";
  }
  if (status === 404) {
    return new ApiError(
      `CodePilot API 404 for ${path} (${detail}). The UI must call the CodePilot backend (default http://127.0.0.1:8010).`,
      status,
    );
  }
  return new ApiError(detail || `HTTP ${status} ${path}`, status, parsed?.field, parsed?.error);
}

function promptValidationMessage(parsed: ValidationBody | null, raw: string): string | null {
  if (!parsed) {
    return /string_too_short|"prompt"/.test(raw) ? TASK_TOO_SHORT : null;
  }
  if (parsed.field === "prompt" && (parsed.message || parsed.detail)) {
    return TASK_TOO_SHORT;
  }
  const details = Array.isArray(parsed.detail) ? parsed.detail : [];
  for (const item of details) {
    if (!item || typeof item !== "object") continue;
    const loc = (item as { loc?: unknown[] }).loc || [];
    const type = String((item as { type?: string }).type || "");
    if (loc.includes("prompt") || loc.includes("task")) {
      if (type.includes("too_short") || type === "missing" || type === "string_too_short") {
        return TASK_TOO_SHORT;
      }
    }
  }
  if (typeof parsed.detail === "string" && /at least 3 character/i.test(parsed.detail)) {
    return TASK_TOO_SHORT;
  }
  return null;
}

export function friendlyError(error: unknown): string {
  if (error instanceof ApiError && error.isValidation && error.field === "prompt") {
    return TASK_TOO_SHORT;
  }
  const raw = error instanceof Error ? error.message : String(error);
  if (!(error instanceof ApiError && error.isValidation)) {
    console.error("[CodePilot]", error);
  }
  if (/string_too_short|at least 3 character/i.test(raw)) {
    return TASK_TOO_SHORT;
  }
  for (const item of MESSAGES) {
    if (item.test.test(raw)) return item.message;
  }
  if (/^\s*[{\[]/.test(raw)) {
    return "Invalid request.";
  }
  return raw.replace(/https?:\/\/\S+/g, "").trim() || "Something went wrong.";
}

export function registrationError(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "CodePilot could not access the selected folder.";
  }
  const raw = friendlyError(error);
  if (
    /could not access the selected folder|cannot access this folder|does not exist|not a directory|no supported project files|too many files|too large|size limit|cannot be imported/i.test(
      raw,
    )
  ) {
    return raw;
  }
  return `Repository registration failed: ${raw}`;
}

export function importFailure(error: unknown): string {
  const raw = friendlyError(error);
  if (raw.startsWith("Repository import failed")) return raw;
  if (/no supported project files|too many files|too large|size limit|cannot be imported|could not access/i.test(raw)) {
    return raw;
  }
  return `Repository import failed: ${raw}`;
}

export function scanFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "CodePilot could not access the selected folder.";
  }
  const raw = friendlyError(error);
  if (/could not access the selected folder|cannot access this folder|does not exist/i.test(raw)) return raw;
  if (raw.startsWith("Repository scan failed")) return raw;
  return `Repository scan failed: ${raw}`;
}

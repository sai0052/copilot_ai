import { API_BASE_URL } from "../config";
import { ApiError, parseHttpError } from "../utils/errors";
import type { AgentMode, AgentTask, Project, RepoMap } from "../types";
import { validateTaskPrompt } from "../utils/taskValidation";

const API = API_BASE_URL;

export function apiBase(): string {
  return API;
}

async function parse<T>(response: Response, path: string): Promise<T> {
  const body = await response.text();
  if (!response.ok) {
    throw parseHttpError(response.status, path, body);
  }
  try {
    return JSON.parse(body) as T;
  } catch {
    throw new ApiError(`Invalid JSON from ${path}: ${body.slice(0, 200)}`, response.status);
  }
}

export async function health(): Promise<{
  status: string;
  service?: string;
  llm_configured: boolean;
  model: string;
  version?: string;
}> {
  const info = await parse<{
    status: string;
    service?: string;
    llm_configured: boolean;
    model: string;
    version?: string;
  }>(await fetch(`${API}/health`), "GET /health");
  if (info.service && info.service !== "codepilot-ai") {
    throw new Error(`Wrong backend at ${API}: expected CodePilot AI`);
  }
  if (info.status !== "ok" || typeof info.llm_configured !== "boolean") {
    throw new Error(
      `Wrong backend at ${API}/health. Point VITE_API_BASE_URL at CodePilot (default http://127.0.0.1:8010).`,
    );
  }
  return info;
}

export async function listProjects(): Promise<Project[]> {
  const projects = await parse<Project[]>(await fetch(`${API}/api/projects`), "GET /api/projects");
  console.info("[CodePilot] projects.list", { count: projects.length });
  return projects;
}

export async function createProject(rootPath: string, name?: string): Promise<Project> {
  console.info("[CodePilot] projects.create", { hasPath: Boolean(rootPath.trim()), name: name || undefined });
  return parse(
    await fetch(`${API}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root_path: rootPath, name }),
    }),
    "POST /api/projects",
  );
}

export async function browseFolder(): Promise<{ root_path: string }> {
  return parse(await fetch(`${API}/api/projects/browse`, { method: "POST" }), "POST /api/projects/browse");
}

export async function importProject(
  name: string,
  files: { path: string; content: string }[],
): Promise<Project> {
  console.info("[CodePilot] projects.import", { name, fileCount: files.length });
  return parse(
    await fetch(`${API}/api/projects/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, files }),
    }),
    "POST /api/projects/import",
  );
}

export async function scanProject(id: number): Promise<RepoMap> {
  console.info("[CodePilot] projects.scan", { id });
  return parse(await fetch(`${API}/api/projects/${id}/scan`, { method: "POST" }), `POST /api/projects/${id}/scan`);
}

export async function readFile(projectId: number, path: string): Promise<{ path: string; content: string }> {
  return parse(
    await fetch(`${API}/api/projects/${projectId}/file?path=${encodeURIComponent(path)}`),
    "GET /api/projects/{id}/file",
  );
}

export async function projectDiff(projectId: number, taskId?: number): Promise<{ diff: string; changed_files: string[] }> {
  const q = taskId ? `?task_id=${taskId}` : "";
  return parse(await fetch(`${API}/api/projects/${projectId}/diff${q}`), "GET /api/projects/{id}/diff");
}

export type TaskCreateBody = {
  project_id: number;
  prompt: string;
  mode: AgentMode;
  problem_description?: string;
};

export async function startTask(
  projectId: number,
  prompt: string,
  mode: AgentMode,
  problemDescription?: string,
): Promise<AgentTask> {
  const checked = validateTaskPrompt(prompt);
  if (!checked.ok) {
    throw new ApiError(checked.message, 422, "prompt", "validation_error");
  }
  const body: TaskCreateBody = { project_id: projectId, prompt: checked.prompt, mode };
  const trimmedProblem = problemDescription?.trim();
  if (trimmedProblem && !["undefined", "null"].includes(trimmedProblem.toLowerCase())) {
    body.problem_description = trimmedProblem;
  }
  return parse(
    await fetch(`${API}/api/agent/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    "POST /api/agent/tasks",
  );
}

export async function getTask(id: number): Promise<AgentTask> {
  return parse(await fetch(`${API}/api/agent/tasks/${id}`), `GET /api/agent/tasks/${id}`);
}

export async function cancelTask(id: number): Promise<void> {
  await fetch(`${API}/api/agent/tasks/${id}/cancel`, { method: "POST" });
}

export async function rollbackTask(id: number): Promise<void> {
  await parse(await fetch(`${API}/api/agent/tasks/${id}/rollback`, { method: "POST" }), `POST /api/agent/tasks/${id}/rollback`);
}

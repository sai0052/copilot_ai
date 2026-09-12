import type { AgentTask, Project, RepoMap } from "../types";

export interface WorkbenchSlice {
  project: Project | null;
  repoMap: RepoMap | null;
  task: AgentTask | null;
  diff: string;
}

export const EMPTY_WORKBENCH: WorkbenchSlice = {
  project: null,
  repoMap: null,
  task: null,
  diff: "",
};

export function workbenchForProject(next: Project): WorkbenchSlice {
  return { project: next, repoMap: null, task: null, diff: "" };
}

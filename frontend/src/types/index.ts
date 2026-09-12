export type AgentMode = "implement" | "review" | "explain" | "issue";

export interface Project {
  id: number;
  name: string;
  root_path: string;
  project_type: string;
  source?: "imported" | "local_path" | string;
}

export interface RepoMap {
  root: string;
  project_type: string;
  file_count: number;
  files: { path: string; kind: string; size: number }[];
  tree: string;
  config_files: string[];
  test_files: string[];
  git_status?: string;
  scan_status?: string;
}

export interface FinalReport {
  task: string;
  status: string;
  summary: string;
  files_changed: string[];
  tests_executed: string;
  tests_passed: number;
  tests_failed: number;
  commands_executed: string[];
  iterations_used: number;
  tool_rounds?: number;
  duration_seconds?: number;
  decisions: string[];
  warnings: string[];
  review_findings: Array<Record<string, unknown>>;
  problem?: string | null;
  root_cause?: string | null;
  fix?: string | null;
  plan?: PlanStep[];
}

export interface PlanStep {
  id?: number;
  index?: number;
  title?: string;
  detail?: string;
  status?: string;
  kind?: string;
}

export interface AgentTask {
  id: number;
  project_id: number;
  prompt: string;
  mode: string;
  status: string;
  phase: string;
  iteration: number;
  max_iterations: number;
  branch_name?: string | null;
  error?: string | null;
  report?: FinalReport | null;
  problem_description?: string | null;
  plan?: PlanStep[];
}

export interface AgentEvent {
  event: string;
  message: string;
  payload?: Record<string, unknown>;
}

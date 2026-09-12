import type { Project, RepoMap } from "../types";
import { typeLabel } from "../utils/format";

interface Props {
  project: Project | null;
  repoMap: RepoMap | null;
  agentStatus: string;
}

export function ProjectOverview({ project, repoMap, agentStatus }: Props) {
  return (
    <section className="panel">
      <h2>Project overview</h2>
      <div className="overview">
        <div className="stat">
          <span>Name</span>
          <b>{project?.name || "—"}</b>
        </div>
        <div className="stat">
          <span>Type</span>
          <b>{typeLabel(project?.project_type)}</b>
        </div>
        <div className="stat">
          <span>Files</span>
          <b>{repoMap?.file_count ?? "—"}</b>
        </div>
        <div className="stat">
          <span>Agent</span>
          <b>{agentStatus}</b>
        </div>
      </div>
      <div className="muted">Git: {repoMap?.git_status?.trim() || "No git status"}</div>
      {project?.source === "imported" ? (
        <div className="muted">This project is an imported workspace copy of a browser-selected folder.</div>
      ) : null}
    </section>
  );
}

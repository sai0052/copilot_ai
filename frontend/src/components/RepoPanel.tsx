import type { Project, RepoMap } from "../types";

interface Props {
  repoPath: string;
  onRepoPath: (value: string) => void;
  projects: Project[];
  project: Project | null;
  repoMap: RepoMap | null;
  busy: boolean;
  onSelect: (project: Project) => void;
  onRegister: () => void;
}

export function RepoPanel({
  repoPath,
  onRepoPath,
  projects,
  project,
  repoMap,
  busy,
  onSelect,
  onRegister,
}: Props) {
  return (
    <aside className="sidebar">
      <h2>Select Repository</h2>
      <label>
        Repository path
        <input
          value={repoPath}
          onChange={(event) => onRepoPath(event.target.value)}
          placeholder="C:\\projects\\myapp"
        />
      </label>
      <button disabled={busy || !repoPath.trim()} onClick={onRegister}>
        Register / Scan
      </button>
      <div className="muted">
        {project ? `${project.name} · ${project.project_type} · id ${project.id}` : "No project selected"}
      </div>
      {projects.length > 0 ? (
        <div className="list">
          {projects.map((item) => (
            <button key={item.id} className="ghost" onClick={() => onSelect(item)}>
              {item.name}
              <span>{item.root_path}</span>
            </button>
          ))}
        </div>
      ) : null}
      <h3>Repository tree</h3>
      <pre className="tree">{repoMap?.tree || "Scan a repository to view files."}</pre>
    </aside>
  );
}

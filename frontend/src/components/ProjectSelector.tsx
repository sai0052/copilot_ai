import { useEffect, useRef, useState } from "react";
import type { Project, RepoMap } from "../types";
import { directoryPickerUsable, isImportedWorkspace, watchNativeDialog } from "../utils/folderPicker";
import { typeLabel } from "../utils/format";

export type FolderPhase = "idle" | "selecting" | "importing" | "scanning" | "ready";

const PHASE_COPY: Record<FolderPhase, string | null> = {
  idle: null,
  selecting: "Selecting folder...",
  importing: "Importing repository...",
  scanning: "Scanning repository...",
  ready: "Repository ready.",
};

interface Props {
  projects: Project[];
  project: Project | null;
  repoMap: RepoMap | null;
  busy: boolean;
  scanning: boolean;
  folderPhase?: FolderPhase;
  manualPath: string;
  onManualPath: (value: string) => void;
  onSelectExisting: (project: Project) => void;
  onSelectFolder: () => void | Promise<"ok" | "cancelled" | "unavailable" | "unsupported" | "failed" | void>;
  onWebkitFiles: (list: FileList) => void;
  onManualRegister: () => void;
  onScan: () => void;
  onClearError?: () => void;
  onFolderCancelled?: () => void;
  onFolderUnsupported?: () => void;
}

export function ProjectSelector({
  projects,
  project,
  repoMap,
  busy,
  scanning,
  folderPhase = "idle",
  manualPath,
  onManualPath,
  onSelectExisting,
  onSelectFolder,
  onWebkitFiles,
  onManualRegister,
  onScan,
  onClearError,
  onFolderCancelled,
  onFolderUnsupported,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const nativeWatchRef = useRef<ReturnType<typeof watchNativeDialog> | null>(null);
  const [manual, setManual] = useState(false);
  const imported = project?.source === "imported" || isImportedWorkspace(project?.root_path);
  const phaseText = PHASE_COPY[folderPhase] || (scanning ? "Scanning repository..." : null);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.setAttribute("webkitdirectory", "");
    el.setAttribute("directory", "");
    el.multiple = true;
  }, []);

  function openFileDirectoryPicker() {
    nativeWatchRef.current?.stop();
    nativeWatchRef.current = watchNativeDialog();
    inputRef.current?.click();
  }

  async function handleSelectFolder() {
    if (busy) return;
    onClearError?.();
    if (directoryPickerUsable()) {
      const result = await onSelectFolder();
      if (result === "unavailable" || result === "unsupported") {
        openFileDirectoryPicker();
      }
      return;
    }
    openFileDirectoryPicker();
  }

  return (
    <section className="panel stack">
      <h2>Project</h2>
      {project ? (
        <div>
          <strong>{project.name}</strong>
          <div className="muted">
            {typeLabel(project.project_type)}
            {repoMap ? ` · ${repoMap.file_count} files` : ""}
            {imported ? " · imported copy" : " · local path"}
          </div>
          {imported ? (
            <div className="muted">Imported workspace copy — browsers cannot send a real Windows path.</div>
          ) : (
            <div className="muted" title={project.root_path}>
              {project.root_path}
            </div>
          )}
        </div>
      ) : (
        <div className="empty">
          <p>No project selected</p>
          <p>Select a local project folder to begin.</p>
        </div>
      )}
      {phaseText ? (
        <div className={folderPhase === "ready" ? "muted" : "muted"} role="status">
          {phaseText}
        </div>
      ) : null}
      <button
        className="btn primary"
        data-testid="select-folder"
        disabled={busy}
        onClick={() => void handleSelectFolder()}
        aria-label="Select project folder"
      >
        + Select Project Folder
      </button>
      <p className="muted">
        Folder selection imports a copy into a CodePilot workspace. To work on the original files, enter a repository path
        manually.
      </p>
      <input
        ref={inputRef}
        className="hidden-input"
        type="file"
        data-testid="webkit-directory"
        multiple
        onChange={(event) => {
          onClearError?.();
          if (event.target.files?.length) {
            onWebkitFiles(event.target.files);
          }
          event.target.value = "";
        }}
        onCancel={() => {
          const nativeUi = nativeWatchRef.current?.observed() ?? false;
          nativeWatchRef.current?.stop();
          if (!nativeUi) {
            onFolderUnsupported?.();
            return;
          }
          onFolderCancelled?.();
        }}
      />
      <button
        className="btn"
        type="button"
        disabled={busy}
        onClick={() => {
          onClearError?.();
          openFileDirectoryPicker();
        }}
      >
        Browser folder picker
      </button>
      {project ? (
        <button className="btn" disabled={busy} onClick={onScan}>
          Scan Repository
        </button>
      ) : null}
      <button
        className="btn tiny"
        type="button"
        onClick={() => {
          onClearError?.();
          setManual((value) => !value);
        }}
      >
        {manual ? "Hide manual path" : "Enter repository path manually"}
      </button>
      {manual ? (
        <div className="stack">
          <input
            aria-label="Repository path"
            value={manualPath}
            onChange={(event) => onManualPath(event.target.value)}
            placeholder="C:\\projects\\myapp"
          />
          <button className="btn" disabled={busy || !manualPath.trim()} onClick={onManualRegister}>
            Register path
          </button>
        </div>
      ) : null}
      {projects.length > 0 ? (
        <div>
          <div className="muted">Recent</div>
          {projects.map((item) => (
            <button
              key={item.id}
              className={`btn ghost${item.id === project?.id ? " active" : ""}`}
              onClick={() => onSelectExisting(item)}
            >
              {item.name}
              <span className="muted">{typeLabel(item.project_type)}</span>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { AgentActivity } from "./components/AgentActivity";
import { AgentPlan } from "./components/AgentPlan";
import { DiffViewer } from "./components/DiffViewer";
import { FilesChanged } from "./components/FilesChanged";
import { FinalResult } from "./components/FinalResult";
import { Header } from "./components/Header";
import { ProjectOverview } from "./components/ProjectOverview";
import { ProjectSelector } from "./components/ProjectSelector";
import { RepositoryTree } from "./components/RepositoryTree";
import { TaskPanel } from "./components/TaskPanel";
import { TerminalPanel } from "./components/TerminalPanel";
import { useAgentEvents } from "./hooks/useAgentEvents";
import {
  cancelTask,
  createProject,
  getTask,
  health,
  importProject,
  listProjects,
  projectDiff,
  rollbackTask,
  scanProject,
  startTask,
} from "./services/api";
import type { AgentMode, AgentTask, Project, RepoMap } from "./types";
import { ApiError, friendlyError, importFailure, registrationError, scanFailure } from "./utils/errors";
import { directoryPickerUsable, pickWithDirectoryPicker, resolveWebkitFiles } from "./utils/folderPicker";
import { LAST_TASK_STORAGE_KEY, derivePlan } from "./utils/planState";
import { createSubmitLock, validateAgentSubmission } from "./utils/taskValidation";

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [manualPath, setManualPath] = useState("");
  const [repoMap, setRepoMap] = useState<RepoMap | null>(null);
  const [prompt, setPrompt] = useState("");
  const [problemDescription, setProblemDescription] = useState("");
  const [mode, setMode] = useState<AgentMode>("implement");
  const [task, setTask] = useState<AgentTask | null>(null);
  const [diff, setDiff] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [llmReady, setLlmReady] = useState<boolean | null>(null);
  const [model, setModel] = useState<string | undefined>();
  const [backendOk, setBackendOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [folderPhase, setFolderPhase] = useState<"idle" | "selecting" | "importing" | "scanning" | "ready">("idle");
  const diffRef = useRef<HTMLDivElement>(null);
  const runLock = useRef(createSubmitLock());

  const events = useAgentEvents(task?.id ?? null);
  const plan = useMemo(
    () => derivePlan(events, task?.report?.plan || task?.plan || []),
    [events, task],
  );

  useEffect(() => {
    setError((current) => (current && /folder selection was cancelled/i.test(current) ? null : current));
  }, []);

  useEffect(() => {
    const stored = window.sessionStorage.getItem(LAST_TASK_STORAGE_KEY);
    if (!stored) return;
    const id = Number(stored);
    if (!id) return;
    getTask(id)
      .then(setTask)
      .catch(() => window.sessionStorage.removeItem(LAST_TASK_STORAGE_KEY));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const connectivityError = /failed to fetch|unable to reach|networkerror|wrong backend/i;

    async function ping() {
      try {
        const info = await health();
        if (cancelled) return;
        setBackendOk(true);
        setLlmReady(info.llm_configured);
        setModel(info.model);
        setError((current) => (current && connectivityError.test(current) ? null : current));
      } catch {
        if (cancelled) return;
        setBackendOk(false);
        return;
      }
      try {
        const nextProjects = await listProjects();
        if (!cancelled) setProjects(nextProjects);
      } catch {
        /* Health already succeeded; retry project list on the next poll. */
      }
    }

    void ping();
    const id = window.setInterval(() => void ping(), 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!task) return;
    const terminal = events.some((item) =>
      ["agent_completed", "agent_failed", "agent_cancelled", "agent_limit_reached", "agent_timeout"].includes(
        item.event,
      ),
    );
    if (!terminal) return;
    runLock.current.release();
    setBusy(false);
    getTask(task.id).then(setTask).catch(() => undefined);
    if (project) {
      projectDiff(project.id, task.id)
        .then((result) => setDiff(result.diff))
        .catch(() => undefined);
    }
  }, [events, task?.id, project?.id]);

  function clearProjectScopedState() {
    setTask(null);
    setDiff("");
    setRepoMap(null);
    window.sessionStorage.removeItem(LAST_TASK_STORAGE_KEY);
  }

  async function applyProject(created: Project) {
    console.info("[CodePilot] project.switch", { from: project?.id ?? null, to: created.id, name: created.name, source: created.source });
    clearProjectScopedState();
    setError(null);
    setProject(created);
    setProjects((current) => [created, ...current.filter((item) => item.id !== created.id)]);
    setScanning(true);
    setFolderPhase("scanning");
    try {
      const scanned = await scanProject(created.id);
      setRepoMap(scanned);
      setProject({ ...created, project_type: scanned.project_type });
      try {
        const listed = await listProjects();
        setProjects(listed);
        const selected = listed.find((item) => item.id === created.id) || created;
        setProject({ ...selected, project_type: scanned.project_type });
      } catch {
        console.info("[CodePilot] projects.list_refresh_failed");
      }
      if (!scanned.file_count) {
        setError("Repository contains no supported project files.");
      }
      setFolderPhase("ready");
    } catch (err) {
      setFolderPhase("idle");
      throw new Error(scanFailure(err));
    } finally {
      setScanning(false);
    }
  }

  async function onSelectFolder(): Promise<"ok" | "cancelled" | "unavailable" | "unsupported" | "failed"> {
    if (busy) return "failed";
    setError(null);
    setBusy(true);
    setFolderPhase("selecting");
    try {
      const picked = await pickWithDirectoryPicker();
      if (picked.status === "cancelled") {
        setError("Folder selection was cancelled.");
        setFolderPhase("idle");
        return "cancelled";
      }
      if (picked.status === "unsupported" || picked.status === "unavailable") {
        setFolderPhase("idle");
        return picked.status;
      }
      setFolderPhase("importing");
      let created: Project;
      try {
        created = await importProject(picked.project.name, picked.project.files);
      } catch (err) {
        throw new Error(importFailure(err));
      }
      await applyProject(created);
      return "ok";
    } catch (err) {
      setFolderPhase("idle");
      setError(friendlyError(err));
      return "failed";
    } finally {
      setBusy(false);
    }
  }

  async function onWebkitFiles(list: FileList) {
    if (busy) return;
    setError(null);
    setBusy(true);
    setFolderPhase("importing");
    try {
      const picked = await resolveWebkitFiles(list);
      console.info("[CodePilot] folder.webkit", { name: picked.name, files: picked.files.length });
      let created: Project;
      try {
        created = await importProject(picked.name, picked.files);
      } catch (err) {
        throw new Error(importFailure(err));
      }
      await applyProject(created);
    } catch (err) {
      setFolderPhase("idle");
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onManualRegister() {
    if (!manualPath.trim()) {
      setError("No folder selected.");
      return;
    }
    if (busy) return;
    setError(null);
    setBusy(true);
    setFolderPhase("importing");
    try {
      console.info("[CodePilot] folder.manual_path");
      let created: Project;
      try {
        created = await createProject(manualPath.trim());
      } catch (err) {
        throw new Error(registrationError(err));
      }
      await applyProject(created);
    } catch (err) {
      setFolderPhase("idle");
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSelectExisting(item: Project) {
    setError(null);
    if (project?.id === item.id && repoMap) {
      return;
    }
    if (busy) return;
    console.info("[CodePilot] project.switch", { from: project?.id ?? null, to: item.id, name: item.name });
    clearProjectScopedState();
    setProject(item);
    setBusy(true);
    setScanning(true);
    setFolderPhase("scanning");
    try {
      const scanned = await scanProject(item.id);
      setRepoMap(scanned);
      setProject({ ...item, project_type: scanned.project_type });
      setFolderPhase("ready");
    } catch (err) {
      setFolderPhase("idle");
      setError(scanFailure(err));
    } finally {
      setScanning(false);
      setBusy(false);
    }
  }

  async function onScan() {
    if (!project) {
      setError("No folder selected.");
      return;
    }
    if (busy) return;
    setBusy(true);
    setScanning(true);
    setError(null);
    setFolderPhase("scanning");
    try {
      const scanned = await scanProject(project.id);
      setRepoMap(scanned);
      setProject({ ...project, project_type: scanned.project_type });
      setFolderPhase("ready");
    } catch (err) {
      setFolderPhase("idle");
      setError(scanFailure(err));
    } finally {
      setScanning(false);
      setBusy(false);
    }
  }

  async function onRun() {
    const gate = validateAgentSubmission({ prompt, hasProject: Boolean(project) });
    if (!gate.ok) {
      return;
    }
    if (!runLock.current.tryAcquire()) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const created = await startTask(project!.id, gate.prompt, mode, problemDescription);
      window.sessionStorage.setItem(LAST_TASK_STORAGE_KEY, String(created.id));
      setTask(created);
      setDiff("");
    } catch (err) {
      runLock.current.release();
      setBusy(false);
      if (err instanceof ApiError && err.isValidation && err.field === "prompt") {
        return;
      }
      setError(friendlyError(err));
    }
  }

  const changedFiles = task?.report?.files_changed ?? [];
  const terminalLines = events
    .filter((item) => item.event.startsWith("command") || item.event.startsWith("test") || item.event === "tool_completed")
    .map((item) => item.message);

  return (
    <div className="app">
      <Header llmReady={llmReady} backendOk={backendOk} model={model} projectName={project?.name} />
      {error ? (
        <div className="banner error" role="alert">
          {error}
        </div>
      ) : null}
      {backendOk && llmReady === false ? (
        <div className="banner warn" role="status">
          LLM unavailable. Configure the server API key in `.env` and restart the backend.
        </div>
      ) : null}
      <div className="workspace">
        <aside className="sidebar">
          <ProjectSelector
            projects={projects}
            project={project}
            repoMap={repoMap}
            busy={busy}
            scanning={scanning}
            folderPhase={folderPhase}
            manualPath={manualPath}
            onManualPath={setManualPath}
            onSelectExisting={onSelectExisting}
            onSelectFolder={onSelectFolder}
            onWebkitFiles={onWebkitFiles}
            onManualRegister={onManualRegister}
            onScan={onScan}
          />
          <RepositoryTree repoMap={repoMap} scanning={scanning} />
        </aside>
        <main className="center">
          <ProjectOverview project={project} repoMap={repoMap} agentStatus={task?.status || "idle"} />
          <TaskPanel
            prompt={prompt}
            problemDescription={problemDescription}
            mode={mode}
            busy={busy}
            hasProject={Boolean(project)}
            onPrompt={setPrompt}
            onProblemDescription={setProblemDescription}
            onMode={setMode}
            onRun={onRun}
            onCancel={() => task && cancelTask(task.id)}
          />
          <div ref={diffRef}>
            <DiffViewer diff={diff} />
          </div>
          <FinalResult
            task={task}
            onRollback={async () => {
              if (!task) return;
              try {
                await rollbackTask(task.id);
                setDiff("");
              } catch (err) {
                setError(friendlyError(err));
              }
            }}
            onViewDiff={() => diffRef.current?.scrollIntoView({ behavior: "smooth" })}
          />
        </main>
        <aside className="right">
          <AgentActivity events={events} />
          <AgentPlan plan={plan} />
          <FilesChanged files={changedFiles} />
          <TerminalPanel lines={terminalLines} />
        </aside>
      </div>
    </div>
  );
}

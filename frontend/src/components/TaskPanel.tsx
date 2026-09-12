import type { FormEvent, KeyboardEvent } from "react";
import type { AgentMode } from "../types";
import { canRunAgent, REPO_REQUIRED, TASK_TOO_SHORT, isValidTaskPrompt } from "../utils/taskValidation";

interface Props {
  prompt: string;
  problemDescription: string;
  mode: AgentMode;
  busy: boolean;
  hasProject: boolean;
  onPrompt: (value: string) => void;
  onProblemDescription: (value: string) => void;
  onMode: (mode: AgentMode) => void;
  onRun: () => void;
  onCancel: () => void;
}

const MODES: { id: AgentMode; label: string }[] = [
  { id: "implement", label: "Implement" },
  { id: "review", label: "Code Review" },
  { id: "explain", label: "Explain" },
  { id: "issue", label: "Issue" },
];

export function TaskPanel({
  prompt,
  problemDescription,
  mode,
  busy,
  hasProject,
  onPrompt,
  onProblemDescription,
  onMode,
  onRun,
  onCancel,
}: Props) {
  const canSubmit = canRunAgent({ prompt, hasProject, busy });
  const taskInvalid = !isValidTaskPrompt(prompt);

  function submit() {
    onRun();
  }

  function onFormSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function onTaskKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  }

  return (
    <section className="panel stack">
      <h2>AI Task</h2>
      <form onSubmit={onFormSubmit}>
        <div className="modes">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`btn ${item.id === mode ? "active" : ""}`}
              onClick={() => onMode(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <label className="field-label" htmlFor="task-prompt">
          Task
        </label>
        <textarea
          id="task-prompt"
          rows={4}
          value={prompt}
          onChange={(event) => onPrompt(event.target.value)}
          onKeyDown={onTaskKeyDown}
          placeholder="Describe what you want CodePilot to do..."
          aria-label="Task"
          aria-invalid={taskInvalid}
          aria-describedby={taskInvalid ? "task-prompt-error" : undefined}
        />
        {taskInvalid ? (
          <p id="task-prompt-error" className="field-error" role="alert">
            ⚠ {TASK_TOO_SHORT}
          </p>
        ) : null}
        <label className="field-label" htmlFor="problem-description">
          Problem description (optional)
        </label>
        <textarea
          id="problem-description"
          rows={4}
          value={problemDescription}
          onChange={(event) => onProblemDescription(event.target.value)}
          placeholder="Describe the error or problem..."
          aria-label="Problem description (optional)"
        />
        {!hasProject ? (
          <p className="field-error" role="alert">
            ⚠ {REPO_REQUIRED}
          </p>
        ) : null}
        <div className="row">
          <button className="btn primary" type="submit" disabled={!canSubmit}>
            Run Agent
          </button>
          <button className="btn" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

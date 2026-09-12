interface Props {
  llmReady: boolean | null;
  backendOk: boolean;
  model?: string;
  projectName?: string;
}

export function Header({ llmReady, backendOk, model, projectName }: Props) {
  return (
    <header className="topbar">
      <div>
        <div className="brand">CODEPILOT AI</div>
        <div className="subtitle">Autonomous AI Coding Agent</div>
      </div>
      <div className="status-row" aria-live="polite">
        <span className="pill">{projectName ? `Project · ${projectName}` : "No project"}</span>
        <span className={`pill ${backendOk ? "ok" : "bad"}`}>{backendOk ? "API online" : "API offline"}</span>
        <span className={`pill ${llmReady ? "ok" : llmReady === false ? "warn" : ""}`}>
          {llmReady
            ? `LLM · ${model || "ready"}`
            : llmReady === false
              ? "LLM key missing"
              : "LLM waiting"}
        </span>
      </div>
    </header>
  );
}

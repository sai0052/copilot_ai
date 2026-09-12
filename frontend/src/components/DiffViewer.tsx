import { parseUnifiedDiff } from "../utils/format";

export function DiffViewer({ diff }: { diff: string }) {
  const files = parseUnifiedDiff(diff);
  return (
    <section className="panel">
      <h2>Diff</h2>
      {!diff.trim() ? (
        <div className="empty">Diff will appear after the agent edits files.</div>
      ) : (
        files.map((file) => (
          <div key={file.name} className="diff-file">
            <div className="diff-name">{file.name}</div>
            <div className="diff">
              {file.lines.map((line, index) => (
                <div key={index} className={`diff-line ${line.type}`}>
                  <span className="n">{line.oldNo ?? ""}</span>
                  <span className="n">{line.newNo ?? ""}</span>
                  <span>{line.text}</span>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </section>
  );
}

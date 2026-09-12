export function TerminalPanel({ lines }: { lines: string[] }) {
  return (
    <section className="panel">
      <h2>Terminal</h2>
      <pre className="terminal">{lines.join("\n") || "$ waiting"}</pre>
    </section>
  );
}

export function DiffPanel({ diff }: { diff: string }) {
  return (
    <section className="card">
      <h2>Diff</h2>
      <pre className="diff">{diff || "Diff will appear after git-aware changes."}</pre>
    </section>
  );
}

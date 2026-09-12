export function FilesChanged({ files }: { files: string[] }) {
  return (
    <section className="panel">
      <h2>Files Changed</h2>
      {files.length === 0 ? (
        <div className="empty">No Changes Yet. CodePilot changes will appear here.</div>
      ) : (
        <ul>
          {files.map((file) => (
            <li key={file}>
              <span aria-hidden>📄</span> {file}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

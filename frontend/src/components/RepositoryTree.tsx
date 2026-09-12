import { useState } from "react";
import type { RepoMap } from "../types";
import { buildTree, type TreeNode } from "../utils/format";

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  if (node.kind === "file") {
    return (
      <div className="tree-item file" style={{ paddingLeft: depth * 14 }}>
        <span aria-hidden>📄</span>
        <span>{node.name}</span>
      </div>
    );
  }
  return (
    <div>
      <button className="btn ghost tree-item" style={{ paddingLeft: depth * 14 }} onClick={() => setOpen((v) => !v)}>
        <span aria-hidden>📁</span>
        <span>{node.name}</span>
      </button>
      {open ? node.children.map((child) => <Node key={child.path} node={child} depth={depth + 1} />) : null}
    </div>
  );
}

export function RepositoryTree({ repoMap, scanning = false }: { repoMap: RepoMap | null; scanning?: boolean }) {
  const nodes = buildTree((repoMap?.files || []).map((item) => item.path));
  return (
    <section className="panel">
      <h2>Repository tree</h2>
      {scanning ? (
        <div className="empty" role="status">
          Scanning repository...
        </div>
      ) : !repoMap ? (
        <div className="empty">Select and scan a project to view files.</div>
      ) : !repoMap.file_count ? (
        <div className="empty">Repository contains no supported project files.</div>
      ) : (
        <div className="tree" role="tree">
          {nodes.map((node) => (
            <Node key={node.path} node={node} depth={0} />
          ))}
        </div>
      )}
    </section>
  );
}

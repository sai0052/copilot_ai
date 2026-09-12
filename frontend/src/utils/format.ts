export const TYPE_LABELS: Record<string, string> = {
  fastapi: "FastAPI",
  flask: "Flask",
  django: "Django",
  react: "React",
  react_vite: "React + Vite",
  vite: "Vite",
  nextjs: "Next.js",
  nodejs: "Node.js",
  python_cli: "Python CLI",
  generic_python: "Python",
  unknown: "Unknown",
};

export function formatDuration(seconds: number | undefined): string {
  const value = Math.max(0, Number(seconds) || 0);
  if (value < 60) return `${value.toFixed(1)}s`;
  const minutes = Math.floor(value / 60);
  const rest = value - minutes * 60;
  return `${minutes}m ${rest.toFixed(0)}s`;
}

export function typeLabel(value: string | undefined): string {
  if (!value) return "Unknown";
  return TYPE_LABELS[value] || value;
}

export interface TreeNode {
  name: string;
  path: string;
  kind: "dir" | "file";
  children: TreeNode[];
}

export function buildTree(paths: string[]): TreeNode[] {
  const root: TreeNode[] = [];
  for (const raw of paths) {
    const parts = raw.replace(/\\/g, "/").split("/").filter(Boolean);
    let level = root;
    let acc = "";
    parts.forEach((part, index) => {
      acc = acc ? `${acc}/${part}` : part;
      const isFile = index === parts.length - 1;
      let node = level.find((item) => item.name === part);
      if (!node) {
        node = { name: part, path: acc, kind: isFile ? "file" : "dir", children: [] };
        level.push(node);
      }
      level = node.children;
    });
  }
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(root);
  return root;
}

export interface DiffLine {
  type: "add" | "del" | "ctx" | "meta" | "hunk";
  text: string;
  oldNo?: number;
  newNo?: number;
}

export interface DiffFile {
  name: string;
  lines: DiffLine[];
}

export function parseUnifiedDiff(diff: string): DiffFile[] {
  if (!diff.trim()) return [];
  const files: DiffFile[] = [];
  let current: DiffFile | null = null;
  let oldNo = 0;
  let newNo = 0;
  for (const raw of diff.split("\n")) {
    if (raw.startsWith("diff --git") || raw.startsWith("--- ") || raw.startsWith("+++ ")) {
      if (raw.startsWith("+++ ") && raw.slice(4).trim() !== "/dev/null") {
        const name = raw.replace(/^\+\+\+\s+[ab]\//, "").trim();
        current = { name, lines: [] };
        files.push(current);
      }
      continue;
    }
    if (!current) continue;
    if (raw.startsWith("@@")) {
      const match = raw.match(/@@ -(\d+)(?:,\d+)? \+(\d+)/);
      oldNo = match ? Number(match[1]) : 0;
      newNo = match ? Number(match[2]) : 0;
      current.lines.push({ type: "hunk", text: raw });
      continue;
    }
    if (raw.startsWith("+")) {
      current.lines.push({ type: "add", text: raw.slice(1), newNo });
      newNo += 1;
    } else if (raw.startsWith("-")) {
      current.lines.push({ type: "del", text: raw.slice(1), oldNo });
      oldNo += 1;
    } else {
      current.lines.push({ type: "ctx", text: raw.slice(0, 1) === " " ? raw.slice(1) : raw, oldNo, newNo });
      oldNo += 1;
      newNo += 1;
    }
  }
  return files;
}

export interface PickedProject {
  name: string;
  files: { path: string; content: string }[];
}

export type PickerStatus = "ok" | "cancelled" | "unavailable" | "unsupported";

export type PickerOutcome =
  | { status: "ok"; project: PickedProject }
  | { status: "cancelled" }
  | { status: "unavailable" }
  | { status: "unsupported" };

const SKIP_DIRS = new Set([".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build"]);
const ACCESS_ERROR = "CodePilot could not access the selected folder.";

async function readDirectoryHandle(
  handle: FileSystemDirectoryHandle,
  prefix = "",
): Promise<{ path: string; content: string }[]> {
  const collected: { path: string; content: string }[] = [];
  for await (const [name, entry] of handle.entries()) {
    if (SKIP_DIRS.has(name) || name.startsWith(".env")) continue;
    const rel = prefix ? `${prefix}/${name}` : name;
    if (entry.kind === "directory") {
      collected.push(...(await readDirectoryHandle(entry as FileSystemDirectoryHandle, rel)));
    } else {
      const file = await (entry as FileSystemFileHandle).getFile();
      if (file.size > 1_048_576) continue;
      collected.push({ path: rel, content: await file.text() });
    }
  }
  return collected;
}

export function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const name = "name" in error ? String((error as { name: unknown }).name) : "";
  return name === "AbortError";
}

function isPermissionFailure(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const name = "name" in error ? String((error as { name: unknown }).name) : "";
  return name === "NotAllowedError" || name === "SecurityError" || name === "NotReadableError";
}

export function isEmbeddedOrRestrictedBrowser(): boolean {
  if (typeof window === "undefined") return true;
  if (!window.isSecureContext) return true;
  try {
    if (window.top !== window.self) return true;
  } catch {
    return true;
  }
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/Electron/i.test(ua)) return true;
  if (typeof (window as Window & { acquireVsCodeApi?: unknown }).acquireVsCodeApi === "function") {
    return true;
  }
  return false;
}

export function directoryPickerSupported(): boolean {
  return typeof window !== "undefined" && typeof window.showDirectoryPicker === "function";
}

export function directoryPickerUsable(): boolean {
  return directoryPickerSupported() && !isEmbeddedOrRestrictedBrowser();
}

/** Abort without a native dialog is an API limitation, not a user cancel. */
export function classifyPickerAbort(nativeUiObserved: boolean): "cancelled" | "unavailable" {
  return nativeUiObserved ? "cancelled" : "unavailable";
}

export function watchNativeDialog(): { observed: () => boolean; stop: () => void } {
  let seen = false;
  const mark = () => {
    seen = true;
  };
  if (typeof window === "undefined") {
    return { observed: () => false, stop: () => undefined };
  }
  window.addEventListener("blur", mark);
  document.addEventListener("visibilitychange", mark);
  return {
    observed: () => seen,
    stop: () => {
      window.removeEventListener("blur", mark);
      document.removeEventListener("visibilitychange", mark);
    },
  };
}

export async function pickWithDirectoryPicker(): Promise<PickerOutcome> {
  if (!directoryPickerSupported()) return { status: "unsupported" };
  if (!directoryPickerUsable()) return { status: "unavailable" };

  const nativeUi = watchNativeDialog();
  let handle: FileSystemDirectoryHandle;
  try {
    handle = await window.showDirectoryPicker!({ mode: "read" });
  } catch (error) {
    nativeUi.stop();
    if (isAbortError(error)) {
      const kind = classifyPickerAbort(nativeUi.observed());
      console.info("[CodePilot] folder.showDirectoryPicker", { result: kind });
      return { status: kind };
    }
    if (isPermissionFailure(error)) {
      throw new Error(ACCESS_ERROR);
    }
    throw error;
  }
  nativeUi.stop();

  try {
    const permission = await handle.requestPermission?.({ mode: "read" });
    if (permission && permission !== "granted") {
      throw new Error(ACCESS_ERROR);
    }
    const files = await readDirectoryHandle(handle);
    if (!files.length) {
      throw new Error("Repository contains no supported project files.");
    }
    console.info("[CodePilot] folder.selected", { name: handle.name, files: files.length });
    return { status: "ok", project: { name: handle.name, files } };
  } catch (error) {
    if (isAbortError(error) || isPermissionFailure(error)) {
      throw new Error(ACCESS_ERROR);
    }
    throw error;
  }
}

export async function resolveWebkitFiles(list: FileList): Promise<PickedProject> {
  if (!list.length) {
    throw new Error("Repository contains no supported project files.");
  }
  const skip = /(\.git|node_modules|venv|\.venv|__pycache__)(\/|\\)/;
  const files: { path: string; content: string }[] = [];
  let name = "project";
  for (const file of Array.from(list)) {
    const relative = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    if (skip.test(relative) || file.name.startsWith(".env")) continue;
    const parts = relative.replace(/\\/g, "/").split("/");
    if (parts.length > 1) name = parts[0];
    const path = parts.slice(1).join("/") || file.name;
    if (file.size > 1_048_576) continue;
    files.push({ path, content: await file.text() });
  }
  if (!files.length) {
    throw new Error("Repository contains no supported project files.");
  }
  return { name, files };
}

export function isImportedWorkspace(rootPath: string | undefined): boolean {
  return (rootPath || "").replace(/\\/g, "/").toLowerCase().includes("/workspaces/");
}

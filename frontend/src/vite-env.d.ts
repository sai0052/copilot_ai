/// <reference types="vite/client" />

interface Window {
  showDirectoryPicker?: (options?: { mode?: "read" | "readwrite" }) => Promise<FileSystemDirectoryHandle>;
}

interface FileSystemDirectoryHandle {
  name: string;
  entries(): AsyncIterableIterator<[string, FileSystemHandle]>;
  requestPermission?: (options?: { mode?: "read" | "readwrite" }) => Promise<"granted" | "denied" | "prompt">;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

import { afterEach, describe, expect, it, vi } from "vitest";
import { classifyPickerAbort, pickWithDirectoryPicker, resolveWebkitFiles } from "../folderPicker";
import { registrationError, scanFailure, friendlyError, ApiError } from "../errors";
import { workbenchForProject } from "../projectSwitch";

describe("classifyPickerAbort", () => {
  it("treats an instant AbortError as unavailable, not cancellation", () => {
    expect(classifyPickerAbort(20)).toBe("unavailable");
  });

  it("treats a delayed AbortError as genuine cancellation", () => {
    expect(classifyPickerAbort(1200)).toBe("cancelled");
  });
});

describe("pickWithDirectoryPicker", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("returns cancelled only after the native picker was shown", async () => {
    vi.stubGlobal(
      "showDirectoryPicker",
      vi.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 500));
        throw new DOMException("The user aborted a request.", "AbortError");
      }),
    );
    const result = await pickWithDirectoryPicker();
    expect(result.status).toBe("cancelled");
  });

  it("returns unavailable when the picker aborts immediately", async () => {
    vi.stubGlobal(
      "showDirectoryPicker",
      vi.fn(async () => {
        throw new DOMException("The user aborted a request.", "AbortError");
      }),
    );
    const result = await pickWithDirectoryPicker();
    expect(result.status).toBe("unavailable");
  });

  it("returns a selected folder", async () => {
    const file = new File(["print(1)\n"], "main.py");
    vi.stubGlobal(
      "showDirectoryPicker",
      vi.fn(async () => ({
        name: "repo_two",
        requestPermission: async () => "granted",
        entries: async function* () {
          yield [
            "main.py",
            {
              kind: "file",
              getFile: async () => file,
            },
          ];
        },
      })),
    );
    const result = await pickWithDirectoryPicker();
    expect(result.status).toBe("ok");
    if (result.status === "ok") {
      expect(result.project.name).toBe("repo_two");
      expect(result.project.files[0].path).toBe("main.py");
    }
  });

  it("does not treat a read failure after selection as cancellation", async () => {
    vi.stubGlobal(
      "showDirectoryPicker",
      vi.fn(async () => ({
        name: "repo",
        requestPermission: async () => "granted",
        entries: async function* () {
          throw new DOMException("The user aborted a request.", "AbortError");
        },
      })),
    );
    await expect(pickWithDirectoryPicker()).rejects.toThrow("CodePilot cannot access this folder.");
  });

  it("rejects empty folders", async () => {
    vi.stubGlobal(
      "showDirectoryPicker",
      vi.fn(async () => ({
        name: "empty",
        requestPermission: async () => "granted",
        entries: async function* () {},
      })),
    );
    await expect(pickWithDirectoryPicker()).rejects.toThrow("Repository contains no supported project files.");
  });
});

describe("webkit import", () => {
  it("preserves relative paths from webkitRelativePath", async () => {
    const file = new File(["x"], "main.py");
    Object.defineProperty(file, "webkitRelativePath", { value: "demo_fastapi/app/main.py" });
    const list = { 0: file, length: 1, item: (i: number) => (i === 0 ? file : null) } as unknown as FileList;
    const picked = await resolveWebkitFiles(list);
    expect(picked.name).toBe("demo_fastapi");
    expect(picked.files[0].path).toBe("app/main.py");
  });

  it("rejects an empty file list", async () => {
    const list = { length: 0, item: () => null } as unknown as FileList;
    await expect(resolveWebkitFiles(list)).rejects.toThrow("Repository contains no supported project files.");
  });
});

describe("error categories", () => {
  it("maps genuine cancellation", () => {
    expect(friendlyError(new Error("Folder selection was cancelled."))).toBe("Folder selection was cancelled.");
  });

  it("does not call cancellation for registration or scan failures", () => {
    expect(registrationError(new Error("sqlite busy"))).toBe("Repository registration failed: sqlite busy");
    expect(scanFailure(new Error("boom"))).toBe("Repository scan failed: boom");
    expect(registrationError(new ApiError("denied", 403))).toBe("CodePilot cannot access this folder.");
  });

  it("keeps specific path errors", () => {
    expect(registrationError(new Error("Repository path does not exist."))).toBe("Repository path does not exist.");
  });
});

describe("switching repositories", () => {
  it("clears repo A state before loading repo B and back", () => {
    const a = workbenchForProject({
      id: 1,
      name: "repo_two",
      root_path: "C:\\\\repos\\\\two",
      project_type: "generic_python",
    });
    const b = workbenchForProject({
      id: 2,
      name: "repo_three",
      root_path: "C:\\\\repos\\\\three",
      project_type: "generic_python",
    });
    expect(b.project?.id).toBe(2);
    expect(b.repoMap).toBeNull();
    expect(b.task).toBeNull();
    const back = workbenchForProject(a.project!);
    expect(back.project?.id).toBe(1);
    expect(back.diff).toBe("");
  });
});

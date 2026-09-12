import { describe, expect, it } from "vitest";
import { friendlyError } from "../errors";
import { resolveWebkitFiles } from "../folderPicker";
import { buildTree } from "../format";

describe("buildTree", () => {
  it("nests directories", () => {
    const tree = buildTree(["app/main.py", "app/routes/items.py"]);
    expect(tree[0].name).toBe("app");
    expect(tree[0].children.some((child) => child.name === "main.py")).toBe(true);
  });
});

describe("friendlyError", () => {
  it("maps known errors", () => {
    expect(friendlyError(new Error("Project contains too many files (9 > 1)"))).toBe(
      "Project contains too many files.",
    );
    expect(friendlyError(new Error("Repository path does not exist."))).toBe("Repository path does not exist.");
    expect(friendlyError(new Error("LLM HTTP 429 rate limit"))).toBe(
      "Groq rate limit reached. Please wait and try again.",
    );
  });
});

describe("webkit fallback", () => {
  it("reads relative paths", async () => {
    const file = new File(["x"], "main.py");
    Object.defineProperty(file, "webkitRelativePath", { value: "demo_fastapi/app/main.py" });
    const list = { 0: file, length: 1, item: (i: number) => (i === 0 ? file : null) } as unknown as FileList;
    const picked = await resolveWebkitFiles(list);
    expect(picked.name).toBe("demo_fastapi");
    expect(picked.files[0].path).toBe("app/main.py");
  });
});

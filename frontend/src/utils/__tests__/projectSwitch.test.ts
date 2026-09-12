import { describe, expect, it } from "vitest";
import { EMPTY_WORKBENCH, workbenchForProject } from "../projectSwitch";

describe("projectSwitch", () => {
  it("clears previous task and tree when switching projects", () => {
    const next = workbenchForProject({
      id: 2,
      name: "repo_two",
      root_path: "C:\\\\repos\\\\two",
      project_type: "generic_python",
    });
    expect(next.project?.id).toBe(2);
    expect(next.repoMap).toBeNull();
    expect(next.task).toBeNull();
    expect(next.diff).toBe("");
    expect(EMPTY_WORKBENCH.project).toBeNull();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentActivity } from "../AgentActivity";
import { ProjectSelector } from "../ProjectSelector";
import { RepositoryTree } from "../RepositoryTree";
import * as folderPicker from "../../utils/folderPicker";

afterEach(() => cleanup());

const baseProps = {
  projects: [],
  project: null,
  repoMap: null,
  busy: false,
  manualPath: "",
  onManualPath: vi.fn(),
  onSelectExisting: vi.fn(),
  onSelectFolder: vi.fn(),
  onWebkitFiles: vi.fn(),
  onManualRegister: vi.fn(),
  onScan: vi.fn(),
  scanning: false,
};

describe("ProjectSelector", () => {
  it("renders select project folder and empty state", () => {
    render(<ProjectSelector {...baseProps} />);
    expect(screen.getByText("No project selected")).toBeInTheDocument();
    expect(screen.getByTestId("select-folder")).toBeInTheDocument();
    expect(screen.getByTestId("webkit-directory")).toBeInTheDocument();
  });

  it("falls back to the file input when the directory picker is unavailable", async () => {
    const user = userEvent.setup();
    const onSelectFolder = vi.fn().mockResolvedValue("unavailable");
    vi.spyOn(folderPicker, "directoryPickerSupported").mockReturnValue(true);
    render(<ProjectSelector {...baseProps} onSelectFolder={onSelectFolder} />);
    const input = screen.getByTestId("webkit-directory") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");
    await user.click(screen.getByTestId("select-folder"));
    expect(onSelectFolder).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
  });

  it("does not open a second picker after genuine cancellation", async () => {
    const user = userEvent.setup();
    const onSelectFolder = vi.fn().mockResolvedValue("cancelled");
    vi.spyOn(folderPicker, "directoryPickerSupported").mockReturnValue(true);
    render(<ProjectSelector {...baseProps} onSelectFolder={onSelectFolder} />);
    const input = screen.getByTestId("webkit-directory") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");
    await user.click(screen.getByTestId("select-folder"));
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it("invokes folder selection", async () => {
    const user = userEvent.setup();
    const onSelectFolder = vi.fn();
    vi.spyOn(folderPicker, "directoryPickerSupported").mockReturnValue(true);
    render(<ProjectSelector {...baseProps} onSelectFolder={onSelectFolder} />);
    await user.click(screen.getByTestId("select-folder"));
    expect(onSelectFolder).toHaveBeenCalled();
  });

  it("shows scanning state", () => {
    render(<ProjectSelector {...baseProps} scanning />);
    expect(screen.getByText("Scanning repository...")).toBeInTheDocument();
  });

  it("shows selected project name", () => {
    render(
      <ProjectSelector
        {...baseProps}
        project={{ id: 1, name: "demo_fastapi", root_path: "/tmp", project_type: "fastapi" }}
      />,
    );
    expect(screen.getByText("demo_fastapi")).toBeInTheDocument();
    expect(screen.getByText(/FastAPI/)).toBeInTheDocument();
  });

  it("handles webkitdirectory fallback", async () => {
    const user = userEvent.setup();
    const onWebkitFiles = vi.fn();
    render(<ProjectSelector {...baseProps} onWebkitFiles={onWebkitFiles} />);
    const input = screen.getByTestId("webkit-directory") as HTMLInputElement;
    const file = new File(["print(1)"], "main.py", { type: "text/plain" });
    Object.defineProperty(file, "webkitRelativePath", { value: "demo/main.py" });
    await user.upload(input, file);
    expect(onWebkitFiles).toHaveBeenCalled();
  });
});

describe("RepositoryTree", () => {
  it("renders tree after scan", () => {
    render(
      <RepositoryTree
        repoMap={{
          root: "/tmp",
          project_type: "fastapi",
          file_count: 2,
          files: [
            { path: "app/main.py", kind: "python", size: 10 },
            { path: "requirements.txt", kind: "text", size: 8 },
          ],
          tree: "",
          config_files: [],
          test_files: [],
        }}
      />,
    );
    expect(screen.getByText("main.py")).toBeInTheDocument();
    expect(screen.getByText("requirements.txt")).toBeInTheDocument();
  });
});

describe("empty states", () => {
  it("shows activity empty state", () => {
    render(<AgentActivity events={[]} />);
    expect(screen.getByText(/No Agent Activity Yet/)).toBeInTheDocument();
  });
});

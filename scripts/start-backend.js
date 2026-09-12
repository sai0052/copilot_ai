const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const { ROOT, portInUse } = require("./ports");

const PYTHON = path.join(ROOT, ".venv", "Scripts", "python.exe");
const PORT = 8010;

function fail(detail) {
  console.error("Backend failed to start.");
  console.error(detail);
  console.error("Check port 8010 and Python environment.");
  process.exit(1);
}

function killTree(pid) {
  if (!pid) return;
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  } else {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  }
}

async function main() {
  if (!fs.existsSync(PYTHON)) {
    fail(`Virtual environment not found at ${PYTHON}`);
  }
  if (await portInUse(PORT)) {
    fail("Port 8010 is already in use.");
  }
  const child = spawn(
    PYTHON,
    ["-m", "uvicorn", "app.main:app", "--reload", "--reload-dir", "backend", "--app-dir", "backend", "--host", "127.0.0.1", "--port", String(PORT)],
    {
      cwd: ROOT,
      env: { ...process.env, PYTHONPATH: path.join(ROOT, "backend") },
      stdio: "inherit",
      windowsHide: false,
    },
  );
  const stop = () => killTree(child.pid);
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  child.on("exit", (code) => {
    process.exit(code === 0 ? 0 : 1);
  });
}

main().catch((error) => fail(error.message || String(error)));

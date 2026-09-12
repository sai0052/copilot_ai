const { spawn } = require("child_process");
const { ROOT, portInUse, waitForHealth, waitForPort } = require("./ports");

function printBanner() {
  console.log("");
  console.log("CodePilot development environment starting...");
  console.log("");
  console.log("Frontend:");
  console.log("http://localhost:5174");
  console.log("");
  console.log("Backend:");
  console.log("http://127.0.0.1:8010");
  console.log("");
  console.log("Health:");
  console.log("http://127.0.0.1:8010/health");
  console.log("");
}

function killTree(pid) {
  if (!pid) return;
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  } else {
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      try {
        process.kill(pid, "SIGTERM");
      } catch {
        /* already gone */
      }
    }
  }
}

async function main() {
  printBanner();
  if (await portInUse(8010)) {
    console.error("Backend failed to start.");
    console.error("Port 8010 is already in use.");
    console.error("Check port 8010 and Python environment.");
    process.exit(1);
  }
  if (await portInUse(5174)) {
    console.error("Frontend failed to start.");
    console.error("Port 5174 is already in use.");
    console.error("Check port 5174 and Node/npm installation.");
    process.exit(1);
  }

  const backend = spawn(process.execPath, ["scripts/start-backend.js"], {
    cwd: ROOT,
    stdio: "inherit",
    windowsHide: false,
  });
  const frontend = spawn(process.execPath, ["scripts/start-frontend.js"], {
    cwd: ROOT,
    stdio: "inherit",
    windowsHide: false,
  });

  let stopping = false;
  const stopAll = (code = 1) => {
    if (stopping) return;
    stopping = true;
    killTree(backend.pid);
    killTree(frontend.pid);
    setTimeout(() => process.exit(code), 300);
  };

  backend.on("exit", (code) => {
    if (stopping) return;
    if (code !== 0) {
      console.error("Backend failed to start.");
      console.error("Check port 8010 and Python environment.");
    }
    stopAll(code || 1);
  });
  frontend.on("exit", (code) => {
    if (stopping) return;
    if (code !== 0) {
      console.error("Frontend failed to start.");
      console.error("Check port 5174 and Node/npm installation.");
    }
    stopAll(code || 1);
  });

  process.on("SIGINT", () => stopAll(0));
  process.on("SIGTERM", () => stopAll(0));

  try {
    await waitForHealth(30000);
    await waitForPort(5174, 30000);
  } catch (error) {
    console.error(error.message);
    console.error("CodePilot did not become ready.");
    stopAll(1);
    return;
  }
  console.log("");
  console.log("CodePilot is ready.");
  console.log("Open http://localhost:5174");
  console.log("");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

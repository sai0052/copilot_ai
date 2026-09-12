const { spawn } = require("child_process");
const { ROOT, portInUse } = require("./ports");

const PORT = 5174;

function fail(detail) {
  console.error("Frontend failed to start.");
  console.error(detail);
  console.error("Check port 5174 and Node/npm installation.");
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
  if (await portInUse(PORT)) {
    fail("Port 5174 is already in use.");
  }
  const child = spawn("npm run dev", {
    cwd: require("path").join(ROOT, "frontend"),
    env: { ...process.env, VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8010" },
    stdio: "inherit",
    windowsHide: false,
    shell: true,
  });
  const stop = () => killTree(child.pid);
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  child.on("exit", (code) => {
    process.exit(code === 0 ? 0 : 1);
  });
}

main().catch((error) => fail(error.message || String(error)));

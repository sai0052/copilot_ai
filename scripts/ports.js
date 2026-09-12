const net = require("net");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function portInUse(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: "127.0.0.1" });
    socket.setTimeout(500);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(false));
  });
}

function waitForPort(port, timeoutMs) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      portInUse(port).then((open) => {
        if (open) return resolve();
        if (Date.now() - started > timeoutMs) {
          return reject(new Error(`Timed out waiting for port ${port}`));
        }
        setTimeout(tick, 400);
      });
    };
    tick();
  });
}

function waitForHealth(timeoutMs) {
  const http = require("http");
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get("http://127.0.0.1:8010/health", (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode === 200 && body.includes("codepilot-ai")) {
            return resolve(body);
          }
          retry();
        });
      });
      req.on("error", retry);
      req.setTimeout(1500, () => {
        req.destroy();
        retry();
      });
    };
    function retry() {
      if (Date.now() - started > timeoutMs) {
        return reject(new Error("Timed out waiting for GET /health"));
      }
      setTimeout(tick, 400);
    }
    tick();
  });
}

module.exports = { ROOT, portInUse, waitForPort, waitForHealth };

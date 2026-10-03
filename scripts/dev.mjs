// Cross-platform dev runner: starts the API (uvicorn, auto-reload) and the Next.js dev server together.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const win = process.platform === "win32";
const venvPy = path.join(root, ".venv", win ? "Scripts" : "bin", win ? "python.exe" : "python");
const py = fs.existsSync(venvPy) ? venvPy : win ? "python" : "python3";
const env = { ...process.env };
if (fs.existsSync(path.join(root, ".env"))) {
  for (const line of fs.readFileSync(path.join(root, ".env"), "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !m[1].startsWith("#") && env[m[1]] === undefined) env[m[1]] = m[2].replace(/^"|"$/g, "");
  }
}
const procs = [
  spawn(py, ["-m", "uvicorn", "editor.api:app", "--port", env.API_PORT ?? "8000", "--reload", "--reload-dir", "editor", "--no-access-log"], {
    cwd: path.join(root, "services", "engine"), env, stdio: "inherit",
  }),
  spawn(win ? "npm.cmd" : "npm", ["run", "dev"], { cwd: path.join(root, "apps", "web"), env, stdio: "inherit", shell: win }),
];
const stop = () => procs.forEach((p) => p.kill());
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
procs.forEach((p) => p.on("exit", (c) => (c ? (stop(), process.exit(c)) : null)));

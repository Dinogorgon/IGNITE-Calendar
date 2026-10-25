// Local stand-in for Vercel: serves docs/ and runs the api/ functions, so the
// officer login can be tested on your computer before pushing.
//
//     node dev-server.js          then open http://localhost:3000
//
// Settings come from .env (same names as the Vercel environment variables).
// Login links in the email point back to localhost while this is running, and
// "Update now" runs update.py here rather than on GitHub.
const fs = require("fs");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const PORT = Number(process.env.PORT) || 3000;
const ROOT = __dirname;
const DOCS = path.join(ROOT, "docs");
const TYPES = { ".html": "text/html; charset=utf-8", ".json": "application/json", ".ics": "text/calendar",
                ".png": "image/png", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml" };

// Load .env without overwriting variables already set in the shell.
const envFile = path.join(ROOT, ".env");
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !line.trimStart().startsWith("#") && !(m[1] in process.env))
      process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}
process.env.SITE_URL = `http://localhost:${PORT}`;  // emailed links come back here

function withHelpers(res) {
  res.status = (code) => { res.statusCode = code; return res; };
  res.json = (body) => {
    if (!res.headersSent) res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(body));
  };
  return res;
}

async function runApi(name, req, res, url) {
  const file = path.join(ROOT, "api", `${name}.js`);
  if (name.startsWith("_") || !fs.existsSync(file)) return withHelpers(res).status(404).json({ error: "Not found" });
  let raw = "";
  for await (const chunk of req) raw += chunk;
  try { req.body = raw ? JSON.parse(raw) : {}; } catch { req.body = {}; }
  req.query = Object.fromEntries(url.searchParams);
  delete require.cache[require.resolve(file)];  // pick up edits without restarting
  delete require.cache[require.resolve(path.join(ROOT, "api", "_auth.js"))];
  try {
    await require(file)(req, withHelpers(res));
  } catch (err) {
    console.error(err);
    if (!res.headersSent) res.status(500).json({ error: err.message });
  }
  console.log(`${req.method} /api/${name} -> ${res.statusCode}`);
}

// "Update now" runs update.py on this computer instead of starting the GitHub
// workflow, so local tests never touch the live site. Login is still required.
let updating = false;
function runLocalUpdate(req, res) {
  delete require.cache[require.resolve(path.join(ROOT, "api", "_auth.js"))];
  const { currentUser } = require("./api/_auth");
  res = withHelpers(res);
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  if (!currentUser(req)) return res.status(401).json({ error: "Log in first" });
  if (updating) return res.status(202).json({ started: true });
  updating = true;
  const py = process.platform === "win32" ? "python" : "python3";
  const child = spawn(py, ["update.py"], { cwd: ROOT, stdio: "inherit" });
  child.on("error", (err) => { updating = false; console.error(`Couldn't run ${py}: ${err.message}`); });
  child.on("exit", (code) => { updating = false; console.log(`update.py finished (exit ${code})`); });
  console.log("POST /api/update -> 202 (running update.py)");
  res.status(202).json({ started: true });
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname.replace(/\/$/, "") === "/api/update") return runLocalUpdate(req, res);
  if (url.pathname.startsWith("/api/")) return runApi(url.pathname.slice(5).replace(/\/$/, ""), req, res, url);
  let file = path.normalize(path.join(DOCS, decodeURIComponent(url.pathname)));
  if (!file.startsWith(DOCS)) { res.statusCode = 403; return res.end(); }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  if (!fs.existsSync(file)) { res.statusCode = 404; return res.end("Not found"); }
  res.setHeader("Content-Type", TYPES[path.extname(file)] || "application/octet-stream");
  fs.createReadStream(file).pipe(res);
}).listen(PORT, "127.0.0.1", () => {
  const set = (k) => (process.env[k] ? "set" : "MISSING");
  console.log(`IGNITE dev server: http://localhost:${PORT}  (Ctrl+C to stop)`);
  console.log(`  RESEND_API_KEY ${set("RESEND_API_KEY")} · SESSION_SECRET ${set("SESSION_SECRET")} · ` +
              `ADMIN_EMAILS ${process.env.ADMIN_EMAILS || "(default) peyton.decker@ufl.edu"} · ` +
              `MAIL_FROM ${process.env.MAIL_FROM || "(default) onboarding@resend.dev"}`);
});

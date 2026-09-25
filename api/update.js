// "Update now" on the hosted site: checks the passcode, then starts the GitHub
// Actions workflow that runs update.py and commits the new calendar. Vercel
// redeploys automatically when that commit lands (~2 minutes total).
//
// Vercel environment variables:
//   UPDATE_PASSCODE  any passcode you choose (officers type it once per browser)
//   GITHUB_TOKEN     fine-grained token with "Actions: Read and write" on this repo
//   GITHUB_REPO      e.g. "your-username/ignite-events"
const crypto = require("crypto");

function same(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const { UPDATE_PASSCODE, GITHUB_TOKEN, GITHUB_REPO } = process.env;
  if (!UPDATE_PASSCODE || !GITHUB_TOKEN || !GITHUB_REPO)
    return res.status(500).json({ error: "Server not configured (see README)" });
  if (!same(req.headers["x-passcode"] || "", UPDATE_PASSCODE))
    return res.status(401).json({ error: "Wrong passcode" });

  const r = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/update.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "ignite-event-coordinator",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (r.status !== 204) return res.status(502).json({ error: `GitHub said ${r.status}: ${await r.text()}` });
  res.status(202).json({ started: true });
};

// "Update now" on the hosted site (logged-in officers only): starts the GitHub
// Actions workflow that runs update.py and commits the new calendar. Vercel
// redeploys automatically when that commit lands (~2 minutes total).
//
// Vercel environment variables:
//   GITHUB_TOKEN  fine-grained token with "Actions: Read and write" on this repo
//   GITHUB_REPO   e.g. "Dinogorgon/IGNITE-Calendar"
const { currentUser } = require("./_auth");

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  if (!currentUser(req)) return res.status(401).json({ error: "Log in first" });
  const { GITHUB_TOKEN, GITHUB_REPO } = process.env;
  if (!GITHUB_TOKEN || !GITHUB_REPO) return res.status(500).json({ error: "Server not configured (see README)" });

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

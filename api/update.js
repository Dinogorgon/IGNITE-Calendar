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
  const missing = ["GITHUB_TOKEN", "GITHUB_REPO"].filter(k => !process.env[k]);
  if (missing.length)
    return res.status(500).json({ error: `${missing.join(" and ")} not set in Vercel → Settings → Environment Variables (then redeploy)` });

  const r = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/update.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "ignite-event-coordinator",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (r.status !== 204) {
    const hint = { 401: "GITHUB_TOKEN is invalid or expired; create a new one.",
                   403: "GITHUB_TOKEN needs the \"Actions: Read and write\" permission.",
                   404: `GITHUB_TOKEN can't see ${GITHUB_REPO}; give it access to that repo and check GITHUB_REPO.` }[r.status];
    return res.status(502).json({ error: hint || `GitHub said ${r.status}: ${await r.text()}` });
  }
  res.status(202).json({ started: true });
};

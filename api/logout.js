// POST: clear the session cookie.
const { clearedCookie } = require("./_auth");

module.exports = (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  res.setHeader("Set-Cookie", clearedCookie);
  res.status(200).json({ ok: true });
};

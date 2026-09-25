// GET ?t=<link token> (the link from the email): sets the session cookie and returns to the site.
const { readToken, sessionCookie } = require("./_auth");

module.exports = (req, res) => {
  let email = null;
  try { email = readToken("link", String((req.query || {}).t || "")); } catch (err) { console.error(err); }
  if (email) res.setHeader("Set-Cookie", sessionCookie(email));
  res.setHeader("Cache-Control", "no-store");
  res.writeHead(302, { Location: email ? "/?login=ok" : "/?login=expired" });
  res.end();
};

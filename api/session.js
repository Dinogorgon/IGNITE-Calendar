// GET: who is logged in (the page uses this to show or hide the officer tools).
const { currentUser } = require("./_auth");

module.exports = (req, res) => {
  const email = currentUser(req);
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({ admin: Boolean(email), email });
};

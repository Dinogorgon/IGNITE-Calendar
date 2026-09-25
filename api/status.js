// Tells the page it's running on Vercel, so "Update now" uses /api/update.
module.exports = (req, res) => res.status(200).json({ mode: "hosted" });

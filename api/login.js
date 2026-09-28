// POST {email}: if the address is allowed, email it a one-time login link.
// The response never reveals whether an address is allowed.
//
// Vercel environment variables:
//   RESEND_API_KEY  from resend.com (free tier)
//   MAIL_FROM       e.g. "IGNITE Events <login@peytondecker.me>" (domain verified in Resend).
//                   Default "onboarding@resend.dev" only delivers to the Resend account's own email.
//   SITE_URL        optional, e.g. "https://gnvevents.peytondecker.me"
const { allowedEmails, makeToken, LINK_MINUTES } = require("./_auth");

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const email = String((req.body || {}).email || "").trim().toLowerCase();
  const reply = { ok: true, message: "If that address is allowed, a login link is on its way. Check your UF inbox (and Quarantine/Junk)." };
  if (!email.endsWith("@ufl.edu")) return res.status(400).json({ error: "Use your @ufl.edu email." });
  if (!allowedEmails().includes(email)) return res.status(200).json(reply);

  try {
    const site = process.env.SITE_URL || `https://${req.headers.host}`;
    const link = `${site}/api/verify?t=${encodeURIComponent(makeToken("link", email, LINK_MINUTES * 60e3))}`;
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${process.env.RESEND_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from: process.env.MAIL_FROM || "IGNITE Events <onboarding@resend.dev>",
        to: [email],
        subject: "Your IGNITE Events login link",
        text: `Log in to the IGNITE events calendar (link works for ${LINK_MINUTES} minutes):\n\n${link}\n\nIf you didn't ask for this, ignore this email.`,
        html: `<div style="font-family:Arial,sans-serif;max-width:420px;margin:auto;text-align:center;color:#18202f">
  <img src="${site}/logo.png" alt="IGNITE" width="72" height="72" style="margin:16px auto 8px">
  <h2 style="color:#2f4a7d;margin:0 0 8px">IGNITE Events</h2>
  <p>Click below to log in to the officer view.</p>
  <p><a href="${link}" style="display:inline-block;background:#2f4a7d;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;border-bottom:3px solid #e7aa35">Log in</a></p>
  <p style="color:#5d677a;font-size:13px">This link works for ${LINK_MINUTES} minutes. If you didn't ask for it, ignore this email.</p>
</div>`,
      }),
    });
    if (!r.ok) throw new Error(`Resend ${r.status}: ${await r.text()}`);
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Couldn't send the email. Check RESEND_API_KEY / MAIL_FROM / SESSION_SECRET in Vercel." });
  }
  res.status(200).json(reply);
};

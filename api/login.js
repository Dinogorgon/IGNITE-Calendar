// POST {email}: if the address is allowed, email it a one-time login link.
// The response never reveals whether an address is allowed.
//
// Vercel environment variables:
//   RESEND_API_KEY  from resend.com (free tier)
//   MAIL_FROM       e.g. "IGNITE Events <login@peytondecker.me>" (domain verified in Resend).
//                   Default "onboarding@resend.dev" only delivers to the Resend account's own email.
//   SITE_URL        optional, e.g. "https://gnvevents.peytondecker.me"
const { allowedEmails, makeToken, LINK_MINUTES } = require("./_auth");

// Turn a setup problem into a message that says what to fix. These only reach
// someone typing an allowed address, so they don't help an outsider.
function explain(status, detail) {
  const d = String(detail || "");
  if (/only send testing emails to your own email/i.test(d))
    return "Resend will only deliver from onboarding@resend.dev to the email you signed up to Resend with. " +
           "Either sign up to Resend with your @ufl.edu address, or verify your domain in Resend and set MAIL_FROM.";
  if (/domain is not verified|not verified/i.test(d))
    return "The domain in MAIL_FROM isn't verified in Resend yet (Resend → Domains). Finish verification, or remove MAIL_FROM to use the test sender.";
  if (status === 401 || status === 403 && /api key/i.test(d))
    return "RESEND_API_KEY is missing or invalid. Create a key in Resend → API Keys.";
  if (/from/i.test(d) && status === 422)
    return 'MAIL_FROM is malformed. Use the form: IGNITE Events <login@yourdomain.com>';
  return `Resend rejected the email (${status}): ${d.slice(0, 300)}`;
}

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const email = String((req.body || {}).email || "").trim().toLowerCase();
  const reply = { ok: true, message: "If that address is allowed, a login link is on its way. Check your UF inbox (and Quarantine/Junk)." };
  if (!email.endsWith("@ufl.edu")) return res.status(400).json({ error: "Use your @ufl.edu email." });
  if (!allowedEmails().includes(email)) return res.status(200).json(reply);

  if (!process.env.RESEND_API_KEY)
    return res.status(500).json({ error: "RESEND_API_KEY isn't set. Add it (Vercel → Settings → Environment Variables, or .env locally) and redeploy." });
  if (!process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32)
    return res.status(500).json({ error: "SESSION_SECRET is missing or shorter than 32 characters." });

  try {
    const host = req.headers.host || "";
    const proto = req.headers["x-forwarded-proto"] || (/^(localhost|127\.0\.0\.1)(:|$)/.test(host) ? "http" : "https");
    const site = (process.env.SITE_URL || `${proto}://${host}`).replace(/\/$/, "");
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
    if (!r.ok) {
      let detail = await r.text();
      try { detail = JSON.parse(detail).message || detail; } catch {}
      console.error("Resend error", r.status, detail);
      return res.status(502).json({ error: explain(r.status, detail) });
    }
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: `Couldn't reach Resend: ${err.message}` });
  }
  res.status(200).json(reply);
};

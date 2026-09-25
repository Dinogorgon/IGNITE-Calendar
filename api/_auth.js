// Shared login helpers (files starting with "_" are not routes on Vercel).
//
// Login is a one-time email link: /api/login emails a signed link to an allowed
// address, /api/verify turns it into a signed session cookie. Nothing is stored
// server-side; tokens are HMAC-signed with SESSION_SECRET.
//
// Vercel environment variables:
//   SESSION_SECRET  long random string (changing it logs everyone out)
//   ADMIN_EMAILS    comma-separated @ufl.edu addresses allowed to log in
//                   (default: peyton.decker@ufl.edu)
const crypto = require("crypto");

const COOKIE = "ignite_session";
const SESSION_DAYS = 30;
const LINK_MINUTES = 15;

function secret() {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 32) throw new Error("SESSION_SECRET is missing or shorter than 32 characters");
  return s;
}

function allowedEmails() {
  return (process.env.ADMIN_EMAILS || "peyton.decker@ufl.edu")
    .split(",").map(e => e.trim().toLowerCase())
    .filter(e => e.endsWith("@ufl.edu"));  // UF addresses only
}

function sign(purpose, payload) {
  return crypto.createHmac("sha256", secret()).update(`${purpose}|${payload}`).digest("base64url");
}

function makeToken(purpose, email, ttlMs) {
  const payload = `${email}|${Date.now() + ttlMs}`;
  return `${Buffer.from(payload).toString("base64url")}.${sign(purpose, payload)}`;
}

// Returns the email if the token is valid, unexpired, and still on the allowlist.
function readToken(purpose, token) {
  if (typeof token !== "string" || !token.includes(".")) return null;
  const [encoded, sig] = token.split(".");
  const payload = Buffer.from(encoded, "base64url").toString();
  const a = Buffer.from(sig), b = Buffer.from(sign(purpose, payload));
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  const [email, expires] = payload.split("|");
  if (!(Number(expires) > Date.now())) return null;
  return allowedEmails().includes(email) ? email : null;
}

function currentUser(req) {
  const cookies = Object.fromEntries((req.headers.cookie || "").split(";").map(c => {
    const i = c.indexOf("=");
    return [c.slice(0, i).trim(), decodeURIComponent(c.slice(i + 1).trim())];
  }));
  try { return readToken("session", cookies[COOKIE]); } catch { return null; }
}

const sessionCookie = (email) =>
  `${COOKIE}=${makeToken("session", email, SESSION_DAYS * 864e5)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${SESSION_DAYS * 86400}`;
const clearedCookie = `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;

module.exports = { allowedEmails, makeToken, readToken, currentUser, sessionCookie, clearedCookie, LINK_MINUTES };

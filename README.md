# IGNITE Event Coordinator

Pulls Gainesville entrepreneurship and innovation events from several sources into one
calendar, removes duplicates, and writes ready-to-paste Slack posts.

## Sources

| Source | How it's read |
|---|---|
| UF Innovate | calendar.ufl.edu JSON feed |
| startGNV (also lists CIED, aiGNV, some UF Innovate) | startgnv.com events API |
| Women in Tech & Entrepreneurship – Gainesville | Eventbrite collection page |
| aiGNV / GNV.AI | gnv.ai's public event database (monthly events are expanded) |
| startGNV on Eventbrite | Eventbrite organizer page |
| GatorConnect (every UF club) | Public events API, filtered by club name + keywords |
| Anything else (e.g. Instagram) | Type it into `manual_events.toml` |

Add or remove sources in `config.toml`. When the same event shows up in several
places (same day, starts within an hour, similar title or same venue), it's merged into one entry
that links to every place it was found.

## Run it on your computer

PowerShell, first time:

```powershell
cd "C:\Users\dinob\Desktop\Claude\Claude Code\IGNITE Event Coordinator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env                # then paste your Gemini key into .env
python serve.py                       # opens http://localhost:8321
```

After that:

```powershell
cd "C:\Users\dinob\Desktop\Claude\Claude Code\IGNITE Event Coordinator"
.\.venv\Scripts\Activate.ps1
python serve.py        # calendar with a working Update button (Ctrl+C to stop)
python update.py       # or: just collect events, no web page
```

(Double-clicking `start.bat` also works without the venv.)

On the page:
- **Update now**: re-collects everything (about a minute).
- Click an event to see details, the Slack post (editable), and **Copy**.
- **Copy 2-week Slack digest**: one post covering the next 14 days (respects the club filters).
- Click the colored club chips to hide or show a club.

## Host it on Vercel (your domain, update from anywhere)

How it works: Vercel serves `docs/` as the website. A GitHub Action runs `update.py`
on the 1st and 15th of each month and commits the new calendar, and Vercel redeploys
automatically.

Visitors get a view-only calendar. **Officer login** emails a one-time link to allowed
`@ufl.edu` addresses. Once logged in (for 30 days), officers see the Slack posts, the
2-week digest, and **Update now**, which starts that same GitHub Action. The server
re-checks the login on every update.

1. Push this folder to a GitHub repo. `.env` is git-ignored, so your key stays private.
2. GitHub repo → **Settings → Secrets and variables → Actions** → add `GEMINI_API_KEY`.
3. Create a GitHub **fine-grained token** (Settings → Developer settings → Personal access
   tokens) with access to only this repo and **Actions: Read and write**.
4. On vercel.com: **Add New → Project** → import the repo (settings come from `vercel.json`).
   Under **Environment Variables**, add:
   - `GITHUB_TOKEN`: the token from step 3
   - `GITHUB_REPO`: `Dinogorgon/IGNITE-Calendar` (or wherever the repo lives now)
   - `ADMIN_EMAILS`: who can log in, comma-separated, `@ufl.edu` only (e.g. `peyton.decker@ufl.edu`)
   - `SESSION_SECRET`: a long random string. In PowerShell:
     `[Convert]::ToBase64String((1..48 | % { Get-Random -Max 256 }))`
   - `RESEND_API_KEY`: from [resend.com](https://resend.com) (free), which sends the login emails
   - `MAIL_FROM`: `IGNITE Events <login@peytondecker.me>` after verifying your domain in
     Resend. Without it, emails come from `onboarding@resend.dev`, which only delivers to
     the email you signed up to Resend with.
   - `SITE_URL`: `https://gnvevents.peytondecker.me`

   Redeploy after changing environment variables (Deployments → ⋯ → Redeploy).
5. Vercel → Project → **Settings → Domains** to add your domain.
6. Google Calendar → *Other calendars → From URL* → `https://your-domain/events.ics`.
   Anyone in the club can subscribe, and it stays in sync.

## For future officers

Welcome! Most of this runs by itself. Here's what you need to know.

**Normal use (no code):**
- Click **Officer login**, enter your UF email, and click the link that arrives in your inbox
  (check Quarantine/Junk the first time). You stay logged in for 30 days.
- Once logged in: click an event for its ready-to-paste Slack post, use **Copy 2-week Slack
  digest**, or **Update now**.
- The calendar also refreshes automatically on the 1st and 15th of every month.

**Common changes:**
- *Add or remove a club or organization:* edit `config.toml` on GitHub (pencil icon → commit).
  Eventbrite organizer and collection pages, UF calendar groups, and GatorConnect clubs
  work without new code.
- *An event found on Instagram:* add it to `manual_events.toml` the same way.
- *Change the tone of the Slack blurbs:* edit `voice` under `[blurbs]` in `config.toml`.

**Handing over access:**
- GitHub: add the new officer as a collaborator, or better, keep the repo in an IGNITE GitHub organization.
- Vercel: invite them to the project or team.
- Put the new officer's `@ufl.edu` address in `ADMIN_EMAILS` (Vercel) and remove old
  officers. Removed addresses are locked out right away.
- Rotate the secrets whenever officers change: a new `SESSION_SECRET` (logs everyone out),
  a new `GITHUB_TOKEN` owned by a current officer, a `RESEND_API_KEY` from an account the
  club controls (all in Vercel), and a new `GEMINI_API_KEY` (GitHub → Settings → Secrets → Actions).

**If something breaks:**
- A yellow "Couldn't reach …" banner means one source changed or is down. Other sources
  keep working, and that source's last-known events stay on the calendar.
- Check **Actions** on GitHub for the log of the last update run.
- GitHub pauses scheduled workflows in repos with no activity for 60 days. If updates
  stop, open Actions → Update event calendar → **Enable workflow**.

## Files

- `update.py`: runs one full update
- `serve.py` / `start.bat`: local web app with a working Update button
- `ignite/sources.py`: one collector per kind of source
- `ignite/store.py`: duplicate merging; detects events removed from their source
- `ignite/blurbs.py`: Gemini Slack blurbs. Only the pitch is AI-written; date, time,
  place and link come straight from the event data.
- `data/store.json`: saved events (the tool's memory between runs)
- `docs/`: the website, `events.json`, and `events.ics`

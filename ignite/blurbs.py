"""Short Slack blurbs written by Gemini. Only the pitch is AI-written; date, time,
place and link are added by the web page straight from the event data."""
import hashlib
import json
import os
import time
from datetime import datetime

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
BATCH = 10
MAX_PER_RUN = 60


def _fingerprint(e):
    raw = "|".join([e["title"], e["start"], e.get("location", ""), e.get("description", "")])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _prompt(voice, batch):
    items = [{
        "id": e["uid"], "title": e["title"], "host": e["org"],
        "when": datetime.fromisoformat(e["start"]).strftime("%A, %B %d at %I:%M %p"),
        "where": e.get("location", ""), "details": e.get("description", "")[:1500],
    } for e in batch]
    return f"""{voice.strip()}

For each event below, write a Slack blurb of 1-3 sentences (under 60 words) telling
club members what it is and why they should go. Do not repeat the date, time,
location or link; those are added separately. Use Slack formatting only (*bold*),
no hashtags.

Return JSON: a list of objects {{"id": "<id>", "blurb": "<text>"}}, one per event.

Events:
{json.dumps(items, indent=1, ensure_ascii=False)}"""


def _ask(key, model, prompt):
    for attempt in range(3):
        r = requests.post(API.format(model=model), headers={"x-goog-api-key": key}, timeout=90, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
        })
        if r.status_code in (429, 500, 503) and attempt < 2:
            time.sleep(30)  # free-tier rate limit; wait and retry
            continue
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)


def fill_blurbs(events, cfg, now, log):
    if not cfg.get("enabled", True):
        return
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        log("Skipping Slack blurbs: no GEMINI_API_KEY in .env")
        return
    todo = [e for e in events
            if datetime.fromisoformat(e["start"]) >= now and e.get("blurb_for") != _fingerprint(e)]
    todo = todo[:MAX_PER_RUN]
    if not todo:
        log("Slack blurbs: all up to date")
        return
    by_id = {e["uid"]: e for e in todo}
    written = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            for item in _ask(key, cfg.get("model", "gemini-2.5-flash"), _prompt(cfg.get("voice", ""), batch)):
                e = by_id.get(item.get("id"))
                if e and item.get("blurb"):
                    e["blurb"] = item["blurb"].strip()
                    e["blurb_for"] = _fingerprint(e)
                    written += 1
        except Exception as exc:  # keep going; blurbs are nice-to-have
            log(f"Gemini error: {exc}")
            break
        if i + BATCH < len(todo):
            time.sleep(5)
    log(f"Slack blurbs: wrote {written} new")

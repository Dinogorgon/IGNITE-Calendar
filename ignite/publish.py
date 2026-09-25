"""Write the files the web page and calendar apps read: docs/events.json and docs/events.ics."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PUBLIC_FIELDS = ["uid", "title", "org", "start", "end", "all_day", "location", "url",
                 "description", "image", "sources", "first_seen", "blurb"]


def write_json(path, store, meta):
    events = [{k: e.get(k) for k in PUBLIC_FIELDS} for e in store["events"]]
    for e in events:
        e["sources"] = [{"name": s["name"], "url": s["url"]} for s in e["sources"]]
    Path(path).write_text(json.dumps({"meta": meta, "events": events}, indent=1, ensure_ascii=False),
                          encoding="utf-8")


def _esc(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,") \
        .replace("\r", "").replace("\n", "\\n")


def _fold(line):
    """iCalendar lines must be <= 75 octets; continuation lines start with a space."""
    out, raw = [], line.encode("utf-8")
    while len(raw) > 75:
        cut = 75 if not out else 74
        while (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode())
        raw = raw[cut:]
    out.append(raw.decode())
    return "\r\n ".join(out)


def _utc(iso):
    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_ics(path, store, calendar_name):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//IGNITE UF//Event Coordinator//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(calendar_name)}",
             "X-WR-TIMEZONE:America/New_York", "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
             "X-PUBLISHED-TTL:PT12H"]
    for e in store["events"]:
        start = datetime.fromisoformat(e["start"])
        details = [e.get("blurb") or "", e.get("description") or ""]
        details.append("Hosted by: " + e["org"])
        details += [f"{s['name']}: {s['url']}" for s in e["sources"] if s.get("url")]
        lines += ["BEGIN:VEVENT", f"UID:{e['uid']}@ignite-gnv-events", f"DTSTAMP:{stamp}",
                  f"SUMMARY:{_esc(e['title'])}"]
        if e["all_day"]:
            end = datetime.fromisoformat(e["end"]) if e.get("end") else start
            lines += [f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{(end + timedelta(days=1)):%Y%m%d}"]
        else:
            end_iso = e.get("end") or (start + timedelta(hours=1)).isoformat()
            lines += [f"DTSTART:{_utc(e['start'])}", f"DTEND:{_utc(end_iso)}"]
        if e.get("location"):
            lines.append(f"LOCATION:{_esc(e['location'])}")
        if e.get("url"):
            lines.append(f"URL:{e['url']}")
        lines += [f"DESCRIPTION:{_esc(chr(10).join(d for d in details if d))}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    Path(path).write_text("\r\n".join(_fold(l) for l in lines) + "\r\n", encoding="utf-8", newline="")

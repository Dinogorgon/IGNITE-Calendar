"""Merging fresh events into the saved list without creating duplicates."""
import hashlib
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

MERGE_FIELDS = ["title", "org", "start", "end", "all_day", "location", "url", "image"]


def load(path):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"events": []}


def save(path, store):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, indent=1, ensure_ascii=False), encoding="utf-8")


def _norm(title):
    t = title.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _start(e):
    return datetime.fromisoformat(e["start"])


def _venue(location):
    """First three words of the location, e.g. 'las carretas mexican'. Empty if too generic."""
    words = _norm(location or "").split()[:3]
    key = " ".join(words)
    return key if len(words) == 3 and len(key) >= 12 else ""


def same_event(a, b):
    """Same day, starts within an hour, and either the titles or the venues look alike."""
    sa, sb = _start(a), _start(b)
    if sa.date() != sb.date():
        return False
    if not (a["all_day"] or b["all_day"]) and abs(sa - sb) > timedelta(minutes=60):
        return False
    ta, tb = _norm(a["title"]), _norm(b["title"])
    if ta == tb:
        return True
    if min(len(ta), len(tb)) >= 10 and (ta in tb or tb in ta):
        return True
    if SequenceMatcher(None, ta, tb).ratio() >= 0.8:
        return True
    # Different names for one event (e.g. "AI for Business Lunch" vs "aiGNV Lunch Meetup")
    va = _venue(a.get("location"))
    return bool(va) and va == _venue(b.get("location"))


def _absorb(ev, new, new_is_primary):
    for s in new["sources"]:
        ev["sources"] = [x for x in ev["sources"] if x["key"] != s["key"]] + [s]
    for f in MERGE_FIELDS:
        if new.get(f) not in ("", None) and (new_is_primary or not ev.get(f)):
            ev[f] = new[f]
    if len(new["description"]) > len(ev.get("description") or ""):
        ev["description"] = new["description"]


def merge(store, fresh, ok_sources, now, days_back):
    """
    fresh: list of (rank, events) where lower rank = more authoritative source.
    ok_sources: names of sources fetched successfully this run. An upcoming event
    that one of them no longer lists has been cancelled/removed there.
    Returns (added, updated, removed) counts.
    """
    events = store["events"]
    by_key = {s["key"]: e for e in events for s in e["sources"]}
    seen, added, updated = set(), 0, 0

    for rank, batch in fresh:
        for new in batch:
            src = new["sources"][0]
            match = by_key.get(src["key"])
            if match is None:
                # Same event listed elsewhere? Never merge two events from the same
                # source (e.g. the 10am and 1pm sessions of one workshop).
                cands = [e for e in events if same_event(e, new) and not any(
                    s["name"] == src["name"] and s["key"] != src["key"] for s in e["sources"])]
                match = min(cands, key=lambda e: abs(_start(e) - _start(new)), default=None)
            if match is None:
                new["uid"] = hashlib.sha1(src["key"].encode()).hexdigest()[:16]
                new["rank"] = rank
                new["first_seen"] = now.isoformat()
                events.append(new)
                match = new
                added += 1
            else:
                _absorb(match, new, rank <= match.get("rank", 99))
                match["rank"] = min(rank, match.get("rank", 99))
                updated += 1
            by_key[src["key"]] = match
            seen.add(src["key"])

    removed = 0
    keep = []
    cutoff = now - timedelta(days=days_back)
    for e in events:
        if _start(e) < cutoff:
            continue  # too old
        if _start(e) >= now:
            e["sources"] = [s for s in e["sources"]
                            if s["name"] not in ok_sources or s["key"] in seen]
            if not e["sources"]:
                removed += 1
                continue
        keep.append(e)
    keep.sort(key=_start)
    store["events"] = keep
    return added, updated, removed

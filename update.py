"""Collect events from every source, merge duplicates, write Slack blurbs, publish the calendar.

    python update.py
"""
import os
import sys
import tomllib
from datetime import timedelta
from pathlib import Path

from ignite import blurbs, publish, sources, store
from ignite.util import now

ROOT = Path(__file__).parent
STORE = ROOT / "data" / "store.json"
DOCS = ROOT / "docs"


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run(log=print):
    load_env()
    cfg = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    settings = cfg.get("settings", {})
    t = now()
    start = t - timedelta(days=1)
    end = t + timedelta(days=settings.get("days_ahead", 120))

    fresh, ok, failed = [], {"Added manually"}, []
    for rank, src in enumerate(cfg.get("sources", [])):
        try:
            found = sources.COLLECTORS[src["type"]](src, start, end)
            fresh.append((rank, found))
            ok.add(src["name"])
            log(f"{src['name']}: {len(found)} events")
        except Exception as exc:
            failed.append(src["name"])
            log(f"{src['name']}: FAILED ({exc}) — keeping its previously saved events")
    manual = sources.fetch_manual(ROOT / "manual_events.toml", start, end)
    fresh.append((-1, manual))  # your own entries always win
    if manual:
        log(f"Manual entries: {len(manual)} events")

    data = store.load(STORE)
    data.setdefault("first_run", t.isoformat())
    added, updated, removed = store.merge(data, fresh, ok, t, settings.get("days_back", 30))
    log(f"Calendar: {added} new, {updated} refreshed/merged, {removed} removed, "
        f"{len(data['events'])} total")

    blurbs.fill_blurbs(data["events"], cfg.get("blurbs", {}), t, log)

    data["last_run"] = t.isoformat()
    store.save(STORE, data)
    DOCS.mkdir(exist_ok=True)
    publish.write_json(DOCS / "events.json", data, {
        "calendar_name": settings.get("calendar_name", "Events"),
        "updated": t.isoformat(),
        "first_run": data["first_run"],
        "failed_sources": failed,
        "github_actions_url": settings.get("github_actions_url", ""),
    })
    publish.write_ics(DOCS / "events.ics", data, settings.get("calendar_name", "Events"))
    log("Done. Wrote docs/events.json and docs/events.ics")
    return not failed


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run()

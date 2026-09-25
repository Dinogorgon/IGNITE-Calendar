"""Collectors: one function per kind of source. Each returns a list of make_event() dicts."""
import json
import re
import tomllib
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from .util import TZ, clean_html, get, make_event, parse_utc


def fetch_startgnv(src, start, end):
    """WordPress 'The Events Calendar' REST API (startgnv.com)."""
    url = src["url"].rstrip("/") + "/wp-json/tribe/events/v1/events"
    params = {"per_page": 50, "start_date": start.strftime("%Y-%m-%d"),
              "end_date": end.strftime("%Y-%m-%d")}
    events = []
    while url:
        data = get(url, params=params).json()
        params = None  # next_rest_url already carries them
        for e in data.get("events", []):
            venue = e.get("venue") if isinstance(e.get("venue"), dict) else {}
            where = ", ".join(x for x in [venue.get("venue"), venue.get("address")] if x)
            organizers = [o.get("organizer") for o in (e.get("organizer") or []) if o.get("organizer")]
            image = e["image"].get("url", "") if isinstance(e.get("image"), dict) else ""
            events.append(make_event(
                source=src["name"], key=f"startgnv:{e['id']}",
                title=e["title"],
                start=parse_utc(e["utc_start_date"]), end=parse_utc(e["utc_end_date"]),
                all_day=e.get("all_day", False),
                org=clean_html(organizers[0]) if organizers else src.get("org", src["name"]),
                location=clean_html(where), url=e.get("url", ""),
                description=clean_html(e.get("description")), image=image,
            ))
        url = data.get("next_rest_url")
    return events


def fetch_uf_calendar(src, start, end):
    """calendar.ufl.edu (LiveWhale) JSON feed for one group."""
    url = f"https://calendar.ufl.edu/live/json/events/group/{quote(src['group'])}/max/200"
    events = []
    for e in get(url).json():
        if e.get("is_canceled"):
            continue
        begins = datetime.fromisoformat(e["date_iso"])
        if not (start <= begins <= end):
            continue
        location = e.get("location") or e.get("location_title") or ("Online" if e.get("is_online") else "")
        events.append(make_event(
            source=src["name"], key=f"ufcal:{e['id']}",
            title=e["title"], start=begins,
            end=datetime.fromisoformat(e["date2_iso"]) if e.get("date2_iso") else None,
            all_day=e.get("is_all_day", False), org=src.get("org", src["name"]),
            location=clean_html(location), url=e.get("url", ""),
            description=clean_html(e.get("description")),
        ))
    return events


def fetch_eventbrite(src, start, end):
    """Eventbrite organizer (/o/…) or collection (/cc/…) page, via its schema.org JSON-LD."""
    page = get(src["url"]).text
    events = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        data = json.loads(block)
        blocks = data if isinstance(data, list) else [data]
        items = []
        for b in blocks:
            if b.get("@type") == "ItemList":
                items += [li.get("item", li) for li in b.get("itemListElement", [])]
            elif b.get("@type") == "Event":
                items.append(b)
        for e in items:
            if e.get("@type") != "Event":
                continue
            begins = datetime.fromisoformat(e["startDate"])
            ends = datetime.fromisoformat(e["endDate"]) if e.get("endDate") else None
            # Skip "every first Tuesday"-style series that span months.
            if ends and ends - begins > timedelta(days=3):
                continue
            if not (start <= begins <= end):
                continue
            loc = e.get("location") or {}
            if loc.get("@type") == "VirtualLocation":
                where = "Online"
            else:
                addr = loc.get("address") or {}
                where = ", ".join(x for x in [loc.get("name"), addr.get("streetAddress"),
                                               addr.get("addressLocality")] if x)
            eid = re.search(r"(\d+)/?$", e.get("url", "")) or re.search(r"(\d+)", e.get("url", ""))
            events.append(make_event(
                source=src["name"], key=f"eventbrite:{eid.group(1) if eid else e['name']}",
                title=e["name"], start=begins, end=ends,
                org=src.get("org", src["name"]), location=where, url=e.get("url", ""),
                description=clean_html(e.get("description")), image=e.get("image", ""),
            ))
    if not events:
        events = _eventbrite_next_data(src, page, start, end)
    return events


def _eventbrite_next_data(src, page, start, end):
    """Organizer pages keep their event list in the Next.js __NEXT_DATA__ blob instead."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    found = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("_type") == "event" and node.get("start_date") and node.get("url"):
                found[node.get("eventbrite_event_id") or node["url"]] = node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(m.group(1)))
    events = []
    for eid, e in found.items():
        if e.get("is_cancelled"):
            continue
        zone = ZoneInfo(e.get("timezone") or "America/New_York")
        begins = datetime.fromisoformat(f"{e['start_date']}T{e.get('start_time') or '00:00:00'}").replace(tzinfo=zone)
        ends = datetime.fromisoformat(f"{e['end_date']}T{e.get('end_time') or '00:00:00'}").replace(tzinfo=zone) \
            if e.get("end_date") else None
        if ends and ends - begins > timedelta(days=3):
            continue
        if not (start <= begins <= end):
            continue
        venue = e.get("primary_venue") or {}
        where = "Online" if e.get("is_online_event") else ", ".join(
            x for x in [venue.get("name"), (venue.get("address") or {}).get("localized_address_display")] if x)
        events.append(make_event(
            source=src["name"], key=f"eventbrite:{eid}", title=e["name"], start=begins, end=ends,
            org=src.get("org", src["name"]), location=where, url=e["url"],
            description=e.get("summary") or "", image=(e.get("image") or {}).get("url", ""),
        ))
    return events


def fetch_gatorconnect(src, start, end):
    """GatorConnect (Campus Labs Engage) public events: listed clubs + keyword matches."""
    base = src["url"].rstrip("/")
    orgs = [o.lower() for o in src.get("organizations", [])]
    keywords = [k.lower() for k in src.get("keywords", [])]
    events, skip, total = [], 0, None
    while total is None or skip < total:
        data = get(f"{base}/api/discovery/event/search", params={
            "endsAfter": start.isoformat(), "orderByField": "endsOn",
            "orderByDirection": "ascending", "status": "Approved", "take": 100, "skip": skip,
        }).json()
        total = data.get("@odata.count", 0)
        batch = data.get("value", [])
        if not batch:
            break
        skip += len(batch)
        for e in batch:
            begins = datetime.fromisoformat(e["startsOn"])
            if begins > end or e.get("visibility") != "Public":
                continue
            club = (e.get("organizationName") or "").strip()
            description = clean_html(e.get("description"))
            text = f"{e.get('name', '')} {description}".lower()
            if not (any(o in club.lower() for o in orgs) or any(k in text for k in keywords)):
                continue
            image = f"https://se-images.campuslabs.com/clink/images/{e['imagePath']}" if e.get("imagePath") else ""
            events.append(make_event(
                source=src["name"], key=f"gatorconnect:{e['id']}",
                title=e["name"], start=begins,
                end=datetime.fromisoformat(e["endsOn"]) if e.get("endsOn") else None,
                org=club or src["name"], location=e.get("location") or "",
                url=f"{base}/event/{e['id']}", description=description, image=image,
            ))
    return events


def _firestore_value(v):
    kind, val = next(iter(v.items()))
    if kind == "mapValue":
        return {k: _firestore_value(x) for k, x in val.get("fields", {}).items()}
    if kind == "arrayValue":
        return [_firestore_value(x) for x in val.get("values", [])]
    return val


def _occurrences(first, rule, start, end):
    """Expand a gnv.ai recurrence rule into start datetimes inside [start, end]."""
    first = first.astimezone(TZ)
    if not rule:
        return [first]
    interval = int(rule.get("interval") or 1)
    until = end
    if rule.get("endDate"):
        until = min(end, datetime.fromisoformat(rule["endDate"]).replace(tzinfo=TZ) + timedelta(days=1))
    kind = rule.get("type", "")
    out = []
    if kind == "weekly":
        d = first
        while d <= until:
            out.append(d)
            d += timedelta(weeks=interval)
    elif kind.startswith("monthly"):
        weekday = (int(rule.get("dayOfWeek", first.isoweekday() % 7)) - 1) % 7  # JS Sun=0 -> Python Mon=0
        week = int(rule.get("weekOfMonth", 1))
        y, m = first.year, first.month
        while True:
            if kind == "monthly-day":  # e.g. "2nd Wednesday"
                d1 = first.replace(year=y, month=m, day=1)
                offset = (weekday - d1.weekday()) % 7
                days = [d1 + timedelta(days=offset + 7 * k) for k in range(5)]
                days = [d for d in days if d.month == m]
                d = days[min(week, len(days)) - 1]
            else:  # same day-of-month
                try:
                    d = first.replace(year=y, month=m)
                except ValueError:
                    d = None
            if d and d > until:
                break
            if d and d >= first:
                out.append(d)
            m += interval
            y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    else:
        out = [first]
    return [d for d in out if start <= d <= end]


def fetch_gnvai(src, start, end):
    """GNV.AI community site (gnv.ai): its public Firestore 'events' collection."""
    url = f"https://firestore.googleapis.com/v1/projects/{src.get('project', 'gnv-community')}/databases/(default)/documents/events"
    docs, token = [], None
    while True:
        data = get(url, params={"pageSize": 100, **({"pageToken": token} if token else {})}).json()
        docs += data.get("documents", [])
        token = data.get("nextPageToken")
        if not token:
            break
    events = []
    for doc in docs:
        f = {k: _firestore_value(v) for k, v in doc["fields"].items()}
        if f.get("status") != "approved" or not f.get("date"):
            continue
        first = datetime.fromisoformat(f["date"])
        length = datetime.fromisoformat(f["endTime"]) - first if f.get("endTime") else None
        if length and not timedelta(0) < length < timedelta(days=1):
            length = None
        doc_id = doc["name"].rsplit("/", 1)[-1]
        title = re.sub(r"\s*\((pending|tentative)\)\s*$", "", f["title"], flags=re.I)
        details = "\n\n".join(x for x in [f.get("tagline"), clean_html(f.get("description"))] if x)
        for when in _occurrences(first, f.get("recurrence"), start, end):
            events.append(make_event(
                source=src["name"], key=f"gnvai:{doc_id}:{when:%Y-%m-%d}",
                title=title, start=when, end=when + length if length else None,
                org=src.get("org", src["name"]), location=f.get("location", ""),
                url=f"https://gnv.ai/events/{f['slug']}" if f.get("slug") else "https://gnv.ai/events",
                description=details, image=f.get("imageUrl", ""),
            ))
    return events


def fetch_manual(path, start, end):
    """Hand-entered events from manual_events.toml."""
    if not Path(path).exists():
        return []
    events = []
    for i, e in enumerate(tomllib.loads(Path(path).read_text(encoding="utf-8")).get("event", [])):
        begins = datetime.strptime(e["start"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        if not (start <= begins <= end):
            continue
        ends = datetime.strptime(e["end"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ) if e.get("end") else None
        events.append(make_event(
            source="Added manually", key=f"manual:{e['title'].lower()}:{e['start']}",
            title=e["title"], start=begins, end=ends, org=e.get("org", ""),
            location=e.get("location", ""), url=e.get("url", ""),
            description=e.get("description", ""),
        ))
    return events


COLLECTORS = {
    "startgnv": fetch_startgnv,
    "uf_calendar": fetch_uf_calendar,
    "eventbrite": fetch_eventbrite,
    "gatorconnect": fetch_gatorconnect,
    "gnvai": fetch_gnvai,
}

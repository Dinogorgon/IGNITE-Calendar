import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("America/New_York")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def get(url, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    return r


def clean_html(text):
    """HTML fragment -> readable plain text."""
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def local(dt):
    """Aware datetime -> Gainesville local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def parse_utc(s, fmt="%Y-%m-%d %H:%M:%S"):
    return local(datetime.strptime(s, fmt).replace(tzinfo=timezone.utc))


def now():
    return datetime.now(TZ)


def make_event(*, source, key, title, start, end=None, all_day=False, org="",
               location="", url="", description="", image=""):
    """The one shape every collector returns."""
    start = local(start)
    end = local(end) if end else None
    if end and end < start:
        end = None
    return {
        "title": html.unescape(title).strip(),
        "org": (org or source).strip(),
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "all_day": bool(all_day),
        "location": (location or "").strip(),
        "url": url or "",
        "description": (description or "").strip(),
        "image": image or "",
        "sources": [{"name": source, "key": key, "url": url or ""}],
    }

"""Wikipedia page titles and page views through Wikimedia's official APIs (registry/sources.csv, SPEC 2.2a, 2.8 N5, N7).

No key. Identifying User-Agent from broadway_rush.http. At least 3 seconds between requests: at one a second,
Wikimedia refused 5 of 53 lookups on 2026-11-11. Raw answers are cached in data/raw/wikimedia/, so a re-run only
fetches what's missing.
"""

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

from broadway_rush.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "raw" / "wikimedia"
API = "https://en.wikipedia.org/w/api.php"
VIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user"
MIN_INTERVAL = 3.0
PERFORMER_RE = re.compile(
    r"actor|actress|singer|dancer|performer|comedian|entertainer|musician|drag|rapper|personality|presenter|"
    r"host|model|songwriter|vocalist|playwright|youtuber|influencer|magician|television personality", re.I)
# A page about a show, season or series isn't a person, even when its description says "television"
NOT_A_PERSON_RE = re.compile(r"(series|season|film|franchise|episode|album|event)", re.I)

log = logging.getLogger("wikimedia")


class Client:
    def __init__(self, min_interval: float = MIN_INTERVAL):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.min_interval = min_interval
        self.last = 0.0
        self.n = 0
        self.refused = 0

    def get(self, url, params=None):
        """GET JSON. 404 returns None. 429 or 5xx: wait and retry, up to 4 times."""
        for attempt in range(5):
            gap = time.monotonic() - self.last
            if gap < self.min_interval:
                time.sleep(self.min_interval - gap)
            self.last = time.monotonic()
            self.n += 1
            r = self.s.get(url, params=params, timeout=60)
            if r.status_code == 404:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                self.refused += 1
                wait = 15 * (attempt + 1)
                log.warning("HTTP %s, waiting %ss", r.status_code, wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"gave up after retries: {url}")


def resolve(client: Client, names: list[str]) -> dict:
    """name -> {title, description, disambiguation, missing}. 50 names per request, redirects followed."""
    out = {}
    for i in range(0, len(names), 50):
        batch = names[i:i + 50]
        q = client.get(API, {"action": "query", "format": "json", "formatversion": 2, "redirects": 1,
                             "prop": "description|pageprops", "ppprop": "disambiguation", "titles": "|".join(batch)})
        q = q["query"]
        norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
        red = {x["from"]: x["to"] for x in q.get("redirects", [])}
        pages = {p["title"]: p for p in q.get("pages", [])}
        for n in batch:
            t = norm.get(n, n)
            t = red.get(t, t)
            p = pages.get(t, {})
            out[n] = {"title": t if p and not p.get("missing") else "", "description": p.get("description", ""),
                      "disambiguation": "disambiguation" in (p.get("pageprops") or {}), "missing": bool(p.get("missing"))}
    return out


def safe(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", title)[:150]


def monthly_views(client: Client, title: str, start="2015070100", end="2026103100") -> dict:
    """YYYY-MM -> views by people (bots filtered), cached. Empty if the page has no data."""
    path = CACHE / "monthly" / f"{safe(title)}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    j = client.get(f"{VIEWS}/{quote(title.replace(' ', '_'), safe='')}/monthly/{start}/{end}")
    data = {it["timestamp"][:4] + "-" + it["timestamp"][4:6]: it["views"] for it in (j or {}).get("items", [])}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def daily_views(client: Client, title: str, start="20240401", end="20261110") -> dict:
    """YYYY-MM-DD -> views by people, cached (show buzz, SPEC 2.8 N7)."""
    path = CACHE / "daily" / f"{safe(title)}_{start}_{end}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    j = client.get(f"{VIEWS}/{quote(title.replace(' ', '_'), safe='')}/daily/{start}00/{end}00")
    data = {f"{t[:4]}-{t[4:6]}-{t[6:8]}": it["views"] for it in (j or {}).get("items", []) for t in [it["timestamp"]]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data

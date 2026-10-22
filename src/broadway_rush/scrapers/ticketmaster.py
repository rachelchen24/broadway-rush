"""Ticketmaster Discovery API (SPEC §3.0, §3.2): upcoming Broadway performances and their sale status.
Official API with a free key (registry/sources.csv); the website itself is never scraped.

    py -m broadway_rush.scrapers.ticketmaster snapshot   # next 8 days -> data/raw/ticketmaster_events.csv
    py -m broadway_rush.scrapers.ticketmaster parse      # re-parse cached JSON only (no requests)

No prices or seat counts for Broadway (priceRanges is empty), but every performance's date, time and status
(onsale / offsale / cancelled / rescheduled / postponed). Run daily: a performance going offsale early may mean
it sold out. Needs TICKETMASTER_API_KEY in .env.
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from broadway_rush.http import PoliteClient
from broadway_rush.scrapers.playbill import write_csv

API = "https://app.ticketmaster.com/discovery/v2/events.json"
DAYS_AHEAD = 8
PAGE_SIZE = 200
MAX_PAGES = 5           # the API won't page past 1,000 results
MIN_INTERVAL = 1.0      # limit is 5 requests/s; we stay far below it

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "ticketmaster"
EVENTS_CSV = RAW / "ticketmaster_events.csv"
SHOWS_CSV = ROOT / "data" / "processed" / "shows.csv"
COLS = ["snapshot_utc", "event_id", "name", "attraction_id", "attraction", "venue_id", "venue", "local_date",
        "local_time", "status", "sales_end_utc", "url"]

log = logging.getLogger("ticketmaster")


def venue_key(name: str) -> str:
    """'Imperial Theatre - NY' / 'August Wilson Theatre-NY' / 'Hudson Theatre' -> 'imperial' / 'august wilson' / 'hudson'."""
    s = name.lower()
    s = re.sub(r"\s*-\s*(ny|nyc|new york)\s*$", "", s)
    s = re.sub(r"\b(the|theatre|theater|new york|nyc)\b", " ", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def broadway_venues() -> set[str]:
    return {venue_key(t) for t in pd.read_csv(SHOWS_CSV).theater.dropna()}


def snapshot(client: PoliteClient):
    load_dotenv(ROOT / ".env")
    key = os.getenv("TICKETMASTER_API_KEY")
    if not key:
        sys.exit("TICKETMASTER_API_KEY missing from .env")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    params = {"apikey": key, "city": "New York", "stateCode": "NY", "classificationName": "Theatre",
              "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "endDateTime": (now + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "size": PAGE_SIZE, "sort": "date,asc"}
    events, page, pages = [], 0, 1
    while page < min(pages, MAX_PAGES):
        body = client.get_json(API, {**params, "page": page})
        events += body.get("_embedded", {}).get("events", [])
        pages = body.get("page", {}).get("totalPages", 0)
        page += 1
    if pages > MAX_PAGES:
        log.warning("%d pages available, only %d fetched: shorten DAYS_AHEAD", pages, MAX_PAGES)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{now.strftime('%Y%m%d%H%M%S')}.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    log.info("snapshot: %d NYC theatre events in the next %d days (%d pages)", len(events), DAYS_AHEAD, page)
    write_all()


def parse_events(events: list[dict], snapshot_utc: str, venues: set[str]) -> list[dict]:
    rows = []
    for e in events:
        emb = e.get("_embedded", {})
        v = (emb.get("venues") or [{}])[0]
        if venue_key(v.get("name", "")) not in venues:
            continue  # Off-Broadway, museums, tours
        a = (emb.get("attractions") or [{}])[0]
        start = e.get("dates", {}).get("start", {})
        rows.append({
            "snapshot_utc": snapshot_utc, "event_id": e.get("id", ""), "name": e.get("name", ""),
            "attraction_id": a.get("id", ""), "attraction": a.get("name", ""),
            "venue_id": v.get("id", ""), "venue": v.get("name", ""),
            "local_date": start.get("localDate", ""), "local_time": start.get("localTime", ""),
            "status": e.get("dates", {}).get("status", {}).get("code", ""),
            "sales_end_utc": e.get("sales", {}).get("public", {}).get("endDateTime", ""), "url": e.get("url", ""),
        })
    return rows


def write_all():
    venues = broadway_venues()
    rows = []
    for f in sorted(CACHE.glob("*.json")):
        ts = datetime.strptime(f.stem, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        rows += parse_events(json.loads(f.read_text(encoding="utf-8")), ts, venues)
    write_csv(EVENTS_CSV, COLS, rows)
    latest = [r for r in rows if r["snapshot_utc"] == max((r["snapshot_utc"] for r in rows), default="")]
    log.info("wrote %s: %d rows; latest snapshot: %d Broadway performances at %d theaters, statuses %s",
             EVENTS_CSV.name, len(rows), len(latest), len({r["venue_id"] for r in latest}),
             dict(pd.Series([r["status"] for r in latest]).value_counts()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["snapshot", "parse"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(CACHE / "scrape.log", encoding="utf-8")],
    )
    client = PoliteClient(min_interval=MIN_INTERVAL)
    snapshot(client) if args.phase == "snapshot" else write_all()
    log.info("%d requests", client.n_requests)


if __name__ == "__main__":
    main()

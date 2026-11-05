"""TKTS same-day discount board (SPEC §3.8): a show on TKTS today = not selling out. Allowed per registry/sources.csv.

    py -m broadway_rush.scrapers.tkts live      # today's board, 1 request -> data/raw/tkts.csv
    py -m broadway_rush.scrapers.tkts history   # Internet Archive copies since June 2024 (one per day)
    py -m broadway_rush.scrapers.tkts parse     # re-parse cached HTML only (no requests)

Snapshots are cached as data/raw/tkts/<UTC YYYYMMDDHHMMSS>-live.html.gz (ours)
or <UTC YYYYMMDDHHMMSS>.html.gz (archive), so the board's history builds up run by run.
Files saved before 2026-11-05 are plain .html; both are read.
"""

import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from broadway_rush.http import PoliteClient
from broadway_rush.scrapers.playbill import (START_WEEK, WAYBACK_CDX, WAYBACK_WEB, cached_files, read_cached, write_csv,
                                             write_gz)

BOARD_URL = "https://www.tdf.org/discount-ticket-programs/tkts-by-tdf/tkts-live/"
MIN_INTERVAL = 5.0
ET = ZoneInfo("America/New_York")

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "tkts"
TKTS_CSV = RAW / "tkts.csv"
COLS = ["snapshot_utc", "snapshot_et", "source", "booth", "section", "board_updated", "show", "tdf_url",
        "pct_off", "price_min", "price_max", "perf_time"]
PRICE_RE = re.compile(r"\$(\d+(?:\.\d+)?)(?:\s*-\s*\$?(\d+(?:\.\d+)?))?")

log = logging.getLogger("tkts")


def parse_board(html: str, snapshot_utc: str, source: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    utc = datetime.strptime(snapshot_utc, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    rows = []
    for grid in soup.find_all("div", class_="tkts__grid"):
        booth = next((p["id"].removeprefix("tkts-shows-") for p in grid.parents
                      if p.get("id", "").startswith("tkts-shows-")), "")
        head = grid.find_previous(["h2", "h3", "h4"])
        updated = grid.find_previous(string=lambda t: t and "Updated" in t)
        upd_text = ""
        if updated is not None:
            nxt = updated.find_next(string=lambda t: t and t.strip() and "Updated" not in t)
            upd_text = nxt.strip() if nxt else ""
        for li in grid.find_all("li", class_="tkts__grid-list-item"):
            def field(name):
                el = li.find(class_=f"tkts__grid-list-item__{name}")
                return el.get_text(" ", strip=True) if el else ""
            a = li.find("a", href=True)
            m = PRICE_RE.search(field("discount"))
            rows.append({
                "snapshot_utc": utc.isoformat(), "snapshot_et": utc.astimezone(ET).isoformat(), "source": source,
                "booth": booth, "section": head.get_text(" ", strip=True) if head else "", "board_updated": upd_text,
                "show": field("title"), "tdf_url": a["href"] if a else "",
                "pct_off": field("percent").rstrip("%"),
                "price_min": m.group(1) if m else "", "price_max": (m.group(2) or m.group(1)) if m else "",
                "perf_time": field("time"),
            })
    return rows or parse_board_tables(soup, utc, source)


OLD_BLOCK_RE = re.compile(r"^(TimesSquare|LincolnCenter)-(.+)$")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*[AP]M\b", re.IGNORECASE)


def parse_board_tables(soup, utc, source) -> list[dict]:
    """Layout before 2026: one <table> per booth/section inside div#<Booth>-<section>, cells in varying order
    (and some captures list titles only), so each cell is recognized by its content."""
    rows = []
    for block in soup.find_all("div", id=OLD_BLOCK_RE):
        booth_raw, section = OLD_BLOCK_RE.match(block["id"]).groups()
        booth = re.sub(r"(?<!^)([A-Z])", r"-\1", booth_raw).lower()  # TimesSquare -> times-square
        upd = block.find(class_="updated-label")
        upd_p = upd.find("p") if upd else None
        for tr in block.find_all("tr"):
            a = tr.find("a", href=True)
            if a is None:
                continue  # header row
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            pct = next((c.rstrip("%") for c in cells if re.fullmatch(r"\d+%", c)), "")
            m = next((m for c in cells if (m := PRICE_RE.search(c))), None)
            time = next((t.group(0) for c in cells if (t := TIME_RE.search(c))), "")
            rows.append({
                "snapshot_utc": utc.isoformat(), "snapshot_et": utc.astimezone(ET).isoformat(), "source": source,
                "booth": booth, "section": section.replace("-", " ").capitalize(),
                "board_updated": upd_p.get_text(" ", strip=True) if upd_p else "",
                "show": a.get_text(" ", strip=True).strip('"'), "tdf_url": a["href"],
                "pct_off": pct, "price_min": m.group(1) if m else "",
                "price_max": (m.group(2) or m.group(1)) if m else "", "perf_time": time,
            })
    return rows


def scrape_live(client: PoliteClient):
    CACHE.mkdir(parents=True, exist_ok=True)
    html = client.get_text(BOARD_URL)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    n = len(parse_board(html, ts, "live"))
    if n == 0:
        log.warning("board has no show rows; not cached (page layout changed?)")
    else:
        write_gz(CACHE / f"{ts}-live.html.gz", html)
        log.info("live board: %d rows", n)
    write_all()


def scrape_history(client: PoliteClient):
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = client.get_json(WAYBACK_CDX, {"url": BOARD_URL.split("://", 1)[1], "from": START_WEEK.replace("-", "")[:8],
                                         "output": "json", "filter": "statuscode:200", "collapse": "timestamp:8"})
    caps = [dict(zip(rows[0], r)) for r in rows[1:]]
    todo = [c for c in caps if not list(CACHE.glob(f"{c['timestamp']}.html*"))]
    log.info("%d archived days, %d to fetch (~%.0f min)", len(caps), len(todo), len(todo) * MIN_INTERVAL / 60)
    empty = 0
    for i, c in enumerate(todo, 1):
        html = client.get_text(f"{WAYBACK_WEB}/{c['timestamp']}id_/{c['original']}")
        write_gz(CACHE / f"{c['timestamp']}.html.gz", html)  # cache even if unparsed
        empty += not parse_board(html, c["timestamp"], "archive")
        if i % 20 == 0 or i == len(todo):
            log.info("%d/%d fetched (%d with no rows so far)", i, len(todo), empty)
    write_all()


def section_key(section: str) -> str:
    """The two page layouts name sections differently; map both to broadway / off_broadway / next_day_*."""
    s = section.lower()
    prefix = "next_day_" if ("matinee" in s or "tomorrow" in s) else ""
    return prefix + ("off_broadway" if "off" in s else "broadway")


def write_all():
    rows = []
    files = cached_files(CACHE, "*.html*")
    for f in files:
        ts, _, tag = f.name.split(".")[0].partition("-")
        rows += parse_board(read_cached(f), ts, tag or "archive")
    for r in rows:
        r["section"] = section_key(r["section"])
    write_csv(TKTS_CSV, COLS, rows)
    snaps = {r["snapshot_utc"] for r in rows}
    log.info("wrote %s: %d rows from %d snapshots with rows (%d cached files)", TKTS_CSV.name, len(rows), len(snaps),
             len(files))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["live", "history", "parse"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(CACHE / "scrape.log", encoding="utf-8")],
    )
    client = PoliteClient(min_interval=MIN_INTERVAL)
    if args.phase == "live":
        scrape_live(client)
    elif args.phase == "history":
        scrape_history(client)
    else:
        write_all()
    log.info("%d requests", client.n_requests)


if __name__ == "__main__":
    main()

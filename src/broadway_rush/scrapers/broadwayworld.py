"""BroadwayWorld weekly grosses (SPEC §3.3), the backup/cross-check for Playbill. Allowed per registry/sources.csv
(robots.txt disallows only the Excel export and ?before=/?after= paging, which we never request).

Adds what Playbill lacks: show type (Musical / Play / Special) and last week's / last year's numbers.

    py -m broadway_rush.scrapers.broadwayworld grosses   # every week since June 2024 -> data/raw/grosses_bww.csv
    py -m broadway_rush.scrapers.broadwayworld parse     # re-parse cached HTML only (no requests)
"""

import argparse
import logging
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from broadway_rush.http import PoliteClient
from broadway_rush.scrapers.playbill import START_WEEK, number, write_csv

GROSSES_URL = "https://www.broadwayworld.com/grosses.php"
MIN_INTERVAL = 5.0  # seconds between requests

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "broadwayworld"
GROSSES_CSV = RAW / "grosses_bww.csv"

# row data-* attribute -> column
ATTRS = {"data-name": "show", "data-typer": "show_type", "data-gross": "gross", "data-gross-prev": "gross_prev_week",
         "data-gross-last-year": "gross_last_year", "data-ticket": "avg_ticket", "data-attendee": "attendance",
         "data-perform": "perfs", "data-capacity": "pct_cap", "data-capacity-last": "pct_cap_prev_week"}
COLS = ["week_ending", "show_slug", "theater", "top_ticket", "attendance_capacity"] + list(ATTRS.values())

log = logging.getLogger("broadwayworld")


def week_list(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    weeks = {o["value"] for o in soup.select("select#week option[value]") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", o["value"])}
    return sorted(w for w in weeks if w >= START_WEEK)


def page_week(html: str) -> str:
    """Week-ending date the page actually shows, from the quick-stats header (MM/DD/YYYY -> YYYY-MM-DD)."""
    end = BeautifulSoup(html, "lxml").find(class_="grosses-quick-stats__date-end")
    if end is None:
        return ""
    m, d, y = end.get_text(strip=True).split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def parse_grosses(html: str, week: str) -> list[dict]:
    rows = []
    # the page has two "grosses-table" divs (quick stats first); show rows are the ones with data-name
    for div in BeautifulSoup(html, "lxml").select("div.row[data-name]"):
        row = dict.fromkeys(COLS, "")
        row["week_ending"] = week
        for attr, col in ATTRS.items():
            row[col] = div.get(attr, "").strip()
        title, theater = div.find("a", class_="title"), div.find("a", class_="theater")
        row["show_slug"] = title["href"].rsplit("/", 1)[-1] if title else ""
        row["theater"] = theater.get_text(" ", strip=True) if theater else ""
        cells = div.find_all("div", class_="cell", recursive=False)
        # cell 4 = avg / top ticket, cell 5 = attendance / capacity (the "in" span is the second value)
        for i, col in ((4, "top_ticket"), (5, "attendance_capacity")):
            if i < len(cells) and (s := cells[i].find("span", class_="in")):
                row[col] = number(s.get_text())
        rows.append(row)
    return rows


def scrape_grosses(client: PoliteClient):
    (CACHE / "grosses").mkdir(parents=True, exist_ok=True)
    landing = client.get_text(GROSSES_URL)
    # the newest week is only served by the plain page (?week=<newest> comes back empty)
    if (newest := page_week(landing)) and parse_grosses(landing, newest):
        (CACHE / "grosses" / f"{newest}.html").write_text(landing, encoding="utf-8")
    weeks = week_list(landing)
    todo = [w for w in weeks if not (CACHE / "grosses" / f"{w}.html").exists()]
    log.info("%d weeks since %s (%s to %s), %d to fetch", len(weeks), START_WEEK, weeks[0], weeks[-1], len(todo))
    for i, w in enumerate(todo, 1):
        html = client.get_text(GROSSES_URL, {"week": w})
        shown, n = page_week(html), len(parse_grosses(html, w))
        if shown != w or n == 0:  # wrong week served or broken page: don't cache, retry next run
            log.warning("week %s: page shows %r with %d rows, not cached", w, shown, n)
            continue
        (CACHE / "grosses" / f"{w}.html").write_text(html, encoding="utf-8")
        if i % 10 == 0 or i == len(todo):
            log.info("%d/%d weeks fetched (last %s: %d shows)", i, len(todo), w, n)
    write_grosses()


def write_grosses():
    rows = []
    for f in sorted((CACHE / "grosses").glob("*.html")):
        rows += parse_grosses(f.read_text(encoding="utf-8"), f.stem)
    write_csv(GROSSES_CSV, COLS, rows)
    log.info("wrote %s: %d rows, %d weeks, %d shows", GROSSES_CSV.name, len(rows),
             len({r["week_ending"] for r in rows}), len({r["show_slug"] for r in rows}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["grosses", "parse"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(CACHE / "scrape.log", encoding="utf-8")],
    )
    client = PoliteClient(min_interval=MIN_INTERVAL)
    if args.phase == "grosses":
        scrape_grosses(client)
    else:
        write_grosses()
    log.info("%d requests", client.n_requests)


if __name__ == "__main__":
    main()

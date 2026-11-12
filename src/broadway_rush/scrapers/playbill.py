"""Playbill weekly grosses and rush policies (SPEC §3.3, §3.4). Allowed per registry/sources.csv.

Phases (each is resumable; raw HTML is cached so re-parsing never re-downloads):
    py -m broadway_rush.scrapers.playbill grosses    # every week since June 2024 -> data/raw/grosses_playbill.csv
    py -m broadway_rush.scrapers.playbill policies   # today's policy article -> data/raw/policies_playbill.csv
    py -m broadway_rush.scrapers.playbill policies-history  # monthly Internet Archive copies since June 2024
    py -m broadway_rush.scrapers.playbill grosses-history   # earlier weeks (2014 to May 2024) for the season pattern
    py -m broadway_rush.scrapers.playbill schedule-history  # weekly schedule, one archived copy per week since June 2024
    py -m broadway_rush.scrapers.playbill parse      # re-parse cached HTML only (no requests)
"""

import argparse
import csv
import gzip
import logging
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from broadway_rush.http import PoliteClient

GROSSES_URL = "https://playbill.com/grosses"
POLICIES_URL = "https://playbill.com/article/broadway-rush-lottery-and-standing-room-only-policies-com-116003"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB = "https://web.archive.org/web"
START_WEEK = "2024-06-02"  # first week-ending Sunday that covers June 2024
MIN_INTERVAL = 3.0         # seconds between requests

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "playbill"
GROSSES_CSV = RAW / "grosses_playbill.csv"
POLICIES_CSV = RAW / "policies_playbill.csv"
HISTORY_START = "2014-01-05"  # first week-ending Sunday of 2014 (SPEC 2.8 C5)
SHUTDOWN = ("2020-03-15", "2021-09-05")  # no Broadway performances: skipped
GROSSES_HISTORY_CSV = RAW / "grosses_history_playbill.csv"
SCHEDULE_URL = "https://playbill.com/article/weekly-schedule-of-current-broadway-shows"
SCHEDULE_CSV = RAW / "schedule_playbill.csv"
SCHEDULE_COLS = ["capture_date", "date", "show", "perfs", "times"]

GROSS_COLS = ["week_ending", "production_id", "show", "theater", "gross", "potential_gross", "diff_gross",
              "avg_ticket", "top_ticket", "seats_sold", "seats_in_theatre", "perfs", "previews",
              "pct_cap", "diff_pct_cap"]
# table column -> (main value, subtext value)
GROSS_CELLS = {1: ("gross", "potential_gross"), 2: ("diff_gross", None), 3: ("avg_ticket", "top_ticket"),
               4: ("seats_sold", "seats_in_theatre"), 5: ("perfs", "previews"), 6: ("pct_cap", None),
               7: ("diff_pct_cap", None)}

POLICY_COLS = ["snapshot_date", "article_modified", "show", "production_url", "theater_text", "policy_type",
               "price", "price_text", "how", "where", "time", "payment", "id_required", "tickets_per_person",
               "seat_locations", "tickets_available", "special_policies", "other"]
POLICY_FIELDS = {  # label in the article (lowercase, no colon) -> column
    "price": "price_text", "how": "how", "where": "where", "time": "time", "payment method": "payment",
    "payment": "payment", "id": "id_required", "tickets per person": "tickets_per_person",
    "seat locations": "seat_locations", "seat location": "seat_locations", "seating locations": "seat_locations",
    "number of tickets available": "tickets_available", "number of lottery tickets available": "tickets_available",
    "special policies": "special_policies",
    "special policy": "special_policies",
}
POLICY_TYPE_RE = re.compile(r"\b(rush|lottery|standing room|sro)\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\$\s*(\d+(?:\.\d{2})?)")

log = logging.getLogger("playbill")


def number(text: str) -> str:
    """'$1,234.50' / '87.01%' / '-$25,555.00' -> '1234.50' / '87.01' / '-25555.00'; blank stays blank."""
    t = text.strip().replace("$", "").replace(",", "").replace("%", "")
    return t if re.fullmatch(r"-?\d+(\.\d+)?", t) else ""


# --- grosses -----------------------------------------------------------------------------------

def week_list(html: str) -> list[str]:
    """Every week-ending date in the page's week picker, from START_WEEK on, oldest first."""
    weeks = set(re.findall(r"grosses\?week=(\d{4}-\d{2}-\d{2})", html))
    return sorted(w for w in weeks if w >= START_WEEK)


def parse_grosses(html: str, week: str) -> list[dict]:
    table = BeautifulSoup(html, "lxml").find("table")
    if table is None:
        return []
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        link = tds[0].find("a")
        href = link["href"] if link else ""
        prod = parse_qs(urlparse(href).query).get("production", [""])[0] or href.rstrip("/").rsplit("/", 1)[-1]
        sub = tds[0].find("span", class_="subtext")
        row = {"week_ending": week, "production_id": prod,
               "show": tds[0].find("span", class_="data-value").get_text(" ", strip=True),
               "theater": sub.get_text(" ", strip=True) if sub else ""}
        for i, (main, extra) in GROSS_CELLS.items():
            val = tds[i].find("span", class_="data-value")
            row[main] = number(val.get_text()) if val else ""
            if extra:
                s = tds[i].find("span", class_="subtext")
                row[extra] = number(s.get_text()) if s else ""
        rows.append(row)
    return rows


def scrape_grosses(client: PoliteClient):
    (CACHE / "grosses").mkdir(parents=True, exist_ok=True)
    weeks = week_list(client.get_text(GROSSES_URL))
    todo = [w for w in weeks if not (CACHE / "grosses" / f"{w}.html").exists()]
    log.info("%d weeks since %s (%s to %s), %d to fetch", len(weeks), START_WEEK, weeks[0], weeks[-1], len(todo))
    for i, w in enumerate(todo, 1):
        html = client.get_text(GROSSES_URL, {"week": w})
        n = len(parse_grosses(html, w))
        if n == 0:  # don't cache an empty or broken page; it will be retried next run
            log.warning("week %s: no table rows, not cached", w)
            continue
        (CACHE / "grosses" / f"{w}.html").write_text(html, encoding="utf-8")
        if i % 10 == 0 or i == len(todo):
            log.info("%d/%d weeks fetched (last %s: %d shows)", i, len(todo), w, n)
    write_grosses()


def scrape_grosses_history(client: PoliteClient):
    """Earlier weeks of grosses, HISTORY_START up to START_WEEK, for the attendance season pattern (SPEC 2.8 N6, C5).
    Kept in their own folder and CSV, so the model tables built from grosses_playbill.csv don't change.
    The 2020-21 shutdown weeks have no table and are skipped (not cached)."""
    folder = CACHE / "grosses_history"
    folder.mkdir(parents=True, exist_ok=True)
    weeks = sorted(w for w in set(re.findall(r"grosses\?week=(\d{4}-\d{2}-\d{2})", client.get_text(GROSSES_URL)))
                   if HISTORY_START <= w < START_WEEK)
    todo = [w for w in weeks if not (folder / f"{w}.html").exists() and not (SHUTDOWN[0] <= w <= SHUTDOWN[1])]
    log.info("%d earlier weeks (%s to %s), %d to fetch", len(weeks), weeks[0], weeks[-1], len(todo))
    for i, w in enumerate(todo, 1):
        html = client.get_text(GROSSES_URL, {"week": w})
        n = len(parse_grosses(html, w))
        if n == 0:
            log.warning("week %s: no table rows, not cached", w)
            continue
        (folder / f"{w}.html").write_text(html, encoding="utf-8")
        if i % 25 == 0 or i == len(todo):
            log.info("%d/%d weeks fetched (last %s: %d shows)", i, len(todo), w, n)
    rows = []
    for f in sorted(folder.glob("*.html")):
        rows += parse_grosses(f.read_text(encoding="utf-8"), f.stem)
    write_csv(GROSSES_HISTORY_CSV, GROSS_COLS, rows)
    log.info("wrote %s: %d rows, %d weeks", GROSSES_HISTORY_CSV.name, len(rows), len({r["week_ending"] for r in rows}))


def write_grosses():
    rows = []
    for f in sorted((CACHE / "grosses").glob("*.html")):
        rows += parse_grosses(f.read_text(encoding="utf-8"), f.stem)
    write_csv(GROSSES_CSV, GROSS_COLS, rows)
    log.info("wrote %s: %d rows, %d weeks, %d productions", GROSSES_CSV.name, len(rows),
             len({r["week_ending"] for r in rows}), len({r["production_id"] for r in rows}))


# --- policies ----------------------------------------------------------------------------------

def parse_policies(html: str, snapshot: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", property="article:modified_time")
    modified = meta["content"][:10] if meta and meta.get("content") else ""
    # the policy list is the article div split by <hr>s ("prose" since spring 2026, "bsp-article-content" before)
    proses = soup.find_all("div", class_=["prose", "bsp-article-content"])
    if not proses:
        return []
    prose = max(proses, key=lambda d: len(d.find_all("hr", recursive=False)))
    # one show per block between <hr>s
    blocks, cur = [], []
    for el in prose.find_all(recursive=False):
        if el.name == "hr":
            blocks.append(cur)
            cur = []
        else:
            cur.append(el)
    blocks.append(cur)

    rows = []
    for els in blocks:
        prod = next((a for el in els for a in el.find_all("a", href=True) if "/production/" in a["href"]), None)
        if prod is None:
            continue  # intro text, ads
        lines = []
        for el in els:
            for br in el.find_all("br"):
                br.replace_with("\n")
            lines += [ln.strip() for ln in el.get_text().split("\n") if ln.strip()]
        show = prod.get_text(" ", strip=True)
        theater = next((m.group(1) for ln in lines[:2] if (m := re.search(r"\((.+)\)", ln))), "")
        policy = None
        body = lines[1:] if lines and show.lower() in lines[0].lower() else lines
        for i, ln in enumerate(body):
            key = field_key(ln)
            if key:
                if policy is None:  # fields before any type heading
                    policy = new_policy(rows, snapshot, modified, show, prod["href"], theater, "")
                col = POLICY_FIELDS[key]
                policy[col] = (policy[col] + " " + ln.partition(":")[2].strip()).strip()
            # a heading is a short line naming a rush/lottery/SRO, or any short line right before "Price:"
            # ("The Friday Forty", "$30 Under 30", "Student Tickets")
            elif len(ln) < 60 and (POLICY_TYPE_RE.search(ln) and ":" not in ln
                                   or i + 1 < len(body) and field_key(body[i + 1]) == "price"):
                policy = new_policy(rows, snapshot, modified, show, prod["href"], theater, ln.strip())
            elif policy is not None:
                policy["other"] = (policy["other"] + " " + ln).strip()
    for r in rows:
        m = MONEY_RE.search(r["price_text"])
        r["price"] = m.group(1) if m else ""
    return rows


def field_key(line: str) -> str | None:
    """'Payment Method: Cash' -> 'payment method' if it's a known policy field, else None."""
    label, sep, _ = line.partition(":")
    key = label.strip().lower()
    return key if sep and key in POLICY_FIELDS else None


def new_policy(rows, snapshot, modified, show, url, theater, ptype) -> dict:
    row = dict.fromkeys(POLICY_COLS, "")
    row.update(snapshot_date=snapshot, article_modified=modified, show=show, production_url=url,
               theater_text=theater, policy_type=ptype)
    rows.append(row)
    return row


def scrape_policies(client: PoliteClient):
    (CACHE / "policies").mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path = CACHE / "policies" / f"{today}.html"
    if path.exists():
        log.info("already have today's policy snapshot %s", path.name)
    else:
        path.write_text(client.get_text(POLICIES_URL), encoding="utf-8")
    write_policies()


def scrape_policy_history(client: PoliteClient):
    """Past versions of the policy article from the Internet Archive (public CDX API; registry/sources.csv).
    One capture per month since START_WEEK, saved like a normal snapshot under its capture date."""
    (CACHE / "policies").mkdir(parents=True, exist_ok=True)
    rows = client.get_json(WAYBACK_CDX, {"url": POLICIES_URL.split("://", 1)[1], "from": START_WEEK[:7].replace("-", ""),
                                         "output": "json", "filter": "statuscode:200", "collapse": "timestamp:6"})
    caps = [dict(zip(rows[0], r)) for r in rows[1:]]
    todo = [c for c in caps if not (CACHE / "policies" / f"{ts_date(c['timestamp'])}.html").exists()]
    log.info("%d monthly captures, %d to fetch", len(caps), len(todo))
    for c in todo:
        # "id_" asks for the page as originally captured, without the Wayback toolbar
        html = client.get_text(f"{WAYBACK_WEB}/{c['timestamp']}id_/{c['original']}")
        (CACHE / "policies" / f"{ts_date(c['timestamp'])}.html").write_text(html, encoding="utf-8")
        log.info("%s: %d policies", ts_date(c["timestamp"]), len(parse_policies(html, ts_date(c["timestamp"]))))
    write_policies()


def scrape_schedule_history(client: PoliteClient):
    """Past copies of Playbill's "Weekly Schedule of Current Broadway Shows" from the Internet Archive (SPEC 2.8 N8:
    two-show days for the model). One capture per ISO week since June 2024, the latest capture in that week."""
    folder = CACHE / "schedule"
    folder.mkdir(parents=True, exist_ok=True)
    rows = client.get_json(WAYBACK_CDX, {"url": SCHEDULE_URL.split("://", 1)[1], "from": START_WEEK[:7].replace("-", ""),
                                         "output": "json", "filter": "statuscode:200", "collapse": "timestamp:8"})
    caps = [dict(zip(rows[0], r)) for r in rows[1:]]
    by_week = {}
    for c in caps:
        by_week[date.fromisoformat(ts_date(c["timestamp"])).isocalendar()[:2]] = c
    todo = [c for c in by_week.values() if not (folder / f"{ts_date(c['timestamp'])}.html").exists()]
    log.info("%d captures, %d weeks, %d to fetch", len(caps), len(by_week), len(todo))
    for c in todo:
        html = client.get_text(f"{WAYBACK_WEB}/{c['timestamp']}id_/{c['original']}")
        (folder / f"{ts_date(c['timestamp'])}.html").write_text(html, encoding="utf-8")
        log.info("%s: %d show-days", ts_date(c["timestamp"]), len(parse_schedule(html, ts_date(c["timestamp"]))))
    write_schedule()


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
DAY_HEAD_RE = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2})\s*$")
TIME_RE = re.compile(r"\d{1,2}(?::\d\d)?\s*(?:am|pm)|noon")


def parse_schedule(html: str, capture: str) -> list[dict]:
    """The schedule table: a header row of days ("Mon. October 26") and one row per show ("DARK" or "2pm, 8pm").
    Keeps only the facts: show, date, number of performances and their times."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    cap = date.fromisoformat(capture)
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        head = [td.get_text(" ", strip=True) for td in trs[0].find_all(["td", "th"])]
        days = []
        for h in head[1:]:
            m = DAY_HEAD_RE.search(h)
            month = MONTHS.get(m[1].lower()) if m else None
            if not month:
                days.append(None)
                continue
            year = cap.year + (1 if month == 1 and cap.month == 12 else -1 if month == 12 and cap.month == 1 else 0)
            days.append(date(year, month, int(m[2])))
        if not any(days):
            continue
        for tr in trs[1:]:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2 or not cells[0]:
                continue
            for d, cell in zip(days, cells[1:]):
                if d is None:
                    continue
                times = TIME_RE.findall(cell.lower())
                out.append({"capture_date": capture, "date": d.isoformat(), "show": cells[0], "perfs": len(times),
                            "times": " ".join(t.replace(" ", "") for t in times)})
    return out


def write_schedule():
    rows = []
    for f in sorted((CACHE / "schedule").glob("*.html")):
        rows += parse_schedule(f.read_text(encoding="utf-8"), f.stem)
    # The same date can appear in two captures (a page updated mid-week): keep the latest capture's version.
    latest = {}
    for r in rows:
        latest[(r["date"], r["show"])] = r
    rows = sorted(latest.values(), key=lambda r: (r["date"], r["show"]))
    write_csv(SCHEDULE_CSV, SCHEDULE_COLS, rows)
    log.info("wrote %s: %d show-days, %d dates, %d with two shows", SCHEDULE_CSV.name, len(rows),
             len({r["date"] for r in rows}), sum(r["perfs"] >= 2 for r in rows))


def ts_date(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def write_policies():
    rows = []
    for f in sorted((CACHE / "policies").glob("*.html")):
        rows += parse_policies(f.read_text(encoding="utf-8"), f.stem)
    write_csv(POLICIES_CSV, POLICY_COLS, rows)
    latest = [r for r in rows if r["snapshot_date"] == max(r["snapshot_date"] for r in rows)]
    log.info("wrote %s: %d rows; latest snapshot: %d shows, %d policies (%d with a price)", POLICIES_CSV.name,
             len(rows), len({r["show"] for r in latest}), len(latest), sum(bool(r["price"]) for r in latest))


def write_csv(path: Path, cols: list[str], rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_gz(path: Path, text: str):
    """Save a raw snapshot gzipped: a Ticketmaster snapshot is ~5 MB of JSON, too big to commit daily as is."""
    path.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))


def cached_files(folder: Path, pattern: str) -> list[Path]:
    """Raw snapshots in time order. If a plain and a gzipped copy both exist, count only one."""
    return sorted({f.name.split(".")[0]: f for f in folder.glob(pattern)}.values())


def read_cached(path: Path) -> str:
    """Read a raw snapshot, gzipped (.gz) or plain (files saved before 2026-11-05)."""
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes()).decode("utf-8")
    return path.read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["grosses", "policies", "policies-history", "schedule-history", "grosses-history", "parse"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(CACHE / "scrape.log", encoding="utf-8")],
    )
    client = PoliteClient(min_interval=MIN_INTERVAL)
    if args.phase == "grosses":
        scrape_grosses(client)
    elif args.phase == "policies":
        scrape_policies(client)
    elif args.phase == "policies-history":
        client.min_interval = 5.0
        scrape_policy_history(client)
    elif args.phase == "grosses-history":
        scrape_grosses_history(client)
    elif args.phase == "schedule-history":
        client.min_interval = 5.0
        scrape_schedule_history(client)
    else:
        write_grosses()
        write_policies()
    log.info("%d requests", client.n_requests)


if __name__ == "__main__":
    main()

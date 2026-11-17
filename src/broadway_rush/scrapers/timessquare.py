"""Times Square Alliance monthly Economic Indicator Reports (SPEC 2.8 N6, C4): average daily pedestrians, the change
from a year earlier, and Times Square hotel occupancy (one month behind the report's own month).

Rachel decided on 2026-11-17 to use the public monthly reports (registry/sources.csv). The Alliance's terms say
personal, noncommercial use, so the site and presentation show only results derived from them, credited, never the
raw counts. Daily counts are only on request (draft email in her Downloads).

    .venv\\Scripts\\python -m broadway_rush.scrapers.timessquare            # fetch missing PDFs, write the CSV
    .venv\\Scripts\\python -m broadway_rush.scrapers.timessquare --parse    # rebuild the CSV from the cache only

Writes data/raw/timessquare_monthly.csv: month, avg_daily_pedestrians, pedestrians_yoy_pct, hotel_month,
hotel_occupancy_pct, published (when the PDF went online: the first 8 hex digits of the site's file id are its
upload time), file.
"""

import argparse
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from broadway_rush.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "raw" / "timessquare"
OUT = ROOT / "data" / "raw" / "timessquare_monthly.csv"
PAGE = "https://www.timessquarenyc.org/business-community/market-research-data"
LINK_RE = re.compile(r'href="(https://[^"]+/([0-9a-f]{24})_([^"/]*Monthly%20Economic%20Indicator[^"/]*\.pdf))"')
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def fetch():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    html = s.get(PAGE, timeout=60).text
    CACHE.mkdir(parents=True, exist_ok=True)
    links = sorted(set(LINK_RE.findall(html)))
    new = 0
    for url, fid, name in links:
        path = CACHE / f"{fid}_{urllib.parse.unquote(name)}"
        if path.exists():
            continue
        time.sleep(3)
        r = s.get(url, timeout=90)
        if r.status_code != 200 or r.content[:4] != b"%PDF":
            print(f"HTTP {r.status_code} for {name}", file=sys.stderr)
            continue
        path.write_bytes(r.content)
        new += 1
    print(f"{len(links)} monthly reports listed, {new} new")


def parse_one(path: Path) -> dict | None:
    from pypdf import PdfReader
    pages = PdfReader(path).pages
    p1 = re.sub(r"\s+", " ", pages[0].extract_text())
    ped = re.search(rf"([\d,]{{6,}}) ({MONTHS}) (\d{{4}}) Average Daily Pedestrians", p1)
    hot = re.search(rf"([\d.]+)% ({MONTHS}) (\d{{4}}) Hotel Occupancy", p1)
    if not ped:
        return None
    p2 = re.sub(r"\s+", " ", pages[1].extract_text()) if len(pages) > 1 else ""
    yoy = re.search(r"% Change from (\d{4}) ([▲▼]) ?(-?[\d.]+)%", p2)
    month = datetime.strptime(f"{ped.group(2)} {ped.group(3)}", "%B %Y").strftime("%Y-%m")
    fid = path.name.split("_", 1)[0]
    published = datetime.fromtimestamp(int(fid[:8], 16), tz=timezone.utc).strftime("%Y-%m-%d")
    pct = None
    if yoy and int(yoy.group(1)) == int(ped.group(3)) - 1:
        pct = abs(float(yoy.group(3))) * (-1 if yoy.group(2) == "▼" else 1)
    return {"month": month, "avg_daily_pedestrians": int(ped.group(1).replace(",", "")), "pedestrians_yoy_pct": pct,
            "hotel_month": datetime.strptime(f"{hot.group(2)} {hot.group(3)}", "%B %Y").strftime("%Y-%m") if hot else None,
            "hotel_occupancy_pct": float(hot.group(1)) if hot else None, "published": published, "file": path.name}


def parse():
    rows, bad = [], []
    for p in sorted(CACHE.glob("*_*Monthly Economic Indicator*.pdf")):
        r = parse_one(p)
        (rows.append(r) if r else bad.append(p.name))
    df = pd.DataFrame(rows).sort_values(["month", "published"]).drop_duplicates("month", keep="last")
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT.name}: {len(df)} months {df.month.min()}..{df.month.max()}; "
          f"{df.pedestrians_yoy_pct.notna().sum()} with a year-on-year change, "
          f"{df.hotel_occupancy_pct.notna().sum()} with hotel occupancy; unreadable: {bad or 'none'}")


DAILY_DIR = ROOT / "data" / "raw" / "times-square-daily"
DAILY_OUT = ROOT / "data" / "raw" / "timessquare_daily.csv"
LATE_CAMERAS = {"East 47th South AI", "West 47th South AI"}  # first count 2024-08-21


def daily():
    tot = pd.read_excel(next(DAILY_DIR.glob("*Daily Pedestrian Counts.xlsx")), header=None,
                        names=["date", "alliance_total"])
    tot["date"] = pd.to_datetime(tot.date)
    cam = pd.concat(pd.read_csv(f) for f in sorted(DAILY_DIR.glob("*by Camera.csv")))
    cam["date"] = pd.to_datetime(cam.Date, format="%d-%b-%y")
    core = cam[~cam.LocationName.isin(LATE_CAMERAS) & (cam.Count > 0)]
    n_core = cam[~cam.LocationName.isin(LATE_CAMERAS)].LocationName.nunique()
    g = core.groupby("date").agg(core_sum=("Count", "sum"), core_cameras=("LocationName", "nunique"))
    df = tot.set_index("date").join(g, how="outer")
    df.loc[df.core_cameras != n_core, "core_sum"] = np.nan
    df = df.reset_index()
    df.to_csv(DAILY_OUT, index=False, date_format="%Y-%m-%d")
    print(f"wrote {DAILY_OUT.name}: {len(df)} days {df.date.min():%Y-%m-%d}..{df.date.max():%Y-%m-%d}; "
          f"core_sum ({n_core} cameras) on {df.core_sum.notna().sum()}, alliance_total on {df.alliance_total.notna().sum()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parse", action="store_true")
    ap.add_argument("--daily", action="store_true")
    a = ap.parse_args()
    if a.daily:
        daily()
        return
    if not a.parse:
        fetch()
    parse()


if __name__ == "__main__":
    main()

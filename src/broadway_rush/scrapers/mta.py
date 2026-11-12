"""Midtown subway riders per day (SPEC 2.8 N6, C4), from the MTA's hourly ridership on data.ny.gov (Socrata API,
registry/sources.csv). Only grouped daily sums are requested: one query per month, several seconds apart.

    .venv\\Scripts\\python -u -m broadway_rush.scrapers.mta            # fetch missing months, write the CSV
    .venv\\Scripts\\python -u -m broadway_rush.scrapers.mta --parse    # rebuild the CSV from the cache only

Writes data/raw/mta_midtown_daily.csv: date, station_complex_id, part (midday = 10:00-15:59, other), riders.
Midday and weekend riders lean toward visitors; the commuter comparison is Grand Central (610).
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from broadway_rush.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "raw" / "mta"
OUT = ROOT / "data" / "raw" / "mta_midtown_daily.csv"
# Theater-district station complexes (checked on the map 2026-11-11), plus Grand Central as the commuter comparison
THEATER = {611: "Times Sq-42 St/Port Authority", 10: "49 St", 316: "50 St (1)", 162: "50 St (C,E)", 277: "7 Av (B,D,E)",
           225: "47-50 Sts-Rockefeller Ctr", 609: "42 St-Bryant Pk/5 Av", 9: "57 St-7 Av"}
COMMUTER = {610: "Grand Central-42 St"}
DATASETS = [("2020-01", "2024-12", "wujg-7c2s"), ("2025-01", "2099-12", "5wq4-mkjj")]
START = "2022-01"
GAP = 4.0

log = logging.getLogger("mta")


def dataset_for(month: str) -> str:
    return next(d for a, b, d in DATASETS if a <= month <= b)


def fetch_month(s: requests.Session, month: str) -> list:
    start = pd.Period(month, freq="M").start_time
    end = (pd.Period(month, freq="M") + 1).start_time
    ids = ", ".join(f"'{i}'" for i in [*THEATER, *COMMUTER])
    q = {
        "$select": "date_trunc_ymd(transit_timestamp) as day, station_complex_id, "
                   "case(date_extract_hh(transit_timestamp) between 10 and 15, 'midday', true, 'other') as part, "
                   "sum(ridership) as riders",
        "$where": f"station_complex_id in ({ids}) AND transit_timestamp >= '{start:%Y-%m-%dT%H:%M:%S}' "
                  f"AND transit_timestamp < '{end:%Y-%m-%dT%H:%M:%S}'",
        "$group": "day, station_complex_id, part",
        "$limit": 50000,
    }
    for attempt in range(4):
        r = s.get(f"https://data.ny.gov/resource/{dataset_for(month)}.json", params=q, timeout=600)
        if r.status_code == 200:
            return r.json()
        log.warning("%s: HTTP %s, retrying", month, r.status_code)
        time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"{month}: gave up")


def write():
    rows = []
    for f in sorted(CACHE.glob("*.json")):
        for x in json.loads(f.read_text(encoding="utf-8")):
            rows.append({"date": x["day"][:10], "station_complex_id": int(x["station_complex_id"]), "part": x["part"],
                         "riders": float(x["riders"])})
    df = pd.DataFrame(rows).sort_values(["date", "station_complex_id", "part"])
    df.to_csv(OUT, index=False)
    log.info("wrote %s: %d rows, %s to %s", OUT.name, len(df), df.date.min(), df.date.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parse", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout)])
    CACHE.mkdir(parents=True, exist_ok=True)
    if not a.parse:
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        this_month = pd.Timestamp.today().to_period("M")
        for m in pd.period_range(START, this_month, freq="M"):
            path = CACHE / f"{m}.json"
            if path.exists() and m < this_month - 1:
                continue  # the last two months get re-fetched: the MTA publishes with a lag
            t = time.time()
            data = fetch_month(s, str(m))
            path.write_text(json.dumps(data), encoding="utf-8")
            log.info("%s: %d rows in %.0fs", m, len(data), time.time() - t)
            time.sleep(GAP)
    write()


if __name__ == "__main__":
    main()

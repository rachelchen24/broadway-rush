"""NYC permitted events (SPEC section 3.9) from NYC Open Data's public API. Allowed per registry/sources.csv.

    py -m broadway_rush.scrapers.nyc_events fetch   # about 2-4 requests -> data/raw/nyc_events.csv
                                                    #                      + data/processed/nyc_events_daily.csv
    py -m broadway_rush.scrapers.nyc_events parse   # rebuild from cached JSON only (no requests)

Raw row counts mostly measure noise: sports permits are left out of the fetch, and "Special Event" includes lawn
closures and setup days (Macy's parade grandstands are listed three weeks early). So the daily table only counts
what would change a street near the theaters: full street closures in the theater district, and parades and races.
Actual dates of the biggest events come from registry/calendar_events.csv, not from this table.

The city publishes in chunks, so some stretches are nearly empty because they aren't published, not because nothing
happened (found 2026-11-05: Sept-Oct 2026, and anything over a month ahead). Those days get permits_complete = 0 and
blank counts: blank means unknown, never "no events". July 3-7, 2026 is flagged too; that one may be a real lull
during the World Cup, but it can't be told apart from unpublished data.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import pandas as pd

from broadway_rush.http import PoliteClient
from broadway_rush.scrapers.playbill import read_cached, write_gz

DATASETS = {  # the historical set also lists future events; the current one adds events further ahead
    "historical": "https://data.cityofnewyork.us/resource/bkfu-528j.json",
    "current": "https://data.cityofnewyork.us/resource/tvpp-9vvx.json",
}
START = "2024-06-01T00:00:00"
PAGE_SIZE = 50000
MIN_INTERVAL = 1.0  # robots.txt: Crawl-delay 1
TYPES = ["Parade", "Street Festival", "Single Block Festival", "Street Event", "Athletic Race / Tour", "Special Event",
         "Plaza Event", "BID Multi-Block", "Block Party", "Miscellaneous", "Open Culture"]
THEATER_DISTRICT_BOARDS = {"4", "5"}  # Manhattan community boards covering the Broadway theaters
MIN_ROWS_PER_DAY = 15  # a 7-day average below this means that stretch isn't published (normal: about 30-60 a day)
COLS = ["event_id", "event_name", "start_date_time", "end_date_time", "event_agency", "event_type", "event_borough",
        "event_location", "street_closure_type", "community_board"]

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "nyc_events"
EVENTS_CSV = RAW / "nyc_events.csv"
DAILY_CSV = ROOT / "data" / "processed" / "nyc_events_daily.csv"

log = logging.getLogger("nyc_events")


def quoted(values: list[str]) -> str:
    return ",".join("'" + v.replace("'", "''") + "'" for v in values)


def fetch(client: PoliteClient):
    CACHE.mkdir(parents=True, exist_ok=True)
    where = f"start_date_time >= '{START}' AND event_borough = 'Manhattan' AND event_type in ({quoted(TYPES)})"
    for name, url in DATASETS.items():
        rows, offset = [], 0
        while True:
            page = client.get_json(url, {"$select": ",".join(COLS), "$where": where,
                                         "$order": "event_id,start_date_time", "$limit": PAGE_SIZE, "$offset": offset})
            rows += page
            log.info("%s: %d rows so far", name, len(rows))
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        write_gz(CACHE / f"{name}.json.gz", json.dumps(rows))


def board_set(value) -> set[str]:
    return set(re.findall(r"\d+", str(value)))


def load_events() -> pd.DataFrame:
    frames = [pd.DataFrame(json.loads(read_cached(CACHE / f"{name}.json.gz"))) for name in DATASETS]
    e = pd.concat(frames, ignore_index=True).reindex(columns=COLS)
    e = e.drop_duplicates(["event_id", "start_date_time"]).sort_values(["start_date_time", "event_id"])
    e["date"] = e["start_date_time"].str[:10]
    return e


def daily_table(e: pd.DataFrame) -> pd.DataFrame:
    in_district = e["community_board"].map(lambda b: bool(board_set(b) & THEATER_DISTRICT_BOARDS))
    closure = e["street_closure_type"].eq("Full Street Closure")

    def count(mask, column):
        return e[mask].groupby("date")["event_id"].nunique().rename(column)

    days = pd.date_range(e["date"].min(), e["date"].max()).strftime("%Y-%m-%d")
    out = pd.concat([
        count(in_district & closure, "district_full_closures"),
        count(in_district & e["event_type"].eq("Parade"), "district_parades"),
        count(e["event_type"].eq("Parade"), "manhattan_parades"),
        count(e["event_type"].eq("Athletic Race / Tour"), "manhattan_races"),
    ], axis=1).reindex(days).fillna(0).astype("Int64")
    rows_per_day = e.groupby("date").size().reindex(days).fillna(0)
    complete = rows_per_day.rolling(7, center=True, min_periods=4).mean() >= MIN_ROWS_PER_DAY
    out[~complete] = pd.NA
    out["permits_complete"] = complete.astype(int)
    names = e[in_district & closure].groupby("date")["event_name"]
    named = names.agg(lambda s: "; ".join(list(dict.fromkeys(s))[:3]))
    out["district_closure_names"] = named.reindex(days).fillna("")
    return out.rename_axis("date").reset_index()


def write_all():
    e = load_events()
    e.drop(columns="date").to_csv(EVENTS_CSV, index=False)
    daily = daily_table(e)
    daily.to_csv(DAILY_CSV, index=False)
    log.info("wrote %s: %d events; %s: %d days, %s to %s", EVENTS_CSV.name, len(e), DAILY_CSV.name, len(daily),
             daily["date"].min(), daily["date"].max())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["fetch", "parse"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(CACHE / "scrape.log", encoding="utf-8")],
    )
    client = PoliteClient(min_interval=MIN_INTERVAL)
    if args.phase == "fetch":
        fetch(client)
    write_all()
    log.info("%d requests", client.n_requests)


if __name__ == "__main__":
    main()

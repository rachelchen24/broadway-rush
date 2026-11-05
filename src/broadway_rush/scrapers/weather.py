"""NYC weather (SPEC section 3.6) from Open-Meteo, at Times Square. Allowed per registry/sources.csv:
free for non-commercial use with no key; the data is CC BY 4.0, so the website must credit Open-Meteo.

    py -m broadway_rush.scrapers.weather history    # June 2024 to about 2 days ago -> data/raw/weather_nyc.csv
    py -m broadway_rush.scrapers.weather forecast   # next 16 days -> data/raw/weather_forecast_nyc.csv
    py -m broadway_rush.scrapers.weather parse      # re-parse cached JSON only (no requests)

One request each. One row per date: the whole day, plus the morning hours when people stand in the rush line.
History is a modeled estimate for that spot, not a station reading: the Jan 25, 2026 storm reads about 7.8 inches
here against 11.4 reported at Central Park. Good for "did it snow, and roughly how much", not for exact totals.
The forecast is a different kind of number again, so a model trained on history and fed forecasts will see a
difference. Keep that in mind at step 5.
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from broadway_rush.http import PoliteClient
from broadway_rush.scrapers.playbill import read_cached, write_gz

ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
START_DATE = "2024-06-01"
ARCHIVE_LAG_DAYS = 2    # the archive is about two days behind
FORECAST_DAYS = 16      # the longest the free API offers; the weekly job needs 14
MORNING_HOURS = range(6, 10)  # 6:00-9:59 am, before most box offices open at 10
MIN_INTERVAL = 1.0

PARAMS = {
    "latitude": 40.7580, "longitude": -73.9855,  # Times Square
    "hourly": "temperature_2m,apparent_temperature,precipitation,snowfall,wind_speed_10m",
    "timezone": "America/New_York", "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
    "precipitation_unit": "inch",
}

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "weather"
HISTORY_JSON = CACHE / "history.json.gz"
FORECAST_JSON = CACHE / "forecast.json.gz"
HISTORY_CSV = RAW / "weather_nyc.csv"
FORECAST_CSV = RAW / "weather_forecast_nyc.csv"

log = logging.getLogger("weather")


def daily_table(body: dict) -> pd.DataFrame:
    """Hourly API response -> one row per date. A date missing any hour is dropped, so no day is half-measured."""
    h = pd.DataFrame(body["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    h = h.dropna(subset=["temperature_2m", "precipitation"])
    h["date"] = h["time"].dt.strftime("%Y-%m-%d")
    day = h.groupby("date").agg(
        hours=("time", "size"), high_f=("temperature_2m", "max"), low_f=("temperature_2m", "min"),
        precip_in=("precipitation", "sum"), snow_in=("snowfall", "sum"),
    )
    m = h[h["time"].dt.hour.isin(MORNING_HOURS)]
    morning = m.groupby("date").agg(
        morning_temp_f=("temperature_2m", "mean"), morning_feels_f=("apparent_temperature", "mean"),
        morning_precip_in=("precipitation", "sum"), morning_snow_in=("snowfall", "sum"),
        morning_wind_mph=("wind_speed_10m", "mean"),
    )
    out = day.join(morning, how="left")
    out = out[out["hours"] >= 23].drop(columns="hours")  # 23: the day clocks go forward has only 23 hours
    return out.round(2).reset_index()


def fetch(client: PoliteClient, url: str, params: dict, path: Path):
    body = client.get_json(url, {**PARAMS, **params})
    CACHE.mkdir(parents=True, exist_ok=True)
    write_gz(path, json.dumps(body))


def write_all():
    for path, csv_path in ((HISTORY_JSON, HISTORY_CSV), (FORECAST_JSON, FORECAST_CSV)):
        if not path.exists():
            continue
        t = daily_table(json.loads(read_cached(path)))
        t.to_csv(csv_path, index=False)
        log.info("wrote %s: %d days, %s to %s", csv_path.name, len(t), t["date"].min(), t["date"].max())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["history", "forecast", "parse"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(CACHE / "scrape.log", encoding="utf-8")],
    )
    client = PoliteClient(min_interval=MIN_INTERVAL)
    if args.phase == "history":
        end = (date.today() - timedelta(days=ARCHIVE_LAG_DAYS)).isoformat()
        fetch(client, ARCHIVE_API, {"start_date": START_DATE, "end_date": end}, HISTORY_JSON)
    elif args.phase == "forecast":
        fetch(client, FORECAST_API, {"forecast_days": FORECAST_DAYS}, FORECAST_JSON)
    write_all()
    log.info("%d requests", client.n_requests)


if __name__ == "__main__":
    main()

"""Bring new ticket snapshots from the data repo into this project, then update the predictions (SPEC 6.2).

    .venv\\Scripts\\python -m broadway_rush.sync               # copy, rebuild the CSVs, update predictions if needed
    .venv\\Scripts\\python -m broadway_rush.sync --no-predict  # stop after the CSVs
    .venv\\Scripts\\python -m broadway_rush.sync --predict     # update predictions even if the schedule hasn't changed

The daily job saves to the private repo broadway-rush-data, cloned next to this project. The model and site read
data/raw here, so nothing new reaches them until this runs. It sends no requests to any ticket site, and never
overwrites or deletes a file already here.

Updating predictions refits the combo with the same settings and the same reports, which takes 2 to 4 minutes. Only
the Ticketmaster schedule changes what the site shows: the model doesn't use TKTS yet, so those files are just kept.
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from broadway_rush.scrapers import ticketmaster, tkts

ROOT = Path(__file__).resolve().parents[2]
DATA_REPO = ROOT.parent / "broadway-rush-data"
PREDICTIONS = ROOT / "web" / "data" / "predictions.json"
SOURCES = [(tkts, "*.html*", tkts.TKTS_CSV), (ticketmaster, "*.json*", ticketmaster.EVENTS_CSV)]
ET = ZoneInfo("America/New_York")
PER_PERSON, BACKTEST = 1.0, "n1.0"  # the settings behind the site's current numbers
LATE_HOURS = 30  # the job saves a Ticketmaster snapshot every morning, so older than this means runs were missed


def pull():
    if not (DATA_REPO / ".git").exists():
        sys.exit(f"No clone of the data repo at {DATA_REPO}, so nothing was copied.")
    if subprocess.run(["git", "-C", str(DATA_REPO), "pull", "--ff-only"]).returncode:
        sys.exit("Couldn't update the data repo (see above), so nothing was copied.")


def copy_new(cache: Path, pattern: str) -> int:
    """Copy snapshots this project doesn't have. A plain and a gzipped copy of one snapshot count as the same file."""
    cache.mkdir(parents=True, exist_ok=True)
    have = {f.name.split(".")[0] for f in cache.glob(pattern)}
    new = [f for f in (DATA_REPO / cache.name).glob(pattern) if f.name.split(".")[0] not in have]
    for f in new:
        shutil.copyfile(f, cache / f.name)  # copied files get today's time, which out_of_date relies on
    return len(new)


def out_of_date(csv: Path, cache: Path, pattern: str) -> bool:
    """Also catches a run that stopped after copying and before rebuilding."""
    if not csv.exists():
        return True
    built = csv.stat().st_mtime
    return any(f.stat().st_mtime > built for f in cache.glob(pattern))


def latest_snapshot(cache: Path, pattern: str) -> datetime:
    stamps = [f.name.split(".")[0].partition("-")[0] for f in cache.glob(pattern)]
    return datetime.strptime(max(stamps), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def schedule_in_predictions() -> str:
    if not PREDICTIONS.exists():
        return ""
    return json.loads(PREDICTIONS.read_text(encoding="utf-8"))["data_through"]["schedule"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    when = ap.add_mutually_exclusive_group()
    when.add_argument("--predict", action="store_true", help="update predictions even if the schedule hasn't changed")
    when.add_argument("--no-predict", action="store_true", help="stop after rebuilding the CSVs")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)

    pull()
    for module, pattern, csv in SOURCES:
        print(f"{module.CACHE.name}: {copy_new(module.CACHE, pattern)} new snapshots", flush=True)
        if out_of_date(csv, module.CACHE, pattern):
            module.write_all()

    # A run that finds an empty TKTS board saves nothing but still shows green, so this is how a long gap gets noticed
    for module, pattern, _ in SOURCES:
        newest = latest_snapshot(module.CACHE, pattern)
        print(f"Newest {module.CACHE.name} snapshot: {newest.astimezone(ET):%b %d, %I:%M %p} ET")
        hours_old = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
        if hours_old > LATE_HOURS:
            print(f"Warning: that's {hours_old:.0f} hours old, so the daily job may be missing data. Check Actions.")

    latest = latest_snapshot(ticketmaster.CACHE, "*.json*")
    if args.no_predict:
        return
    if not args.predict and schedule_in_predictions() >= latest.date().isoformat():
        print("Predictions already use this schedule, so they were left as they are.")
        return
    try:
        from broadway_rush.model.predict import build
    except ImportError:
        sys.exit('Predictions need the model packages: .venv\\Scripts\\python -m pip install -e ".[model]"')
    print("Updating predictions (2 to 4 minutes)...", flush=True)
    build(PER_PERSON, BACKTEST)


if __name__ == "__main__":
    main()

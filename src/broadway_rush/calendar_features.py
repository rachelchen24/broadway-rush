"""Calendar features, one row per date (SPEC sections 3.6 and 3.9). No web requests.

    py -m broadway_rush.calendar_features build   # -> data/processed/calendar_daily.csv

Dates that follow a rule (weekday, federal holidays, Thanksgiving, Pride March) are computed here. Everything else
comes from registry/calendar_events.csv, a hand-kept list with a source and confidence for each row.

The table stops at END because the list isn't complete after that (Fashion Week Feb 2027, the Tonys, and school
breaks after Jan 2027 aren't in it). A date past END is unknown, not "no event". Extend the list, then END.
College breaks are left out: only one was verifiable (March 16-20, 2026), and a feature with holes would mark
most real breaks as "not a break".
"""

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

START = "2024-06-01"
END = "2027-01-31"

ROOT = Path(__file__).resolve().parents[2]
EVENTS_CSV = ROOT / "registry" / "calendar_events.csv"
DAILY_CSV = ROOT / "data" / "processed" / "calendar_daily.csv"
FLAGS = ["broadway_week", "tony_awards", "nyc_marathon", "unga_general_debate", "fashion_week", "us_open_tennis",
         "world_cup_2026"]


def thanksgiving(year: int) -> pd.Timestamp:
    """Fourth Thursday of November."""
    return pd.date_range(f"{year}-11-01", f"{year}-11-30", freq="W-THU")[3]


def pride_march(year: int) -> pd.Timestamp:
    """Last Sunday of June."""
    return pd.date_range(f"{year}-06-01", f"{year}-06-30", freq="W-SUN")[-1]


def in_ranges(days: pd.DatetimeIndex, rows: pd.DataFrame) -> pd.Series:
    hit = pd.Series(False, index=days)
    for r in rows.itertuples():
        hit.loc[r.start_date:r.end_date] = True
    return hit


def build() -> pd.DataFrame:
    days = pd.date_range(START, END)
    ev = pd.read_csv(EVENTS_CSV, parse_dates=["start_date", "end_date"])
    bad = ev[ev["end_date"] < ev["start_date"]]
    if len(bad):
        raise ValueError(f"end before start in {EVENTS_CSV.name}: {bad.to_dict('records')}")

    out = pd.DataFrame(index=days)
    out["weekday"] = days.weekday  # 0 = Monday
    out["is_weekend"] = (days.weekday >= 5).astype(int)
    out["month"] = days.month
    out["day_of_month"] = days.day

    holidays = USFederalHolidayCalendar().holidays(START, END, return_name=True)
    out["federal_holiday"] = holidays.reindex(days).fillna("")
    out["is_federal_holiday"] = (out["federal_holiday"] != "").astype(int)

    years = sorted(set(days.year))
    giving = {thanksgiving(y) for y in years if thanksgiving(y) in days}
    out["thanksgiving_parade"] = days.isin(giving).astype(int)
    week = pd.Series(False, index=days)
    for d in giving:  # Monday through Sunday of that week
        week.loc[d - pd.Timedelta(days=3):d + pd.Timedelta(days=3)] = True
    out["thanksgiving_week"] = week.astype(int)
    late_december = (days.month == 12) & (days.day >= 20)
    out["christmas_new_year"] = (late_december | ((days.month == 1) & (days.day == 1))).astype(int)
    out["new_years_eve"] = ((days.month == 12) & (days.day == 31)).astype(int)
    out["pride_march"] = days.isin([pride_march(y) for y in years]).astype(int)

    breaks = ev[ev["category"] == "school_break"]
    out["school_break"] = ""
    for r in breaks.itertuples():
        out.loc[r.start_date:r.end_date, "school_break"] = r.event.removeprefix("nyc_school_")
    out["is_school_break"] = (out["school_break"] != "").astype(int)

    for flag in FLAGS:
        out[flag] = in_ranges(days, ev[ev["event"] == flag]).astype(int)

    tonys = sorted(ev.loc[ev["event"] == "tony_awards", "start_date"])
    # Blank before the first ceremony on the list, so the model can't read it as "just after the Tonys".
    out["days_since_tonys"] = [next(((d - t).days for t in reversed(tonys) if t <= d), pd.NA) for d in days]
    out["days_since_tonys"] = out["days_since_tonys"].astype("Int64")
    return out.rename_axis("date").reset_index().assign(date=lambda t: t["date"].dt.strftime("%Y-%m-%d"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["build"])
    ap.parse_args()
    t = build()
    t.to_csv(DAILY_CSV, index=False)
    print(f"wrote {DAILY_CSV.name}: {len(t)} days, {t['date'].min()} to {t['date'].max()}")


if __name__ == "__main__":
    main()

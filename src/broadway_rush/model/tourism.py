"""Tourist and season inputs (SPEC 2.8 N6), for any date, from what was published before it.

- midtown_riders_vs_last_year: subway riders at the 8 theater-district stations over the 28 days ending 14 days
  before the date (the MTA publishes about two weeks late), against the same 28 days a year earlier. 0.05 = 5% busier.
- midtown_riders_season: how busy that week of the year usually is at those stations (all hours), from earlier years
  only: the week's average day over the year's average day, so 1.10 = a usually busy week.
- tourist_season_index: the same, but for the visitor-leaning share: midday (10:00-15:59) riders at the theater
  stations divided by midday riders at Grand Central, a mostly-commuter station.
- attendance_season_index: how full Broadway usually is that week of the year: total weekly attendance over the
  year's average week, from earlier years' grosses only (2020-21 shutdown left out).

Week of year is ISO; each index is smoothed over the week and its two neighbours. The Times Square foot-traffic
inputs (ts_peds_*) wait for Rachel's decision on the Alliance's terms (registry/sources.csv).
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
THEATER_IDS = [611, 10, 316, 162, 277, 225, 609, 9]
COMMUTER_ID = 610
LAG_DAYS = 14
WINDOW = 28
TOURISM_FEATURES = ["midtown_riders_vs_last_year", "midtown_riders_season", "tourist_season_index",
                    "attendance_season_index"]


def _season_profile(series: pd.Series) -> pd.DataFrame:
    """Daily (or weekly) values -> per (year, iso week) ratio to that year's mean, for full-ish years only."""
    df = series.rename("v").to_frame()
    iso = df.index.isocalendar()
    df["year"], df["week"] = iso.year.to_numpy(), iso.week.to_numpy()
    wk = df.groupby(["year", "week"]).v.mean().reset_index()
    counts = wk.groupby("year").week.transform("size")
    wk = wk[counts >= 40]  # a year needs most of its weeks to say what's usual
    wk["ratio"] = wk.v / wk.groupby("year").v.transform("mean")
    return wk[["year", "week", "ratio"]]


def _lookup(profile: pd.DataFrame, dates: pd.Series) -> np.ndarray:
    """For each date: mean ratio for its iso week (+-1 week) over years strictly before the date's year."""
    out = []
    by_week = {w: g for w, g in profile.groupby("week")}
    for d in dates:
        y, w = d.isocalendar()[0], d.isocalendar()[1]
        parts = [by_week.get(((w - 1 + k - 1) % 53) + 1) for k in (-1, 0, 1)]
        g = pd.concat([p for p in parts if p is not None]) if any(p is not None for p in parts) else None
        g = g[g.year < y] if g is not None else None
        out.append(float(g.ratio.mean()) if g is not None and len(g) else np.nan)
    return np.array(out)


class Tourism:
    def __init__(self):
        path = RAW / "mta_midtown_daily.csv"
        self.ok = path.exists()
        if self.ok:
            m = pd.read_csv(path, parse_dates=["date"])
            theater = m[m.station_complex_id.isin(THEATER_IDS)]
            self.all_day = theater.groupby("date").riders.sum().asfreq("D")
            mid_t = theater[theater.part == "midday"].groupby("date").riders.sum()
            mid_c = m[(m.station_complex_id == COMMUTER_ID) & (m.part == "midday")].groupby("date").riders.sum()
            self.ratio = (mid_t / mid_c).asfreq("D")
            self.rider_profile = _season_profile(self.all_day.dropna())
            self.tourist_profile = _season_profile(self.ratio.dropna())
        frames = [pd.read_csv(RAW / "grosses_playbill.csv", parse_dates=["week_ending"])]
        if (RAW / "grosses_history_playbill.csv").exists():
            frames.insert(0, pd.read_csv(RAW / "grosses_history_playbill.csv", parse_dates=["week_ending"]))
        g = pd.concat(frames).drop_duplicates(["week_ending", "production_id"])
        att = g.groupby("week_ending").seats_sold.sum()
        att = att[(att.index < "2020-03-08") | (att.index > "2021-09-12")]
        self.attendance_profile = _season_profile(att)

    def vs_last_year(self, dates: pd.Series) -> np.ndarray:
        s = self.all_day
        out = []
        for d in dates:
            end = d - pd.Timedelta(days=LAG_DAYS)
            now = s.loc[end - pd.Timedelta(days=WINDOW - 1):end]
            ago = s.loc[end - pd.Timedelta(days=364 + WINDOW - 1):end - pd.Timedelta(days=364)]
            ok = now.notna().sum() >= 20 and ago.notna().sum() >= 20
            out.append(float(now.mean() / ago.mean() - 1) if ok else np.nan)
        return np.array(out)

    def build(self, dates: pd.Series) -> pd.DataFrame:
        u = pd.Series(pd.to_datetime(pd.Series(dates).unique()))
        res = pd.DataFrame({"date": u})
        if self.ok:
            res["midtown_riders_vs_last_year"] = self.vs_last_year(u)
            res["midtown_riders_season"] = _lookup(self.rider_profile, u)
            res["tourist_season_index"] = _lookup(self.tourist_profile, u)
        else:
            for c in TOURISM_FEATURES[:3]:
                res[c] = np.nan
        res["attendance_season_index"] = _lookup(self.attendance_profile, u)
        return res

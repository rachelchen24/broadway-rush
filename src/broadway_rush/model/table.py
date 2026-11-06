"""Model table (SPEC 5.2, 5.2a): turns reports into line points, cutoff labels and outcomes, plus features.

    .venv\\Scripts\\python -m broadway_rush.model.table

Every feature is computed by Features.build(), for history and the future alike, from what would be known 7 days
before the performance: grosses at least 9 days old, line reports at least 7 days old, the calendar. Writes
model_line.csv, model_cutoff.csv, model_outcomes.csv and model_funnel.json to data/processed.
"""

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from broadway_rush.catalog import match, name_keys

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
START = pd.Timestamp("2024-06-01")
FAILED = {"sold_out_before_me", "sro_only", "full_price_only"}
MAX_HOURS_BEFORE = 9.0  # earlier than this is a camp-out or a mistyped time, not a morning line

LINE_FEATURES = [
    "hours_before", "show_code", "weekday", "is_school_break", "is_federal_holiday", "thanksgiving_week",
    "christmas_new_year", "broadway_week", "tonys_30d", "pct_cap", "avg_ticket", "weeks_since_first",
    "show_type_code", "seats", "recent_level", "recent_thin",
]
WEATHER_FEATURES = ["morning_feels_f", "morning_precip_in", "morning_snow_in"]
CUTOFF_FEATURES = ["weekend", "pct_cap", "log_seats", "is_musical"]
FALLBACK_OPENING = {**{d: 10.0 for d in range(6)}, 6: 12.0}


def clean_text(s) -> str:
    return re.sub(r"[^\x20-\x7e]+", "-", s).strip() if isinstance(s, str) else ""


def parse_opening(text) -> dict[int, float] | None:
    """'10 AM Monday-Saturday, 12 PM Sunday' -> {0: 10.0, ..., 5: 10.0, 6: 12.0}. None if there's no usable time."""
    t = clean_text(text).lower()
    m = re.match(r"(\d{1,2})(?::(\d\d))?\s*(am|pm)", t)
    if not m:
        return None
    hour = (int(m[1]) % 12) + (12 if m[3] == "pm" else 0) + int(m[2] or 0) / 60
    sunday = hour
    if "sunday" in t:
        after = t[t.index("sat"):] if "sat" in t else t
        s = re.search(r"(noon|\d{1,2}\s*(?:am|pm)).{0,20}sunday|sunday.{0,20}(noon|\d{1,2}\s*(?:am|pm))", after)
        word = (s[1] or s[2]) if s else None
        if word == "noon":
            sunday = 12.0
        elif word:
            n = re.match(r"(\d{1,2})\s*(am|pm)", word)
            sunday = (int(n[1]) % 12) + (12 if n[2] == "pm" else 0)
    if "monday" in t and "sunday" not in t:
        sunday = 12.0  # "10 AM Monday-Saturday" says nothing about Sunday: use the usual noon
    return {**{d: hour for d in range(6)}, 6: sunday}


def load_policies(shows: pd.DataFrame) -> pd.DataFrame:
    """Every policy row, with show_id ('' if the show isn't in the catalog yet)."""
    p = pd.read_csv(RAW / "policies_playbill.csv")
    keys = name_keys(shows)
    by_id = {s.show_id: s for s in shows.itertuples()}
    last = shows.last_week.max()
    ids = {}
    for name, when in p[["show", "snapshot_date"]].drop_duplicates().itertuples(index=False):
        sid, _ = match(name, when, keys, by_id, last)
        ids[(name, when)] = sid
    p["show_id"] = [ids[k] for k in zip(p.show, p.snapshot_date)]
    p["policy_type"] = p.policy_type.map(clean_text)
    return p


def opening_lookup(policies: pd.DataFrame):
    """show_id, date -> box office opening hours by weekday, from the General Rush policy in force on that date."""
    g = policies[policies.policy_type.str.startswith("General Rush") & policies.show_id.fillna("").ne("")]
    table: dict[str, list] = {}
    for sid, rows in g.sort_values("snapshot_date").groupby("show_id"):
        table[sid] = [(pd.Timestamp(r.snapshot_date), parse_opening(r.time)) for r in rows.itertuples()]

    def opening(sid, day) -> dict[int, float]:
        rows = table.get(sid)
        if not rows:
            return FALLBACK_OPENING
        chosen = rows[0][1]
        for when, parsed in rows:
            if when <= day and parsed:
                chosen = parsed
        return chosen or FALLBACK_OPENING

    return opening


def clock_hours(s: pd.Series) -> pd.Series:
    parts = s.str.extract(r"^(\d{1,2}):(\d{2})")
    return pd.to_numeric(parts[0], errors="coerce") + pd.to_numeric(parts[1], errors="coerce") / 60


def base_reports(funnel: dict) -> pd.DataFrame:
    r = pd.read_csv(PROCESSED / "reports.csv", low_memory=False)
    funnel["all_observations"] = len(r)
    r = r[r.rush_type == "general"]
    funnel["in_person_general_rush"] = len(r)
    r = r[r.show_id.notna() & (r.show_id != "-")]
    funnel["mapped_to_a_broadway_show"] = len(r)
    r = r[r.confidence != "low"]
    funnel["not_low_confidence"] = len(r)
    r = r.assign(date=pd.to_datetime(r.perf_date, errors="coerce"))
    r = r[r.date.notna() & (r.date >= START)].copy()
    funnel["stated_valid_date_from_june_2024"] = len(r)
    r["created"] = pd.to_datetime(r.created_et, errors="coerce", utc=True).dt.tz_localize(None)
    # A date far from when the comment was posted is usually a misread year or a plan, not a report.
    gap = (r.created.dt.normalize() - r.date).dt.days
    r = r[gap.between(-2, 14)]
    funnel["date_within_2_days_before_to_14_days_after_the_comment"] = len(r)
    # A date outside the show's run can't be a real rush report for it.
    shows = pd.read_csv(PROCESSED / "shows.csv", parse_dates=["first_week", "last_week"]).set_index("show_id")
    first = shows.first_week.reindex(r.show_id).to_numpy()
    last = shows.last_week.reindex(r.show_id).to_numpy()
    open_ended = shows.last_week.max()
    last = np.where(last == np.datetime64(open_ended), np.datetime64("2100-01-01"), last)
    r = r[(r.date.to_numpy() >= first - np.timedelta64(7, "D")) & (r.date.to_numpy() <= last + np.timedelta64(7, "D"))]
    funnel["date_inside_the_shows_run"] = len(r)
    return r.copy()


def line_points(r: pd.DataFrame, opening, funnel: dict) -> pd.DataFrame:
    """People already in line at a time before opening. Someone who arrives and is #p sees p-1 people ahead."""
    lc = r[(r.kind == "line_count") & r["count"].notna() & r.time.notna() & ~r.count_qual.isin(["at_least", "at_most"])]
    lc = lc.assign(clock=clock_hours(lc.time), raw=lc["count"], people=lc["count"])
    at = r[(r.kind == "attempt") & r.arrival_time.notna() & (r.line_position >= 1)]
    at = at.assign(clock=clock_hours(at.arrival_time), raw=at.line_position, people=at.line_position - 1)
    cols = ["show_id", "date", "created", "kind", "clock", "raw", "people", "source"]
    x = pd.concat([lc[cols], at[cols]], ignore_index=True).dropna(subset=["clock"])
    funnel["line_points_with_a_time_and_number"] = len(x)
    x["open_hour"] = [opening(s, d)[d.weekday()] for s, d in zip(x.show_id, x.date)]
    x["hours_before"] = x.open_hour - x.clock
    x = x[(x.hours_before > 0) & (x.hours_before <= MAX_HOURS_BEFORE)]
    funnel["line_points_before_opening"] = len(x)
    x = x.drop_duplicates(["show_id", "date", "clock", "raw"]).copy()
    funnel["line_points_after_dropping_duplicates"] = len(x)
    x["weight"] = 1 / x.groupby(["show_id", "date"]).show_id.transform("size")
    return x.sort_values(["date", "show_id", "clock"]).reset_index(drop=True)


def cutoff_labels(r: pd.DataFrame, funnel: dict) -> pd.DataFrame:
    """One row per show-day: stated total, highest position that got a ticket, lowest position that didn't."""
    stated = r[(r.kind == "supply") & (r.stated_qual == "total") & (r.stated_count > 0)]
    exact = stated.groupby(["show_id", "date"]).stated_count.median().round().rename("exact")
    at = r[(r.kind == "attempt") & (r.line_position >= 1)]
    low = at[at.outcome == "got_rush"].groupby(["show_id", "date"]).line_position.max().rename("lower_pos")
    up = at[at.outcome.isin(FAILED)].groupby(["show_id", "date"]).line_position.min().rename("upper_pos")
    x = pd.concat([exact, low, up], axis=1).reset_index()
    created = r.groupby(["show_id", "date"]).created.min().rename("created")
    x = x.merge(created, on=["show_id", "date"], how="left")
    bad = x.exact.isna() & x.lower_pos.notna() & x.upper_pos.notna() & (x.lower_pos >= x.upper_pos)
    funnel["cutoff_show_days_contradictory_dropped"] = int(bad.sum())
    x = x[~bad]
    funnel["cutoff_show_days"] = len(x)
    funnel["cutoff_stated_count"] = int(x.exact.notna().sum())
    funnel["cutoff_lower_only"] = int((x.exact.isna() & x.lower_pos.notna() & x.upper_pos.isna()).sum())
    funnel["cutoff_upper_only"] = int((x.exact.isna() & x.lower_pos.isna() & x.upper_pos.notna()).sum())
    funnel["cutoff_both_bounds"] = int((x.exact.isna() & x.lower_pos.notna() & x.upper_pos.notna()).sum())
    return x.sort_values(["date", "show_id"]).reset_index(drop=True)


def outcomes(r: pd.DataFrame, opening, funnel: dict) -> pd.DataFrame:
    """Attempts with an arrival time and a known result: the rough check on the chance of a ticket."""
    a = r[(r.kind == "attempt") & r.arrival_time.notna() & r.outcome.isin(FAILED | {"got_rush"})]
    a = a.assign(clock=clock_hours(a.arrival_time), got=(a.outcome == "got_rush").astype(int))
    a["open_hour"] = [opening(s, d)[d.weekday()] for s, d in zip(a.show_id, a.date)]
    a["hours_before"] = a.open_hour - a.clock
    a = a[(a.hours_before > 0) & (a.hours_before <= MAX_HOURS_BEFORE)]
    a = a.drop_duplicates(["show_id", "date", "clock", "outcome", "line_position"])
    funnel["outcomes_arrived_before_opening_known_result"] = len(a)
    funnel["outcomes_share_got_a_ticket"] = round(float(a.got.mean()), 4)
    cols = ["show_id", "date", "created", "clock", "hours_before", "got", "outcome", "line_position"]
    return a[cols].sort_values(["date", "show_id"]).reset_index(drop=True)


class Features:
    """Builds features for any (show_id, date), using only what's known 7 days before that date."""

    def __init__(self, shows: pd.DataFrame, line: pd.DataFrame):
        self.shows = shows.set_index("show_id")
        self.codes = {sid: i for i, sid in enumerate(sorted(shows.show_id))}
        g = pd.read_csv(RAW / "grosses_playbill.csv", parse_dates=["week_ending"])
        by_prod = shows.drop_duplicates("production_id").set_index("production_id").show_id
        g["show_id"] = g.production_id.map(by_prod)
        self.grosses = (
            g.dropna(subset=["show_id"])[["show_id", "week_ending", "pct_cap", "avg_ticket"]]
            .sort_values("week_ending").reset_index(drop=True)
        )
        cal = pd.read_csv(PROCESSED / "calendar_daily.csv", parse_dates=["date"])
        cal["tonys_30d"] = cal.days_since_tonys.between(0, 30).astype(int)
        self.calendar = cal[
            ["date", "weekday", "is_weekend", "is_school_break", "is_federal_holiday", "thanksgiving_week",
             "christmas_new_year", "broadway_week", "tonys_30d"]
        ]
        wx = pd.concat([
            pd.read_csv(RAW / "weather_nyc.csv", parse_dates=["date"]),
            pd.read_csv(RAW / "weather_forecast_nyc.csv", parse_dates=["date"]),
        ]).drop_duplicates("date", keep="last")
        self.weather = wx[["date", *WEATHER_FEATURES]]
        # Recent line level: each show-day counts once, from reports about 2 to 0.5 hours before opening.
        near = line[(line.hours_before >= 0.5) & (line.hours_before <= 2)]
        self.near = (
            near.assign(level=np.log1p(near.people))
            .groupby(["show_id", "date"]).agg(level=("level", "mean"), n=("level", "size"), created=("created", "max"))
            .reset_index()
        )

    def recent(self, keys: pd.DataFrame) -> pd.DataFrame:
        by_show = {s: g for s, g in self.near.groupby("show_id")}
        levels, counts = [], []
        for sid, day in keys[["show_id", "date"]].itertuples(index=False):
            g = by_show.get(sid)
            if g is None:
                levels.append(np.nan)
                counts.append(0)
                continue
            newest = day - pd.Timedelta(days=7)
            keep = (g.date >= day - pd.Timedelta(days=35)) & (g.date <= newest) & (g.created <= newest + pd.Timedelta(days=1))
            use = g[keep]
            levels.append(use.level.mean() if len(use) else np.nan)
            counts.append(int(use.n.sum()))
        return pd.DataFrame({"recent_level": levels, "recent_n": counts}, index=keys.index)

    def build(self, rows: pd.DataFrame) -> pd.DataFrame:
        keys = rows[["show_id", "date"]].drop_duplicates().reset_index(drop=True)
        keys = keys.merge(self.calendar, on="date", how="left").merge(self.weather, on="date", how="left")
        keys[["recent_level", "recent_n"]] = self.recent(keys)
        keys["recent_thin"] = (keys.recent_n < 3).astype(int)
        lagged = keys.assign(asof=keys.date - pd.Timedelta(days=9)).sort_values("asof")
        lagged = pd.merge_asof(
            lagged, self.grosses, left_on="asof", right_on="week_ending", by="show_id",
            tolerance=pd.Timedelta(days=35),
        )
        keys = lagged.drop(columns="asof")
        meta = self.shows.reindex(keys.show_id)
        keys["show_code"] = [self.codes.get(s, -1) for s in keys.show_id]
        keys["show_type_code"] = meta.show_type.map({"Musical": 0, "Play": 1, "Special": 2}).to_numpy()
        keys["is_musical"] = (meta.show_type == "Musical").astype(int).to_numpy()
        keys["seats"] = meta.seats.to_numpy()
        keys["log_seats"] = np.log(keys.seats)
        first = pd.to_datetime(meta.first_week).to_numpy()
        keys["weeks_since_first"] = (keys.date.to_numpy() - first) / np.timedelta64(7, "D")
        keys["weekend"] = keys.is_weekend
        return rows.merge(keys, on=["show_id", "date"], how="left")


def load_tables() -> dict:
    p = PROCESSED
    return {
        "shows": pd.read_csv(p / "shows.csv"),
        "line": pd.read_csv(p / "model_line.csv", parse_dates=["date", "created"]),
        "cutoff": pd.read_csv(p / "model_cutoff.csv", parse_dates=["date", "created"]),
        "outcomes": pd.read_csv(p / "model_outcomes.csv", parse_dates=["date", "created"]),
    }


def tickets_bounds(cut: pd.DataFrame, per_person: float) -> pd.DataFrame:
    """Turns positions (people) into bounds on tickets. Someone at p who got one: at least per_person * p tickets.
    Someone at p who didn't: fewer than per_person * p."""
    out = cut.copy()
    out["lower_t"] = [math.ceil(per_person * p - 1e-9) if p == p else np.nan for p in out.lower_pos]
    out["upper_t"] = [math.ceil(per_person * p - 1e-9) - 1 if p == p else np.nan for p in out.upper_pos]
    return out


def build():
    funnel: dict = {"comments_scanned": 139584}
    shows = pd.read_csv(PROCESSED / "shows.csv")
    policies = load_policies(shows)
    opening = opening_lookup(policies)
    r = base_reports(funnel)
    line = line_points(r, opening, funnel)
    cut = cutoff_labels(r, funnel)
    out = outcomes(r, opening, funnel)
    feats = Features(shows, line)
    line = feats.build(line)
    cut = feats.build(cut)
    out = feats.build(out)
    funnel["line_show_days"] = int(line.groupby(["show_id", "date"]).ngroups)
    funnel["line_shows"] = int(line.show_id.nunique())
    funnel["cutoff_shows"] = int(cut.show_id.nunique())
    funnel["first_date"] = str(line.date.min().date())
    funnel["last_date"] = str(line.date.max().date())
    line.to_csv(PROCESSED / "model_line.csv", index=False)
    cut.to_csv(PROCESSED / "model_cutoff.csv", index=False)
    out.to_csv(PROCESSED / "model_outcomes.csv", index=False)
    (PROCESSED / "model_funnel.json").write_text(json.dumps(funnel, indent=2), encoding="utf-8")
    print(json.dumps(funnel, indent=2))
    return funnel


if __name__ == "__main__":
    build()

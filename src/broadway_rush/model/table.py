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
# Built 2026-11-11 for the final model (SPEC 2.8 N7, N8). Not in LINE_FEATURES or CUTOFF_FEATURES until the N9 tests.
SCHEDULE_FEATURES = ["two_shows_today", "shows_playing_today", "rush_shows_today"]
# Show stage from the weekly grosses (SPEC 2.8 N7, C9): week-level, since grosses are weekly. Opening dates are
# announced months ahead, so they count as known 7 days out. Blank days_since_opening = opened before June 2024.
STAGE_FEATURES = ["in_previews", "days_since_opening"]
# Tourist traffic and season (SPEC 2.8 N6), see model/tourism.py
from broadway_rush.model.tourism import TIMES_SQUARE_FEATURES, TOURISM_FEATURES, Tourism  # noqa: E402
# NYU classes / finals / break (SPEC 2.8 N11), see nyu_calendar.py. Same rule: out of the models until N9.
from broadway_rush.nyu_calendar import NYU_FEATURES, session_by_day  # noqa: E402
from broadway_rush.special_days import drop_special  # noqa: E402
# Star and cast inputs (SPEC 2.8 N5) and the TKTS board (tier 3), see model/cast.py and model/board.py
from broadway_rush.model.board import BOARD_FEATURES, Board  # noqa: E402
from broadway_rush.model.cast import STAR_FEATURES, Cast  # noqa: E402
# The final model's candidate inputs (SPEC 2.8 N9 step 1, "one full model with everything", 2026-11-17). The first
# model's lists above stay unchanged so its results (tag more1) can be reproduced. Ticket side: the 4 first-model
# inputs plus 4 with a reason to move ticket counts (SPEC: test only 6-8 on the slow ticket model).
LINE_FEATURES_V2 = (LINE_FEATURES + SCHEDULE_FEATURES + STAGE_FEATURES + TOURISM_FEATURES + TIMES_SQUARE_FEATURES
                    + NYU_FEATURES + STAR_FEATURES + BOARD_FEATURES)
CUTOFF_FEATURES_V2 = CUTOFF_FEATURES + ["two_shows_today", "stars_in_cast", "star_final_2wks", "tkts_board_share_14d"]
# The final model (Rachel 2026-11-18 / 11-23): the lean 14 line inputs (LINE_FEATURES_V2 minus data/interim/lean_drop.txt,
# tags lean_t4 / lean_so2 / final_locked) and the original 4 ticket inputs (CUTOFF_FEATURES), trained with sold-out caps.
LINE_FEATURES_FINAL = ["hours_before", "show_code", "weekday", "pct_cap", "avg_ticket", "weeks_since_first", "show_type_code",
                       "seats", "recent_level", "recent_thin", "two_shows_today", "shows_playing_today", "rush_shows_today",
                       "nyu_session"]
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


AT_OPENING_HOURS = 1 / 60  # a report "at opening" counts as one minute before


def clock_hours(s: pd.Series) -> pd.Series:
    parts = s.str.extract(r"^(\d{1,2}):(\d{2})")
    return pd.to_numeric(parts[0], errors="coerce") + pd.to_numeric(parts[1], errors="coerce") / 60


def base_reports(funnel: dict) -> pd.DataFrame:
    r = pd.read_csv(PROCESSED / "reports.csv", low_memory=False)
    funnel["all_observations"] = len(r)
    r = drop_special(r, funnel)  # one-off events (registry/special_rush_days.csv), Rachel 2026-11-18
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
    return fix_am_pm(r.copy(), funnel)


def fix_am_pm(r: pd.DataFrame, funnel: dict) -> pd.DataFrame:
    """A report can't describe a time later than when it was posted, so "16:45" posted at 9:30 that morning is 4:45 am.
    The extraction sometimes reads "7:13" in a list as 19:13, which would throw the report out as after opening."""
    posted = clock_hours(r.created_et.str[11:16])
    same_day = r.created_et.str[:10] == r.perf_date.astype(str).str[:10]
    fixed = 0
    for col in ("time", "arrival_time"):
        t = clock_hours(r[col])
        bad = same_day & (t >= 12.5) & (t > posted + 0.25)
        am = t[bad] - 12
        r.loc[bad, col] = [f"{int(h):02d}:{int(round((h - int(h)) * 60)):02d}" for h in am]
        fixed += int(bad.sum())
    funnel["times_corrected_from_pm_to_am"] = fixed
    return r


def line_points(r: pd.DataFrame, opening, funnel: dict) -> pd.DataFrame:
    """People already in line at a time before opening. Someone who arrives and is #p sees p-1 people ahead."""
    lc = r[(r.kind == "line_count") & r["count"].notna() & r.time.notna() & ~r.count_qual.isin(["at_least", "at_most"])]
    lc = lc.assign(clock=clock_hours(lc.time), raw=lc["count"], people=lc["count"])
    at = r[(r.kind == "attempt") & r.arrival_time.notna() & (r.line_position >= 1)]
    at = at.assign(clock=clock_hours(at.arrival_time), raw=at.line_position, people=at.line_position - 1)
    cols = ["show_id", "date", "created", "kind", "clock", "raw", "people", "source"]
    x = pd.concat([lc[cols], at[cols]], ignore_index=True).dropna(subset=["clock"])
    # A count "by the time the box office opened" has no clock time: it's the last moment before opening
    ao = r[r["at_opening"].astype(str).eq("True")] if "at_opening" in r else r.iloc[0:0]
    ao = ao[~ao.count_qual.isin(["at_least", "at_most"])]
    ao = ao.assign(clock=np.nan, raw=ao["count"], people=ao["count"])
    x = pd.concat([x, ao[cols]], ignore_index=True)
    funnel["line_points_with_a_time_and_number"] = len(x)
    x["open_hour"] = [opening(s, d)[d.weekday()] for s, d in zip(x.show_id, x.date)]
    x["clock"] = x.clock.fillna(x.open_hour - AT_OPENING_HOURS)
    x["hours_before"] = x.open_hour - x.clock
    x = x[(x.hours_before > 0) & (x.hours_before <= MAX_HOURS_BEFORE)]
    funnel["line_points_before_opening"] = len(x)
    x = x.drop_duplicates(["show_id", "date", "clock", "raw"]).copy()
    funnel["line_points_after_dropping_duplicates"] = len(x)
    x["weight"] = 1 / x.groupby(["show_id", "date"]).show_id.transform("size")
    return x.sort_values(["date", "show_id", "clock"]).reset_index(drop=True)


# "Sold out at T" plus a line count within this many hours before T caps the day's tickets (Rachel 2026-11-23: 2 h).
SOLD_OUT_WINDOW_H = 2.0


def sold_out_caps(r: pd.DataFrame, funnel: dict) -> pd.DataFrame:
    """An "at most" clue: a show sold out at T and someone counted N people in line within 2 h before T, so the day
    had at most about N tickets. Stored as upper_pos_soldout = N + 1 (as if the person at N + 1 missed out). Only
    `backtest --soldout` trains on it; test labels never change, so runs stay comparable on identical reports."""
    so = r[r.sold_out_time.notna()]
    so = so.assign(so=clock_hours(so.sold_out_time.astype(str))).dropna(subset=["so"])
    so = so.groupby(["show_id", "date"]).so.min().reset_index()
    lc = r[(r.kind == "line_count") & r["count"].notna() & r.time.notna() & ~r.count_qual.isin(["at_least", "at_most"])]
    lc = lc.assign(t=clock_hours(lc.time.astype(str)))[["show_id", "date", "t", "count"]].dropna()
    lc = lc[lc["count"] >= 1]
    m = so.merge(lc, on=["show_id", "date"])
    m = m[(m.t <= m.so) & (m.so - m.t <= SOLD_OUT_WINDOW_H)]
    m = m.sort_values("t").groupby(["show_id", "date"]).tail(1)
    funnel["cutoff_sold_out_days"] = len(so)
    funnel["cutoff_sold_out_caps"] = len(m)
    return m.assign(upper_pos_soldout=m["count"] + 1)[["show_id", "date", "upper_pos_soldout"]]


def with_soldout(cut: pd.DataFrame, use: bool) -> pd.DataFrame:
    """Rows with the usual labels; with use=True also the sold-out caps, applied only where there's no stated count
    and the cap doesn't contradict someone who got a ticket further back."""
    has = cut.exact.notna() | cut.lower_pos.notna() | cut.upper_pos.notna()
    if not use or "upper_pos_soldout" not in cut:
        return cut[has]
    cap = cut.upper_pos_soldout
    ok = cap.notna() & cut.exact.isna() & (cut.lower_pos.isna() | (cap > cut.lower_pos))
    out = cut.copy()
    out.loc[ok, "upper_pos"] = np.fmin(out.upper_pos[ok], cap[ok])
    return out[has | ok]


def cutoff_labels(r: pd.DataFrame, funnel: dict) -> pd.DataFrame:
    """One row per show-day: stated total, highest position that got a ticket, lowest position that didn't."""
    stated = r[(r.kind == "supply") & (r.stated_qual == "total") & (r.stated_count > 0)]
    exact = stated.groupby(["show_id", "date"]).stated_count.median().round().rename("exact")
    at = r[(r.kind == "attempt") & (r.line_position >= 1)]
    low = at[at.outcome == "got_rush"].groupby(["show_id", "date"]).line_position.max().rename("lower_pos")
    up = at[at.outcome.isin(FAILED)].groupby(["show_id", "date"]).line_position.min().rename("upper_pos")
    x = pd.concat([exact, low, up], axis=1).reset_index()
    bad = x.exact.isna() & x.lower_pos.notna() & x.upper_pos.notna() & (x.lower_pos >= x.upper_pos)
    funnel["cutoff_show_days_contradictory_dropped"] = int(bad.sum())
    x = x[~bad]
    funnel["cutoff_show_days"] = len(x)
    x = x.merge(sold_out_caps(r, funnel), on=["show_id", "date"], how="outer")
    funnel["cutoff_sold_out_caps_new_days"] = int((x.exact.isna() & x.lower_pos.isna() & x.upper_pos.isna()).sum())
    created = r.groupby(["show_id", "date"]).created.min().rename("created")
    x = x.merge(created, on=["show_id", "date"], how="left")
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


def load_schedule_days(shows: pd.DataFrame, policies: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per show-day performance counts from Playbill's archived weekly schedules (SPEC 2.8 N7, N8), mapped to show_id.
    Weeks with no archived copy are filled from the same show's usual count for that weekday, taken from the
    nearest captured weeks (within 6 weeks either side). A schedule is announced ahead, so using it 7 days out is fair.
    Columns: show_id, date, perfs, filled (1 when it's the usual count rather than that week's own page)."""
    path = RAW / "schedule_playbill.csv"
    cols = ["show_id", "date", "perfs", "filled"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    s = pd.read_csv(path, parse_dates=["date"])
    keys = name_keys(shows)
    by_id = {x.show_id: x for x in shows.itertuples()}
    last = shows.last_week.max()
    ids = {}
    for name, when in s[["show", "capture_date"]].drop_duplicates().itertuples(index=False):
        ids[(name, when)] = match(name, when, keys, by_id, last)[0]
    s["show_id"] = [ids[k] for k in zip(s.show, s.capture_date)]
    s = s[s.show_id.ne("") & s.show_id.ne("-")]
    s = s.groupby(["show_id", "date"], as_index=False).perfs.max().assign(filled=0)
    # Fill weeks with no capture: every date in each show's run that the pages don't cover
    meta = shows.set_index("show_id")
    fills = []
    for sid, g in s.groupby("show_id"):
        first = max(pd.Timestamp(meta.loc[sid].first_week) - pd.Timedelta(days=6), START)
        end = pd.Timestamp(meta.loc[sid].last_week)
        have = set(g.date)
        missing = [d for d in pd.date_range(first, end) if d not in have]
        if not missing:
            continue
        g = g.assign(wd=g.date.dt.weekday)
        for d in missing:
            near = g[(g.wd == d.weekday()) & ((g.date - d).abs() <= pd.Timedelta(weeks=6))]
            if len(near):
                fills.append((sid, d, int(near.perfs.median()), 1))
    if fills:
        s = pd.concat([s, pd.DataFrame(fills, columns=cols)], ignore_index=True)
    return s.sort_values(["date", "show_id"]).reset_index(drop=True)[cols]


def schedule_day_counts(days: pd.DataFrame, policies: pd.DataFrame | None) -> pd.DataFrame:
    """date -> shows_playing_today, rush_shows_today (shows playing that day with in-person General Rush listed in
    Playbill's policy list in force then). Rushers spread across fewer shows on dark days like Monday."""
    playing = days[days.perfs > 0]
    out = playing.groupby("date").show_id.nunique().rename("shows_playing_today").to_frame()
    if policies is not None and len(policies):
        g = policies[policies.policy_type.str.startswith("General Rush") & policies.show_id.fillna("").ne("")]
        snaps = sorted(pd.to_datetime(g.snapshot_date.unique()))
        by_snap = {pd.Timestamp(k): set(v.show_id) for k, v in g.groupby("snapshot_date")}
        def rush_count(day, ids):
            known = [x for x in snaps if x <= day] or snaps[:1]
            return len(ids & by_snap[known[-1]])
        out["rush_shows_today"] = [rush_count(d, set(v.show_id)) for d, v in playing.groupby("date")]
    return out.reset_index()


class Features:
    """Builds features for any (show_id, date), using only what's known 7 days before that date."""

    def __init__(self, shows: pd.DataFrame, line: pd.DataFrame, policies: pd.DataFrame | None = None):
        self.shows = shows.set_index("show_id")
        self.codes = {sid: i for i, sid in enumerate(sorted(shows.show_id))}
        g = pd.read_csv(RAW / "grosses_playbill.csv", parse_dates=["week_ending"])
        by_prod = shows.drop_duplicates("production_id").set_index("production_id").show_id
        g["show_id"] = g.production_id.map(by_prod)
        self.stage = self._stage(g)
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
        # Two-show days and shows playing that day, from Playbill's archived weekly schedules (SPEC 2.8 N7, N8)
        if policies is None:
            policies = load_policies(shows)
        self.sched = load_schedule_days(shows, policies)
        self.sched_counts = schedule_day_counts(self.sched, policies)
        self.tourism = Tourism()
        self.cast = Cast()
        self.board = Board(shows)

    @staticmethod
    def _stage(g: pd.DataFrame) -> pd.DataFrame:
        """show_id -> first preview day and opening day, to the week: the Monday of the first week with previews,
        and the Monday of the first week with regular performances. Blank when the show was already open in June 2024."""
        g = g.dropna(subset=["show_id"])
        out = {}
        for sid, w in g.groupby("show_id"):
            prev = w[w.previews.fillna(0) > 0].week_ending.min()
            reg = w[w.perfs.fillna(0) > 0].week_ending.min()
            began_before = w.week_ending.min() <= START + pd.Timedelta(days=7) and pd.isna(prev)
            out[sid] = {
                "first_preview": prev - pd.Timedelta(days=6) if pd.notna(prev) else pd.NaT,
                "opening": pd.NaT if began_before else (reg - pd.Timedelta(days=6) if pd.notna(reg) else pd.NaT),
            }
        return pd.DataFrame.from_dict(out, orient="index")

    def stage_features(self, keys: pd.DataFrame) -> pd.DataFrame:
        st = self.stage.reindex(keys.show_id)
        opening = pd.to_datetime(st.opening).to_numpy()
        first = pd.to_datetime(st.first_preview).to_numpy()
        d = keys.date.to_numpy()
        since = (d - opening) / np.timedelta64(1, "D")
        in_prev = np.where(pd.isna(first), 0.0, ((d >= first) & ((d < opening) | pd.isna(opening))).astype(float))
        return pd.DataFrame({"in_previews": in_prev, "days_since_opening": since}, index=keys.index)

    def schedule(self, keys: pd.DataFrame, override: pd.DataFrame | None = None) -> pd.DataFrame:
        """two_shows_today (1/0, blank when unknown), shows_playing_today, rush_shows_today. `override` (show_id,
        date, perfs) is the live schedule, from Ticketmaster at prediction time, and wins over the archive."""
        s = self.sched[["show_id", "date", "perfs"]]
        if override is not None and len(override):
            s = pd.concat([s, override[["show_id", "date", "perfs"]]]).drop_duplicates(["show_id", "date"], keep="last")
        k = keys[["show_id", "date"]].merge(s, on=["show_id", "date"], how="left")
        k = k.merge(self.sched_counts, on="date", how="left")
        return pd.DataFrame({
            "two_shows_today": np.where(k.perfs.isna(), np.nan, (k.perfs >= 2).astype(float)),
            "shows_playing_today": k.shows_playing_today.to_numpy(),
            "rush_shows_today": k.get("rush_shows_today", pd.Series(np.nan, index=k.index)).to_numpy(),
        }, index=keys.index)

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

    def build(self, rows: pd.DataFrame, schedule_override: pd.DataFrame | None = None) -> pd.DataFrame:
        keys = rows[["show_id", "date"]].drop_duplicates().reset_index(drop=True)
        keys = keys.merge(self.calendar, on="date", how="left").merge(self.weather, on="date", how="left")
        keys[["recent_level", "recent_n"]] = self.recent(keys)
        keys[SCHEDULE_FEATURES] = self.schedule(keys, schedule_override)
        keys[STAGE_FEATURES] = self.stage_features(keys)
        keys = keys.merge(self.tourism.build(keys.date), on="date", how="left")
        keys["nyu_session"] = session_by_day(keys.date)
        keys[STAR_FEATURES] = self.cast.build(keys)
        keys[BOARD_FEATURES] = self.board.build(keys)
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


def load_tables(raw_cutoff: bool = False) -> dict:
    """raw_cutoff keeps the sold-out-only rows (backtest --soldout); everyone else gets the usual labels."""
    p = PROCESSED
    return {
        "shows": pd.read_csv(p / "shows.csv"),
        "line": pd.read_csv(p / "model_line.csv", parse_dates=["date", "created"]),
        "cutoff": (lambda c: c if raw_cutoff else with_soldout(c, False))(
            pd.read_csv(p / "model_cutoff.csv", parse_dates=["date", "created"])),
        "outcomes": pd.read_csv(p / "model_outcomes.csv", parse_dates=["date", "created"]),
    }


def tickets_bounds(cut: pd.DataFrame, per_person: float) -> pd.DataFrame:
    """Turns positions (people) into bounds on tickets. Someone at p who got one: at least per_person * p tickets.
    Someone at p who didn't: fewer than per_person * p."""
    out = cut.copy()
    out["lower_t"] = [math.ceil(per_person * p - 1e-9) if p == p else np.nan for p in out.lower_pos]
    out["upper_t"] = [math.ceil(per_person * p - 1e-9) - 1 if p == p else np.nan for p in out.upper_pos]
    return out


def wider_attempts(funnel: dict):
    """Every in-person attempt with an arrival time and a known result, including reports with no usable date."""
    r = drop_special(pd.read_csv(PROCESSED / "reports.csv", low_memory=False))
    a = r[(r.rush_type == "general") & r.show_id.notna() & (r.show_id != "-") & (r.kind == "attempt")
          & r.arrival_time.notna() & r.outcome.isin(FAILED | {"got_rush"})]
    funnel["attempts_wider_count"] = len(a)
    funnel["attempts_wider_share_got"] = round(float((a.outcome == "got_rush").mean()), 4)


def build():
    scanned = pd.read_csv(RAW / "comments.csv", usecols=["comment_id"], dtype=str).comment_id.nunique()
    funnel: dict = {"comments_scanned": int(scanned)}
    wider_attempts(funnel)
    shows = pd.read_csv(PROCESSED / "shows.csv")
    policies = load_policies(shows)
    opening = opening_lookup(policies)
    r = base_reports(funnel)
    line = line_points(r, opening, funnel)
    cut = cutoff_labels(r, funnel)
    out = outcomes(r, opening, funnel)
    feats = Features(shows, line, policies)
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

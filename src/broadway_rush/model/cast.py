"""Star and cast inputs (SPEC 2.8 N5, tier 3), for any show and day, from what was known 7 days before.

Runs come from casting news and Wikipedia (data/interim/star_stints.csv, `star_history stints`); who counts as a star
comes from data/interim/star_stints_scored.csv (`stars --history`): the same 20,000-views rule as the site's stars.

- stars_in_cast: stars whose run covers the day. A run starts at its latest start date (a return counts from the
  return). It ends at its last performance once that has been announced 7 days before the day; with no announced end
  it's assumed to last at most 365 days (casting news doesn't always report exits).
- top_star_views_log: log10 of the most-viewed star's pre-joining median monthly views (0 = no star).
- star_final_2wks: 1 if a star's announced final performance is 0-14 days after the day.
- days_until_star_leaves: days to the nearest announced star exit, capped at 90; blank if none is announced.
- star_limited_run: 1 if a star in the cast is on a limited engagement.
- cast_change_14d: 1 if any principal (star or not) started in the 14 days up to the day, announced 7 days before.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
INTERIM = ROOT / "data" / "interim"
STAR_FEATURES = ["stars_in_cast", "top_star_views_log", "star_final_2wks", "days_until_star_leaves",
                 "star_limited_run", "cast_change_14d"]
AS_OF_DAYS = 7
OPEN_RUN_DAYS = 365


class Cast:
    def __init__(self):
        path = INTERIM / "star_stints.csv"
        self.ok = path.exists()
        if not self.ok:
            return
        s = pd.read_csv(path, dtype=str, keep_default_na=False)
        scored = INTERIM / "star_stints_scored.csv"
        if scored.exists():
            sc = pd.read_csv(scored, dtype=str, keep_default_na=False)[["show_id", "key", "star", "views_median"]]
            s = s.merge(sc.drop_duplicates(["show_id", "key"]), on=["show_id", "key"], how="left")
        else:
            s["star"], s["views_median"] = "no", ""
        ts = lambda c: pd.to_datetime(s[c].replace("", None), errors="coerce")  # noqa: E731
        s["start"] = ts("latest_start").fillna(ts("first_performance"))
        s["announced"] = ts("casting_announced")
        s["end"] = ts("last_performance")
        s["end_announced"] = ts("last_announced")
        s["is_star"] = s.star.eq("yes")
        s["views"] = pd.to_numeric(s.views_median, errors="coerce")
        s["limited"] = s.is_limited.astype(str).str.lower().eq("true")
        self.runs = {sid: g for sid, g in s.dropna(subset=["start"]).groupby("show_id")}

    def build(self, keys: pd.DataFrame) -> pd.DataFrame:
        out = np.full((len(keys), len(STAR_FEATURES)), np.nan)
        if not self.ok:
            return pd.DataFrame(out, columns=STAR_FEATURES, index=keys.index)
        for i, (sid, day) in enumerate(keys[["show_id", "date"]].itertuples(index=False)):
            g = self.runs.get(sid)
            if g is None:
                out[i] = [0, 0, 0, np.nan, 0, 0]
                continue
            asof = day - pd.Timedelta(days=AS_OF_DAYS)
            # Known by then: casting announced (or the run already started) by the as-of day
            known = g[(g.announced <= asof) | (g.start <= asof)]
            end_known = known.end.where(known.end_announced <= asof)
            end = end_known.fillna(known.start + pd.Timedelta(days=OPEN_RUN_DAYS))
            in_cast = known[(known.start <= day) & (day <= end)]
            stars = in_cast[in_cast.is_star]
            left = (end_known[stars.index] - day).dt.days
            left = left[left >= 0]
            changes = known[(known.start > day - pd.Timedelta(days=14)) & (known.start <= day)]
            out[i] = [len(stars),
                      np.log10(stars.views.max()) if len(stars) and stars.views.notna().any() else 0.0,
                      float((left <= 14).any()),
                      float(min(left.min(), 90)) if len(left) else np.nan,
                      float(stars.limited.any()),
                      float(len(changes) > 0)]
        return pd.DataFrame(out, columns=STAR_FEATURES, index=keys.index)

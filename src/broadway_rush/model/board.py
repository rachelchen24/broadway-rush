"""TKTS board input (SPEC 2.8 tier 3), from data/raw/tkts.csv (our own snapshots + Internet Archive copies).

- tkts_board_share_14d: of the dates in the 14 days ending 7 days before the day on which we have a copy of TKTS's
  same-day Broadway board, the share with this show on it. Blank with fewer than 3 such dates. Checked 2026-11-17
  (process.md): same show, weekday and seats sold, a show always on the board ran lines about 7 people shorter.
  Same-day board status isn't used: the board goes up in the afternoon, after the morning rush.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BOARD_FEATURES = ["tkts_board_share_14d"]
AS_OF_DAYS = 7
WINDOW_DAYS = 14
MIN_BOARDS = 3


class Board:
    def __init__(self, shows: pd.DataFrame):
        from broadway_rush.catalog import lookup, name_keys
        path = ROOT / "data" / "raw" / "tkts.csv"
        self.ok = path.exists()
        if not self.ok:
            return
        t = pd.read_csv(path, usecols=["snapshot_et", "section", "show"])
        t = t[t.section == "broadway"].copy()
        t["date"] = pd.to_datetime(t.snapshot_et.str[:10])
        keys = name_keys(shows)
        ids = {n: lookup(n, keys)[0] for n in t.show.unique()}
        t["show_id"] = t.show.map(lambda n: next(iter(ids[n])) if len(ids[n]) == 1 else None)
        self.dates = np.array(sorted(t.date.unique()), dtype="datetime64[ns]")
        self.on = {sid: set(g.date) for sid, g in t.dropna(subset=["show_id"]).groupby("show_id")}

    def build(self, keys: pd.DataFrame) -> pd.DataFrame:
        out = np.full(len(keys), np.nan)
        if self.ok:
            for i, (sid, day) in enumerate(keys[["show_id", "date"]].itertuples(index=False)):
                hi = np.datetime64(day - pd.Timedelta(days=AS_OF_DAYS))
                lo = hi - np.timedelta64(WINDOW_DAYS, "D")
                window = self.dates[(self.dates > lo) & (self.dates <= hi)]
                if len(window) >= MIN_BOARDS:
                    on = self.on.get(sid, set())
                    out[i] = sum(pd.Timestamp(d) in on for d in window) / len(window)
        return pd.DataFrame({"tkts_board_share_14d": out}, index=keys.index)

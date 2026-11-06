"""The per-show lookup table (SPEC 5.2): the bar to beat. No model, only medians and shares from earlier days."""

import numpy as np
import pandas as pd

TIME_EDGES = [0, 0.5, 1, 1.5, 2, 3, 4, 100]
MIN_CELL = 3


def time_window(hours_before) -> np.ndarray:
    return np.digitize(hours_before, TIME_EDGES[1:-1], right=True)


class Lookup:
    """Line: show + weekday + time window, then show + time window, then all shows + time window.
    Tickets: the show's stated counts, then all shows' stated counts. Chance: the share who got a ticket in that show
    and time window, pulled toward the overall share."""

    def __init__(self, line: pd.DataFrame, cutoff: pd.DataFrame, outcomes: pd.DataFrame):
        x = line.assign(tw=time_window(line.hours_before))
        self.fine = x.groupby(["show_id", "weekday", "tw"]).people.quantile([0.1, 0.5, 0.9]).unstack()
        self.fine_n = x.groupby(["show_id", "weekday", "tw"]).size()
        self.mid = x.groupby(["show_id", "tw"]).people.quantile([0.1, 0.5, 0.9]).unstack()
        self.mid_n = x.groupby(["show_id", "tw"]).size()
        self.broad = x.groupby("tw").people.quantile([0.1, 0.5, 0.9]).unstack()
        self.broad_all = x.people.quantile([0.1, 0.5, 0.9])
        stated = cutoff.dropna(subset=["exact"])
        self.t_show = stated.groupby("show_id").exact.quantile([0.1, 0.5, 0.9]).unstack()
        self.t_n = stated.groupby("show_id").size()
        self.t_all = stated.exact.quantile([0.1, 0.5, 0.9]) if len(stated) else pd.Series({0.1: 2.0, 0.5: 6.0, 0.9: 20.0})
        o = outcomes.assign(tw=time_window(outcomes.hours_before))
        self.overall = float(o.got.mean()) if len(o) else 0.87
        self.o_got = o.groupby(["show_id", "tw"]).got.sum()
        self.o_n = o.groupby(["show_id", "tw"]).got.size()

    def line(self, rows: pd.DataFrame) -> pd.DataFrame:
        """10th percentile, median and 90th percentile of the line for each row."""
        tw = time_window(rows.hours_before)
        out = []
        for sid, wd, w in zip(rows.show_id, rows.weekday, tw):
            if self.fine_n.get((sid, wd, w), 0) >= MIN_CELL:
                out.append(self.fine.loc[(sid, wd, w)].to_numpy())
            elif self.mid_n.get((sid, w), 0) >= MIN_CELL:
                out.append(self.mid.loc[(sid, w)].to_numpy())
            elif w in self.broad.index:
                out.append(self.broad.loc[w].to_numpy())
            else:
                out.append(self.broad_all.to_numpy())
        return pd.DataFrame(out, columns=["lo", "med", "hi"], index=rows.index)

    def tickets(self, rows: pd.DataFrame) -> pd.DataFrame:
        out = []
        for sid in rows.show_id:
            if self.t_n.get(sid, 0) >= MIN_CELL:
                out.append(self.t_show.loc[sid].to_numpy())
            else:
                out.append(self.t_all.to_numpy())
        return pd.DataFrame(out, columns=["lo", "med", "hi"], index=rows.index)

    def chance(self, rows: pd.DataFrame, pseudo: float = 5.0) -> np.ndarray:
        tw = time_window(rows.hours_before)
        out = []
        for sid, w in zip(rows.show_id, tw):
            got, n = self.o_got.get((sid, w), 0), self.o_n.get((sid, w), 0)
            out.append((got + pseudo * self.overall) / (n + pseudo))
        return np.array(out)

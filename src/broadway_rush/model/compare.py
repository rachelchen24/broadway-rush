"""Compare backtest runs on identical test reports (SPEC 2.8 N9: "score both on the identical test reports").

    .venv\\Scripts\\python -m broadway_rush.model.compare more1 v1new v2all

Reads data/processed/backtest_<tag>_{line,tickets,outcomes}.csv and keeps only the test reports every run has, so
new or cleaned reports can't flatter one run. For each run: the combo ("model") and the per-show lookup table, plus
the month-to-month spread of the line and ticket errors, which is the noise a difference has to beat (cut rule).
Ticket error is on days with a stated count; "at least"/"at most" days are scored as how often the middle estimate
respects the bound. Rachel's priority (2026-11-17): ticket error first, then line error.
"""

import sys

import numpy as np
import pandas as pd

from broadway_rush.model.table import PROCESSED

KEYS = {"line": ["show_id", "date", "hours_before", "people"],
        "tickets": ["show_id", "date", "exact", "lower_t", "upper_t"],
        "outcomes": ["show_id", "date", "hours_before", "got"]}


def load(tag: str, kind: str) -> pd.DataFrame | None:
    p = PROCESSED / f"backtest_{tag}_{kind}.csv"
    return pd.read_csv(p) if p.exists() else None


def common(tags: list[str], kind: str) -> dict:
    frames = {t: load(t, kind) for t in tags}
    frames = {t: f for t, f in frames.items() if f is not None}
    if not frames:
        return {}
    keys = KEYS[kind]
    def key(f):
        cells = f[keys].round(4).apply(lambda c: c.map(lambda v: "" if pd.isna(v) else str(v)))
        return cells.agg("|".join, axis=1)
    shared = set.intersection(*(set(key(f)) for f in frames.values()))
    return {t: f[key(f).isin(shared)].drop_duplicates(keys) for t, f in frames.items()}


def auc(y, p) -> float:
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return np.nan
    wins = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(wins / (len(pos) * len(neg)))


def score(tags: list[str]) -> pd.DataFrame:
    rows = {}
    lines, tix, outs = common(tags, "line"), common(tags, "tickets"), common(tags, "outcomes")
    for t in tags:
        r = {}
        for who in ("combo", "lookup"):
            if t in lines:
                f = lines[t]
                err = (f[f"{who}_med"] - f.people).abs()
                w = f.weight if "weight" in f else 1
                r[f"line_mae_{who}"] = float(np.average(err, weights=w))
                r[f"line_cover80_{who}"] = float(((f[f"{who}_lo"] <= f.people) & (f.people <= f[f"{who}_hi"])).mean())
                r[f"line_month_sd_{who}"] = float(err.groupby(f.month).mean().std())
            if t in tix:
                f = tix[t]
                ex = f[f.exact.notna()]
                e = ex[f"{who}_med"] - ex.exact
                r[f"tickets_mae_{who}"] = float(e.abs().mean())
                r[f"tickets_bias_{who}"] = float(e.mean())
                inside = (ex[f"{who}_lo"] <= ex.exact) & (ex.exact <= ex[f"{who}_hi"])
                r[f"tickets_cover80_{who}"] = float(inside.mean())
                r[f"tickets_month_sd_{who}"] = float(e.abs().groupby(ex.month).mean().std())
                lo = f[f.exact.isna() & f.lower_t.notna()]
                up = f[f.exact.isna() & f.upper_t.notna()]
                r[f"tickets_respects_atleast_{who}"] = float((lo[f"{who}_med"] >= lo.lower_t).mean())
                r[f"tickets_respects_atmost_{who}"] = float((up[f"{who}_med"] <= up.upper_t).mean())
            if t in outs:
                f = outs[t]
                r[f"chance_auc_{who}"] = auc(f.got, f[who])
                r[f"chance_brier_{who}"] = float(((f[who] - f.got) ** 2).mean())
                r[f"chance_acc50_{who}"] = float(((f[who] >= 0.5) == (f.got == 1)).mean())
        r["n_line"] = len(lines.get(t, []))
        r["n_ticket_exact"] = int(tix[t].exact.notna().sum()) if t in tix else 0
        r["n_outcomes"] = len(outs.get(t, []))
        rows[t] = r
    return pd.DataFrame(rows)


def main():
    tags = sys.argv[1:] or ["more1"]
    pd.set_option("display.width", 200)
    print(score(tags).round(3).to_string())


if __name__ == "__main__":
    main()

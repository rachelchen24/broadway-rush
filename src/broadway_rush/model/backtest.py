"""Rolling monthly test (SPEC 5.2): each month is predicted by models trained only on earlier days. Never shuffled.

    .venv\\Scripts\\python -m broadway_rush.model.backtest --per-person 1.4
    .venv\\Scripts\\python -m broadway_rush.model.backtest --line-only --weather

12 monthly windows, Nov 2025 to Oct 2026. Three are locked (LOCKED) and never scored here: they're for the final score,
so that picking winners on the other nine can't become overfitting. They were chosen by how many labels they hold, before
any model ran.
"""

import argparse
import json
import time

import numpy as np
import pandas as pd

from broadway_rush.model import cutoff as cutoff_model
from broadway_rush.model import join
from broadway_rush.model import line as line_model
from broadway_rush.model.lookup import Lookup
from broadway_rush.model.table import LINE_FEATURES, PROCESSED, WEATHER_FEATURES, load_tables, tickets_bounds

MONTHS = [str(p) for p in pd.period_range("2025-11", "2026-10", freq="M")]
LOCKED = {"2025-12", "2026-04", "2026-08"}
DEV = [m for m in MONTHS if m not in LOCKED]
GRID = np.arange(0.25, 7.01, 0.25)
GO, MAYBE = 0.70, 0.40  # placeholder thresholds (SPEC 9, question 1)


def split(df: pd.DataFrame, month: str):
    start = pd.Timestamp(month + "-01")
    end = start + pd.offsets.MonthBegin(1)
    train = df[(df.date < start) & (df.created < start)]
    test = df[(df.date >= start) & (df.date < end)]
    return train, test


def _wmean(v, w):
    return float(np.sum(np.asarray(v) * w) / np.sum(w)) if len(v) else None


def line_score(y, med, lo, hi, weight, hours) -> dict:
    y, med, lo, hi, w, h = map(np.asarray, (y, med, lo, hi, weight, hours))
    near = (h >= 0.5) & (h <= 2)
    return {
        "points": int(len(y)),
        "mae": _wmean(np.abs(y - med), w),
        "mae_near": _wmean(np.abs(y - med)[near], w[near]),
        "log_mae": _wmean(np.abs(np.log1p(y) - np.log1p(med)), w),
        "bias": _wmean(med - y, w),
        "coverage80": _wmean((y >= lo) & (y <= hi), w),
        "width80": _wmean(hi - lo, w),
    }


def arrival_error(rows: pd.DataFrame, curves: dict) -> np.ndarray:
    """Minutes between when the model says the line reaches this count and when someone really reported it."""
    out = []
    for sid, day, h, c in zip(rows.show_id, rows.date, rows.hours_before, rows.people):
        curve = curves.get((sid, day))
        if curve is None or h > GRID[-1] or c < 1:
            out.append(np.nan)
            continue
        reached = GRID[curve >= c]
        out.append(abs((reached.max() if len(reached) else 0.0) - h) * 60)
    return np.array(out)


def grid_rows(rows: pd.DataFrame) -> pd.DataFrame:
    days = rows.drop_duplicates(["show_id", "date"])
    n = len(days)
    g = days.loc[days.index.repeat(len(GRID))].copy()
    g["hours_before"] = np.tile(GRID, n)
    return g


def ticket_score(y, med, lo, hi) -> dict:
    y, med, lo, hi = map(np.asarray, (y, med, lo, hi))
    if not len(y):
        return {"days": 0, "mae": None, "bias": None, "coverage80": None, "width80": None}
    return {
        "days": int(len(y)), "mae": float(np.abs(y - med).mean()), "bias": float((med - y).mean()),
        "coverage80": float(((y >= lo) & (y <= hi)).mean()), "width80": float((hi - lo).mean()),
    }


def bounds_score(rows: pd.DataFrame, lo, hi) -> dict:
    """On days with only "at least" / "at most" labels: does the 80% range agree with the label?"""
    lo, hi = np.asarray(lo), np.asarray(hi)
    has_low, has_up = rows.lower_t.notna().to_numpy(), rows.upper_t.notna().to_numpy()
    return {
        "lower_days": int(has_low.sum()),
        "lower_agree": float((hi[has_low] >= rows.lower_t.to_numpy()[has_low]).mean()) if has_low.any() else None,
        "upper_days": int(has_up.sum()),
        "upper_agree": float((lo[has_up] <= rows.upper_t.to_numpy()[has_up]).mean()) if has_up.any() else None,
    }


def chance_score(got, p) -> dict:
    got, p = np.asarray(got, float), np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    misses = got == 0
    order = pd.Series(p).rank().to_numpy()
    n1, n0 = int(got.sum()), int(misses.sum())
    auc = (order[got == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else None
    return {
        "attempts": int(len(got)),
        "share_got": float(got.mean()),
        "misses": n0,
        "brier": float(np.mean((p - got) ** 2)),
        "log_loss": float(-np.mean(got * np.log(p) + (1 - got) * np.log(1 - p))),
        "auc": auc,
        "accuracy_at_50": float(((p >= 0.5) == (got == 1)).mean()),
        "misses_caught_at_50": int((p[misses] < 0.5).sum()),
        "wins_wrongly_warned_at_50": int((p[~misses] < 0.5).sum()),
        "mean_chance": float(p.mean()),
    }


def verdict_score(got, p) -> dict:
    got, p = np.asarray(got, float), np.asarray(p, float)
    out = {}
    for name, keep in (("GO", p >= GO), ("Maybe", (p >= MAYBE) & (p < GO)), ("Stay home", p < MAYBE)):
        out[name] = {"attempts": int(keep.sum()), "got": int(got[keep].sum()),
                     "share_got": float(got[keep].mean()) if keep.any() else None}
    return out


def calibration(got, p) -> list:
    got, p = np.asarray(got, float), np.asarray(p, float)
    edges = [0, 0.5, 0.7, 0.85, 0.95, 1.0001]
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        keep = (p >= a) & (p < b)
        if keep.any():
            out.append({"from": a, "to": min(b, 1.0), "attempts": int(keep.sum()),
                        "mean_chance": float(p[keep].mean()), "share_got": float(got[keep].mean())})
    return out


def run(per_person: float, line_only: bool, features: list[str], months: list[str], tag: str, seed: int = 0,
        phi_prior=(2.0, 0.4)):
    rng = np.random.default_rng(seed)
    t = load_tables()
    cut = tickets_bounds(t["cutoff"], per_person)
    windows, preds_line, preds_ticket, preds_outcome = [], [], [], []
    started = time.time()
    for month in months:
        t0 = time.time()
        line_train, line_test = split(t["line"], month)
        cut_train, cut_test = split(cut, month)
        out_train, out_test = split(t["outcomes"], month)
        lk = Lookup(line_train, cut_train, out_train)
        t1 = time.time()
        lm = line_model.fit(line_train, features)
        t2 = time.time()
        row = {"month": month, "line_train_points": len(line_train), "cutoff_train_days": len(cut_train),
               "line_rounds": lm.rounds, "line_phi": lm.phi, "seconds_lookup": t1 - t0, "seconds_line": t2 - t1}

        # Line
        mu = lm.mean(line_test)
        lo, hi = lm.interval(mu)
        med = lm.interval(mu, 0.0)[0]
        lk_line = lk.line(line_test)
        row["line_combo"] = line_score(line_test.people, med, lo, hi, line_test.weight, line_test.hours_before)
        row["line_lookup"] = line_score(line_test.people, lk_line.med, lk_line.lo, lk_line.hi, line_test.weight,
                                        line_test.hours_before)
        grid = grid_rows(line_test)
        gm = lm.mean(grid)
        gl = lk.line(grid).med.to_numpy()
        k = list(zip(grid.show_id, grid.date))
        n = len(GRID)
        curves_m = {k[i]: gm[i:i + n] for i in range(0, len(k), n)}
        curves_l = {k[i]: gl[i:i + n] for i in range(0, len(k), n)}
        err_m, err_l = arrival_error(line_test, curves_m), arrival_error(line_test, curves_l)
        ok = ~np.isnan(err_m)
        row["line_combo"]["arrival_error_min"] = _wmean(err_m[ok], line_test.weight.to_numpy()[ok])
        row["line_lookup"]["arrival_error_min"] = _wmean(err_l[ok], line_test.weight.to_numpy()[ok])
        preds_line.append(line_test[["show_id", "date", "hours_before", "people", "weight"]].assign(
            month=month, combo_med=med, combo_lo=lo, combo_hi=hi, lookup_med=lk_line.med, lookup_lo=lk_line.lo,
            lookup_hi=lk_line.hi))

        if not line_only:
            cm = cutoff_model.fit(cut_train, per_person, seed=seed, phi_prior=phi_prior)
            row["seconds_cutoff"] = cm.seconds
            row["cutoff_diagnostics"] = cm.diagnostics
            row["cutoff_posterior"] = {
                "a": float(cm.samples["a"].mean()), "sigma": float(cm.samples["sigma"].mean()),
                "phi": float(cm.samples["phi"].mean()),
                "beta": [float(b) for b in cm.samples["beta"].mean(axis=0)],
            }
            # Tickets
            d = cm.draws(cut_test, rng) if len(cut_test) else np.zeros((0, 1))
            qlo, qmed, qhi = (np.quantile(d, q, axis=1) if len(cut_test) else np.array([]) for q in (0.1, 0.5, 0.9))
            lk_t = lk.tickets(cut_test) if len(cut_test) else pd.DataFrame(columns=["lo", "med", "hi"])
            ex = cut_test.exact.notna().to_numpy()
            row["tickets_combo"] = ticket_score(cut_test.exact[ex], qmed[ex], qlo[ex], qhi[ex])
            row["tickets_lookup"] = ticket_score(cut_test.exact[ex], lk_t.med[ex], lk_t.lo[ex], lk_t.hi[ex])
            nb = ~ex
            row["bounds_combo"] = bounds_score(cut_test[nb], qlo[nb], qhi[nb])
            row["bounds_lookup"] = bounds_score(cut_test[nb], lk_t.lo[nb], lk_t.hi[nb])
            preds_ticket.append(cut_test[["show_id", "date", "exact", "lower_t", "upper_t"]].assign(
                month=month, combo_med=qmed, combo_lo=qlo, combo_hi=qhi, lookup_med=lk_t.med, lookup_lo=lk_t.lo,
                lookup_hi=lk_t.hi))
            # Chance
            if len(out_test):
                td = cm.draws(out_test, rng)
                pc = join.chance(lm.mean(out_test), lm.phi, td, per_person)
                pl = lk.chance(out_test)
                preds_outcome.append(out_test[["show_id", "date", "hours_before", "got", "outcome"]].assign(
                    month=month, combo=pc, lookup=pl, base_rate=lk.overall))
        row["seconds_total"] = time.time() - t0
        windows.append(row)
        print(month, "line", round(row["seconds_line"], 1), "s", "cutoff", round(row.get("seconds_cutoff", 0), 1), "s",
              "| line MAE combo", round(row["line_combo"]["mae"], 2), "lookup", round(row["line_lookup"]["mae"], 2),
              row.get("cutoff_diagnostics", ""), flush=True)

    allline = pd.concat(preds_line)
    res = {
        "tag": tag, "per_person": per_person, "phi_prior": list(phi_prior), "features": features, "months": months, "locked": sorted(LOCKED),
        "windows": windows, "seconds_total": time.time() - started,
        "pooled": {
            "line_combo": line_score(allline.people, allline.combo_med, allline.combo_lo, allline.combo_hi,
                                     allline.weight, allline.hours_before),
            "line_lookup": line_score(allline.people, allline.lookup_med, allline.lookup_lo, allline.lookup_hi,
                                      allline.weight, allline.hours_before),
        },
    }
    w = [x for x in windows if x["line_combo"].get("arrival_error_min") is not None]
    weights = [x["line_combo"]["points"] for x in w]
    res["pooled"]["line_combo"]["arrival_error_min"] = float(
        np.average([x["line_combo"]["arrival_error_min"] for x in w], weights=weights))
    res["pooled"]["line_lookup"]["arrival_error_min"] = float(
        np.average([x["line_lookup"]["arrival_error_min"] for x in w], weights=weights))
    if not line_only:
        tick = pd.concat(preds_ticket)
        ex = tick.exact.notna()
        res["pooled"]["tickets_combo"] = ticket_score(tick.exact[ex], tick.combo_med[ex], tick.combo_lo[ex], tick.combo_hi[ex])
        res["pooled"]["tickets_lookup"] = ticket_score(tick.exact[ex], tick.lookup_med[ex], tick.lookup_lo[ex], tick.lookup_hi[ex])
        res["pooled"]["bounds_combo"] = bounds_score(tick[~ex], tick.combo_lo[~ex], tick.combo_hi[~ex])
        res["pooled"]["bounds_lookup"] = bounds_score(tick[~ex], tick.lookup_lo[~ex], tick.lookup_hi[~ex])
        o = pd.concat(preds_outcome)
        res["pooled"]["chance_combo"] = chance_score(o.got, o.combo)
        res["pooled"]["chance_lookup"] = chance_score(o.got, o.lookup)
        res["pooled"]["chance_base_rate"] = chance_score(o.got, o.base_rate)
        res["pooled"]["always_yes_accuracy"] = float(o.got.mean())
        res["pooled"]["verdict_combo"] = verdict_score(o.got, o.combo)
        res["pooled"]["calibration_combo"] = calibration(o.got, o.combo)
        res["pooled"]["calibration_lookup"] = calibration(o.got, o.lookup)
        for row in windows:
            q = o[o.month == row["month"]]
            row["chance_combo"] = chance_score(q.got, q.combo) if len(q) else None
            row["chance_lookup"] = chance_score(q.got, q.lookup) if len(q) else None
        o.to_csv(PROCESSED / f"backtest_{tag}_outcomes.csv", index=False)
        tick.to_csv(PROCESSED / f"backtest_{tag}_tickets.csv", index=False)
    allline.to_csv(PROCESSED / f"backtest_{tag}_line.csv", index=False)
    (PROCESSED / f"backtest_{tag}.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps(res["pooled"], indent=1, default=float))
    print("total seconds", round(res["seconds_total"], 1))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-person", type=float, default=1.4)
    ap.add_argument("--line-only", action="store_true")
    ap.add_argument("--weather", action="store_true", help="adds what really happened: a best case, not a fair test")
    ap.add_argument("--drop", nargs="*", default=[], help="line features to leave out")
    ap.add_argument("--phi-prior", nargs=2, type=float, default=[2.0, 0.4], help="Gamma prior on the ticket spread")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--features", choices=["v1", "v2"], default="v1",
                    help="v1 = the first model's inputs (tag more1); v2 = every new input (SPEC 2.8 N9 step 1)")
    ap.add_argument("--cutoff", choices=["v1", "v2"], default=None,
                    help="ticket-model inputs; defaults to the --features choice (v1 = the first model's 4)")
    a = ap.parse_args()
    base = LINE_FEATURES
    if a.features == "v2":
        from broadway_rush.model import table
        base = table.LINE_FEATURES_V2
        # cutoff.py reads table.CUTOFF_FEATURES; swap its contents in place so the ticket model sees the v2 list
        if a.cutoff != "v1":
            table.CUTOFF_FEATURES[:] = table.CUTOFF_FEATURES_V2
    features = [f for f in base if f not in a.drop] + (WEATHER_FEATURES if a.weather else [])
    tag = a.tag or (f"pp{a.per_person}" + ("_weather" if a.weather else "") + ("_lineonly" if a.line_only else ""))
    run(a.per_person, a.line_only, features, DEV, tag, phi_prior=tuple(a.phi_prior))


if __name__ == "__main__":
    main()

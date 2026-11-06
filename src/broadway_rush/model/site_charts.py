"""Numbers behind the site's charts (SPEC 2.4 and 2.6). Each one is counted from the model tables or read from the
finished test, so the site only draws what really happened. Used by predict.py, which puts them in the predictions file.
"""

import numpy as np
import pandas as pd

from broadway_rush.model.table import PROCESSED

GROWTH_EDGES = [5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0]  # hours before the box office opens
GROWTH_MIN_REPORTS = 10
NEAR_OPENING_HOURS = 2.0  # "typical line" on the show-by-day charts means this close to opening
MIN_DAYS_PER_CELL = 3  # fewer past days than this and the cell stays blank
BAND_WIDTH = 2  # predicted-vs-real bands, in people
BAND_TOP = 20
BAND_MIN_REPORTS = 10
DRIVER_NAMES = {
    "hours_before": "How early you arrive",
    "show_code": "Which show",
    "weekday": "Day of the week",
    "pct_cap": "Seats sold recently",
    "recent_level": "Recent line lengths",
    "recent_thin": "Few recent reports",
    "avg_ticket": "Average ticket price",
    "weeks_since_first": "Weeks since the first listed week",
    "seats": "Theater size",
    "show_type_code": "Play or musical",
    "is_school_break": "NYC school break",
    "is_federal_holiday": "Federal holiday",
    "thanksgiving_week": "Thanksgiving week",
    "christmas_new_year": "Christmas and New Year's",
    "broadway_week": "Broadway Week",
    "tonys_30d": "Month after the Tonys",
}


def line_growth(line: pd.DataFrame) -> dict:
    """Average people ahead, by time before opening. Weighted so one busy day's many reports count as one day."""
    bands = list(zip(GROWTH_EDGES, GROWTH_EDGES[1:]))
    out = {"bands": [{"from": a, "to": b} for a, b in bands]}
    for name, part in (("weekday", line[line.weekday < 5]), ("weekend", line[line.weekday >= 5])):
        rows = []
        for a, b in bands:
            g = part[(part.hours_before <= a) & (part.hours_before > b)]
            enough = len(g) >= GROWTH_MIN_REPORTS
            rows.append({"average": round(float(np.average(g.people, weights=g.weight)), 1) if enough else None,
                         "reports": len(g)})
        out[name] = rows
    return out


def show_days(line: pd.DataFrame, show_ids: set[str]) -> dict:
    """Typical line near opening per show and weekday. Each past day counts once, however many people posted."""
    near = line[(line.hours_before <= NEAR_OPENING_HOURS) & line.show_id.isin(show_ids)]
    by_day = near.groupby(["show_id", "date", "weekday"], as_index=False).people.median()
    out = {}
    for sid, g in by_day.groupby("show_id"):
        cells = []
        for wd in range(7):
            days = g[g.weekday == wd].people
            cells.append({"typical": round(float(days.median()), 1) if len(days) >= MIN_DAYS_PER_CELL else None,
                          "days": len(days)})
        out[sid] = cells
    return out


def drivers(line: pd.DataFrame, model) -> list[dict]:
    """How much each input typically moves the line model's prediction. Contributions are on the log of the line."""
    push = model.contributions(line).abs()
    rows = [{"name": DRIVER_NAMES.get(f, f), "factor": round(float(np.exp(np.average(push[f], weights=line.weight))), 2)}
            for f in push.columns]
    return sorted(rows, key=lambda r: -r["factor"])


def predicted_vs_real(tag: str) -> dict | None:
    """From the finished test: what the real line was when each method predicted a given number of people."""
    path = PROCESSED / f"backtest_{tag}_line.csv"
    if not path.exists():
        return None
    t = pd.read_csv(path)
    edges = list(range(0, BAND_TOP + BAND_WIDTH, BAND_WIDTH))
    bands = []
    for a, b in zip(edges, edges[1:]):
        row = {"from": a, "to": b}
        for name in ("combo", "lookup"):
            g = t[(t[f"{name}_med"] >= a) & (t[f"{name}_med"] < b)]
            row[name] = {"real": float(g.people.median()) if len(g) >= BAND_MIN_REPORTS else None, "reports": len(g)}
        bands.append(row)
    return {
        "reports": len(t), "bands": bands,
        "correlation": {n: round(float(t[f"{n}_med"].corr(t.people)), 2) for n in ("combo", "lookup")},
        "above_top": {n: int((t[f"{n}_med"] >= BAND_TOP).sum()) for n in ("combo", "lookup")},
    }


def build(line: pd.DataFrame, model, tag: str, show_ids: set[str]) -> dict:
    return {
        "line_growth": line_growth(line),
        "show_days": show_days(line, show_ids),
        "near_opening_hours": NEAR_OPENING_HOURS,
        "min_days_per_cell": MIN_DAYS_PER_CELL,
        "drivers": drivers(line, model),
        "predicted_vs_real": predicted_vs_real(tag),
    }

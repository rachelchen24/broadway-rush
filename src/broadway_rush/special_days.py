"""One-off rush events kept out of everything: training, tests and Nerd stats (Rachel 2026-11-18: "we don't train
on them, we don't report anything on them"). Dress rehearsals, first previews, $5 days, added performances with a
special price. The site only notes a special offer on a tile while one is going on now (registry/special_deals.csv).

registry/special_rush_days.csv: a row with show_id + date drops that show-day's reports (by performance date, or the
thread date if there's none); a row with thread_title_contains drops every report from posts whose title contains it
(some reports from those posts carry wrong dates). Nothing is deleted from reports.csv itself.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SPECIAL = ROOT / "registry" / "special_rush_days.csv"


def special_mask(r: pd.DataFrame) -> pd.Series:
    """True for reports from a special rush event."""
    mask = pd.Series(False, index=r.index)
    if not SPECIAL.exists():
        return mask
    s = pd.read_csv(SPECIAL, dtype=str, keep_default_na=False)
    day = r.perf_date.astype(str).str[:10].where(r.perf_date.notna(), r.thread_date.astype(str).str[:10])
    title = r.thread_title.fillna("").astype(str).str.lower()
    for x in s.itertuples():
        if x.show_id and x.date:
            mask |= (r.show_id == x.show_id) & (day == x.date)
        if x.thread_title_contains:
            mask |= title.str.contains(x.thread_title_contains.lower(), regex=False)
    return mask


def drop_special(r: pd.DataFrame, funnel: dict | None = None) -> pd.DataFrame:
    m = special_mask(r)
    if funnel is not None:
        funnel["special_events_removed"] = int(m.sum())
    return r[~m]

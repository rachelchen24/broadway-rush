"""Drop-one tests on the line side (SPEC 2.8 N9 step 2): refit the line trees without one input group at a time on
the 9 open test months, and compare with the full v2 set. Line-only, so each run takes about a minute.

    .venv\\Scripts\\python -u -m broadway_rush.model.dropone            # run every group (skips ones already done)
    .venv\\Scripts\\python -m broadway_rush.model.dropone --report      # table only

Tags: drop_<group>. Reference: drop_none (all v2 inputs, line-only). The cut decision is Rachel's; this only
measures. A group "matters" when removing it makes the line error worse by more than the month-to-month noise.
"""

import subprocess
import sys

import numpy as np
import pandas as pd

from broadway_rush.model import table as t
from broadway_rush.model.compare import common

GROUPS = {
    "none": [],
    "show_identity": ["show_code"],
    "weekday": ["weekday"],
    "holidays_and_events": ["is_school_break", "is_federal_holiday", "thanksgiving_week", "christmas_new_year",
                            "broadway_week", "tonys_30d"],
    "grosses": ["pct_cap", "avg_ticket"],
    "show_facts": ["show_type_code", "seats", "weeks_since_first"],
    "recent_reports": ["recent_level", "recent_thin"],
    "schedule": t.SCHEDULE_FEATURES,
    "show_stage": t.STAGE_FEATURES,
    "subway_and_season": t.TOURISM_FEATURES,
    "times_square": t.TIMES_SQUARE_FEATURES,
    "nyu": t.NYU_FEATURES,
    "stars": t.STAR_FEATURES,
    "tkts": t.BOARD_FEATURES,
}


def run_all():
    for g, cols in GROUPS.items():
        tag = f"drop_{g}"
        if (t.PROCESSED / f"backtest_{tag}_line.csv").exists():
            continue
        cmd = [sys.executable, "-u", "-m", "broadway_rush.model.backtest", "--line-only", "--features", "v2",
               "--tag", tag]
        if cols:
            cmd += ["--drop", *cols]
        print("running", tag, flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def report() -> pd.DataFrame:
    tags = [f"drop_{g}" for g in GROUPS if (t.PROCESSED / f"backtest_drop_{g}_line.csv").exists()]
    lines = common(tags, "line")
    ref = lines["drop_none"]
    ref_err = (ref.combo_med - ref.people).abs().groupby(ref.month).mean()
    rows = []
    for tag in tags:
        f = lines[tag]
        err = (f.combo_med - f.people).abs()
        by_month = err.groupby(f.month).mean()
        diff = (by_month - ref_err).dropna()
        rows.append({"group": tag.removeprefix("drop_"), "inputs": len(GROUPS[tag.removeprefix("drop_")]),
                     "line_error": round(float(err.mean()), 3),
                     "worse_by": round(float(diff.mean()), 3),
                     "months_worse": int((diff > 0).sum()),
                     "t": round(float(diff.mean() / (diff.std() / np.sqrt(len(diff)))), 2) if diff.std() > 0 else 0.0})
    return pd.DataFrame(rows).sort_values("worse_by", ascending=False)


def main():
    if "--report" not in sys.argv:
        run_all()
    print(report().to_string(index=False))


if __name__ == "__main__":
    main()

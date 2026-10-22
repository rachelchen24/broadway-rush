"""Build the hand-labeling sheet for step 2 (schema: docs/labeling-schema.md).

    py -m broadway_rush.labeling.make_sheet          # -> data/labels/hand_labels.xlsx

Samples ~70 report-like + ~30 random daily-thread comments (fixed seed). Which group a comment
came from is kept out of the sheet (in sample_manifest.csv) so it can't bias the labels.
Refuses to overwrite an existing sheet, so labels are never lost.
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[3]
COMMENTS_CSV = ROOT / "data" / "raw" / "comments.csv"
LABELS = ROOT / "data" / "labels"
SHEET = LABELS / "hand_labels.xlsx"
MANIFEST = LABELS / "sample_manifest.csv"

SEED = 42
N_REPORT_LIKE, N_RANDOM = 70, 30
SKIP_AUTHORS = {"BroadwayRushReport", "AutoModerator", "[deleted]"}
REPORT_LIKE_RE = re.compile(r"\d|\b(?:line|sold out|sro|standing|rush|got|left)\b", re.IGNORECASE)

CONTEXT_COLS = ["comment_id", "thread_date", "comment_time", "parent_body", "body"]
# (column, allowed values or None for free text)
LABEL_COLS = [
    ("kind", ["line_count", "attempt", "supply", "none"]),
    ("show_text", None), ("show", None), ("perf_date", None),
    ("perf", ["matinee", "evening", "unknown"]),
    ("rush_type", ["general", "digital", "student", "sro", "lottery", "other", "unknown"]),
    ("secondhand", ["true", "false"]),
    ("confidence", ["high", "medium", "low"]),
    ("needs_context", ["true", "false"]),
    ("time", None), ("count", None),
    ("count_qual", ["exact", "approx", "at_least", "at_most"]),
    ("arrival_time", None), ("line_position", None),
    ("outcome", ["got_rush", "sro_only", "full_price_only", "sold_out_before_me", "left", "unknown"]),
    ("tickets", None), ("seat", None), ("window_time", None),
    ("stated_count", None), ("stated_qual", ["total", "remaining"]),
    ("sold_out_time", None), ("sro_offered", ["yes", "no", "unknown"]),
    ("late_release", ["true", "false"]),
    ("cast_note", None), ("notes", None),
]
WIDTHS = {"comment_id": 10, "thread_date": 11, "comment_time": 9, "parent_body": 40, "body": 70,
          "show_text": 14, "show": 20, "seat": 14, "cast_note": 18, "notes": 25}

INSTRUCTIONS = """\
How to label (full rules: docs/labeling-schema.md)

One row = one observation. Each comment starts with one row.
 - Nothing usable (question, chat, joke)? Set kind = none and move on.
 - Several observations (several shows, or one show at several times)? Insert rows below,
   copy the comment_id (and context if you like), and fill one observation per row.

kind
 - line_count: N people in line at a show at a time -> time, count, count_qual
 - attempt: the writer's (or a friend's) own visit -> arrival_time, line_position, outcome, tickets, seat
 - supply: how many rush tickets existed / were left / when they ran out -> stated_count, stated_qual, sold_out_time

Conventions
 - Times are 24-hour ET, HH:MM. "around 8" -> 08:00 (and count_qual/confidence as appropriate).
 - perf_date is pre-filled with the thread date; change it for "yesterday", "Saturday", etc.
 - line_position counts PEOPLE, not parties, unless the text says parties.
 - "5 or 6" -> 5 + approx.  "50+" -> 50 + at_least.  "a couple dozen" -> 24 + approx.
 - show: expand nicknames / theater names when you're sure (DBH -> Death Becomes Her). Blank if unsure.
 - secondhand = true for "my friend said...", "1st in line said he got there at 5".
 - needs_context = true if the row only makes sense with the parent comment.
 - Leave a field blank if the comment doesn't say. Don't guess.
"""


def build_sample(n_report: int = N_REPORT_LIKE, n_random: int = N_RANDOM, seed: int = SEED,
                 exclude: set[str] = frozenset()) -> pd.DataFrame:
    c = pd.read_csv(COMMENTS_CSV, dtype=str, keep_default_na=False)
    bodies = dict(zip("t1_" + c.comment_id, c.body))
    d = c[(c.source == "daily_thread") & ~c.body.isin(["[deleted]", "[removed]", ""])
          & ~c.author.isin(SKIP_AUTHORS) & ~c.comment_id.isin(exclude)].copy()
    d["parent_body"] = d.parent_id.map(bodies).fillna("")
    d["comment_time"] = d.created_et.str[11:16]
    report_like = d[d.body.str.contains(REPORT_LIKE_RE)]
    a = report_like.sample(n_report, random_state=seed).assign(sample_group="report_like")
    rest = d.drop(a.index)
    b = rest.sample(n_random, random_state=seed).assign(sample_group="random")
    return pd.concat([a, b]).sample(frac=1, random_state=seed).reset_index(drop=True)


def write_sheet(s: pd.DataFrame, path: Path = SHEET):
    wb = Workbook()
    ws = wb.active
    ws.title = "labels"
    cols = CONTEXT_COLS + [name for name, _ in LABEL_COLS]
    ws.append(cols)
    for _, r in s.iterrows():
        ws.append([r.comment_id, r.thread_date, r.comment_time, r.parent_body, r.body]
                  + ["" if name != "perf_date" else r.thread_date for name, _ in LABEL_COLS])

    head_ctx, head_lab = PatternFill("solid", fgColor="D9D2E9"), PatternFill("solid", fgColor="FFF2CC")
    for i, name in enumerate(cols, 1):
        cell = ws.cell(1, i)
        cell.font = Font(bold=True)
        cell.fill = head_ctx if name in CONTEXT_COLS else head_lab
        ws.column_dimensions[cell.column_letter].width = WIDTHS.get(name, 12)
    wrap = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap
        n = max(len(str(row[3].value or "")) / 40, len(str(row[4].value or "")) / 70)
        ws.row_dimensions[row[0].row].height = min(300, 15 * (int(n) + 1))
    ws.freeze_panes = "F2"  # keep header and context visible while scrolling right

    for name, values in LABEL_COLS:
        if values:
            letter = ws.cell(1, cols.index(name) + 1).column_letter
            dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True)
            dv.add(f"{letter}2:{letter}1000")
            ws.add_data_validation(dv)

    info = wb.create_sheet("instructions")
    for line in INSTRUCTIONS.splitlines():
        info.append([line])
    info.column_dimensions["A"].width = 110
    wb.save(path)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", help="build an extra sheet data/labels/<name>.xlsx (+ <name>_manifest.csv), "
                                   "excluding comments already in other manifests (e.g. a held-out test set)")
    ap.add_argument("--n-report", type=int, default=N_REPORT_LIKE)
    ap.add_argument("--n-random", type=int, default=N_RANDOM)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    sheet = LABELS / f"{args.name}.xlsx" if args.name else SHEET
    manifest = LABELS / f"{args.name}_manifest.csv" if args.name else MANIFEST
    if sheet.exists():
        sys.exit(f"{sheet} already exists; not overwriting your labels. Move or rename it first.")
    LABELS.mkdir(parents=True, exist_ok=True)
    exclude = set()
    for m in LABELS.glob("*manifest.csv"):
        exclude |= set(pd.read_csv(m, dtype=str).comment_id)
    s = build_sample(args.n_report, args.n_random, args.seed, exclude)
    write_sheet(s, sheet)
    s[["comment_id", "post_id", "sample_group", "thread_date"]].to_csv(manifest, index=False)
    print(f"wrote {sheet} ({len(s)} comments, {len(exclude)} excluded as already sampled) and {manifest}")
    print(s.groupby("sample_group").size().to_string())
    print("threads:", s.post_id.nunique(), "| years:", s.thread_date.str[:4].value_counts().sort_index().to_dict(),
          "| replies:", (~s.parent_id.str.startswith("t3_")).sum())


if __name__ == "__main__":
    main()

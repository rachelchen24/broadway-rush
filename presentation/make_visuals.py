"""Charts for the poster, slides and the Expo form's "other visualizations" upload (2026-11-23, preliminary).

    .venv\\Scripts\\python presentation\\make_visuals.py

Reads only finished results (data/processed), writes PNGs to presentation/visuals/. Colors match the website:
deep purple surface, gold = the model (Rachel's brightened chart gold), teal = the lookup-table baseline.
"""

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = Path(__file__).resolve().parent / "visuals"
OUT.mkdir(parents=True, exist_ok=True)

BG, CARD, INK, INK2, MUTED, GRID = "#3b2862", "#513b7d", "#f7f1ff", "#d6c9ec", "#c6b9de", "#6c5592"
GOLD, TEAL, PINK = "#f0b829", "#2f9fc0", "#ff4fb3"
DISPLAY, BODY = "Arial Black", "Segoe UI"
TAG, FINAL = "lean_so2", "final_locked"  # the final model: 9 test months, then the 3 locked months scored once

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "font.family": BODY, "font.size": 13,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
    "axes.grid": True, "grid.color": GRID, "grid.alpha": .45, "grid.linewidth": .8, "axes.spines.top": False,
    "axes.spines.right": False, "axes.spines.left": False, "legend.frameon": False, "legend.labelcolor": INK2,
})


def title(fig, head, sub):
    fig.text(0.04, 0.95, head.upper(), fontfamily=DISPLAY, fontsize=19, color=INK, va="top")
    fig.text(0.04, 0.875, sub, fontsize=12.5, color=INK2, va="top")


def save(fig, name):
    fig.savefig(OUT / name, dpi=250)
    plt.close(fig)
    print("wrote", OUT / name)


def line_growth():
    """How the line builds before opening: median and middle half of all line counts, by half hour."""
    x = pd.read_csv(PROC / "model_line.csv", usecols=["hours_before", "people"])
    x = x[x.hours_before <= 5]
    x["bin"] = (np.ceil(x.hours_before * 2) / 2).clip(lower=0.5)
    g = x.groupby("bin").people.describe(percentiles=[.25, .5, .75])
    g = g[g["count"] >= 30].sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=.08, right=.97, top=.76, bottom=.14)
    ax.fill_between(g.index, g["25%"], g["75%"], color=GOLD, alpha=.22, linewidth=0, label="Middle half of mornings")
    ax.plot(g.index, g["50%"], color=GOLD, linewidth=2.5, marker="o", markersize=6, label="Typical (median)")
    ax.invert_xaxis()
    ax.set_xlabel("Hours before the box office opens")
    ax.set_ylabel("People in line")
    ax.set_ylim(bottom=0)
    last = g.index.min()
    ax.annotate(f"about {g.loc[last, '50%']:.0f} people\nat opening", (last, g.loc[last, "50%"]), xytext=(-110, 18),
                textcoords="offset points", color=INK, fontsize=12, arrowprops=dict(arrowstyle="-", color=MUTED))
    ax.legend(loc="upper left")
    title(fig, "How rush lines build", f"{len(x):,} line counts from Reddit reports, Jun 2024 – Nov 2026")
    save(fig, "1_line_growth.png")


def line_error_by_month():
    res = json.loads((PROC / f"backtest_{TAG}.json").read_text(encoding="utf-8"))
    fin = json.loads((PROC / f"backtest_{FINAL}.json").read_text(encoding="utf-8"))
    w = pd.DataFrame([{"month": x["month"], "model": x["line_combo"]["mae"], "lookup": x["line_lookup"]["mae"]}
                      for x in res["windows"] + fin["windows"]])
    months = pd.period_range("2025-11", "2026-10", freq="M").astype(str)
    w = w.set_index("month").reindex(months)
    labels = [pd.Period(m).strftime("%b\n%y") for m in months]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=.08, right=.97, top=.76, bottom=.14)
    xs = np.arange(len(months))
    ax.plot(xs, w.lookup, color=TEAL, linewidth=2, linestyle="--", marker="s", markersize=7, label="Per-show lookup table")
    ax.plot(xs, w.model, color=GOLD, linewidth=2.5, marker="o", markersize=8, label="Model")
    ax.set_xticks(xs, labels)
    top = max(w.max(numeric_only=True).max() * 1.25, 1)
    ax.set_ylim(0, top)
    for i, m in enumerate(months):
        if m in res["locked"]:
            ax.axvspan(i - .4, i + .4, color=PINK, alpha=.12, linewidth=0)
            ax.text(i, top * .04, "locked", rotation=90, ha="center", va="bottom", color=PINK, fontsize=10)
    lk = [i for i, m in enumerate(months) if m in res["locked"]]
    ax.scatter(lk, w.model.iloc[lk], s=150, facecolor="none", edgecolor=PINK, linewidth=2, zorder=5)
    ax.set_ylabel("Average miss, people in line")
    ax.legend(loc="upper left", ncols=2)
    p, q = res["pooled"], fin["pooled"]
    title(fig, "Line predictions beat the baseline",
          f"Each month predicted using only earlier months · test months {p['line_combo']['mae']:.2f} vs "
          f"{p['line_lookup']['mae']:.2f} people\nPink = locked months, scored once at the end: {q['line_combo']['mae']:.2f} vs "
          f"{q['line_lookup']['mae']:.2f}")
    save(fig, "2_line_error_by_month.png")


def what_mattered():
    from broadway_rush.model.dropone import report
    r = report()
    r = r[r.group != "none"].copy()
    names = {"weekday": "Day of the week", "recent_reports": "Recent reports for the show", "schedule": "Schedule (2-show days, shows on)",
             "grosses": "Box-office grosses", "nyu": "NYU calendar", "show_facts": "Show facts (type, seats, age)",
             "times_square": "Times Square foot traffic", "tkts": "TKTS discount board", "stars": "Star casting",
             "holidays_and_events": "Holidays and events", "show_stage": "Previews / since opening",
             "show_identity": "Which show", "subway_and_season": "Subway riders and season"}
    cut = {"times_square", "tkts", "stars", "holidays_and_events", "show_stage", "subway_and_season"}
    r = r.sort_values("worse_by")
    fig, ax = plt.subplots(figsize=(10, 6.6))
    fig.subplots_adjust(left=.34, right=.95, top=.8, bottom=.12)
    ys = np.arange(len(r))
    colors = [TEAL if g in cut else GOLD for g in r.group]
    ax.barh(ys, r.worse_by, color=colors, height=.62, edgecolor=BG, linewidth=2)
    ax.set_yticks(ys, [names.get(g, g) for g in r.group])
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_xlim(r.worse_by.min() - 0.035, r.worse_by.max() + 0.03)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in line error when the input is removed (people)  ·  right = it was helping")
    for y, (v, t) in enumerate(zip(r.worse_by, r.t)):
        ax.text(v + (0.004 if v >= 0 else -0.004), y, f"{v:+.3f}", va="center", ha="left" if v >= 0 else "right", color=INK2, fontsize=10.5)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=GOLD, label="Kept (14 inputs)"), Patch(color=TEAL, label="Cut")], loc="lower right")
    title(fig, "Testing every input by removing it",
          "Only day of the week clearly helped; six groups made predictions slightly worse and were cut")
    save(fig, "3_what_mattered.png")


def tickets_two_tests():
    res = json.loads((PROC / f"backtest_{TAG}.json").read_text(encoding="utf-8"))["pooled"]
    t = pd.read_csv(PROC / f"backtest_{TAG}_tickets.csv")
    lo = t[t.exact.isna() & t.lower_t.notna()]
    ok_model, ok_lookup = (lo.combo_med >= lo.lower_t).mean() * 100, (lo.lookup_med >= lo.lower_t).mean() * 100
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.6))
    fig.subplots_adjust(left=.07, right=.97, top=.64, bottom=.12, wspace=.35)
    names = ["Model", "Lookup\ntable"]
    for ax, vals, head, fmt, better in (
            (a, [res["tickets_combo"]["mae"], res["tickets_lookup"]["mae"]], f"Miss on stated counts ({res['tickets_combo']['days']} days)\nlower is better", "{:.1f}", 1),
            (b, [ok_model, ok_lookup], f"Estimate ≥ N when someone got #N ({len(lo)} days)\nhigher is better", "{:.0f}%", 0)):
        ax.bar(names, vals, color=[GOLD, TEAL], width=.55, edgecolor=BG, linewidth=2)
        ax.set_title(head, fontsize=12.5, color=INK2, loc="left")
        ax.grid(axis="x", visible=False)
        for i, v in enumerate(vals):
            ax.text(i, v, fmt.format(v), ha="center", va="bottom", fontsize=15, fontfamily=DISPLAY, color=INK)
        ax.set_ylim(0, max(vals) * 1.25)
    title(fig, "Two ticket tests, two winners (9 test months)",
          "People post counts mostly when they're small, which rewards guessing low; the far more common\n\"got one at #N\" reports favor the model")
    save(fig, "4_tickets_two_tests.png")


def funnel():
    src = ROOT / "docs" / "slides" / "cleaning-funnel.png"
    if src.exists():
        shutil.copy(src, OUT / "0_cleaning_funnel.png")
        print("copied", OUT / "0_cleaning_funnel.png")


if __name__ == "__main__":
    funnel()
    line_growth()
    line_error_by_month()
    what_mattered()
    tickets_two_tests()

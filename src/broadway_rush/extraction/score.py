"""Score an extraction run against the hand labels (docs/labeling-schema.md § Scoring).

    py -m broadway_rush.extraction.score data/interim/pilot_haiku_adaptive.csv
        -> prints metrics; writes <run>_errors.csv with every mismatch for error analysis
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "data" / "labels" / "hand_labels.xlsx"

TIME_FIELDS = {"time", "arrival_time", "window_time", "sold_out_time"}
COUNT_FIELDS = {"count", "line_position", "tickets", "stated_count"}
TIME_TOLERANCE_MIN = 10
KEY_FIELDS = ["show", "line_position", "outcome", "count", "time", "arrival_time"]
FIELDS = ["show", "perf_date", "perf", "rush_type", "secondhand", "confidence", "needs_context", "time", "count",
          "count_qual", "arrival_time", "line_position", "outcome", "tickets", "seat", "window_time",
          "stated_count", "stated_qual", "sold_out_time", "sro_offered", "late_release"]


def norm(v) -> str:
    s = "" if pd.isna(v) else str(v).strip().lower()
    return re.sub(r"\.0$", "", s)  # Excel turns 4 into 4.0


def norm_show(v) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", norm(v))
    return re.sub(r"^the ", "", s).strip()


def minutes(v) -> int | None:
    m = re.match(r"^(\d{1,2}):(\d{2})", norm(v))
    return int(m[1]) * 60 + int(m[2]) if m else None


BOOL_FIELDS = {"secondhand", "needs_context", "late_release"}


def same(field: str, g, p) -> bool:
    g, p = norm(g), norm(p)
    # "unknown" and a blank mean the same thing (not stated); so do "false" and blank for flags
    g, p = ("" if v == "unknown" or (field in BOOL_FIELDS and v == "false") else v for v in (g, p))
    if not g and not p:
        return True
    if field in TIME_FIELDS:
        gm, pm = minutes(g), minutes(p)
        return gm is not None and pm is not None and abs(gm - pm) <= TIME_TOLERANCE_MIN
    if field == "show":
        gs, ps = norm_show(g), norm_show(p)
        return bool(gs) and bool(ps) and (gs == ps or gs in ps or ps in gs)
    return g == p


def load_gold() -> pd.DataFrame:
    g = pd.read_excel(GOLD, sheet_name="labels", dtype=str)
    g["comment_id"] = g.comment_id.ffill()  # rows inserted for extra observations may leave it blank
    unlabeled = g.groupby("comment_id").kind.apply(lambda k: k.isna().all())
    if unlabeled.any():
        print(f"note: {unlabeled.sum()} comments have no 'kind' yet; scoring only the labeled ones")
    return g[g.comment_id.isin(unlabeled[~unlabeled].index) & g.kind.notna()]


def match(gold: list[dict], pred: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """Greedy one-to-one pairing within a comment: same kind, then show, then nearby time."""
    def sim(g, p):
        if norm(g["kind"]) != norm(p["kind"]):
            return -1
        s = 2 * same("show", g.get("show"), p.get("show")) + same("show", g.get("show_text"), p.get("show_text"))
        for f in ("time", "arrival_time"):
            if norm(g.get(f)) and same(f, g.get(f), p.get(f)):
                s += 1
        return s
    pairs = sorted(((sim(g, p), i, j) for i, g in enumerate(gold) for j, p in enumerate(pred)), reverse=True)
    used_g, used_p, out = set(), set(), []
    for s, i, j in pairs:
        if s >= 0 and i not in used_g and j not in used_p:
            used_g.add(i), used_p.add(j)
            out.append((gold[i], pred[j]))
    out += [(g, None) for i, g in enumerate(gold) if i not in used_g]
    out += [(None, p) for j, p in enumerate(pred) if j not in used_p]
    return out


def score(pred_path: Path):
    gold = load_gold()
    pred = pd.read_csv(pred_path, dtype=str, keep_default_na=False)
    ids = sorted(set(gold.comment_id))
    pred = pred[pred.comment_id.isin(ids)]

    comment_rows, field_hits, errors = [], {f: [0, 0] for f in FIELDS}, []
    tp = fp = fn = 0
    for cid in ids:
        g = [r for r in gold[gold.comment_id == cid].to_dict("records") if norm(r["kind"]) != "none"]
        p = [r for r in pred[pred.comment_id == cid].to_dict("records") if norm(r["kind"]) not in ("none", "")]
        missing = (pred[pred.comment_id == cid].kind == "MISSING").any() or cid not in set(pred.comment_id)
        comment_rows.append({"cid": cid, "gold_has": bool(g), "pred_has": bool(p), "n_ok": len(g) == len(p),
                             "missing": missing})
        for gr, pr in match(g, p):
            if gr is None:
                fp += 1
                errors.append({"comment_id": cid, "issue": "extra observation", "kind": pr["kind"],
                               "show": pr.get("show", ""), "gold": "", "pred": str({k: v for k, v in pr.items() if v})})
                continue
            if pr is None:
                fn += 1
                errors.append({"comment_id": cid, "issue": "missed observation", "kind": gr["kind"],
                               "show": gr.get("show", ""), "gold": str({k: v for k, v in gr.items()
                                                                       if isinstance(v, str) and v}), "pred": ""})
                continue
            tp += 1
            for f in FIELDS:
                gv, pv = gr.get(f), pr.get(f)
                if not norm(gv) and not norm(pv):
                    continue
                ok = same(f, gv, pv)
                field_hits[f][0] += ok
                field_hits[f][1] += 1
                if not ok:
                    errors.append({"comment_id": cid, "issue": f"field: {f}", "kind": gr["kind"],
                                   "show": gr.get("show", ""), "gold": norm(gv), "pred": norm(pv)})

    c = pd.DataFrame(comment_rows)
    print(f"\n== {pred_path.name} vs {len(ids)} hand-labeled comments ==")
    print(f"comments missing from output: {int(c.missing.sum())}")
    has_acc = (c.gold_has == c.pred_has).mean()
    prec = (c.gold_has & c.pred_has).sum() / max(1, c.pred_has.sum())
    rec = (c.gold_has & c.pred_has).sum() / max(1, c.gold_has.sum())
    print(f"report vs none:  accuracy {has_acc:.0%}  precision {prec:.0%}  recall {rec:.0%}  "
          f"(gold: {int(c.gold_has.sum())} comments with observations)")
    print(f"same number of observations per comment: {c.n_ok.mean():.0%}")
    print(f"observations: gold {tp + fn}, predicted {tp + fp}, matched {tp} -> "
          f"precision {tp / max(1, tp + fp):.0%}, recall {tp / max(1, tp + fn):.0%}")
    print("\nfield accuracy on matched observations (n = pairs where either side filled it):")
    for f in FIELDS:
        ok, n = field_hits[f]
        if n:
            star = " *" if f in KEY_FIELDS else ""
            print(f"  {f:14s} {ok / n:5.0%}  (n={n}){star}")
    print("  * = fields the model depends on most")
    out = pred_path.with_name(pred_path.stem + "_errors.csv")
    pd.DataFrame(errors).to_csv(out, index=False)
    print(f"\n{len(errors)} mismatches -> {out}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pred", type=Path)
    score(ap.parse_args().pred)


if __name__ == "__main__":
    main()

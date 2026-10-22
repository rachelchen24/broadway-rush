"""Haiku extraction of rush observations (SPEC §4, §5.5).

    py -m broadway_rush.extraction.run pilot [--thinking adaptive|off] [--tag NAME]
        -> data/interim/pilot_<tag>.csv  (same columns as the hand-label sheet)

The pilot sends the ~100 hand-labeled comments as normal (synchronous) requests of CHUNK comments
each. Every call's token usage goes to data/interim/llm_spend.csv; the run refuses to start or
continue past the per-run cap or the project-wide hard stop (SPEC §5.5: $4 of the $5 budget).
The full run (step 3) will use the Batches API at half price; `project` estimates its cost.
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

from broadway_rush.extraction.prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT, render_comments

ROOT = Path(__file__).resolve().parents[3]
COMMENTS_CSV = ROOT / "data" / "raw" / "comments.csv"
MANIFEST = ROOT / "data" / "labels" / "sample_manifest.csv"
INTERIM = ROOT / "data" / "interim"
LEDGER = INTERIM / "llm_spend.csv"

MODEL = "claude-haiku-5-5"
CHUNK = 10                      # comments per request
MAX_TOKENS = 16000              # thinking counts toward this
# USD per token, Haiku 5.5 (prompts <=100K tokens): input $0.10/M, output $0.50/M;
# cache writes 1.25x input, cache reads 0.1x input; Batches API halves everything.
PRICE = {"input": 0.10e-6, "cache_write": 0.125e-6, "cache_read": 0.01e-6, "output": 0.50e-6}
HARD_STOP_USD = 8.00            # project-wide, across every run in the ledger (raised from $4 on 2026-10-22: $10 of credits, $8 allowed)
PILOT_CAP_USD = 0.25            # per pilot run

SKIP_BODIES = {"[deleted]", "[removed]", ""}
# Cheap pre-filter for the full run: comments with no digit and no rush-ish word are almost never reports
PREFILTER_RE = re.compile(r"\d|\b(?:line|sold out|sro|standing|rush|got|left|nobody|no one|empty)\b",
                          re.IGNORECASE)
LABEL_COLS = ["comment_id", "kind", "show_text", "show", "perf_date", "perf", "rush_type", "secondhand",
              "confidence", "needs_context", "time", "count", "count_qual", "arrival_time", "line_position",
              "outcome", "tickets", "seat", "window_time", "stated_count", "stated_qual", "sold_out_time",
              "sro_offered", "late_release", "cast_note"]


# ---------- data ----------

def load_comments() -> pd.DataFrame:
    """All comments with the context the model sees: parent body, post time (ET), weekday."""
    c = pd.read_csv(COMMENTS_CSV, dtype=str, keep_default_na=False)
    bodies = dict(zip("t1_" + c.comment_id, c.body))
    c["parent_body"] = c.parent_id.map(bodies).fillna("")
    c["comment_time"] = c.created_et.str[11:16]
    c["weekday"] = [date.fromisoformat(d).strftime("%A") if d else "" for d in c.thread_date]
    return c


# ---------- spend ledger ----------

def spent_total() -> float:
    if not LEDGER.exists():
        return 0.0
    return float(pd.read_csv(LEDGER).usd.sum())


def call_cost(usage, batch: bool = False) -> float:
    usd = (usage.input_tokens * PRICE["input"]
           + (usage.cache_creation_input_tokens or 0) * PRICE["cache_write"]
           + (usage.cache_read_input_tokens or 0) * PRICE["cache_read"]
           + usage.output_tokens * PRICE["output"])
    return usd * (0.5 if batch else 1.0)


def record(run: str, usage, usd: float, n_comments: int):
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["at", "run", "model", "n_comments", "input", "cache_write", "cache_read", "output", "usd"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), run, MODEL, n_comments, usage.input_tokens,
                    usage.cache_creation_input_tokens or 0, usage.cache_read_input_tokens or 0,
                    usage.output_tokens, f"{usd:.6f}"])


# ---------- requests ----------

def request_params(rows: list[dict], thinking: str) -> dict:
    params = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        # cache the shared instructions; every chunk reuses them
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": render_comments(rows)}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    if thinking == "off":
        params["thinking"] = {"type": "disabled"}  # allowed on Haiku 5.5 at effort low/medium/high
    return params


def parse_response(msg) -> dict[str, list[dict]]:
    if msg.stop_reason != "end_turn":
        raise RuntimeError(f"stop_reason={msg.stop_reason} {getattr(msg, 'stop_details', None)}")
    text = next(b.text for b in msg.content if b.type == "text")
    return {c["comment_id"]: c["observations"] for c in json.loads(text)["comments"]}


def flatten(comment_ids: list[str], extracted: dict[str, list[dict]]) -> list[dict]:
    """Same shape as the hand-label sheet: a comment with no observations gets one kind=none row."""
    def fmt(v):
        return "" if v is None else str(v).lower() if isinstance(v, bool) else str(v)
    rows = []
    for cid in comment_ids:
        obs = extracted.get(cid)
        if obs is None:
            rows.append({"comment_id": cid, "kind": "MISSING"})
        elif not obs:
            rows.append({"comment_id": cid, "kind": "none"})
        else:
            rows.extend({"comment_id": cid, **{k: fmt(o.get(k)) for k in LABEL_COLS[1:]}} for o in obs)
    return rows


# ---------- commands ----------

def pilot(args):
    load_dotenv(ROOT / ".env")
    INTERIM.mkdir(parents=True, exist_ok=True)
    ids = pd.read_csv(MANIFEST, dtype=str).comment_id.tolist()
    c = load_comments().set_index("comment_id")
    rows = [{"comment_id": i, **c.loc[i, ["thread_date", "weekday", "comment_time", "parent_body", "body"]]}
            for i in ids]
    tag = args.tag or f"haiku_{args.thinking}"
    before = spent_total()
    if before >= HARD_STOP_USD:
        sys.exit(f"hard stop: ${before:.2f} already spent (limit ${HARD_STOP_USD:.2f})")

    client = anthropic.Anthropic(max_retries=4)
    extracted, usages, run_usd, t0 = {}, [], 0.0, time.monotonic()
    for start in range(0, len(rows), CHUNK):
        if run_usd >= PILOT_CAP_USD or before + run_usd >= HARD_STOP_USD:
            print(f"stopping: run spend ${run_usd:.4f} hit a cap")
            break
        chunk = rows[start:start + CHUNK]
        msg = client.messages.create(**request_params(chunk, args.thinking))
        usd = call_cost(msg.usage)
        run_usd += usd
        record(f"pilot:{tag}", msg.usage, usd, len(chunk))
        usages.append(msg.usage)
        try:
            extracted.update(parse_response(msg))
        except (RuntimeError, json.JSONDecodeError, StopIteration) as e:
            print(f"  chunk {start // CHUNK}: {e}")
        print(f"  chunk {start // CHUNK + 1}/{-(-len(rows) // CHUNK)}: in {msg.usage.input_tokens} "
              f"cache_r {msg.usage.cache_read_input_tokens or 0} cache_w {msg.usage.cache_creation_input_tokens or 0} "
              f"out {msg.usage.output_tokens} ${usd:.4f}")

    out = INTERIM / f"pilot_{tag}.csv"
    pd.DataFrame(flatten(ids, extracted), columns=LABEL_COLS).fillna("").to_csv(out, index=False)
    done = sum(u is not None for u in usages) * CHUNK
    print(f"\nwrote {out}")
    print(f"pilot spend ${run_usd:.4f} for {min(done, len(rows))} comments in {time.monotonic() - t0:.0f}s "
          f"(project total ${before + run_usd:.4f} of ${HARD_STOP_USD:.2f} hard stop)")
    if done:
        project(per_comment_usd=run_usd / min(done, len(rows)))


def project(per_comment_usd: float | None = None, args=None):
    """Estimate the full-run cost from the pilot's per-comment cost (sync price), at batch price."""
    if per_comment_usd is None:
        p = pd.read_csv(LEDGER)
        p = p[p.run.str.startswith("pilot:")]
        if args and args.tag:
            p = p[p.run == f"pilot:{args.tag}"]
        per_comment_usd = p.usd.sum() / p.n_comments.sum()
    c = pd.read_csv(COMMENTS_CSV, dtype=str, keep_default_na=False)
    c = c[~c.body.isin(SKIP_BODIES)]
    keep = c.body.str.contains(PREFILTER_RE)
    print("\nfull-run projection (Batches API = half the pilot's per-comment cost):")
    print(f"  per comment (sync): ${per_comment_usd * 1000:.3f} per 1,000")
    for label, mask in [("daily threads", c.source == "daily_thread"), ("all sources", c.source != "")]:
        n_all, n_kept = int(mask.sum()), int((mask & keep).sum())
        print(f"  {label:13s}: {n_all:6,} comments -> ${n_all * per_comment_usd / 2:.2f} | "
              f"after pre-filter {n_kept:6,} -> ${n_kept * per_comment_usd / 2:.2f}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot", help="extract the hand-labeled sample (sync API calls)")
    p.add_argument("--thinking", choices=["adaptive", "off"], default="adaptive")
    p.add_argument("--tag", help="name for this run's output (default haiku_<thinking>)")
    q = sub.add_parser("project", help="estimate full-run cost from pilot spend in the ledger")
    q.add_argument("--tag")
    args = ap.parse_args()
    pilot(args) if args.cmd == "pilot" else project(args=args)


if __name__ == "__main__":
    main()

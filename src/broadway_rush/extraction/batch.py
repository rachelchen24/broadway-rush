"""Full extraction via the Message Batches API (step 3; half price, results within ~24 h, usually <1 h).

    py -m broadway_rush.extraction.batch full --dry-run   # count + cost estimate, sends nothing
    py -m broadway_rush.extraction.batch full             # submit one batch of all not-yet-extracted comments
    py -m broadway_rush.extraction.batch collect          # poll; when done, validate + save results
    py -m broadway_rush.extraction.batch reports          # -> data/processed/reports.csv

Extracted comments are appended to data/interim/extractions.jsonl (one line per comment) and never sent again,
so later runs only pay for new comments. Chunks that fail validation are simply left unextracted; the next
`full` picks them up.
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

from broadway_rush.extraction.run import (CHUNK, HARD_STOP_USD, INTERIM, LABEL_COLS, MODEL, PREFILTER_RE, ROOT,
                                          SKIP_BODIES, BadOutput, call_cost, load_comments, parse_response,
                                          record, request_params, spent_total)

EXTRACTIONS = INTERIM / "extractions.jsonl"
BATCHES = INTERIM / "batches"
REPORTS = ROOT / "data" / "processed" / "reports.csv"
PILOT_TAG = "pilot:holdout_v2"   # per-comment cost for the estimate comes from this pilot run
SAFETY = 1.5                     # submit only if estimate x SAFETY still fits under the hard stop
SEED = 11


def extracted_ids() -> set[str]:
    if not EXTRACTIONS.exists():
        return set()
    with EXTRACTIONS.open(encoding="utf-8") as f:
        return {json.loads(line)["comment_id"] for line in f}


def pending_batches() -> list[Path]:
    return [p for p in sorted(BATCHES.glob("*.json")) if not json.loads(p.read_text())["collected"]]


def per_comment_usd() -> float:
    led = pd.read_csv(INTERIM / "llm_spend.csv")
    led = led[led.run == PILOT_TAG]
    return float(led.usd.sum() / led.n_comments.sum())


def select_comments() -> pd.DataFrame:
    c = load_comments().drop_duplicates("comment_id")
    c = c[~c.body.isin(SKIP_BODIES) & c.body.str.contains(PREFILTER_RE)]
    done = extracted_ids()
    for p in pending_batches():  # don't resubmit comments sitting in a batch we haven't collected yet
        done |= {cid for ids in json.loads(p.read_text())["chunks"].values() for cid in ids}
    return c[~c.comment_id.isin(done)]


def full(args):
    load_dotenv(ROOT / ".env")
    todo = select_comments()
    # shuffle so a chunk's 10 comments come from different threads (less chance of borrowing between them)
    ids = todo.comment_id.tolist()
    random.Random(SEED).shuffle(ids)
    if args.limit:
        ids = ids[:args.limit]
        todo = todo[todo.comment_id.isin(ids)]
    rows = todo.set_index("comment_id")
    chunks = {f"chunk-{i:05d}": ids[i * CHUNK:(i + 1) * CHUNK] for i in range(-(-len(ids) // CHUNK))}
    est = len(ids) * per_comment_usd() / 2  # batch = half price
    spent = spent_total()
    print(f"to extract: {len(ids):,} comments in {len(chunks):,} requests "
          f"({todo.source.value_counts().to_dict()})")
    print(f"estimated cost: ${est:.2f} (batch price) | spent so far ${spent:.2f} | hard stop ${HARD_STOP_USD:.2f}")
    if not ids:
        return
    if spent + est * SAFETY > HARD_STOP_USD:
        sys.exit(f"refusing: ${spent:.2f} + ${est:.2f} x {SAFETY} safety margin "
                 f"would pass the ${HARD_STOP_USD:.2f} stop")
    if args.dry_run:
        print("dry run: nothing sent")
        return

    ctx = ["thread_date", "weekday", "comment_time", "parent_body", "body"]
    requests = [{"custom_id": cid_chunk,
                 "params": request_params([{"comment_id": i, **rows.loc[i, ctx]} for i in members], "adaptive")}
                for cid_chunk, members in chunks.items()]
    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=requests)
    BATCHES.mkdir(parents=True, exist_ok=True)
    (BATCHES / f"{batch.id}.json").write_text(json.dumps({
        "batch_id": batch.id, "submitted": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
        "n_comments": len(ids), "estimate_usd": round(est, 4), "collected": False, "chunks": chunks}))
    print(f"submitted batch {batch.id} ({batch.processing_status}); run `collect` to check on it")


def collect(args):
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    pending = pending_batches()
    if not pending:
        print("no batches waiting to be collected")
    for path in pending:
        meta = json.loads(path.read_text())
        b = client.messages.batches.retrieve(meta["batch_id"])
        rc = b.request_counts
        print(f"{b.id}: {b.processing_status} | processing {rc.processing}, succeeded {rc.succeeded}, "
              f"errored {rc.errored}, expired {rc.expired}")
        if b.processing_status != "ended":
            continue
        stats = {"bad_kind": 0, "unknown_field": 0, "bad_value": 0}
        n_ok = n_bad = usd_total = 0
        with EXTRACTIONS.open("a", encoding="utf-8") as out:
            for res in client.messages.batches.results(b.id):
                members = meta["chunks"][res.custom_id]
                if res.result.type != "succeeded":
                    n_bad += 1
                    continue
                msg = res.result.message
                usd = call_cost(msg.usage, batch=True)
                usd_total += usd
                record(f"batch:{b.id}", msg.usage, usd, len(members))
                try:
                    got = parse_response(msg, stats)
                except BadOutput:
                    n_bad += 1
                    continue
                for cid in members:
                    if cid in got:  # a comment the model skipped stays unextracted and is retried next run
                        out.write(json.dumps({"comment_id": cid, "observations": got[cid], "batch": b.id,
                                              "model": MODEL}) + "\n")
                n_ok += 1
        meta.update(collected=True, collected_at=datetime.now().isoformat(timespec="seconds"),
                    actual_usd=round(usd_total, 4), ok_chunks=n_ok, bad_chunks=n_bad, checks=stats)
        path.write_text(json.dumps(meta))
        print(f"collected: {n_ok} chunks ok, {n_bad} failed (rerun `full` to retry them) | "
              f"actual cost ${usd_total:.2f} vs estimate ${meta['estimate_usd']:.2f} | checks {stats} | "
              f"project total ${spent_total():.2f}")


def reports(args):
    """Flatten extractions.jsonl into one row per observation, joined with comment metadata."""
    c = load_comments().drop_duplicates("comment_id").set_index("comment_id")
    meta_cols = ["post_id", "source", "subreddit", "thread_title", "thread_date", "created_et", "author", "score"]
    rows, n_none = [], 0
    with EXTRACTIONS.open(encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if not e["observations"]:
                n_none += 1
            for k, o in enumerate(e["observations"]):
                rows.append({"comment_id": e["comment_id"], "obs_index": k,
                             **{m: c.at[e["comment_id"], m] for m in meta_cols},
                             **{f: o.get(f) for f in LABEL_COLS[1:]}})
    df = pd.DataFrame(rows)
    REPORTS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORTS, index=False)
    print(f"wrote {REPORTS}: {len(df):,} observations from {df.comment_id.nunique():,} comments "
          f"({n_none:,} extracted comments had none)")
    print(df.kind.value_counts().to_string())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("full", help="submit all not-yet-extracted comments as one batch")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--limit", type=int, help="only this many comments (for a test batch)")
    sub.add_parser("collect", help="check on submitted batches; save results when done")
    sub.add_parser("reports", help="build data/processed/reports.csv")
    args = ap.parse_args()
    {"full": full, "collect": collect, "reports": reports}[args.cmd](args)


if __name__ == "__main__":
    main()

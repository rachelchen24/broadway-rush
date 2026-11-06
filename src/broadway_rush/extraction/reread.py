"""Second read: check every report the first pass pulled out of Reddit, with more context than it had (2026-11-06).

The first pass saw a comment and its immediate parent, so thousands of reports came out with no show or no date when
the answer was in the post title ("Oh Mary rush tix") or further up the reply chain. Some reports are also just wrong
(a question read as a count). This pass shows the model the post title, post text and whole reply chain, plus the
reports already extracted, and asks for a verdict on each: keep, fix or drop. It can't add reports: a first attempt
that re-extracted from scratch with this context invented reports and scored worse on the human-reviewed labels.

    py -m broadway_rush.extraction.reread pilot --manifest data/labels/sample_manifest.csv --tag check_hand
    py -m broadway_rush.extraction.reread full --dry-run
    py -m broadway_rush.extraction.reread full
    py -m broadway_rush.extraction.reread collect
    py -m broadway_rush.extraction.reread reports    # -> data/processed/reports_v3.csv, label_audit.csv

The first pass stays untouched in data/interim/extractions.jsonl. Every change is kept with its reason in
label_audit.csv. Pilots are scored against the human-reviewed labels with broadway_rush.extraction.score.
"""

import argparse
import csv
import json
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

from broadway_rush.extraction.run import (CHUNK, INTERIM, LABEL_COLS, LEDGER, MAX_TOKENS, ROOT, BadOutput, flatten,
                                          load_comments, spent_total, validate)

POSTS_CSV = ROOT / "data" / "raw" / "posts.csv"
FIRST_PASS = INTERIM / "extractions.jsonl"
CHECKED = INTERIM / "extractions_checked.jsonl"
BATCHES = INTERIM / "batches_checked"
REPORTS = ROOT / "data" / "processed" / "reports_v3.csv"
AUDIT = ROOT / "data" / "processed" / "label_audit.csv"
BUDGET_USD = 6.49  # project total: the $1.49 spent before this pass plus the $5 Rachel approved on 2026-11-06
PILOT_CAP_USD = 0.60
SAFETY = 1.5
SEED = 17
MAX_ANCESTORS = 4
MAX_CONTEXT_CHARS = 800  # each piece of context, so a long post doesn't crowd out the request; the body is never cut
DEFAULT_MODEL = "claude-haiku-5-5"
# USD per token; the Batches API halves these. Cache writes are 1.25x input.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10e-6, "cache_write": 0.125e-6, "cache_read": 0.01e-6, "output": 0.50e-6},
    "claude-sonnet-5-5": {"input": 2.00e-6, "cache_write": 2.50e-6, "cache_read": 0.20e-6, "output": 10.0e-6},
    "claude-opus-5-5": {"input": 4.00e-6, "cache_write": 5.00e-6, "cache_read": 0.20e-6, "output": 20.0e-6},
}
FIXABLE = ["show_text", "show", "perf_date", "perf", "rush_type", "time", "count", "count_qual", "arrival_time",
           "line_position", "outcome", "stated_count", "stated_qual", "sold_out_time"]
DROP_REASONS = {"question", "hypothetical", "vague", "quoted", "plan", "joke", "not_a_report", "other"}

SYSTEM_PROMPT = """\
You check structured rush-ticket observations that another model extracted from Reddit comments. Rush = discounted \
day-of tickets sold at the box office to whoever lines up first. Each comment comes with the date and time it was \
posted (ET), the thread date if it is in a daily "Broadway Rush" reporting thread, the post's title and sometimes its \
text, the comments it replies to (<ancestor> blocks oldest first, then <parent>), its <body>, and the numbered \
observations extracted from it.

For each observation give one verdict:
- keep: the <body> really reports this and every filled field is right.
- fix: the <body> reports this, but a field is wrong or a blank can be filled. Give only the fields to change.
- drop: the <body> doesn't report this. Reasons: question ("only 5 people for the outsiders?"), hypothetical, vague \
(an impression with no real number: "the bulk of people got there at 7:30"), quoted (just repeats a number from \
the context, or restates what another comment said), plan (what they intend to do), joke, not_a_report, other.

Only the <body> can be the source of an observation. Everything else is context for reading it. You can't add \
observations. Be conservative: if an observation is a fair reading of the body, keep it. Don't change a value just \
because you'd have written it a little differently, and don't drop a report because it seems surprising: large lines \
do happen. A big number is only wrong if the body doesn't say it.

Fields you may fix:
- show: the full show title, and show_text: the show as written. If show is blank and the body names no show, fill it \
from the context: the nearest <parent> or <ancestor> about one show, otherwise a <post_title> or <post_text> about one \
show ("Oh Mary rush tix"). A subreddit named after one show (r/Hadestown) is also context about that show. A daily thread's title names no show. If you can't tell which show, leave it blank.
- perf_date (YYYY-MM-DD): if blank, fill it. In a daily thread, use the thread date unless the body says otherwise. \
With no thread date, use the posted date when the body describes today or reads as happening now ("I'm here", "this \
morning", "just got"), and count back from the posted date for "yesterday" or "last Saturday". Leave it blank if the \
visit can't be dated ("once", "last year", "a few months ago").
- time, arrival_time, sold_out_time: "HH:MM", 24-hour, Eastern. Morning unless the body says otherwise.
- count: people in line, and count_qual: exact / approx / at_least / at_most.
- line_position: the writer's place in line, as written.
- outcome: got_rush / sro_only / full_price_only / sold_out_before_me / left / unknown.
- rush_type: general (in-person box office) / digital / student / sro / lottery / other / unknown.
- perf: matinee / evening / unknown. stated_count and stated_qual (total / remaining): rush tickets stated.

Reply with only a JSON object, with every comment and every observation, in order. "reason" is one word from the list \
for a drop, otherwise leave it out. Example:
{"comments": [{"comment_id": "abc", "checks": [
  {"i": 0, "verdict": "keep"},
  {"i": 1, "verdict": "fix", "fixes": {"show": "Oh, Mary!", "show_text": "Oh Mary"}},
  {"i": 2, "verdict": "drop", "reason": "question"}
]}]}
"""


class Checked(dict):
    """comment_id -> list of per-observation checks."""


def cost(usage, model: str, batch: bool = False) -> float:
    p = PRICES[model]
    usd = (usage.input_tokens * p["input"] + (usage.cache_creation_input_tokens or 0) * p["cache_write"]
           + (usage.cache_read_input_tokens or 0) * p["cache_read"] + usage.output_tokens * p["output"])
    return usd * (0.5 if batch else 1.0)


def log_spend(run: str, model: str, usage, usd: float, n: int):
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), run, model, n, usage.input_tokens,
                                usage.cache_creation_input_tokens or 0, usage.cache_read_input_tokens or 0,
                                usage.output_tokens, f"{usd:.6f}"])


def first_pass() -> dict[str, list[dict]]:
    """Comment id -> its observations, last extraction wins."""
    out = {}
    with FIRST_PASS.open(encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            out[e["comment_id"]] = e["observations"]
    return out


def _cut(text: str) -> str:
    return text if len(text) <= MAX_CONTEXT_CHARS else text[:MAX_CONTEXT_CHARS] + " [cut]"


def load_context() -> pd.DataFrame:
    c = load_comments().drop_duplicates("comment_id").copy()
    posts = pd.read_csv(POSTS_CSV, dtype=str, keep_default_na=False, usecols=["post_id", "title", "selftext", "source"])
    posts = posts.drop_duplicates("post_id").set_index("post_id")
    c["post_title"] = c.post_id.map(posts.title).fillna("")
    c["sub"] = c.subreddit
    daily = c.post_id.map(posts.source).fillna("").eq("daily_thread")
    c["post_text"] = c.post_id.map(posts.selftext).fillna("").where(~daily, "")  # a bot's thread text says nothing
    body = dict(zip("t1_" + c.comment_id, c.body))
    up = dict(zip("t1_" + c.comment_id, c.parent_id))
    chains = []
    for parent in c.parent_id:
        chain, at = [], up.get(parent)  # the parent itself is shown as <parent>
        while at and at in body and len(chain) < MAX_ANCESTORS:
            chain.append(body[at])
            at = up.get(at)
        chains.append(chain[::-1])
    c["ancestors"] = chains
    c["posted_date"] = c.created_et.str[:10]
    c["posted_day"] = [date.fromisoformat(d).strftime("%A") if d else "" for d in c.posted_date]
    return c.set_index("comment_id", drop=False)


def render(rows: list[dict], obs: dict[str, list[dict]]) -> str:
    parts = []
    for r in rows:
        blocks = [f"<post_title>{r['post_title']}</post_title>"] if r["post_title"] else []
        if r["post_text"]:
            blocks.append(f"<post_text>{_cut(r['post_text'])}</post_text>")
        blocks += [f"<ancestor>{_cut(a)}</ancestor>" for a in r["ancestors"]]
        if r["parent_body"]:
            blocks.append(f"<parent>{_cut(r['parent_body'])}</parent>")
        blocks.append(f"<body>{r['body']}</body>")
        listed = [{"i": i, **o} for i, o in enumerate(obs[r["comment_id"]])]
        blocks.append(f"<observations>{json.dumps(listed, ensure_ascii=False)}</observations>")
        thread = f'thread_date="{r["thread_date"]} ({r["weekday"]})" ' if r["thread_date"] else ""
        parts.append(f'<comment id="{r["comment_id"]}" subreddit="r/{r["sub"]}" {thread}posted="{r["posted_date"]} ({r["posted_day"]}) '
                     f'{r["comment_time"]}">\n' + "\n".join(blocks) + "\n</comment>")
    return "\n\n".join(parts)


def params(rows: list[dict], obs: dict, model: str, effort: str) -> dict:
    return dict(
        model=model, max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": render(rows, obs)}],
        output_config={"effort": effort},
    )


def parse(msg) -> Checked:
    if msg.stop_reason != "end_turn":
        raise BadOutput(f"stop_reason={msg.stop_reason}")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1])
        return Checked({c["comment_id"]: c["checks"] for c in data["comments"]})
    except (ValueError, KeyError, TypeError) as e:
        raise BadOutput(f"unparseable JSON: {e}") from e


def apply_checks(observations: list[dict], checks: list[dict], stats: dict) -> tuple[list[dict], list[dict]]:
    """Returns the observations after the verdicts, and one audit row per observation. A verdict that doesn't validate
    leaves the observation as it was, and an observation with no verdict is kept."""
    by_i = {c.get("i"): c for c in checks if isinstance(c, dict)}
    kept, audit = [], []
    for i, o in enumerate(observations):
        c = by_i.get(i, {})
        verdict = c.get("verdict", "keep")
        row = {"obs_index": i, "verdict": verdict, "reason": "", "changed": ""}
        if verdict == "drop":
            reason = c.get("reason", "other")
            row["reason"] = reason if reason in DROP_REASONS else "other"
            audit.append(row)
            stats["drop"] = stats.get("drop", 0) + 1
            continue
        new = dict(o)
        if verdict == "fix" and isinstance(c.get("fixes"), dict):
            asked = {k: v for k, v in c["fixes"].items() if k in FIXABLE}
            clean = validate({"kind": o.get("kind"), **asked}, stats) or {}
            changed = []
            for k in asked:
                if k == "perf_date" and o.get(k):  # fill blanks only: shifting a stated date scored worse on the labels
                    continue
                if k in clean and clean[k] != o.get(k):
                    new[k] = clean[k]
                    changed.append(f"{k}: {o.get(k, '')} -> {clean[k]}")
            row["changed"] = "; ".join(changed)
            row["verdict"] = "fix" if changed else "keep"
        else:
            row["verdict"] = "keep"
        stats[row["verdict"]] = stats.get(row["verdict"], 0) + 1
        kept.append(new)
        audit.append(row)
    return kept, audit


def pilot(args):
    load_dotenv(ROOT / ".env")
    ids = pd.read_csv(args.manifest, dtype=str).comment_id.tolist()
    obs = first_pass()
    c = load_context()
    fields = ["comment_id", "thread_date", "weekday", "comment_time", "parent_body", "body", "post_title", "post_text",
              "ancestors", "posted_date", "posted_day", "sub"]
    todo = [c.loc[i, fields].to_dict() for i in ids if obs.get(i)]
    client = anthropic.Anthropic(max_retries=4)
    usd_run, out, stats, audits = 0.0, {}, {}, []
    for start in range(0, len(todo), CHUNK):
        chunk = todo[start:start + CHUNK]
        if usd_run >= PILOT_CAP_USD or spent_total() >= BUDGET_USD:
            sys.exit(f"stopping: ${usd_run:.4f} this run, ${spent_total():.2f} in total")
        for attempt in (1, 2):
            msg = client.messages.create(**params(chunk, obs, args.model, args.effort))
            usd = cost(msg.usage, args.model)
            usd_run += usd
            log_spend(f"pilot:{args.tag}", args.model, msg.usage, usd, len(chunk) if attempt == 1 else 0)
            try:
                got = parse(msg)
                for r in chunk:
                    cid = r["comment_id"]
                    kept, audit = apply_checks(obs[cid], got.get(cid, []), stats)
                    out[cid] = kept
                    audits += [{"comment_id": cid, **a} for a in audit]
                break
            except BadOutput as e:
                print(f"  bad output (attempt {attempt}): {e}")
    final = {i: out.get(i, obs.get(i, [])) for i in ids}
    path = INTERIM / f"pilot_{args.tag}.csv"
    pd.DataFrame(flatten(ids, final), columns=LABEL_COLS).fillna("").to_csv(path, index=False)
    pd.DataFrame(audits).to_csv(INTERIM / f"pilot_{args.tag}_audit.csv", index=False)
    print(f"{args.tag}: {args.model} effort {args.effort} | {stats} | ${usd_run:.4f} for {len(todo)} comments "
          f"| project total ${spent_total():.2f}")


def done_ids() -> set[str]:
    done = set()
    if CHECKED.exists():
        with CHECKED.open(encoding="utf-8") as f:
            done = {json.loads(line)["comment_id"] for line in f}
    for p in sorted(BATCHES.glob("*.json")) if BATCHES.exists() else []:
        meta = json.loads(p.read_text())
        if not meta["collected"]:
            done |= {cid for ids in meta["chunks"].values() for cid in ids}
    return done


def full(args):
    load_dotenv(ROOT / ".env")
    obs = first_pass()
    done = done_ids()
    ids = [i for i, o in obs.items() if o and i not in done]
    random.Random(SEED).shuffle(ids)
    c = load_context()
    fields = ["comment_id", "thread_date", "weekday", "comment_time", "parent_body", "body", "post_title", "post_text",
              "ancestors", "posted_date", "posted_day", "sub"]
    chunks = {f"chunk-{i:05d}": ids[i * CHUNK:(i + 1) * CHUNK] for i in range(-(-len(ids) // CHUNK))}
    led = pd.read_csv(LEDGER)
    led = led[led.run.isin([f"pilot:{args.pilot_tag}", f"pilot:{args.pilot_tag}_holdout"])]
    per = float(led.usd.sum() / led.n_comments.sum())
    est = len(ids) * per / 2
    spent = spent_total()
    print(f"to check: {len(ids):,} comments in {len(chunks):,} requests | {args.model} effort {args.effort} | "
          f"estimate ${est:.2f} | spent ${spent:.2f} | budget ${BUDGET_USD:.2f}")
    if spent + est * SAFETY > BUDGET_USD:
        sys.exit(f"refusing: ${spent:.2f} + ${est:.2f} x {SAFETY} would pass the ${BUDGET_USD:.2f} budget")
    if args.dry_run or not ids:
        print("nothing sent")
        return
    requests = [{"custom_id": k, "params": params([c.loc[i, fields].to_dict() for i in members], obs, args.model, args.effort)}
                for k, members in chunks.items()]
    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=requests)
    BATCHES.mkdir(parents=True, exist_ok=True)
    (BATCHES / f"{batch.id}.json").write_text(json.dumps({
        "batch_id": batch.id, "submitted": datetime.now().isoformat(timespec="seconds"), "model": args.model,
        "n_comments": len(ids), "estimate_usd": round(est, 4), "collected": False, "chunks": chunks}))
    print(f"submitted {batch.id} ({batch.processing_status})")


def collect(args):
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    obs = first_pass()
    for path in sorted(BATCHES.glob("*.json")):
        meta = json.loads(path.read_text())
        if meta["collected"]:
            continue
        b = client.messages.batches.retrieve(meta["batch_id"])
        rc = b.request_counts
        print(f"{b.id}: {b.processing_status} | processing {rc.processing}, succeeded {rc.succeeded}, "
              f"errored {rc.errored}, expired {rc.expired}")
        if b.processing_status != "ended":
            continue
        stats, n_ok, n_bad, usd_total = {}, 0, 0, 0.0
        with CHECKED.open("a", encoding="utf-8") as out:
            for res in client.messages.batches.results(b.id):
                members = meta["chunks"][res.custom_id]
                if res.result.type != "succeeded":
                    n_bad += 1
                    continue
                msg = res.result.message
                usd = cost(msg.usage, meta["model"], batch=True)
                usd_total += usd
                log_spend(f"batch_checked:{b.id}", meta["model"], msg.usage, usd, len(members))
                try:
                    got = parse(msg)
                except BadOutput:
                    n_bad += 1
                    continue
                for cid in members:
                    if cid in got:  # a comment the model skipped stays unchecked and is retried next run
                        kept, audit = apply_checks(obs[cid], got[cid], stats)
                        out.write(json.dumps({"comment_id": cid, "observations": kept, "audit": audit,
                                              "batch": b.id, "model": meta["model"]}) + "\n")
                n_ok += 1
        meta.update(collected=True, collected_at=datetime.now().isoformat(timespec="seconds"),
                    actual_usd=round(usd_total, 4), ok_chunks=n_ok, bad_chunks=n_bad, checks=stats)
        path.write_text(json.dumps(meta))
        print(f"collected: {n_ok} chunks ok, {n_bad} failed | ${usd_total:.2f} vs estimate ${meta['estimate_usd']:.2f} "
              f"| {stats} | project total ${spent_total():.2f}")


def reports(args):
    c = load_comments().drop_duplicates("comment_id").set_index("comment_id")
    meta_cols = ["post_id", "source", "subreddit", "thread_title", "thread_date", "created_et", "author", "score"]
    final = first_pass()
    audit_rows = []
    if CHECKED.exists():
        with CHECKED.open(encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                final[e["comment_id"]] = e["observations"]
                audit_rows += [{"comment_id": e["comment_id"], **a} for a in e["audit"]]
    rows = []
    for cid, observations in final.items():
        for k, o in enumerate(observations):
            rows.append({"comment_id": cid, "obs_index": k, **{m: c.at[cid, m] for m in meta_cols},
                         **{f: o.get(f) for f in LABEL_COLS[1:]}})
    df = pd.DataFrame(rows)
    df.to_csv(REPORTS, index=False)
    pd.DataFrame(audit_rows).to_csv(AUDIT, index=False)
    print(f"wrote {REPORTS}: {len(df):,} observations from {df.comment_id.nunique():,} comments")
    if audit_rows:
        print(pd.DataFrame(audit_rows).verdict.value_counts().to_string())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL, choices=list(PRICES))
    p.add_argument("--effort", default="low")
    q = sub.add_parser("full")
    q.add_argument("--dry-run", action="store_true")
    q.add_argument("--model", default=DEFAULT_MODEL, choices=list(PRICES))
    q.add_argument("--effort", default="low")
    q.add_argument("--pilot-tag", required=True, help="pilot whose per-comment cost sets the estimate")
    sub.add_parser("collect")
    sub.add_parser("reports")
    args = ap.parse_args()
    {"pilot": pilot, "full": full, "collect": collect, "reports": reports}[args.cmd](args)


if __name__ == "__main__":
    main()

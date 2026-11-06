"""Reddit rush reports via the Arctic Shift archive (SPEC §3.1).

Phases (run in order; each is resumable):
    py -m broadway_rush.scrapers.reddit posts     # daily threads + keyword posts -> data/raw/posts.csv
    py -m broadway_rush.scrapers.reddit comments  # comments per post -> data/raw/comments.csv
    py -m broadway_rush.scrapers.reddit summary   # stats + random sample comments
"""

import argparse
import csv
import logging
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from broadway_rush.http import PoliteClient

API = "https://arctic-shift.photon-reddit.com/api"
ET = ZoneInfo("America/New_York")
START_UTC = int(datetime(2024, 6, 1, tzinfo=ET).timestamp())
RECENT_SECONDS = 72 * 3600      # threads younger than this are re-fetched on the next run
SAVE_EVERY = 10                 # pages between posts.csv / cursor checkpoints
MAX_FAILED_IN_A_ROW = 5       # consecutive posts that fail before the comments phase stops

# Title search on the archive is unreliable (keeps returning "Timeout"), so we scan each
# subreddit by date and match keywords locally in title + body.
DAILY_AUTHOR = "BroadwayRushReport"
BOT_NON_DAILY = re.compile(r"availability list", re.IGNORECASE)  # bot posts that are not daily reports
MAX_TITLE_DATE_DRIFT = 3  # days between title date and post date before we distrust the title
# Show-fan subreddits added 2026-11-06: they hold reports for shows the daily threads rarely cover (Hadestown, Six)
SUBREDDITS = ["Broadway", "musicals", "AskNYC", "nyc", "Hadestown", "wicked", "SixTheMusical", "andjuliet",
              "hamiltonmusical", "TheOutsidersMusical", "BroadwayTickets", "theatre"]
KEYWORDS = ["rush", "lottery", "standing room", "SRO", "digital rush", "TodayTix", "box office", "line"]
# In these general NYC subs most keyword hits aren't theater ("rush hour", "the 7 line"); only
# fetch comments when the post looks theater-related. Posts are kept either way.
FILTERED_SUBS = {"AskNYC", "nyc"}
THEATER_RE = re.compile(
    r"\b(broadway|off-broadway|theat(er|re)s?|musicals?|plays?|shows?|tickets?|tkts|todaytix|"
    r"matinee|playbill|box office|rush tickets?|standing room|sro|lottery|"
    r"hamilton|wicked|lion king|book of mormon|hadestown|moulin rouge|mj|six|chicago|aladdin)\b",
    re.IGNORECASE,
)
KEYWORD_RES = {kw: re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in KEYWORDS}
TITLE_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
# "line" is everywhere in post bodies; a body-only "line" match keeps the post but skips its comments
WEAK_BODY_KEYWORDS = {"line"}

POST_FIELDS = "id,title,author,created_utc,num_comments,score,subreddit,selftext"
COMMENT_FIELDS = "id,link_id,parent_id,author,created_utc,score,body"

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
STATE = RAW / "_state"
POSTS_CSV = RAW / "posts.csv"
COMMENTS_CSV = RAW / "comments.csv"
DONE_CSV = STATE / "threads_done.csv"

POST_COLS = ["post_id", "subreddit", "source", "matched_keywords", "matched_in", "title", "author", "created_utc",
             "created_et", "thread_date", "num_comments", "score", "fetch_comments", "permalink", "selftext"]
COMMENT_COLS = ["comment_id", "post_id", "parent_id", "author", "created_utc", "created_et", "score",
                "body", "subreddit", "thread_title", "thread_date", "source"]

log = logging.getLogger("reddit")


def to_et(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), ET).isoformat(timespec="seconds")


def thread_date(title: str, created_utc: int) -> str:
    """Performance date named in the daily thread title ('6/15/24', or '9/23' with the nearest year).
    Falls back to the post date when there's no date or it's >3 days off (bot typos like '1/1/24'
    posted on 11/1/24)."""
    posted = datetime.fromtimestamp(int(created_utc), ET).date()
    m = TITLE_DATE_RE.search(title)
    if m:
        mo, d = int(m[1]), int(m[2])
        if m[3]:
            y = int(m[3])
            years = [y + 2000 if y < 100 else y]
        else:
            years = [posted.year - 1, posted.year, posted.year + 1]
        candidates = []
        for y in years:
            try:
                candidates.append(date(y, mo, d))
            except ValueError:
                pass
        if candidates:
            best = min(candidates, key=lambda c: abs((c - posted).days))
            if abs((best - posted).days) <= MAX_TITLE_DATE_DRIFT:
                return best.isoformat()
    return posted.isoformat()


# ---------- fetching ----------

def _pages(client: PoliteClient, endpoint: str, params: dict, after: int):
    """Yield pages walking forward in time (sort=asc), using the last created_utc as the cursor."""
    cur = after
    while True:
        page = client.get_json(f"{API}/{endpoint}", {**params, "limit": 100, "sort": "asc", "after": cur})["data"] or []
        yield page
        if len(page) < 100:
            return
        # -1 so items sharing the boundary second aren't skipped (dedupe by id downstream)
        cur = max(cur + 1, int(page[-1]["created_utc"]) - 1)


def _fetch_all(client: PoliteClient, endpoint: str, params: dict, after: int) -> list[dict]:
    out: dict[str, dict] = {}
    for page in _pages(client, endpoint, params, after):
        for x in page:
            out.setdefault(x["id"], x)
    return list(out.values())


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_atomic(path: Path, cols: list[str], rows: list[dict]):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def match_keywords(p: dict) -> tuple[set[str], set[str]]:
    title, body = p["title"], p.get("selftext") or ""
    return ({kw for kw, rx in KEYWORD_RES.items() if rx.search(title)},
            {kw for kw, rx in KEYWORD_RES.items() if rx.search(body)})


def post_row(p: dict, source: str) -> dict:
    sub = p["subreddit"]
    in_title, in_body = match_keywords(p)
    if source in ("daily_thread", "bot_post"):
        fetch = True
    else:
        strong = bool(in_title) or bool(in_body - WEAK_BODY_KEYWORDS)
        theater = sub not in FILTERED_SUBS or bool(THEATER_RE.search(f"{p['title']} {p.get('selftext') or ''}"))
        fetch = strong and theater
    where = [w for w, s in (("title", in_title), ("body", in_body)) if s]
    return {
        "post_id": p["id"], "subreddit": sub, "source": source,
        "matched_keywords": ";".join(kw for kw in KEYWORDS if kw in in_title | in_body),
        "matched_in": ";".join(where),
        "title": p["title"], "author": p["author"], "created_utc": int(p["created_utc"]),
        "created_et": to_et(p["created_utc"]),
        "thread_date": thread_date(p["title"], p["created_utc"]) if source == "daily_thread" else "",
        "num_comments": p.get("num_comments", ""), "score": p.get("score", ""),
        "fetch_comments": fetch, "permalink": f"https://www.reddit.com/r/{sub}/comments/{p['id']}/",
        "selftext": p.get("selftext") or "",
    }


def _save_posts(posts: dict[str, dict]):
    write_csv_atomic(POSTS_CSV, POST_COLS, sorted(posts.values(), key=lambda r: int(r["created_utc"])))


def scrape_posts(client: PoliteClient):
    posts: dict[str, dict] = {r["post_id"]: r for r in load_csv(POSTS_CSV)}
    n_before = len(posts)

    # 1) everything the thread bot posted in r/Broadway (author search is fast and reliable)
    bot = _fetch_all(client, "posts/search", {"subreddit": "Broadway", "author": DAILY_AUTHOR,
                                              "fields": POST_FIELDS}, START_UTC)
    for p in bot:
        source = "bot_post" if BOT_NON_DAILY.search(p["title"]) else "daily_thread"
        posts[p["id"]] = post_row(p, source)
    others = sorted(p["title"] for p in bot if BOT_NON_DAILY.search(p["title"]))
    log.info("bot posts: %d (%d daily threads, %d other)", len(bot), len(bot) - len(others), len(others))
    for t in others[:20]:
        log.info("  other bot post: %s", t)
    _save_posts(posts)

    # 2) scan each subreddit by date; keep posts with a keyword in title or body. Resumable per subreddit.
    for sub in SUBREDDITS:
        cursor_file = STATE / f"cursor_{sub}.txt"
        cur = int(cursor_file.read_text()) if cursor_file.exists() else START_UTC
        log.info("r/%s: scanning from %s", sub, to_et(cur))
        scanned = matched = 0
        for i, page in enumerate(_pages(client, "posts/search", {"subreddit": sub, "fields": POST_FIELDS}, cur), 1):
            for p in page:
                scanned += 1
                if posts.get(p["id"], {}).get("source") in ("daily_thread", "bot_post"):
                    continue
                if any(match_keywords(p)):
                    posts[p["id"]] = post_row(p, "keyword_match")
                    matched += 1
            if page:
                cur = max(cur, int(page[-1]["created_utc"]) - 1)
            if i % SAVE_EVERY == 0 or len(page) < 100:
                _save_posts(posts)
                cursor_file.write_text(str(cur))
                log.info("r/%s: up to %s, scanned %d, matched %d (%d requests total)",
                         sub, to_et(cur)[:10], scanned, matched, client.n_requests)

    log.info("posts.csv: %d rows (%d new), %d requests", len(posts), len(posts) - n_before, client.n_requests)


# ---------- comments ----------

def scrape_comments(client: PoliteClient):
    posts = load_csv(POSTS_CSV)
    if not posts:
        sys.exit("posts.csv missing: run the 'posts' phase first")
    done = {r["post_id"] for r in load_csv(DONE_CSV)}
    have = set()
    if COMMENTS_CSV.exists():
        with COMMENTS_CSV.open(encoding="utf-8", newline="") as f:
            have = {r["comment_id"] for r in csv.DictReader(f)}

    now = time.time()

    def empty(p):  # old posts the archive says have no comments; recent counts may be stale
        return p["num_comments"] in ("0", "") and now - int(p["created_utc"]) > RECENT_SECONDS

    def priority(p):  # bot threads first, then keyword-in-title posts, then body-only matches
        if p["source"] in ("daily_thread", "bot_post"):
            return 0
        return 1 if "title" in p["matched_in"] else 2

    todo = [p for p in posts if p["fetch_comments"] == "True" and p["post_id"] not in done]
    skipped = sum(map(empty, todo))
    todo = [p for p in todo if not empty(p)]
    todo.sort(key=lambda p: (priority(p), int(p["created_utc"])))
    log.info("%d posts to fetch (%d already done, %d skipped with 0 comments, %d comments on disk)",
             len(todo), len(done), skipped, len(have))

    new_comments_file = not COMMENTS_CSV.exists()
    new_done_file = not DONE_CSV.exists()
    t0, added, failed = time.monotonic(), 0, []
    with COMMENTS_CSV.open("a", encoding="utf-8", newline="") as cf, DONE_CSV.open("a", encoding="utf-8", newline="") as df:
        cw = csv.DictWriter(cf, fieldnames=COMMENT_COLS)
        dw = csv.DictWriter(df, fieldnames=["post_id", "n_comments", "scraped_at"])
        if new_comments_file:
            cw.writeheader()
        if new_done_file:
            dw.writeheader()

        failed_in_a_row = 0
        for i, p in enumerate(todo, 1):
            try:
                comments = _fetch_all(client, "comments/search", {"link_id": p["post_id"], "fields": COMMENT_FIELDS},
                                     int(p["created_utc"]) - 1)
                failed_in_a_row = 0
            except RuntimeError as e:
                # skip this post (not marked done, so the next run retries it); several in a row = archive is down
                failed_in_a_row += 1
                failed.append(p["post_id"])
                log.error("skipping post %s: %s", p["post_id"], e)
                if failed_in_a_row >= MAX_FAILED_IN_A_ROW:
                    log.error("%d posts failed in a row; stopping. Rerun later to resume.", failed_in_a_row)
                    break
                continue
            for c in comments:
                if c["id"] in have:
                    continue
                have.add(c["id"])
                cw.writerow({
                    "comment_id": c["id"], "post_id": p["post_id"], "parent_id": c["parent_id"],
                    "author": c["author"], "created_utc": int(c["created_utc"]), "created_et": to_et(c["created_utc"]),
                    "score": c.get("score", ""), "body": c.get("body") or "", "subreddit": p["subreddit"],
                    "thread_title": p["title"], "thread_date": p["thread_date"], "source": p["source"],
                })
                added += 1
            cf.flush()
            if time.time() - int(p["created_utc"]) > RECENT_SECONDS:
                dw.writerow({"post_id": p["post_id"], "n_comments": len(comments),
                             "scraped_at": datetime.now(ET).isoformat(timespec="seconds")})
                df.flush()
            if i % 25 == 0 or i == len(todo):
                rate = (time.monotonic() - t0) / i
                log.info("%d/%d posts, +%d comments, ~%.0f min left", i, len(todo), added,
                         rate * (len(todo) - i) / 60)
    log.info("done: +%d comments, %d requests, %d posts skipped (rerun to retry them): %s",
             added, client.n_requests, len(failed), ",".join(failed[:20]))


# ---------- summary ----------

def summary():
    import pandas as pd

    posts = pd.read_csv(POSTS_CSV, dtype=str, keep_default_na=False)
    com = pd.read_csv(COMMENTS_CSV, dtype=str, keep_default_na=False) if COMMENTS_CSV.exists() else None
    daily = posts[posts.source == "daily_thread"]
    print(f"\n== Posts: {len(posts)} total ==")
    print(f"daily threads: {len(daily)}  ({daily.thread_date.min()} → {daily.thread_date.max()})")
    print(f"other bot posts: {(posts.source == 'bot_post').sum()}")
    kw = posts[posts.source == "keyword_match"]
    print(f"keyword posts: {len(kw)}  (comments will be fetched for {(kw.fetch_comments == 'True').sum()})")
    exploded = kw.assign(kw=kw.matched_keywords.str.split(";")).explode("kw").reset_index(drop=True)
    print("\nposts per keyword (a post can match several):")
    print(pd.crosstab(exploded.kw, exploded.subreddit, margins=True).to_string())
    print("\nposts by where the keyword matched:")
    print(pd.crosstab(kw.matched_in, kw.subreddit, margins=True).to_string())
    print("\ncomments to fetch, by subreddit (post counts):")
    print(pd.crosstab(kw.subreddit, kw.fetch_comments, margins=True).to_string())
    if com is None:
        return
    print(f"\n== Comments: {len(com)} total ==")
    print(com.groupby(["source", "subreddit"]).size().to_string())
    print(f"date range: {com.created_et.min()[:10]} → {com.created_et.max()[:10]}")
    dead = com.body.isin(["[deleted]", "[removed]"]).sum()
    print(f"deleted/removed bodies: {dead}")
    month = com.created_et.str[:7]
    print("\ncomments per month (daily threads | keyword posts):")
    print(pd.crosstab(month, com.source).to_string())
    d = com[com.source == "daily_thread"]
    per = d.groupby("post_id").size()
    print(f"\ncomments per daily thread: median {per.median():.0f}, mean {per.mean():.1f}, max {per.max()}")
    print(f"daily threads with 0 comments: {len(daily) - per.size}")
    live = com[~com.body.isin(["[deleted]", "[removed]"])]
    print("\n== 10 random comments (daily threads, seed 42) ==")
    for _, r in live[live.source == "daily_thread"].sample(10, random_state=42).iterrows():
        print(f"\n[{r.thread_date}] {r.body[:300]!r}")
    print("\n== 3 random comments (keyword posts) ==")
    for _, r in live[live.source == "keyword_match"].sample(3, random_state=42).iterrows():
        print(f"\n[r/{r.subreddit}: {r.thread_title[:60]}] {r.body[:300]!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["posts", "comments", "summary"])
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252; comments have emoji
    STATE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(STATE / "scrape.log", encoding="utf-8")],
    )
    if args.phase == "summary":
        summary()
        return
    client = PoliteClient(min_interval=1.0)
    scrape_posts(client) if args.phase == "posts" else scrape_comments(client)


if __name__ == "__main__":
    main()

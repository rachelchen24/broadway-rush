"""BroadwayWorld forum threads about rush lines, June 2024 onward (SPEC 3.1b; allowed per registry/sources.csv).

    py -m broadway_rush.scrapers.bww_forum sitemap   # thread list from the public sitemap -> data/raw/bww_forum/targets.json
    py -m broadway_rush.scrapers.bww_forum threads   # fetch those threads, cached and resumable
    py -m broadway_rush.scrapers.bww_forum parse     # cached pages -> data/raw/bww_comments.csv, bww_posts.csv

Threads come only from the sitemap, chosen by rush words in the thread's name: the forum's search page is disallowed in
robots.txt, so it's never used. Requests stay 5 s apart (Crawl-delay is 3). The CSVs use the same columns as the Reddit
files, so the extraction pipeline can read them once they're merged in with `merge`.
"""

import argparse
import csv
import gzip
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from broadway_rush.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "bww_forum"
TARGETS = CACHE / "targets.json"
COMMENTS_OUT = RAW / "bww_comments.csv"
POSTS_OUT = RAW / "bww_posts.csv"
SITEMAP = "https://forum.broadwayworld.com/sitemap.xml"
SINCE = "2024-06-01"
DELAY = 5.0
ET = ZoneInfo("America/New_York")
NAME_RE = re.compile(r"(?:^|[-_])(rush|rushing|rushed|rushes|standing-room|sro|box-office|in-person-line|line)(?:$|[-_])", re.I)
SKIP_RE = re.compile(r"august-rush|gold-rush|rush-hour|rush-limbaugh|geoffrey-rush|sugar-rush|the-line(?:$|-)|chorus-line|"
                     r"security-line|wild-party|buyer-got|lottery-winner|line-up|lineup|bottom-line|tag-line|story-line|"
                     r"caryl-churchill|top-line", re.I)
MAX_PAGES = 12
COMMENT_COLS = ["comment_id", "post_id", "parent_id", "author", "created_utc", "created_et", "score", "body", "subreddit",
                "thread_title", "thread_date", "source"]
POST_COLS = ["post_id", "subreddit", "source", "matched_keywords", "matched_in", "title", "author", "created_utc",
             "created_et", "thread_date", "num_comments", "score", "fetch_comments", "permalink", "selftext"]
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s*(?:at\s*)?(\d{1,2}):(\d{2})\s*([ap]m?)?", re.I)

log = logging.getLogger("bww_forum")
session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def fetch(url: str) -> requests.Response:
    time.sleep(DELAY)
    return session.get(url, timeout=40)


def sitemap():
    CACHE.mkdir(parents=True, exist_ok=True)
    found = []
    for sm in re.findall(r"<loc>(.*?)</loc>", fetch(SITEMAP).text):
        if "forumboard" not in sm:  # the off-topic boards aren't about shows
            continue
        for url, mod in re.findall(r"<url>\s*<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", fetch(sm).text):
            name = url.rsplit("/", 1)[1]
            if mod[:10] >= SINCE and "/thread/" in url and NAME_RE.search(name) and not SKIP_RE.search(name):
                found.append({"url": url, "lastmod": mod[:10]})
    TARGETS.write_text(json.dumps(found, indent=0))
    log.info("%d threads to read", len(found))


def page_path(url: str, page: int) -> Path:
    return CACHE / f"{url.rsplit('/', 1)[1][:120]}__p{page}.html.gz"


def threads():
    targets = json.loads(TARGETS.read_text())
    for i, t in enumerate(targets, 1):
        for page in range(1, MAX_PAGES + 1):
            path = page_path(t["url"], page)
            if path.exists():
                continue
            r = fetch(t["url"] if page == 1 else f"{t['url']}?page={page}")
            if r.status_code in (403, 429):
                sys.exit(f"stopping: {r.status_code} from {t['url']}; we never push past a block")
            if r.status_code != 200:
                log.warning("%s page %d: %d", t["url"], page, r.status_code)
                break
            posts = BeautifulSoup(r.text, "lxml").select(".board-thread-post")
            if not posts or (page > 1 and same_as_previous(t["url"], page, posts)):
                break
            path.write_bytes(gzip.compress(r.text.encode("utf-8"), mtime=0))
            if len(posts) < 20:
                break
        log.info("%d/%d %s", i, len(targets), t["url"].rsplit("/", 1)[1][:70])


def same_as_previous(url: str, page: int, posts) -> bool:
    """A forum that ignores ?page= just shows page 1 again."""
    prev = page_path(url, page - 1)
    if not prev.exists():
        return False
    old = BeautifulSoup(gzip.decompress(prev.read_bytes()).decode("utf-8"), "lxml").select(".board-thread-post")
    return bool(old) and old[0].get_text(" ", strip=True) == posts[0].get_text(" ", strip=True)


def parse_when(text: str) -> datetime | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    mo, d, y, h, mi, ap = m.groups()
    y = int(y) + 2000 if len(y) == 2 else int(y)
    h = int(h)
    if ap and ap.lower().startswith("p") and h != 12:
        h += 12
    if ap and ap.lower().startswith("a") and h == 12:
        h = 0
    return datetime(y, int(mo), int(d), h, int(mi), tzinfo=ET)


def parse():
    targets = json.loads(TARGETS.read_text())
    comments, posts = [], []
    for t in targets:
        slug = t["url"].rsplit("/", 1)[1]
        if SKIP_RE.search(slug):
            continue
        post_id = "bww_" + slug[:80]
        title, n = "", 0
        for page in range(1, MAX_PAGES + 1):
            path = page_path(t["url"], page)
            if not path.exists():
                break
            soup = BeautifulSoup(gzip.decompress(path.read_bytes()).decode("utf-8"), "lxml")
            if not title and soup.title:
                title = soup.title.get_text().split(" - BWW Forum")[0].strip()
            for p in soup.select(".board-thread-post"):
                body_el = p.select_one(".board-thread-post__message")
                date_el = p.select_one(".board-thread-post__date")
                when = parse_when(date_el.get_text(" ", strip=True)) if date_el else None
                if body_el is None or when is None or when.date().isoformat() < SINCE:
                    continue
                for q in body_el.select("blockquote, .quote, .board-quote"):
                    q.decompose()  # quoted text belongs to the post it came from
                body = body_el.get_text(" ", strip=True)
                if not body:
                    continue
                n += 1
                author = p.select_one(".post-author")
                comments.append({
                    "comment_id": f"bww_{slug[:60]}_{page}_{n}", "post_id": post_id, "parent_id": f"t3_{post_id}",
                    "author": author.get_text(" ", strip=True)[:60] if author else "",
                    "created_utc": str(int(when.timestamp())), "created_et": when.isoformat(), "score": "0", "body": body,
                    "subreddit": "BroadwayWorldForum", "thread_title": title, "thread_date": "", "source": "forum_bww",
                })
        if n:
            first = next(c for c in comments if c["post_id"] == post_id)
            posts.append({"post_id": post_id, "subreddit": "BroadwayWorldForum", "source": "forum_bww", "matched_keywords": "rush",
                          "matched_in": "title", "title": title, "author": "", "created_utc": first["created_utc"],
                          "created_et": first["created_et"], "thread_date": "", "num_comments": str(n), "score": "0",
                          "fetch_comments": "0", "permalink": t["url"], "selftext": ""})
    for path, cols, rows in ((COMMENTS_OUT, COMMENT_COLS, comments), (POSTS_OUT, POST_COLS, posts)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    log.info("%d posts from %d threads", len(comments), len(posts))


def merge():
    """Add the forum rows to the Reddit files once, so `batch full` and `reread full` pick them up."""
    for name, out, cols, key in (("comments.csv", COMMENTS_OUT, COMMENT_COLS, "comment_id"), ("posts.csv", POSTS_OUT, POST_COLS, "post_id")):
        target = RAW / name
        with open(target, newline="", encoding="utf-8") as f:
            have = {row[key] for row in csv.DictReader(f)}
            f.seek(0)
            header = next(csv.reader(f))
        with open(out, newline="", encoding="utf-8") as f:
            new = [r for r in csv.DictReader(f) if r[key] not in have]
        with open(target, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", restval="")
            w.writerows(new)
        log.info("%s: +%d rows", name, len(new))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["sitemap", "threads", "parse", "merge"])
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
    {"sitemap": sitemap, "threads": threads, "parse": parse, "merge": merge}[args.phase]()


if __name__ == "__main__":
    main()

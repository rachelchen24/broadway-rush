"""Star history (SPEC 2.8 N5 step 4, C2): who joined and left Broadway shows since June 2024, and when it was announced.

    .venv\\Scripts\\python -u -m broadway_rush.star_history candidates   # BroadwayWorld sitemaps -> casting headlines

Order (Rachel, 2026-11-11): Wikipedia replacement lists first, then BroadwayWorld casting news, then official show
sites. AI reading of articles is capped at $2.50 in total (aim about $1), one pass only, tested on about 50 articles
that Claude pre-fills and Rachel reviews before any full run.

`candidates` uses only the article addresses in BroadwayWorld's public sitemaps (robots.txt allows them, and allows
ClaudeBot by name): each address holds the headline and the date. Nothing is read from the articles here.
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from broadway_rush.catalog import norm
from broadway_rush.http import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]
SITEMAPS = ROOT / "data" / "raw" / "broadwayworld" / "sitemaps"
CANDIDATES = ROOT / "data" / "interim" / "casting_candidates.csv"
FIRST = "2024-04-01"  # a little before June 2024, so announcements for early-June stints are caught
# Headline words that mark joining, leaving or extending a run
CASTING_RE = re.compile(
    r"(?:^|-)(join|joins|joining|to-star|will-star|stars|starring|cast|casting|replac\w*|succeed\w*|step-into|"
    r"steps-into|takes-over|take-over|final-performance|final-performances|last-performance|depart\w*|leav\w*|"
    r"exit\w*|extend\w*|extension|return\w*|debut\w*|lead|headline\w*|will-play|to-play|role)(?:-|$)", re.I)

log = logging.getLogger("star_history")


def fetch_sitemaps():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    index = s.get("https://www.broadwayworld.com/sitemaps.xml", timeout=60).text
    maps = sorted((int(m[1]), u) for u in re.findall(r"<loc>([^<]+)</loc>", index)
                  for m in [re.search(r"article_sitemap_(\d+)\.xml", u)] if m)
    SITEMAPS.mkdir(parents=True, exist_ok=True)
    # Newest first; stop once a whole sitemap is older than FIRST
    for num, u in reversed(maps):
        path = SITEMAPS / u.rsplit("/", 1)[1]
        if not path.exists() or num == maps[-1][0]:
            time.sleep(5)
            path.write_text(s.get(u, timeout=180).text, encoding="utf-8")
            log.info("fetched %s", path.name)
        mods = re.findall(r"<lastmod>([^<]+)</lastmod>", path.read_text(encoding="utf-8"))
        if mods and max(mods)[:10] < FIRST:
            break


def candidates():
    fetch_sitemaps()
    shows = pd.read_csv(ROOT / "data" / "processed" / "shows.csv")
    keys = {}
    for s in shows.itertuples():
        for k in {norm(s.name), norm(s.name.split(":")[0]), norm(re.sub(r"\(.*?\)", " ", s.name))}:
            if len(k) >= 3:
                keys[k] = s.show_id
    rows = []
    for f in sorted(SITEMAPS.glob("article_sitemap_*.xml")):
        x = f.read_text(encoding="utf-8")
        for u, mod in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", x):
            if not u.startswith("https://www.broadwayworld.com/article/"):
                continue  # regional and international sections
            slug = u.rsplit("/", 1)[1]
            m = re.search(r"-(\d{8})$", slug)
            day = f"{m[1][:4]}-{m[1][4:6]}-{m[1][6:]}" if m else mod[:10]
            if day < FIRST or not CASTING_RE.search(slug):
                continue
            words = " " + norm(slug.replace("-", " ")) + " "
            hits = sorted({sid for k, sid in keys.items() if f" {k} " in words})
            if hits:
                rows.append({"date": day, "url": u, "headline": re.sub(r"-\d{8}$", "", slug).replace("-", " "),
                             "show_ids": ";".join(hits)})
    df = pd.DataFrame(rows).drop_duplicates("url").sort_values("date")
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CANDIDATES, index=False)
    log.info("wrote %s: %d casting headlines for %d shows, %s to %s", CANDIDATES.name, len(df),
             df.show_ids.str.split(";").explode().nunique(), df.date.min(), df.date.max())


# ---------- test run: ~50 articles, one AI pass (SPEC 2.8 C2) ----------
ARTICLES = ROOT / "data" / "raw" / "broadwayworld" / "articles"
TEST_OUT = ROOT / "data" / "interim" / "casting_test_extractions.jsonl"
REVIEW = ROOT / "data" / "labels" / "casting_test_review.csv"
LEDGER = ROOT / "data" / "interim" / "llm_spend.csv"
MODEL = "claude-haiku-5-5"
PRICE = {"input": 0.10e-6, "cache_write": 0.125e-6, "cache_read": 0.01e-6, "output": 0.50e-6}
SPENT_BEFORE_STAR_HISTORY = 2.96  # ledger total on 2026-11-11, before any star-history reading
STAR_HISTORY_CAP = 2.50  # Rachel's hard cap for all star-history AI reading (aim about $1)
# Tightened after the 50-article test (2026-11-11): "Videos", character breakdowns, buying guides, concerts and
# obituaries produced false "joins".
NOISE_RE = re.compile(r"^(videos?|photos?|watch|listen|review|first-look|exclusive-video|podcast|interview|"
                      r"character-breakdown|broadway-buying-guide|debut-of-the-month|up-on-the-marquee)\b|"
                      r"cast-recording|cast-album|sitzprobe|meet-the-press|tony-award|tonys|nominat|gala|"
                      r"benefit|concert|tour\b|national-tour|west-end|london|movie|film|broadway-sessions|"
                      r"celebrates|instagram|dies-at|passing|honor-late", re.I)
TEST_N = 50

SYSTEM = """You read one Broadway news article and list the cast changes it announces for Broadway productions.

Return only JSON: {"changes": [ ... ]}, an empty list if the article announces none. Each change:
{"person": full name as written, "role": character name or "" if not given, "show": Broadway show title,
 "change": one of "joins" (starts a run in the show), "leaves" (final performance announced), "returns",
 "extends" (a performer's own run is extended), "show_extends" (the production's run is extended: one entry with
 person "" and the new end date as last_performance), "cast_announced" (opening cast of a new production),
 "limited_run" (a run with a stated end date), "other",
 "first_performance": "YYYY-MM-DD" or "", "last_performance": "YYYY-MM-DD" or "",
 "is_limited": true/false (the article says the run is limited or names an end date),
 "certain": true/false (false if the article is vague, a date is a guess, or the show might not be on Broadway),
 "note": short reason when certain is false, else ""}

Rules:
- Only performers. Skip directors, writers, producers and ensemble or swing announcements.
- Only Broadway. Skip tours, West End, Off-Broadway and concerts, unless the same article also has a Broadway change.
- Use the article's publication date (given) to fill a missing year. Never invent a date: leave it "" if not stated.
- "Beginning March 4" means first_performance; "through June 1" or "final performance June 1" means last_performance.
- One entry per person per show. List every principal named as joining or leaving, not only the first.
- If the article's main news is not a cast change or run extension (a video, interview, concert, one-night event,
  feature or obituary), return {"changes": []} even if it names cast members."""


def clean_slug_ok(headline_slug: str) -> bool:
    return not NOISE_RE.search(headline_slug)


def article_text(html: str) -> str:
    """Article paragraphs only (no navigation, ads or comments)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # BroadwayWorld puts the story's paragraphs in div.disnep-area blocks (checked 2026-11-11)
    blocks = soup.find_all("div", class_="disnep-area")
    paras = [p.get_text(" ", strip=True) for blk in blocks for p in blk.find_all("p")]
    paras = [p for p in paras if len(p) > 40 and not p.lower().startswith(("photo", "click here", "get access"))]
    return "\n".join(paras)[:9000]


def pick_test(df: pd.DataFrame) -> pd.DataFrame:
    df = df[[clean_slug_ok(u.rsplit("/", 1)[1]) for u in df.url]].copy()
    df["show"] = df.show_ids.str.split(";").str[0]
    # Spread across shows and over time: one per show first, then fill at random
    rng = 20261111
    first = df.sample(frac=1, random_state=rng).drop_duplicates("show").head(TEST_N)
    rest = df.drop(first.index).sample(frac=1, random_state=rng).head(max(0, TEST_N - len(first)))
    return pd.concat([first, rest]).sort_values("date")


def spent_total() -> float:
    return float(pd.read_csv(LEDGER).usd.sum()) if LEDGER.exists() else 0.0


def record(usage, usd: float):
    import csv
    from datetime import datetime
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), "star_history_test", MODEL, 1,
                                usage.input_tokens, usage.cache_creation_input_tokens or 0,
                                usage.cache_read_input_tokens or 0, usage.output_tokens, f"{usd:.6f}"])


def test():
    import json
    import anthropic
    from dotenv import load_dotenv
    cand = pd.read_csv(CANDIDATES)
    log.info("%d headlines, %d after dropping video/photo/review/recording/tour noise", len(cand),
             sum(clean_slug_ok(u.rsplit("/", 1)[1]) for u in cand.url))
    pick = pick_test(cand)
    ARTICLES.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    for r in pick.itertuples():
        path = ARTICLES / f"{r.url.rsplit('/', 1)[1][:150]}.txt"
        if not path.exists():
            time.sleep(5)
            resp = s.get(r.url, timeout=60)
            if resp.status_code != 200:
                log.warning("HTTP %s for %s", resp.status_code, r.url)
                continue
            path.write_text(article_text(resp.text), encoding="utf-8")
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic(max_retries=4)
    stop_at = SPENT_BEFORE_STAR_HISTORY + STAR_HISTORY_CAP
    done = set()
    if TEST_OUT.exists():
        done = {json.loads(x)["url"] for x in TEST_OUT.read_text(encoding="utf-8").splitlines() if x.strip()}
    run_usd = 0.0
    for r in pick.itertuples():
        if r.url in done:
            continue
        path = ARTICLES / f"{r.url.rsplit('/', 1)[1][:150]}.txt"
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            continue
        if spent_total() + 0.01 >= stop_at:
            log.warning("stopping: the next call could pass the $%.2f star-history cap", STAR_HISTORY_CAP)
            break
        msg = client.messages.create(
            model=MODEL, max_tokens=4000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": f"Published: {r.date}\nHeadline: {r.headline}\n\n{path.read_text(encoding='utf-8')}"}],
            thinking={"type": "disabled"}, output_config={"effort": "low"},
        )
        usd = (msg.usage.input_tokens * PRICE["input"]
               + (msg.usage.cache_creation_input_tokens or 0) * PRICE["cache_write"]
               + (msg.usage.cache_read_input_tokens or 0) * PRICE["cache_read"]
               + msg.usage.output_tokens * PRICE["output"])
        record(msg.usage, usd)
        run_usd += usd
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        m = re.search(r"\{.*\}", text, re.S)
        try:
            changes = json.loads(m.group(0))["changes"] if m else None
        except (ValueError, KeyError):
            changes = None
        with TEST_OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"url": r.url, "date": r.date, "headline": r.headline, "show_hint": r.show,
                                "changes": changes, "raw": None if changes is not None else text}) + "\n")
    log.info("test run spent $%.4f; project total $%.4f (star-history stop at $%.2f)", run_usd, spent_total(), stop_at)
    write_review()


def write_review():
    """One row per extracted change (or one row per article with none), for Rachel to review."""
    import json
    rows = []
    for line in TEST_OUT.read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        if not a["changes"]:
            rows.append({"date": a["date"], "headline": a["headline"], "url": a["url"], "person": "", "role": "",
                         "show": "", "change": "none found" if a["changes"] == [] else "unreadable answer",
                         "first_performance": "", "last_performance": "", "is_limited": "", "certain": "",
                         "note": "", "flag": "check" if a["changes"] is None else ""})
        for c in a["changes"] or []:
            flag = "check" if (not c.get("certain") or c.get("change") == "other") else ""
            rows.append({"date": a["date"], "headline": a["headline"], "url": a["url"],
                         **{k: c.get(k, "") for k in ["person", "role", "show", "change", "first_performance",
                                                      "last_performance", "is_limited", "certain", "note"]},
                         "flag": flag})
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for col in ["claude_prefill", "rachel_ok", "rachel_fix"]:
        df[col] = ""
    df.to_csv(REVIEW, index=False)
    log.info("wrote %s: %d rows from %d articles, %d flagged", REVIEW.name, len(df), df.url.nunique(),
             (df.flag == "check").sum())


# ---------- Wikipedia cast and replacement sections (C2's first source) ----------
WIKI_SECTIONS = ROOT / "data" / "interim" / "wiki_cast_sections.jsonl"
CAST_HEAD_RE = re.compile(r"cast|replacement|casting|principal", re.I)


def wiki():
    """Each show article's cast-related sections, as wikitext (CC BY-SA, through the official API). Only cached and
    measured here; reading them into stints happens with the casting news, after Rachel's review of the test."""
    import json
    from broadway_rush.scrapers import wikimedia
    titles = pd.read_csv(ROOT / "registry" / "show_wiki_titles.csv", dtype=str, keep_default_na=False)
    titles = titles[titles.wiki_title != ""]
    client = wikimedia.Client()
    cache = ROOT / "data" / "raw" / "wikimedia" / "wikitext"
    cache.mkdir(parents=True, exist_ok=True)
    out = []
    for r in titles.itertuples():
        path = cache / f"{wikimedia.safe(r.wiki_title)}.json"
        if not path.exists():
            j = client.get(wikimedia.API, {"action": "parse", "page": r.wiki_title, "prop": "wikitext", "format": "json",
                                           "formatversion": 2, "redirects": 1})
            path.write_text(json.dumps(j or {}), encoding="utf-8")
        text = (json.loads(path.read_text(encoding="utf-8")).get("parse") or {}).get("wikitext", "")
        parts = re.split(r"(?m)^(={2,4}[^=\n]+={2,4})\s*$", text)
        keep = []
        for i in range(1, len(parts) - 1, 2):
            if CAST_HEAD_RE.search(parts[i]):
                keep.append(parts[i].strip("= ") + "\n" + parts[i + 1].strip())
        body = "\n\n".join(keep)
        out.append({"show_id": r.show_id, "wiki_title": r.wiki_title, "sections": [k.split("\n", 1)[0] for k in keep],
                    "chars": len(body), "people_links": len(re.findall(r"\[\[[^\]|#]+(?:\|[^\]]+)?\]\]", body)),
                    "text": body})
    WIKI_SECTIONS.write_text("\n".join(json.dumps(x) for x in out), encoding="utf-8")
    log.info("wrote %s: %d shows, %d with a cast section, %d characters in all; %d requests, %d refused",
             WIKI_SECTIONS.name, len(out), sum(bool(x["sections"]) for x in out), sum(x["chars"] for x in out),
             client.n, client.refused)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["candidates", "test", "review", "wiki"])
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout)])
    if a.step == "candidates":
        candidates()
    elif a.step == "test":
        test()
    elif a.step == "wiki":
        wiki()
    else:
        write_review()


if __name__ == "__main__":
    main()

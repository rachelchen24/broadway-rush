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


def write_review(src: Path = TEST_OUT, dest: Path = REVIEW):
    """One row per extracted change (or one row per article with none), for Rachel to review."""
    import json
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
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
    dest.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for col in ["claude_prefill", "rachel_ok", "rachel_fix"]:
        df[col] = ""
    df.to_csv(dest, index=False)
    log.info("wrote %s: %d rows from %d articles, %d flagged", dest.name, len(df), df.url.nunique(),
             (df.flag == "check").sum())


# ---------- Full run (approved by Rachel 2026-11-11: one pass, batch service, $2.50 star-history cap) ----------
FULL_OUT = ROOT / "data" / "interim" / "casting_extractions.jsonl"
FULL_REVIEW = ROOT / "data" / "labels" / "casting_review.csv"
BATCH_ID = ROOT / "data" / "interim" / "casting_batch_id.txt"
BATCH_DISCOUNT = 0.5
WIKI_SYSTEM = """You read the cast sections of one English Wikipedia article about a stage show (wikitext).
List the Broadway performers' runs it states, using the same JSON as below.
""" + SYSTEM.split("\n", 1)[1].replace(
    "- Use the article's publication date (given) to fill a missing year.",
    "- Only runs with a stated date or year from 2024 on. Skip the original cast unless it opened in 2024 or later.\n"
    "- Wikitext links look like [[Name]] or [[Page|Name]]: use the shown name.")


def _path(url: str) -> Path:
    return ARTICLES / f"{url.rsplit('/', 1)[1][:150]}.txt"


def _usd(u, discount=1.0) -> float:
    return discount * (u.input_tokens * PRICE["input"] + (u.cache_creation_input_tokens or 0) * PRICE["cache_write"]
                       + (u.cache_read_input_tokens or 0) * PRICE["cache_read"] + u.output_tokens * PRICE["output"])


def _parse(text: str):
    import json
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0))["changes"] if m else None
    except (ValueError, KeyError):
        return None


def fetch_all():
    """Every candidate article that passes the headline filter, 5 s apart; cached ones are skipped (resumable)."""
    cand = pd.read_csv(CANDIDATES)
    cand = cand[[clean_slug_ok(u.rsplit("/", 1)[1]) for u in cand.url]]
    todo = [u for u in cand.url if not _path(u).exists()]
    log.info("%d candidates, %d to fetch (about %d min)", len(cand), len(todo), len(todo) * 5.5 // 60)
    ARTICLES.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    bad = 0
    for i, url in enumerate(todo, 1):
        time.sleep(5)
        try:
            resp = s.get(url, timeout=60)
        except requests.RequestException as e:
            log.warning("%s for %s", type(e).__name__, url)
            bad += 1
            continue
        if resp.status_code != 200:
            log.warning("HTTP %s for %s", resp.status_code, url)
            bad += 1
            if resp.status_code in (403, 429):
                log.warning("refused: stopping fetches here (re-run later to resume)")
                break
            continue
        _path(url).write_text(article_text(resp.text), encoding="utf-8")
        if i % 50 == 0:
            log.info("fetched %d of %d", i, len(todo))
    log.info("fetch done: %d failed", bad)
    return cand


def full():
    import json
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic(max_retries=4)
    stop_at = SPENT_BEFORE_STAR_HISTORY + STAR_HISTORY_CAP
    if not BATCH_ID.exists():
        cand = fetch_all()
        reqs, meta = [], {}
        for i, r in enumerate(cand.itertuples()):
            text = _path(r.url).read_text(encoding="utf-8").strip() if _path(r.url).exists() else ""
            if not text:
                continue
            cid = f"a{i:05d}"
            meta[cid] = {"source": "broadwayworld", "url": r.url, "date": r.date, "headline": r.headline,
                         "show_hint": r.show_ids.split(";")[0]}
            reqs.append((cid, SYSTEM, f"Published: {r.date}\nHeadline: {r.headline}\n\n{text}"))
        for i, line in enumerate(WIKI_SECTIONS.read_text(encoding="utf-8").splitlines()):
            w = json.loads(line)
            if not w["text"].strip():
                continue
            cid = f"w{i:04d}"
            meta[cid] = {"source": "wikipedia", "url": f"https://en.wikipedia.org/wiki/{w['wiki_title']}",
                         "date": "", "headline": w["wiki_title"], "show_hint": w["show_id"]}
            reqs.append((cid, WIKI_SYSTEM, f"Article: {w['wiki_title']}\n\n{w['text'][:24000]}"))
        # Rough upper estimate before spending: 3.5 characters a token, 900 system tokens, 400 out, no caching
        est = BATCH_DISCOUNT * sum((len(sy) + len(u)) / 3.5 * PRICE["input"] + 400 * PRICE["output"] for _, sy, u in reqs)
        log.info("%d requests, estimated $%.3f; spent %.4f, stop at %.2f", len(reqs), est, spent_total(), stop_at)
        if spent_total() + est >= stop_at:
            log.warning("stopping: the estimate would pass the $%.2f star-history cap", STAR_HISTORY_CAP)
            return
        (FULL_OUT.parent / "casting_batch_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        batch = client.messages.batches.create(requests=[{"custom_id": cid, "params": {
            "model": MODEL, "max_tokens": 4000,
            "system": [{"type": "text", "text": sy, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": u}],
            "thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}} for cid, sy, u in reqs])
        BATCH_ID.write_text(batch.id, encoding="utf-8")
        log.info("submitted batch %s", batch.id)
    bid = BATCH_ID.read_text(encoding="utf-8").strip()
    meta = json.loads((FULL_OUT.parent / "casting_batch_meta.json").read_text(encoding="utf-8"))
    while (b := client.messages.batches.retrieve(bid)).processing_status != "ended":
        log.info("batch %s: %s", bid, b.request_counts)
        time.sleep(60)
    import csv
    from datetime import datetime
    run_usd, failed, out = 0.0, 0, []
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for res in client.messages.batches.results(bid):
            if res.result.type != "succeeded":
                failed += 1
                continue
            msg = res.result.message
            usd = _usd(msg.usage, BATCH_DISCOUNT)
            run_usd += usd
            w.writerow([datetime.now().isoformat(timespec="seconds"), "star_history_full", MODEL, 1,
                        msg.usage.input_tokens, msg.usage.cache_creation_input_tokens or 0,
                        msg.usage.cache_read_input_tokens or 0, msg.usage.output_tokens, f"{usd:.6f}"])
            text = "".join(bl.text for bl in msg.content if bl.type == "text").strip()
            changes = _parse(text)
            out.append({**meta[res.custom_id], "id": res.custom_id, "changes": changes,
                        "raw": None if changes is not None else text})
    FULL_OUT.write_text("\n".join(json.dumps(x) for x in sorted(out, key=lambda x: x["id"])), encoding="utf-8")
    BATCH_ID.rename(BATCH_ID.with_suffix(".done.txt"))
    log.info("full run: %d results, %d failed, $%.4f; project total $%.4f", len(out), failed, run_usd, spent_total())
    write_review(FULL_OUT, FULL_REVIEW)


# ---------- Stints: one row per person per show, from the extractions ----------
STINTS = ROOT / "data" / "interim" / "star_stints.csv"
SHOW_ENDS = ROOT / "data" / "interim" / "show_end_dates.csv"
STARTS = {"joins", "returns", "cast_announced", "limited_run"}
ENDS = {"leaves", "extends", "limited_run"}
CAST_LISTED = "2026-11-06"  # the Playbill cast pages behind registry/stars.csv were cached this day


def person_key(name: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z ]", "", re.sub(r"[-.]", " ", s)).split())


def stints(src: Path = FULL_OUT):
    """Join and leave dates per person per show (all shows, closed ones too) -> star_stints.csv; production end
    dates from show extensions -> show_end_dates.csv; blank date columns in registry/stars.csv filled from it
    (Rachel's edits are never overwritten)."""
    import json
    from broadway_rush.catalog import lookup, name_keys
    shows = pd.read_csv(ROOT / "data" / "processed" / "shows.csv")
    keys = name_keys(shows)
    last_week = shows.set_index("show_id").last_week.to_dict()
    rows, ends, unmatched = [], [], 0
    for line in src.read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        for c in a["changes"] or []:
            ids, _ = lookup(c.get("show", ""), keys)
            if not ids:
                unmatched += 1
                continue
            # Revivals share a name: the article's own show first, else the production that ran latest
            sid = a["show_hint"] if a["show_hint"] in ids else max(ids, key=lambda s: str(last_week.get(s, "")))
            ch = c.get("change", "")
            if ch == "show_extends" or not c.get("person"):
                if ch == "show_extends" and c.get("last_performance"):
                    ends.append({"show_id": sid, "last_performance": c["last_performance"], "announced": a["date"],
                                 "url": a["url"]})
                continue
            rows.append({"show_id": sid, "person": c["person"], "key": person_key(c["person"]),
                         "role": c.get("role", ""), "change": ch, "first": c.get("first_performance", "") or "",
                         "last": c.get("last_performance", "") or "", "announced": a["date"] or "",
                         "source": a.get("source", "broadwayworld"), "certain": bool(c.get("certain")),
                         "url": a["url"]})
    ch = pd.DataFrame(rows)
    out = []
    for (sid, key), g in ch.groupby(["show_id", "key"]):
        st = g[g.change.isin(STARTS)]
        # A limited return ("returns March 8 through March 29") ends a run too
        en = g[g.change.isin(ENDS | {"returns"}) & (g["last"] != "")]
        firsts = st[st["first"] != ""]["first"]
        news = st[(st.announced != "")]
        latest_start = firsts.max() if len(firsts) else ""
        last_row = en.sort_values(["last", "announced"]).iloc[-1] if len(en) else None
        # Left and came back later with no end date given: the latest run is still open
        if last_row is not None and latest_start and last_row["last"] < latest_start:
            last_row = None
        out.append({"show_id": sid, "person": g.person.iloc[0], "key": key,
                    "role": next((r for r in g.role if r), ""),
                    # The first run's dates set the "famous before joining" window; latest_start is the current run
                    "casting_announced": news.announced.min() if len(news) else "",
                    "first_performance": firsts.min() if len(firsts) else "",
                    "latest_start": latest_start,
                    "last_performance": last_row["last"] if last_row is not None else "",
                    "last_announced": last_row["announced"] if last_row is not None else "",
                    "is_limited": bool((g.change == "limited_run").any()),
                    "uncertain": not g.certain.all(), "n_sources": g.url.nunique(),
                    "sources": ";".join(sorted(g.url.unique()))[:2000]})
    out = pd.DataFrame(out).sort_values(["show_id", "first_performance", "person"])
    out.to_csv(STINTS, index=False)
    e = pd.DataFrame(ends, columns=["show_id", "last_performance", "announced", "url"])
    if len(e):
        e = e.sort_values(["show_id", "announced", "last_performance"]).groupby("show_id").tail(1)
    e.to_csv(SHOW_ENDS, index=False)
    log.info("%d changes (%d unmatched shows) -> %d stints in %d shows; %d with a join date, %d with a leave date; "
             "%d show end dates", len(ch), unmatched, len(out), out.show_id.nunique(),
             (out.first_performance != "").sum(), (out.last_performance != "").sum(), len(e))
    # Fill the stars list's blank dates
    stars_path = ROOT / "registry" / "stars.csv"
    s = pd.read_csv(stars_path, dtype=str, keep_default_na=False)
    by = {(r.show_id, r.key): r for r in out.itertuples()}
    filled = 0
    for i, r in s.iterrows():
        m = by.get((r.show_id, person_key(r.person)))
        if m is None:
            continue
        # Everyone in stars.csv was in Playbill's current cast on CAST_LISTED, so a leave date before that belongs
        # to an earlier run (Ryan McCartan: left Mar 29, 2026, back in the role by Oct 2026)
        earlier = isinstance(m.last_performance, str) and m.last_performance and m.last_performance < CAST_LISTED
        if earlier and "earlier run ended" not in r.review_note:
            s.loc[i, "review_note"] = (r.review_note + "; " if r.review_note else "") + \
                f"earlier run ended {m.last_performance}; in the current cast on {CAST_LISTED}"
        for col in ["casting_announced", "first_performance", "last_performance", "last_announced"]:
            v = getattr(m, col)
            if earlier and col in ("last_performance", "last_announced"):
                continue
            if not r[col] and isinstance(v, str) and v:
                s.loc[i, col] = v
                filled += 1
        if "casting news" not in r.source:
            s.loc[i, "source"] = r.source + "; casting news (BroadwayWorld, Wikipedia), read by Claude Haiku"
    s.to_csv(stars_path, index=False)
    log.info("stars.csv: %d dates filled for %d of %d people", filled,
             sum((r.show_id, person_key(r.person)) in by for r in s.itertuples()), len(s))


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
    ap.add_argument("step", choices=["candidates", "test", "review", "wiki", "full", "stints"])
    a, _ = ap.parse_known_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout)])
    if a.step == "candidates":
        candidates()
    elif a.step == "test":
        test()
    elif a.step == "stints":
        stints(TEST_OUT if "--test" in sys.argv else FULL_OUT)
    elif a.step == "full":
        full()
    elif a.step == "wiki":
        wiki()
    else:
        write_review()


if __name__ == "__main__":
    main()

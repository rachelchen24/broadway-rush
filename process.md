# Broadway Rush — Process Log

What was built, how, and why, step by step. Updated as coding happens, so it's easy to see what was done (and what was tried and dropped).

**Entry format:**
```
## YYYY-MM-DD — <what was worked on>
**Did:** what was built or changed (files, scripts, data)
**Why:** the reasoning / decision behind it
**Result:** numbers, outputs, what worked
**Didn't work / dropped:** dead ends and why
**Next:** what comes after
```

---

## 2026-10-19 — Planning (no code)
**Did:** wrote `SPEC.md` covering the concept, UI, data sources, labels, models, scraping plan and risks.
**Why:** check feasibility before building anything.
**Result / findings:**
- reddit.com blocks unauthenticated API calls (403). The Arctic Shift archive works without credentials.
- r/Broadway has daily "Broadway Rush Community Reporting Threads" back to June 2024 (~850 threads). This is the main label source.
- No historical record of online seat availability exists, so snapshots have to start going forward. Weekly grosses (capacity %, avg paid admission) are the historical proxy.
- Most Reddit labels are bounds ("8th in line, got tickets"), not exact counts, so an interval-censored model is needed.
- Scrape on a schedule, never on click: estimates are ~5–15 min per date for all shows and sites, ~30–90 min for the week.

**Next:** pick the tech stack, then start with the data pipeline (Reddit scrape → LLM extraction pilot on ~100 comments).

## 2026-10-19/20 — Step 1a: Reddit posts via Arctic Shift
**Did:**
- Project skeleton: `pyproject.toml`, `.venv` (Python 3.14), package `src/broadway_rush/`, `registry/sources.csv` (SPEC §3.11; first rows = reddit.com and Arctic Shift). `.gitignore` now covers `.venv/`, `.env`, `data/raw/`.
- `broadway_rush/http.py`: shared polite client (≥1 s between requests; on rate-limit waits for the server's `x-ratelimit-reset`, else exponential backoff; up to 8 retries).
- `broadway_rush/scrapers/reddit.py` with three phases: `posts`, `comments`, `summary`. Run with `.venv\Scripts\python -m broadway_rush.scrapers.reddit <phase>`.
  - Daily threads = every r/Broadway post by u/BroadwayRushReport. `thread_date` is parsed from the title (handles "9/23" with no year; falls back to the post date if the title date is >3 days off).
  - Keyword posts = date scan of r/Broadway, r/musicals, r/AskNYC, r/nyc from 2024-06-01, with whole-word regexes matched locally in title + body (`matched_keywords`, `matched_in`).
  - `fetch_comments` flag: always for bot threads. For keyword posts, only if the match is in the title or the body match isn't just "line"; in r/nyc and r/AskNYC the post must also look theater-related.
  - Resumable: a cursor per subreddit and posts.csv saved every 10 pages. Comments are appended per thread, and finished threads are logged in `_state/threads_done.csv` (threads <72 h old are re-fetched next run).

**Why:** Reddit's own API needs OAuth (403 unauthenticated). Arctic Shift is a public archive with a JSON API.

**Result:**
- `data/raw/posts.csv`: 12,123 posts. 790 daily threads (2024-06-14 → 2026-10-20), 1 other bot post (Ticket Availability List), 11,332 keyword posts.
- About 251k posts scanned (Broadway 74.5k, musicals 29.7k, AskNYC 91.7k, nyc 54.7k) in ~9 h overnight with 3,111 requests and 593 rate-limit waits, all recovered.
- Keyword posts per keyword: rush 3,733 · line 4,596 · lottery 3,033 · box office 1,774 · TodayTix 776 · digital rush 306 · standing room 257 · SRO 161.
- 7,761 posts queued for comments (750 skipped: old with 0 comments), ~124k comments expected, about 5× SPEC §5.5's assumption. Step 2 needs a rush-keyword pre-filter before Haiku.

**Didn't work / dropped:**
- **Title search** (`/posts/search?title=...`): it returned "Timeout. Maybe slow down a bit" on almost every call, even after long pauses, while author and plain date queries worked. Replaced by full date scans + local regex, which also catches keywords in post bodies.
- **The "Timeout" error is sent with HTTP 422**, not 429. The first client checked the status code first, didn't treat it as a rate limit and gave up. Fixed by reading the JSON error body first.
- **Splitting slow queries into smaller date windows** didn't help, because the problem was the rate limit, not the size of the query. The real limit is about 10 requests/min (`x-ratelimit-reset` header), so the fix was waiting for the reset instead of short backoffs.
- **Matching daily threads on "Reporting Thread" only** missed 177 of the bot's daily posts ("Broadway Rush Report 1/14/25", "Monday 11/24/25 rush report - 12 shows"). Now: any bot post except the Availability List.

**Next:** comments phase (running; ~35 h at ~3.5 posts/min, daily threads first, ~4 h). Then summary stats → step 2 (labeling schema, ~100-comment hand-label sheet, Haiku pilot).

## 2026-10-20 → 10-22: Step 2: labeling schema, labels, Haiku pilot
**Did:**
- `docs/labeling-schema.md`: one row per **observation**, with kind `line_count` / `attempt` / `supply` (or `none`). Line counts turned out to be the most common report type ("25 in line at 8:45"), so they get their own kind. Includes the rules for common cases (own arrival = 1 attempt; someone else's arrival = line_count; replies only get what they say themselves).
- `broadway_rush/labeling/make_sheet.py` → `data/labels/hand_labels.xlsx` (Excel with dropdowns): 70 report-like + 30 random daily-thread comments, seed 42. Which group each came from is hidden from the labeler (`sample_manifest.csv`).
- **Labels:** Claude pre-labeled all 100 (→ 138 rows: 38 none, 46 line_count, 44 attempt, 10 supply), with 14 uncertain rows highlighted for Rachel's review. `data/labels/claude_prelabels.py` keeps them.
- `broadway_rush/extraction/`: `prompt.py` (instructions + field spec), `run.py` (pilot runner, spend ledger `data/interim/llm_spend.csv`, hard stop $8, cost projection), `score.py` (report-vs-none, observation precision/recall, per-field accuracy, errors CSV).
- `http.py`: survives Wi-Fi drops and laptop sleep (waits up to 3 h), and server outages (up to 30 min per request). The comments phase skips a post that keeps failing and retries it on the next run.

**Why:** the extraction becomes the training labels, so it has to be measured before the full run.

**Result (Haiku 5.5, effort low, 10 comments per request, cached instructions):**
| Run | Report vs none | Obs. precision | Obs. recall | Key fields (show/time/count/arrival/position/outcome) | $ / 1k comments |
|---|---|---|---|---|---|
| v1, thinking on | 83% | 67% | 90% | 88/87/91/92/92/83% | $0.111 |
| v1, thinking off | 80% | 57% | 93% | 92/95/96/83/85/74% | $0.128 |
| **v2, thinking on** | **90%** | **80%** | 85% | **93/91/95/96/92/82%** | $0.116 |
- Thinking **off** cost more (it over-extracted, so more output) and was less precise. Keep thinking on at effort low.
- Full-run projection (Batches API, half price): daily threads ≈ $0.54, all sources after the keyword pre-filter (≈45.6k comments) ≈ $2.64. Pilot spend so far: $0.035.
- 0 bad JSON / 0 retries across 300 comments.

**Didn't work / dropped:**
- **Structured outputs** (`output_config.format`): the API rejected our 25-field schema three ways ("too many union-typed parameters" with 23 nullable fields, limit 16; then "Schema is too complex" with optional fields). Rejected requests aren't billed. Switched to describing the JSON in the prompt and validating it in code (`validate()`: drops unknown fields and invalid values, normalizes "8:45" → "08:45", one retry on unparseable JSON).
- v1 prompt's main errors: extracting data from the **parent** comment (most of the 44 extra observations), `rush_type` "unknown" instead of "general", and guessing `tickets`. Fixed in v2.

**Caveat:** v2 was tuned on the same 100 comments it's scored on, so its numbers are optimistic. Report final accuracy on a fresh held-out sample.

**Held-out test (2026-10-22):** Rachel reviewed the 14 flagged rows (7 comments changed, kept as-is). Built `data/labels/holdout.xlsx`: 50 new comments (35 report-like + 15 random, seed 7, excluding the first 100), pre-labeled by Claude **before** running the model (`claude_prelabels_holdout.py`). v2 on held-out ($0.006):
| Set | Report vs none | Obs. precision / recall | show / time / count / arrival / position / outcome |
|---|---|---|---|
| Tuning (100, reviewed) | 90% | 80% / 84% | 93 / 89 / 93 / 90 / 79 / 74% |
| **Held-out (50)** | **94%** | **77% / 87%** | 89 / 83 / 95 / 88 / 85 / 90% |
- Held-out ≈ tuning set, so the prompt wasn't overfit.
- Scorer fixes found along the way: "Sunset Blvd." = "Sunset Boulevard"; the row matcher now also uses `perf`, so it doesn't pair the "last evening ticket" row with the matinee row.
- New failure mode: **leakage between comments in a batch**. Haiku named "Schmigadoon!" for a comment that never mentions it, because another comment in the same 10-comment request did. Added a prompt rule ("each comment stands alone").
- Remaining real errors: unexpanded abbreviations ("EBT"), "thought I was 10th… ended up 14th" → 10, using the parent for the show inconsistently.

**Next:** the full run via the Batches API (step 3) once the scraper finishes, then a structured `reports` table.

## 2026-10-22: Step 3: full extraction → reports table
**Did:**
- `broadway_rush/extraction/batch.py`: `full [--dry-run] [--limit N]` (submit every not-yet-extracted, keyword-filtered comment as one Message Batch, 10 comments per request, shuffled so a request's comments come from different threads; refuses if spent + estimate × 1.5 > $8), `collect` (poll, validate, append to `data/interim/extractions.jsonl`, log real cost), `reports` (→ `data/processed/reports.csv`, one row per observation joined with comment metadata). Resumable and incremental: an extracted comment is never sent again.
- Test batch of 20 comments first: the path worked, but 1 of 2 chunks failed on an unquoted enum (`"count_qual": approx`). Added a JSON repair step (quote bare words, re-parse).
- Submitted the full batch while the scraper was still finishing (the new comments go in a follow-up run).

**Result:**
- 46,771 comments / 4,678 requests, finished in ~10 min. **Cost $1.30** (estimate was $3.00; batch requests got more cache hits than the sync pilot). Project LLM total: **$1.34**.
- 4,676 requests ok, 2 failed (retried next run); **228 responses needed the JSON repair**. Without it about 5% of requests would have been lost.
- **17,926 observations from 10,018 comments**: 8,806 line_count (8,567 with count + time), 6,441 attempt, 2,679 supply (1,088 with a stated count). 70% have a show name.
- Every month from June 2024 → Oct 2026; peak May–Jul 2025 (~1,100/month).
- Attempt outcomes: got_rush 3,251 · unknown 2,528 · sro_only 335 · sold_out_before_me 155 · left 77 · full_price_only 33. That's the selection bias the SPEC predicted: people post their wins.

**Issues for later:**
- Show names aren't canonical yet: 346 distinct ("Outsiders" / "The Outsiders", "Oh Mary" / "Oh, Mary!", "Mincemeat"). → the show catalog in step 4.
- `perf_date` isn't validated (one "2025-00-…"). Validate dates when building model tables.

**Next:** re-run `full` after the scraper finishes (new comments + 2 failed chunks; done, see the wrap-up below). Then step 4 (weekly grosses + rush policies + show catalog), after checking the sources' robots.txt/ToS.

---

## Step 1 + 3 wrap-up: scrape finished, top-up extraction (2026-10-22)

**Did:**
- The comments scraper finished at 13:53, before a computer restart, so nothing was lost: the last run added +28,909 comments (1,484 requests, 0 posts skipped).
- Ran `batch full` on everything not yet extracted: 7,393 comments (7,391 new keyword-post comments + the 2 daily-thread comments from last run's failed chunks) in 740 requests. Then `collect` and `reports`.

**Why:** the first full batch was sent while the scraper was still running, so the comments it fetched afterwards still needed extracting.

**Result:**
- **Reddit raw data, final:** 12,123 posts (790 daily threads 2024-06-14 → 2026-10-20, 11,332 keyword posts, 1 other bot post) → **139,584 comments**, no duplicate IDs.
- Batch: 739/740 requests ok, finished in under an hour. **Cost $0.13** (estimate $0.47). Validation: 1 JSON repair, 2 unknown fields, 2 bad values dropped. **Project LLM total: $1.47.**
- **`reports.csv`: 18,262 observations from 10,301 comments** (43,835 extracted comments had no report): 8,845 line_count · 6,643 attempt · 2,774 supply (1,119 with a stated count). By source: daily_thread 13,021 · keyword_match 5,235 · bot_post 6. 70% have a show name; 358 distinct show strings.
- Keyword posts added few observations (+336) compared with their comment count. Almost all the useful data is in the daily threads, as expected.
- Attempt outcomes: got_rush 3,382 · unknown 2,577 · sro_only 340 · sold_out_before_me 160 · left 83 · full_price_only 34.

**Didn't work / left as-is:** 1 request (10 keyword-post comments) failed. Not worth retrying for now; the next `batch full` will pick it up automatically.

**Next:** step 4, waiting on Rachel's go-ahead.

---

## ▶ Open items (as of 2026-10-22, after the top-up extraction)
1. **Steps 1–3 are done.** The Reddit scrape is complete and all comments are extracted except 10 (1 failed request; `batch full` retries it).
2. **Step 4 done** (4a source check, 4b grosses + policies, 4c show catalog, 4d policy history + website scope decision). Weekly refresh: `.venv\Scripts\python -m broadway_rush.scrapers.playbill grosses`, `... playbill policies`, `... broadwayworld grosses`, then `.venv\Scripts\python -m broadway_rush.catalog build`. After any `batch reports`, re-run `catalog build` (it adds show_id to reports.csv). **Step 5: Rachel is starting a new chat to build the first model, the simple combo (SPEC §5.2a; last entry in this file).**
2b. **Step 6 started early** (ticket-site rules + TKTS scraper; see the step 6 entry). TKTS + Ticketmaster scrapers built, daily job working (manual run succeeded 2026-11-05; first scheduled run still to confirm). Then cast and closing news, then step 5 (model). The data refresh plan changed on 2026-11-02 (SPEC §6; entry below).
3. **Notes for future sessions:**
   - LLM spend ledger: `data/interim/llm_spend.csv`; hard stop $8, $1.47 spent.
   - To refresh Reddit later: `.venv\Scripts\python -m broadway_rush.scrapers.reddit posts`, then `comments` (resumable; run one copy at a time), then `batch full` → `collect` → `reports`.
   - API key lives in `.env` (git-ignored); the variable name must be `ANTHROPIC_API_KEY` (underscores).
   - Never run `data/labels/claude_prelabels*.py` again: they overwrite the reviewed label sheets (the holdout one refuses; the first one does not).

---

## Step 4a: source check for grosses, policies, show catalog (2026-10-22)

**Did:**
- Read robots.txt for Playbill, BroadwayWorld, IBDB and the Broadway League, then searched each site for terms-of-use language about scraping/automated access (a handful of requests, ≥2 s apart, with a descriptive user agent).
- Probed the pages we'd actually use and parsed one historical grosses week.
- Logged all four in `registry/sources.csv`. Added `beautifulsoup4` + `lxml` to `pyproject.toml` (HTML parsing).

**Result:**
| Site | robots.txt | ToS | Decision |
|---|---|---|---|
| playbill.com | `Allow: /` for everyone; Content-Signal `ai-train=no` (we don't train AI on it) | no terms page found | **scrape** (main) |
| broadwayworld.com | `Allow: /` except the grosses Excel export and `?before=/?after=` paging | no terms page found | scrape (backup) |
| ibdb.com | mostly allowed | forbids automated harvesting | **skip** |
| broadwayleague.com | none | same terms as IBDB, forbids harvesting | **skip** |

- **Grosses backfill is easy:** `playbill.com/grosses?week=2024-06-16` returns one clean table (35 shows that week): gross, potential, avg + top ticket, seats sold, theater size, perfs/previews, % capacity. ~125 weeks to June 2024 = ~125 requests.
- **Rush policies:** Playbill's policy article has structured per-show text (price, how, time, payment, ID, limit, seats, special policies). It's edited in place, so history needs archived copies.
- **Show catalog:** without IBDB/League, the grosses tables give show + theater per week (which shows were running, and when they opened/closed, to within a week).

**Didn't work:** no dedicated BroadwayWorld rush-policy page found (the old URL 404s). Playbill covers it.

**Next:** build the Playbill grosses backfill scraper (June 2024 → now, ~125 requests at ≥3 s apart, about 7 minutes).

---

## Step 4b: grosses backfill + rush policies (2026-10-22)

**Did:**
- `broadway_rush/http.py`: added `get_text()` for HTML pages (same retry/outage rules as `get_json`). Added `beautifulsoup4` + `lxml`.
- `broadway_rush/scrapers/playbill.py`:
  - `grosses`: reads the week picker, then fetches `playbill.com/grosses?week=YYYY-MM-DD` for every week-ending Sunday from 2024-06-02. 3 s between requests; raw HTML is cached in `data/raw/playbill/grosses/`.
  - `policies`: today's copy of the rush/lottery/SRO article, cached in `data/raw/playbill/policies/<date>.html`. Running it on later dates builds up a policy history.
  - `parse`: re-parses from the cache with no requests.
- `broadway_rush/scrapers/broadwayworld.py`: `grosses` does the same for `broadwayworld.com/grosses.php?week=…` (5 s between requests), and `parse` re-parses the cache.

**Why both grosses sources:** Playbill gives a stable production ID + seats per performance. BroadwayWorld adds **show type (Musical / Play)** plus last week's / last year's numbers, and it cross-checks Playbill.

**Result:**
- `data/raw/grosses_playbill.csv`: **4,024 rows, 125 weeks (2024-06-02 → 2026-10-18), 118 productions**, 24–40 shows/week. Columns: gross, avg + top ticket, seats sold, seats in theater, perfs, previews, % capacity (+ week-over-week diffs). `potential_gross` is blank everywhere (Playbill no longer publishes it). 126 requests, ~7 min.
- `data/raw/grosses_bww.csv`: **4,024 rows, 125 weeks, 119 show slugs**; Musical 2,945 · Play 955 rows. 127 requests, ~11 min.
- **Cross-check:** every week has the same show count on both sites, and weekly total gross differs by at most **0.02%**.
- `data/raw/policies_playbill.csv`: **56 policies for 28 shows** (Digital Lottery 21, General Rush 13, Digital Rush 8, Standing Room 6, Student Rush 3, plus one-offs like Harry Potter's "Friday Forty" and The Outsiders' "$30 Under 30"). 55 have a dollar price (Rocky Horror's student rush is "50% off").

**Didn't work (fixed):**
- The policy page has two `div.prose`; the parser now picks the one split by `<hr>`.
- Policy headings without "rush/lottery/SRO" in them ("The Friday Forty", "Student Tickets") were missed. A short line directly before "Price:" now also counts as a heading. Added the label variants "Seating Locations" and "Number of Lottery Tickets Available".
- BroadwayWorld's newest week returns an empty page with `?week=`; it's only served by the plain URL, so the scraper caches the landing page as that week. The scraper also checks that the page shows the requested week before caching.
- The Windows console can't print "→" in log lines (cp1252). Replaced it with "to"; the data was unaffected.

**Issues for later:**
- 6 BroadwayWorld shows have no type (Two Strangers, Oedipus, The Hills of California, 3 specials). Fill them by hand in the show catalog.
- Policy history before today needs archived copies (Internet Archive) of the Playbill article. Not checked yet.

**Next:** build the show catalog. Join Playbill production IDs ↔ BroadwayWorld slugs ↔ policy shows, and map the 358 Reddit show-name variants in `reports.csv` onto it.

---

## Step 4c: show catalog + show-name mapping (2026-10-22)

**Did:** `broadway_rush/catalog.py`:
- `build` writes **`data/processed/shows.csv`**: one row per production from the Playbill grosses. Columns: readable `show_id` (e.g. `maybe-happy-ending`), name, theater, show_type, first/last grosses week, n_weeks, seats, Playbill production_id, BroadwayWorld slug(s). Playbill ↔ BroadwayWorld are joined on week + gross, which match exactly (4,018/4,024 rows).
- It also adds `show_id` + `show_match` to `data/processed/reports.csv`, and writes `data/processed/show_names.csv` (every Reddit show string → show_id, with report counts). `review` lists what still needs a look.
- Matching steps:
  1. normalized name (lowercase, "&"/"+" → "and", drop "The", "the Musical", punctuation, apostrophes)
  2. also the part before a colon and without (parentheses)
  3. BroadwayWorld slugs
  4. the hand alias list
  5. a close spelling (difflib ≥ 0.88, only when unambiguous; marked `fuzzy`)
- **Date check:** a match only counts if the show was on Broadway on the report's date (first → last grosses week + 7 days; shows still running are open-ended). The date is the daily thread's date, or the comment's date for keyword posts. This also chooses between same-name productions and rejects Off-Broadway runs of shows that later transferred (Titanique, Cats: The Jellicle Ball).
- Hand-curated files (committed): **`registry/show_aliases.csv`** (nicknames like Mincemeat, MHE, JPITV, Dorian Gray; `-` = known non-Broadway, e.g. Off-Broadway, Shakespeare in the Park, shows that closed before June 2024) and **`registry/show_overrides.csv`** (show_type for the 6 shows BroadwayWorld left blank).

**Result:**
- **118 productions** (June 2024 → Oct 2026), all with a type.
- **12,417 of 12,797 named reports (97.0%) mapped to 107 shows.** Breakdown: exact/alias 12,348 · fuzzy 55 · date-disambiguated 15 · known non-Broadway 185 · outside the show's run 89 · unmatched 106 (mostly one-offs).
- All 28 policy shows map to the catalog.
- Coverage is uneven: 41 shows have ≥50 reports (Oh, Mary! 1,036 · The Outsiders 1,019 · Just in Time 799 · Maybe Happy Ending 722 …), 34 have <10. That's the cold-start problem the SPEC predicted.

**Checked by hand:**
- All 22 fuzzy spellings are right ("O Mary", "Sterophonic", "Bueno Vista Social Club").
- The 89 outside-run reports are comments from before previews or after closing ("I miss Sunset Boulevard"). No rush happened on those days, so excluding them is correct.

**Found:** ~15 one-off "show names" were invented by Haiku expanding acronyms ("Edward Bear Tonight", "Bad Vibes: The Sheffield Crossroads", "Back to the Vaudeville Sumptuous Carnival"). Only 1 report each, so they're left unmatched. A prompt fix for next time: keep acronyms as written.

**Order matters:** `batch reports` rewrites `reports.csv` without `show_id`, so always run `python -m broadway_rush.catalog build` after it.

**Next:** policy history from archived copies of the Playbill article (Internet Archive; check its API terms first). Then step 5 (baseline model).

---

## Step 4d: rush-policy history + "has rush changed?" (2026-10-22)

**Did:**
- Added `playbill.py policies-history`. It queries the Internet Archive's public CDX API for monthly captures of the Playbill policy article since June 2024 (29 captures), fetches each original page (`<timestamp>id_/` = no Wayback toolbar, 5 s apart, 30 requests total) and caches them next to today's snapshot. Logged the archive in `registry/sources.csv`.
- Parser fix: before spring 2026 the article body was `div.bsp-article-content`, not `div.prose`.
- Analysis (scratch script): mapped every policy row to the catalog (99.9%; only "Cult of Love" was listed after its run), grouped policy types, and tracked prices per show over time.

**Result:** `policies_playbill.csv` now has **30 snapshots (2024-06-12 → 2026-10-22), 1,954 rows**, 22–40 shows each. **Rush has been very stable:**
- **In-person general rush: median $45 in every one of the 30 months.** Of 61 shows with ≥2 snapshots, **5 changed price**: Maybe Happy Ending $40 → $49 (July 2025, after its Tony wins), Death Becomes Her $35 → $40, Boop $40 → $50, Job $39 → $47, Suffs $45 → $19 for one month (a promo) → $45.
- Digital rush and lottery drifted up slightly: median $45 → $49.
- The mix of what shows offer barely moved: ~55% of shows have in-person general rush, ~77% a lottery, ~25% digital rush, ~20% SRO, in each year.
- **3 shows switched in-person rush on/off mid-run (verified, not parsing errors):** Harry Potter dropped its $49 general rush (late 2025); & Juliet added one (summer 2025); Wicked added $45 general rush (2026).
- Box-office times only changed in wording.

**Implication:** price is nearly constant, so it won't drive the model much. **Whether a show offers in-person rush on a given date matters a lot**, and we now have that month by month.

**Also checked: is "few Reddit reports" = "low demand"?** Daily-thread reports per running week vs. average % capacity from the grosses (110 shows with ≥4 weeks):
- Overall only weakly related (rank correlation 0.21). Many quiet shows are sold out: Hamilton, Lion King, Book of Mormon, Wicked, Hadestown (≥94% capacity, ~0 reports).
- The reason: **shows without in-person rush/SRO get almost no reports** (39 shows, median 0.05/week) vs. 2.3/week for shows with it. Reddit's rush threads are about the in-person line.
- **Among in-person-rush shows the idea holds:** the 10 quietest (<0.5 reports/week) average 84.5% capacity vs. 94% for the most discussed.

**Decision (Rachel, 2026-10-22):** three groups. (1) in-person rush + enough data → full prediction; (2) in-person rush, little data → "limited data, probably easy" + policy + % capacity; (3) no in-person rush → lottery/digital info only. Recorded in SPEC §8.

**Next:** step 5 (baseline model), after Rachel's go-ahead.

---

## Step 6 (moved up): ticket-site rules check + TKTS scraper (2026-10-22)

**Why now:** ticket sites only show current inventory and prices, with no history (SPEC §3.2). Every day without snapshots is data we can't get back, so the snapshot scrapers move ahead of the model. Rachel asked me to check the rules first, then decide now vs. later.

**Rules check (robots.txt + terms for 11 sites; all logged in `registry/sources.csv`):**
| Site | Decision | Why |
|---|---|---|
| TKTS (tdf.org live board) | **scrape** | robots allows; no terms page (privacy policy only); 1 request per snapshot |
| Ticketmaster | **API only** (Rachel gets a free key) | website ToU bans automated access; the Discovery API is allowed (5,000 calls/day, 5 req/s); events/dates/price ranges, no seat counts |
| TodayTix | **hold** | ToU bans automated downloading, but its `/llms.txt` agent guide offers a read-only MCP server (`/mcp`: performances, availability, all-in seat prices) for helping a customer. Fits a user-initiated refresh better than a daily dataset; ask TodayTix before any scheduled use |
| Telecharge, Broadway Direct, Lucky Seat, SeatGeek (site + API) | skip | 403 even on robots.txt = bot protection; we never bypass it |
| StubHub, TickPick | skip | terms explicitly ban robots/scrapers |
| Vivid Seats, Gametime | skip | terms unreadable / listing pages disallowed in robots.txt |

**Implication:** there is no legal resale-price source. Price signals come from the weekly grosses (avg/top ticket), TKTS discounts, and Ticketmaster price ranges once we have a key.

**Built:** `broadway_rush/scrapers/tkts.py`
- `live`: today's board, cached as `data/raw/tkts/<UTC>-live.html`.
- `history`: Internet Archive day-captures since June 2024 (CDX), cached as `<UTC>.html`.
- `parse`: re-parse only.
- Output `data/raw/tkts.csv`: snapshot time (UTC + ET), booth (times-square / lincoln-center), section (`broadway` / `off_broadway` / `next_day_*`), board "Updated" time, show, TDF URL, % off, price min/max, performance time.
- Two page layouts: the 2026+ `div.tkts__grid` lists, and the older `div#<Booth>-<section>` tables (cells in varying order, some captures titles only), so each cell is recognized by content.

**Result:**
- Live board today: 54 rows (21 Broadway shows per booth).
- History: 145 archived days fetched (146 requests, 5 s apart, ~13 min); **117 days with a board, 2024-06-12 → 2026-10-22, ~22 Broadway shows per board**; 54 days also have % off + prices. 9,083 rows total.
- Caveats: archive captures happen at random hours (some at night, showing that day's or the next day's board); coverage is uneven (1–9 days/month, thin in early 2026). Good for a "share of days on TKTS" feature, not a daily one, until our own snapshots build up.

**Didn't work (fixed):** the first parse only read the 2026 layout (18 of 145 days); added the table-layout parser and normalized the section names.

**Waiting on Rachel:**
1. A Ticketmaster Discovery API key (developer.ticketmaster.com, free), saved in `.env` as `TICKETMASTER_API_KEY`.
2. How to run snapshots daily: Windows Task Scheduler on the laptop, or GitHub Actions (repo on GitHub).

**Ticketmaster (same day, after Rachel added the key):**
- Key check: 1 test request, HTTP 200, quota 5,000/day. Rachel first saved the line in the wrong file. Checked: no key text left in `.flake8` (that file is committed).
- What the Discovery API gives for Broadway: every performance's date/time, attraction, venue, sale status (`onsale`/`offsale`/`cancelled`/…), and sales end time. **No `priceRanges`, no seat counts** (checked the list and one event's detail).
- Safety: the key has to go in the URL, so `http.py` now hides key/token values in every error message (`redact`) and log line (`scrub`).
- Built `broadway_rush/scrapers/ticketmaster.py`:
  - `snapshot`: NYC theatre events for the next 8 days (paged, 200/page, 1 s apart), raw JSON cached in `data/raw/ticketmaster/<UTC>.json`.
  - `parse`: re-parse only. Keeps only venues that match a catalog theater (`venue_key` drops "Theatre", "- NY", …).
  - Output `data/raw/ticketmaster_events.csv`.
- First snapshot: 683 NYC theatre events → **362 Broadway performances at 40 theaters**, 4 requests, no duplicate venue+time. (Corrected 2026-11-05: this counted duplicates. Many shows are listed under two venue IDs, so the real figure is 263 performances at 29 theaters.) It also has shows too new for the grosses (Downstate, The Fantasticks). Not on Ticketmaster: Stephen Sondheim (& Juliet), Todd Haimes, Vivian Beaumont.
- Use: the next-7-days performance schedule (SPEC §3.0) and, from daily snapshots, early `offsale` as a possible sell-out signal (to test).

**Still waiting on Rachel:** Task Scheduler vs. GitHub Actions for the daily runs (TKTS `live` + Ticketmaster `snapshot`).

---

## 2026-11-02 — Planning: data refresh plan changed (no code)

**Did:** brought `SPEC.md` in line with what's built (no seat counts or resale prices from any legal source, Ticketmaster has no price ranges for Broadway, sections marked built) and recorded Rachel's new decisions. Started `claude-notes.md` (Claude's working notes) and reorganized `interview-notes.md`; both git-ignored.

**Decisions (Rachel):**
- **Weekly job:** Reddit scrape → extract new comments → grosses + policies → catalog → retrain → predictions for the next 14 days.
- **Ticket data (TKTS, Ticketmaster):** daily snapshots for now, to have training data; after launch, only when someone clicks Refresh. Reason: Rachel may not check the site every day or even every week. The old "never scrape on click" rule assumed 6–10 slow sources per performance; only two fast ones turned out to be legal (~5 requests, ~10–15 s for all shows).
- **Repo:** private for now, probably public when the project is done (for interviewers). **Website:** Vercel.

**Found:**
- `data/labels/hand_labels.xlsx` (100 full Reddit comments + parent comments) is committed despite the `data/labels/` ignore rule, and `reports.csv` has an `author` column. Both need cleaning before the repo goes public (git history included).
- No snapshots were taken Oct 23 – Nov 1 (nothing scheduled yet). Ticketmaster days are lost; TKTS can be partly backfilled from the Internet Archive.

**Next:** Rachel picks where the scheduled jobs run and where snapshot data is saved (SPEC §9), then set up the daily snapshots, then step 5.

---

## 2026-11-05 — Step 6: daily snapshot job + private data repo

**Did:**
- Rachel chose GitHub Actions plus a separate private repo, `broadway-rush-data`.
- `.github/workflows/snapshots.yml`: Ticketmaster at 7:07 am EST; TKTS at 12:07 and 6:07 pm EST. The "Run workflow" button runs both. The data repo is checked out at `data/raw`, so the scrapers needed no path changes. If one scraper fails, the other's data is still saved and the run shows as failed.
- New snapshots are gzipped (`write_gz`, `read_cached`, `cached_files` in `playbill.py`). The scrapers still read older plain files, and count one copy if both exist.
- Took today's snapshots and re-ran the TKTS archive backfill.
- Cloned the data repo next to this project, copied all snapshots in (gzipped), added a README and `.gitignore`, and staged 154 files for Rachel to commit.

**Why:** ticket sites keep no history, so each day without a snapshot is lost. A raw Ticketmaster snapshot is ~5 MB, too big to commit daily.

**Result:**
- Today's snapshots: 768 NYC theatre events from Ticketmaster (4 requests), 82 TKTS rows (1 request). Ticketmaster file 5 MB → ~450 KB gzipped. Everything staged is ~4.3 MB.
- Checked: the copies parse to the same rows as the local CSVs (TKTS 9,179 rows from 128 snapshots; Ticketmaster 773), and no API key appears in any staged file.
- The workflow file parses as valid YAML but **hasn't run on GitHub yet**. Whether TKTS accepts GitHub's machines is unknown until the first test.
- **Correction:** Ticketmaster lists many shows twice under two venue IDs. Nov 5: 411 rows → 302 unique performances at 36 theaters. Oct 22: 263 at 29, not the 362 at 40 logged earlier. Remove duplicates by theater + date + time when building model tables.
- Reddit reports are scarcer than the spec assumed: ~6–11 a day in Sep–Oct, not ~16 (SPEC §6.2 updated).

**Didn't work / dropped:** the TKTS backfill recovered little: 3 new archive captures since Oct 22, only 1 with a board (the evening of Oct 25). Ticketmaster has lost Oct 23 – Nov 4 (13 days), and TKTS has lost the same days except that one.

**Next:** Rachel commits both repos, adds the token and secrets, and runs the first test. Then catch up Reddit, grosses and policies (running) and extract the new comments with Haiku.

---

## 2026-11-05 — Deadline and plan (no code)

**Did:** set the schedule to the deadline and recorded the decision (SPEC §8).

**Why:** this is Rachel's entry in a data project competition, due 2026-11-17, and the goal is to win.

**Result:** the scope doesn't change. Schedule:
| Dates | Work |
|---|---|
| Nov 5–7 | Data: catch-up, calendar, weather, NYC permitted events, cast + closing news |
| Nov 8–11 | Model: baseline, negative binomial, Bayesian hierarchical, LightGBM, digital rush, results and with/without tables |
| Nov 12–14 | Website: day picker, tiles, details, accuracy page; then report form + email approval, Refresh + PIN |
| Nov 15 | Weekly automatic job and a full end-to-end test |
| Nov 16 | Repo cleanup, README, competition write-up |
| Nov 17 | Buffer and submit |

**Didn't work / dropped:** Claude proposed cutting six features to fit the time (cast news, permitted events, Refresh + PIN, report form, weekly job, digital rush predictions). Rachel kept them all. Time is handled through build order instead: data, model and site first, so a delay only moves an add-on.

**Next:** get the competition rules and judging criteria (SPEC §9, question 13). Finish the data stage.

---

## 2026-11-05 — Data stage: catch-up, weather, permitted events, calendar

**Did:**
- Caught up the existing sources: Playbill and BroadwayWorld grosses (through week ending Nov 1), today's rush policies, and Reddit (172 new posts, 1,493 new comments). Extracted 576 comments with Haiku, including the 10 from the earlier failed request, then rebuilt `reports.csv` and the catalog.
- Rules checks, logged in `registry/sources.csv`: Open-Meteo (free for private sites with no ads or subscriptions; CC BY 4.0, so the site must credit it) and NYC Open Data (public API, 1 s between requests; no ban found in a keyword search of nyc.gov's terms, not a full read).
- `scrapers/weather.py`, `scrapers/nyc_events.py`, `calendar_features.py`, and `registry/calendar_events.csv` (each date with its source and confidence).

**Why:** the model needs these for demand features, and all of them have history back to June 2024, so they don't depend on the daily snapshots.

**Result:**
- Haiku: **$0.02** (estimate $0.04). **Project total $1.49.** 58 of 58 requests ok, 3 needed the JSON repair.
- `reports.csv`: **18,412 observations from 10,396 comments.** 12,510 of 12,899 named reports (97.0%) map to 108 shows. Catalog: 121 productions. Grosses: 127 weeks, 4,089 rows per site, same shows every week, weekly totals within 0.018%.
- Reddit is quiet, not broken: late Oct–Nov daily threads have about 7 comments a day, and fetched counts match each thread's count.
- Weather: 886 days, no gaps. Calendar: 975 days, checked against known dates (Thanksgiving, Pride, Tonys, holidays, school breaks).
- Permits: 48,105 Manhattan events → a daily table of closures, parades and races. Thanksgiving, Pride and St. Patrick's parades land on the right days; a plain Tuesday is zero.

**Found (would have hurt the model):**
- **Zeros that mean "no data":** the permit files drop ~90% in Sept–Oct 2026 and more than a month ahead because the city hasn't published them. Those days are now marked unknown.
- **Noise:** ~157k of 212k Manhattan rows are sports permits, and parade grandstands are listed three weeks early. So the table counts only street closures, parades and races.
- **Third-party dates are often wrong:** search results gave winter recess 2024 as Dec 24; the official PDF says Dec 23. School dates came from the official calendars.
- **Modeled weather:** the Jan 25, 2026 storm reads ~7.8 in. against 11.4 reported at Central Park.
- `show_id` holds `-` for known non-Broadway reports (188 rows). Filter those out in model tables.

**Didn't work / dropped:** college breaks. NYU's calendar isn't publicly readable and only Mar 16–20, 2026 could be verified. Weather, permits and the calendar are built, but the daily job doesn't refresh them; that's the weekly job on Nov 15.

**Daily job, fixed:** the first test runs ended in "Not Found" when getting the data repo, even with token settings that looked right. The cause was never found. Switched from a token to a deploy key (`DATA_REPO_SSH_KEY`), which is tied to the one repo and doesn't expire, and tested it from the laptop first. **Manual run succeeded 2026-11-05:** commit `cc2029d` in the data repo, with Ticketmaster (302 unique performances at 36 theaters) and TKTS (81 rows). So TKTS accepts GitHub's machines. The first scheduled run hasn't happened yet.

**Next:** cast and closing news (check Playbill's `use=reference` signal first), then the model.

---

## 2026-11-05 — Step 5 planning: model options (no code)

**Did:** Rachel asked for model options to choose from, evaluated against this project, docs only. Counted what the labels actually look like (read-only, nothing saved in the project), did a dry-run package check (nothing installed), and wrote the evaluation into SPEC §5.2.

**Why:** the first model list (SPEC §5.2) named model families without checking them against the data. The choice depends on the shape of the labels, so that had to be measured first.

**Result:**
- In-person rush mapped to a show: 11,588 rows, 100 shows, 4,493 show-days.
- **The line is the strong part:** 7,973 time + count points before 10:00, on 3,397 show-days. Spread about 5.7× what a Poisson model allows.
- **The cutoff is the weak part:** 1,064 show-days, and almost all one-sided: 207 stated counts, 686 lower bound only, 81 upper bound only, 11 both, 79 sold-out time only.
- Four options, compared in SPEC §5.2: Bayesian hierarchical, boosted trees, penalized negative binomial regressions, and a mix. **I recommended Bayesian hierarchical**, with a stop rule (end of Nov 10) and a fallback that reuses the work. Rachel's choice is pending.
- First answer to the §4 question: a show's stated rush count typically swings by about half its average (13 shows with 5+ counts).

**Found (would have hurt the model):**
- **"Always yes" scores 89%.** Of 1,133 attempts with an arrival time and known outcome, 89% got a ticket. Any verdict score means little without that comparison (SPEC §5.3).
- **A last-3-months test is too thin:** only 3 stated counts and 5 negative outcomes. 12 months of rolling windows gives 80 and 52.
- **91% of rows don't say matinee or evening,** so the model has to predict per show-day.
- **1,135 in-person rows have no performance date,** only a comment date (keyword posts), and a few dates are impossible (1900, "2025-06-00").
- **Digital rush:** only 143 of 443 rows are tied to a Broadway show.
- **The spec disagrees with itself on thin shows** (SPEC §9, question 15).

**Didn't work / dropped:** a direct "got it / didn't" classifier (it would learn who posts), Poisson (too narrow), survival on clock time as its own model (134 sold-out times), LightGBM for the cutoff (it can't take bounds, so XGBoost's AFT objective fills that role in the trees option), `lifelines` (it would force pandas 3 back to 2.3).

**Not checked:** fit times and build times are estimates. No model has been installed or run. `interview-notes.md` wasn't updated, because Rachel limited this work to the spec, this log and `claude-notes.md`.

**Next:** Rachel picks a model. Then shared groundwork: model table, features as known at prediction time, rolling test windows, baseline, scoring.

---

## 2026-11-05 — New dates; combo option rescored (no code)

**Did:** Rachel corrected the dates and asked about the models, and leaned toward the combo (trees for the line, Bayesian for the cutoff). Stretched the schedule, ran two more read-only counts, and corrected the combo's scores in SPEC §5.2.

**Why:** the first dates were wrong, and thinking the combo through showed my first scoring of it was too harsh.

**Result:**
- **New dates:** complete by Nov 23, turn in Nov 24, present Dec 7. After turn-in: small tweaks only, no model changes. New schedule in SPEC §8, not yet reviewed by Rachel: model Nov 8–13, website Nov 14–19, weekly job Nov 20, cleanup and write-up Nov 21–22, buffer Nov 23.
- **Line and tickets are mostly separate questions.** On the 125 show-days with both, rank correlation is 0.09 within a show (100 days, 14 shows), 0.29 pooled, 0.24 between shows (21 shows). This also backs the combo's joining step, on thin evidence.
- **Line length tracks popularity but isn't the same thing:** 0.57 with % capacity and 0.43 with average ticket price across 38 shows. 45% of shows moved by 1.5× or more between the first and second half of their reports, so a "recent line level" input matters.
- Days with a "fewer than" label had slightly longer lines than usual for that show (log difference 0.20, vs 0.07 on days with only "at least" labels), the direction the line-vs-cutoff logic expects.
- **Recommendation changed from Option 1 to Option 4** (the combo). Rachel hasn't picked yet.

**Didn't work / dropped:** my first scoring of the combo.
- It charged the combo 10–40 minutes a fit, but that figure was for the whole Bayesian model. The cutoff alone is much smaller.
- It said the slider had the trees' problem, but the ticket range and slider come from the Bayesian cutoff.
- It said Refresh needed a tree reader on Vercel, but the weekly job can save predictions for the few cases Refresh can change.
- It overstated the busy-day loss for trees and the combo: weighting each show-day to count once handles the over-counting, and ranges calibrated on later days already include day-to-day swings.
- I had also missed a cost of Option 1: 12 test windows at 10–40 minutes each is about 2–8 hours per backtest, repeated for every with/without row.

**Not checked:** fit and build times are still estimates. Nothing has been installed or run. `interview-notes.md` and my saved memory of the old deadline weren't updated, because writes are limited to the spec, this log and `claude-notes.md`.

**Next:** Rachel decides on the combo and reviews the schedule.

---

## 2026-11-05 — Rubric received (no code)

**Did:** recorded Rachel's judging rubric in SPEC §1.1 and compared the project against it.

**Why:** the rubric decides where the remaining time should go. It had been an open question since the deadline was set.

**Result:**
- 50 points: Data Preprocessing 8, Data Processing 10, Visualization 7, Presentation 10, Results 7, Creativity 8.
- No criterion scores accuracy by itself. Data Processing asks whether the techniques make sense, whether bias and overfitting are handled, whether the technology is innovative, and whether there are mistakes.
- Charts and the presentation (17 points) aren't in the schedule yet. The spec plans only one chart.
- Nothing in the rubric directly scores the report form, Refresh or the PIN. Those stay in scope; this only affects their order, which Rachel hasn't decided.

**Didn't work / dropped:** I took Rachel's "I want to try one model now" as a go-ahead and started setting up to train. Rachel stopped me. Nothing was trained and no code was written; SciPy 1.18.1 did get installed in `.venv` (not added to `pyproject.toml`), and a throwaway environment was never created.

**Next:** Rachel picks a baseline model, and says whether this is solo or a team, whether the presentation is live or recorded, and what gets turned in on Nov 24. No building until Rachel says so.

---

## 2026-11-05 — First model chosen: the combo (no code)

**Did:** added the rubric to-do list to SPEC §1.2, recorded the first-model decision in SPEC §5.2 and §8, added the combo and final model to the results table (§5.3), and renamed the old "baseline" to "lookup table" so the two don't get confused.

**Why:** Rachel wants to see the whole site working on a first model, then decide the final one: full Bayesian or an improved combo. Rachel also plans to use the app for real show-going, so accuracy matters beyond the rubric. Rachel will take care of the rubric to-do list.

**Result:** the schedule in SPEC §8 now runs first model Nov 8–10, website Nov 11–16, final model Nov 17–19. I proposed these dates; Rachel hasn't reviewed them. Whether the combo beats full Bayesian is still untested.

**Update (same day):** Rachel said "we're going with the combo". I read that as the final model too: a leveled-up combo, no longer full Bayesian or a combo. SPEC §5.2 and §8 now say so. Full Bayesian can still appear as a comparison row.

**Next:** waiting on Rachel's plain go before any building.

---

## 2026-11-05 — Handoff before the new chat (no code)

**Did:** wrote everything from this planning chat into the docs, because Rachel is starting a new chat to build the first model. SPEC additions: rubric to-do (§1.2), how the combo works (§5.2a), training-time estimates (§5.2b), level-ups (§5.2c), answers to Rachel's questions (§5.2d), and open questions 16–19 (§9).

**Why:** a new chat only knows what's written down.

**Result:**
- **Confirmed by Rachel:** the combo for both the first and final models, because it's more fun to talk about. Level-ups stay undecided until later. Rachel will take care of the rubric to-do list.
- **Decided in this chat:** complete by Nov 23, turn in Nov 24, present Dec 7, no model changes after turn-in. Worth-it bar is black (stay home), gray (Maybe), gold (GO).
- **Proposed, not reviewed by Rachel:** the dates in SPEC §8, and the suggested order of level-ups.
- **Found while planning the build, and new in the spec:** the verdict as first written is circular, because the chance at the recommended time comes out about the same for every show (§5, §9 question 16). Line times should be measured from each show's opening, since many box offices open at noon on Sundays.
- **Moved the stop rule** to the end of Nov 10, to match the new first-model slot.

**Not checked:** every training time, build time and accuracy expectation in SPEC §5.2–§5.2d is an estimate. Nothing has been trained, and lightgbm, numpyro and jax haven't been installed or run on this setup. Only SciPy is installed.

**Also updated:** `interview-notes.md`, at Rachel's request: the model plan and new findings (items 17–24), the dates, and what to emphasize. I also marked two likely-question answers as planned, because they described a model that isn't built.

**Not updated:** my saved memory of the old deadline, because it's outside the files Rachel listed. `claude-notes.md` tells the next chat to fix it.

**Next:** in the new chat, the first model: model table, rolling test windows, lookup table, simple combo, scores, predictions file. Website and level-ups come later.

---

## 2026-11-05 18:20 ET — Overnight build, step 1: stale memory, daily job check

**Did:** started the 2-hour unattended build Rachel asked for (steps 1–9). Replaced my stale memory file `finish-by-2026-11-17` with `competition-deadline` (complete Nov 23, turn in Nov 24, present Dec 7, rubric in SPEC §1.1) and fixed its line in `MEMORY.md`. Pulled `../broadway-rush-data` and read its log.

**Why:** `claude-notes.md` listed the memory fix as owed, and the first scheduled run of the daily job was due at about 23:07 UTC.

**Result:** the data repo's latest commit is still `cc2029d` (the manual run, 21:52 UTC), and that's also what's on GitHub. It's 23:20 UTC now, so the 23:07 run hasn't landed. That doesn't mean it failed: GitHub often starts scheduled runs late, especially a brand-new schedule. **Not confirmed yet.** I'll check again before I finish.

**Choice made for Rachel:** renamed the memory file rather than keeping a wrong date in its name.

**Next:** step 2, install lightgbm and numpyro.

---

## 2026-11-05 18:35 ET — Step 2: lightgbm and numpyro on Python 3.14 + Windows

**Did:** installed lightgbm 4.7.0 and numpyro 0.22.0 (which brings jax 0.12.0.1) into `.venv` in 45 seconds, then ran a real test of each with made-up data, not just an import: LightGBM with the Poisson objective and the "line never shrinks as opening approaches" constraint, and NumPyro sampling a small negative binomial model with "at least" labels.

**Why:** the earlier dry run only proved they install.

**Result:** both really run. LightGBM fit 8,000 rows in 0.26 seconds, and the constraint held. NumPyro ran 600 sampling steps on 500 rows in 13 seconds with 0 divergences (a sampler health check, 0 is what you want) and got close to the values I'd built in. Sampling runs on the CPU, the only device jax sees here.

**Didn't work / dropped:** my first Bayesian test crashed: "Betainc gradient with respect to a and b not supported". JAX can't take the slope of the standard formula for "chance of at least k", and the sampler needs that slope. **Fix:** add up the chances of 0, 1, 2 ... k−1 directly. It's slower per step but works, and the test above used it.

**Choice made for Rachel:** in `pyproject.toml` these go in an optional group, `model` (lightgbm, numpyro, scipy), not the main list. The daily snapshot job runs `pip install -e .` on every run, so putting them in the main list would add heavy downloads and a new way for that job to break. To install everything: `.venv\Scripts\python -m pip install -e ".[model]"`.

**Next:** step 3, the model table.

---

## 2026-11-05 18:33 ET — Step 3: model table

**Correction to the entry above:** I typed its time by hand, and 18:35 was wrong: it was written around 18:25. From here on, times come from the computer's clock.

**Did:** wrote `src/broadway_rush/model/table.py`. It makes three tables in `data/processed/` (`model_line.csv`, `model_cutoff.csv`, `model_outcomes.csv`) plus the row counts at each cleaning step (`model_funnel.json`). All features come from one function, used for history and for future dates alike, so training and predicting can't drift apart.

**Why:** this follows the plan in `claude-notes.md`, with only what's known at prediction time and only data already on disk.

**What "known at prediction time" means here:** the model predicts up to 7 days ahead, so every feature must be available 7 days before the performance. Grosses come from a week that ended at least 9 days before. "Recent line level" uses only reports from 35 to 7 days before. The calendar is known ahead of time.

**Result, the cleaning funnel (also useful for the rubric):**
| Step | Rows |
|---|---|
| Comments scanned | 139,584 |
| Observations extracted | 18,412 |
| In-person general rush | 15,728 |
| Mapped to a real Broadway show | 11,588 |
| Not low confidence | 10,860 |
| Stated, valid date from June 2024 | 9,894 |
| Date within 2 days before to 14 days after the comment | 9,407 |
| Date inside the show's run | 9,406 |

From those 9,406 rows:
- **Line:** 7,746 points with a time and a number → 7,106 before that show's opening → **6,060** after dropping duplicates (3,098 show-days, 81 shows).
- **Cutoff:** **762 show-days** (66 shows): 138 with a stated count, 549 lower bound only, 69 upper bound only, 6 both. 1 contradictory day dropped.
- **Outcomes:** **669** attempts with an arrival before opening and a known result. **87.3% got a ticket.**

**The numbers came out lower than the SPEC counts, as expected:** those counted comment-date rows and used a flat 10:00 cutoff. One consequence: the **89% "always yes" was measured on the wider 1,133-row set.** On the rows I'm actually scoring it will be a bit different, so I'll report it on the same rows as the model, next to the 89%.

**Parsing check:** I ran all the General Rush opening-time wordings through the parser, and each came out right (10 AM Mon–Sat with noon or 11 AM Sunday, and so on).

**Choices made for Rachel:**
1. **Two extra date checks I added, not in the plan:** drop rows dated more than 2 days after or 14 days before the comment was posted (487 rows, usually a misread year or a plan rather than a report), and rows dated outside the show's run (1 row). Why: `weeks_since_first` first came out as low as −84 weeks, which can't be right.
2. **Someone who arrives and is #6 counts as 5 people already in line,** so line counts and attempts mean the same thing.
3. **No times more than 9 hours before opening:** overnight camp-outs or mistyped times.
4. **Dates only as stated:** comment-date rows are left for a later with/without test, as planned.
5. **Left out of the first version, per SPEC §5.2a:** NYC events, TKTS and cast news.
6. **Weather:** it's in the table, but the history is what actually happened, and a real prediction can only have a forecast. No past forecasts are on disk. So using it in a test would quietly be cheating. I'll test what it adds as a best case, and leave it out of the scored model unless it's clearly worth it.

**Next:** step 4, test windows and the lookup table.

---

## 2026-11-05 18:37 ET — Step 4: test windows and the lookup table

**Did:** wrote `model/lookup.py` (the bar to beat) and `model/backtest.py` (the rolling test). Ran the line half first, because it takes seconds.

**Test windows:** 12 calendar months, Nov 2025 to Oct 2026. Each month is predicted by models trained only on earlier days, never shuffled. For a row to be in training, both its date and its posting time must be before the month starts.

**Lookup table:** line = median for that show + weekday + time window, falling back to show + time window, then all shows + time window, when there are under 3 reports. Tickets = that show's stated counts, falling back to all shows. Chance = share who got a ticket for that show and time window, pulled toward the overall share.

**Choices made for Rachel:**
1. **Three windows are locked for the final score and are not scored here: Dec 2025, Apr 2026, Aug 2026.** SPEC §5.2 says to keep some untouched. I picked "every fourth month" and chose which ones by label counts only, before any model ran: this set holds 12 of the 28 misses and 14 of the 47 stated counts. The obvious alternative (Feb, Jun, Oct) held only 1 miss, so its final score couldn't have tested anything. **All scores below come from the other 9 windows.** The locked three stay locked for the final model.
2. **Weather stays out of the first model.** Tested as a best case, using what really happened: line error 4.73 with it, 4.73 without (1,507 points). Even with a perfect forecast it adds nothing, so there's no need for the unfair test or for forecasts.

**Result, line half only (9 windows, 1,507 points, each show-day counted once):**
| | Combo (LightGBM) | Lookup table |
|---|---|---|
| Line error (people) | **4.73** | 5.82 |
| Line error, 2 to 0.5 hours before opening | **4.96** | 6.48 |
| 80% range really contains the count | **86.5%** | 58.8% |
| Average width of that range (people) | 15.1 | 13.5 |
| Arrival-time error (minutes) | 102 | **95** |

- The combo wins clearly on line length and on honest ranges. It beat the lookup in all 9 windows.
- **The lookup table wins slightly on arrival-time error.** Both are bad, off by over an hour and a half. This measures: given a real count at a real time, how far off is the predicted time for the line to reach that count? Lines jump around a lot from day to day, so a typical-day curve can't time a specific report well.
- The combo's ranges run a bit wide (86.5% against the 80% target), which is better than too narrow.

**Next:** the cutoff half. Three background runs are going now, trying 1.0, 1.4 and 1.8 tickets per person.

---

## 2026-11-05 20:34 ET — Cutoff model too slow; computer seems to have paused; switching to a faster fit

**What happened:** the three background test runs (1.0, 1.4 and 1.8 tickets per person, 4 chains, 1,000 steps each) hadn't finished even their first window after about 11 minutes. A profile showed why: the fit does run, but my settings were too heavy. 200 steps took 17–50 seconds with the machine busy.

**Didn't work:**
1. I tried to stop those three runs so I could restart them with lighter settings. **A safety check on this session blocked that command,** which stopped every Python process using a lot of CPU. I didn't try to get around it. The three runs are still going, and I'll give Rachel the command to stop them.
2. My next command ran past its 5-minute limit. **The clock then read 20:33, up from 18:48.** The runs had used only about 1,400 more CPU-seconds in that 1 hour 45 minutes, when they'd used about 2,000 in the first 7.5 minutes. So the computer most likely went to sleep or was heavily throttled. I can't prove which: the Windows power log returned nothing.

**Where that leaves us:** Rachel's 2 hours are about up, and no Bayesian test has finished. The rule she gave me: "use a faster fit, then the regressions' cutoff, label that clearly, and move on."

**Choice made for Rachel:** moving to the **faster fit now,** with the same Bayesian model and the same labels but less sampling: 2 chains, 300 warmup + 300 kept steps (was 4 chains, 500 + 500), acceptance target 0.8 (was 0.9), tree depth capped at 6. The risk is rougher ranges. I'll report R-hat, sample size and divergences for every window, and the site will label it as a faster fit. The regressions' cutoff isn't needed unless this fails too.

**Also seen in the profile, worth watching:** on data before Nov 2025 the model's average day comes out around 45 tickets with a very wide spread, while stated counts have a median of about 6–7. That's the risk SPEC §5.2 flagged: "at least" labels (549 days) far outnumber upper bounds (69). The test on stated counts will show how much it hurts.

---

## 2026-11-05 23:29 ET — Second pause, Rachel back, and the first faster fit failed one window

**What happened:**
- The clock jumped again, from about 21:02 to 23:24. Same signs as before: very little CPU used over that time, so the computer most likely slept. **I should have blocked sleep at the start.** Now I've done it for this session: a background command asks Windows not to sleep for up to 3 hours, then lets go. No power settings changed.
- Rachel came back. I told her the site wasn't working yet and which runs were stuck. She plugged in the laptop and said to continue.
- I tried again to stop my 4 stuck test runs, this time only those exact process IDs. **The safety check blocked it again,** so I won't try a third time. They're still using CPU. Rachel can stop them with `Stop-Process -Id 26512,27504,32492,14708`.

**Didn't work:** the first faster fit (2 chains on separate devices) looked healthy for three windows (R-hat about 1.01, 0 divergences), then **failed on March 2026: R-hat 6.16, effective sample size 1.** That means its chains never agreed, so that window's numbers mean nothing. I won't use that run.

**What I tried next:**
1. A profile had shown 4 chains run together ("vectorized") finishing cleanly on older data (R-hat 1.015, sample size 369, 0 divergences). That's the second run, still going.
2. **Likely cause of the failure:** the sampler picks a random start. If it lands where every "at least" label looks impossible, the slope goes flat and that chain stays stuck. I haven't confirmed this. I changed the code to start from the middle of the priors, and to try again with a new seed, up to 3 attempts, if R-hat is above 1.05. Each fit now records whether it converged.

**Choice made for Rachel:** a fit that still fails after 3 attempts gets marked as not converged, and I'll say so rather than quietly using it.

---

## 2026-11-05 23:46 ET — Steps 6–9, first pass: predictions file written, site clicked through, bugs fixed

**Did:** wrote `model/predict.py`, which writes `web/data/predictions.json`, and built the site in `web/` (`index.html`, `styles.css`, `app.js`). It's plain HTML, CSS and JS and reads only that file.

**The first predictions file is NOT usable, and I'm replacing it:** the Bayesian fit in that run didn't converge (R-hat 28.5, sample size 2). It started before my fix, and ticket ranges like "13 to 183" come from that failure. I used it only to test the pages. `predict.py` now refuses to write anything from a fit that didn't converge.

**The click-through:**
- **The browser pane isn't available in this session,** so I drove headless Chrome with a test script instead: every day, every kind of tile, details, slider, chart hover, picks filter, accuracy page, report form, Refresh + PIN, at 390 and 1280 pixels wide. I also read the screenshots myself.
- **Bugs found and fixed:** a stray word "null" on the home page; a blank chance chart on the details view (it was drawn before its panel was on the page); "a 80%"; a missing tab icon; "price not listed" on shows that have no rush at all; and the nav label "Today's picks", now "Shows", because the picked day often isn't today.
- **After the fixes:** every interaction check passes at both widths, and the only page error left was the tab icon, now added. **Not yet rerun with final predictions and accuracy results.**

**Choices made for Rachel:**
1. **Verdict and ranking:** the chance if you arrive at 9:00, as you asked. **Placeholders: GO at 70% and up, Maybe at 40% and up, target chance for the arrival time 80%.** On Sundays 9:00 is three hours before a noon opening, so Sundays look better; that's real, not a bug.
2. **Show groups (§8):** I added one thing. Playbill's list misses shows with real reported lines: Rocky Horror, Paranormal Activity, Two Strangers, Wanted, Stranger Things and Downstate. A show with no General Rush listing but 3 or more in-person reports in the last 30 days counts as in-person rush, marked "not on Playbill's current list". Going by Playbill alone would have hidden the most-reported show. Standing room counts as in-person too, which matches the §8 list (Hadestown, Six).
3. **"Enough data":** at least 2 daily-thread reports per running week over the show's whole run.
4. **Low confidence badge:** under 35 line reports or under 5 days with ticket information.
5. **Prices:** where a show isn't on Playbill's current list I show the last listed price with its date if there is one (Stranger Things), or "price not listed". Never a guess.
6. **"± range":** the range isn't symmetric, so the sentence uses its midpoint and half-width and also says "that's X to Y tickets".
7. **Schedule:** The next 7 days come from Ticketmaster's Nov 5 snapshot (Nov 6–12), matched by theater. A Few Good Men and The Imaginary Invalid aren't on Ticketmaster, so they're listed every day as "schedule not confirmed". Blue Man Group, Inter Alia and Now You See Me Live have no policy, grosses or reports, so they're skipped (§2.7).
8. **Not shown because nothing computes them:** digital rush sell-out time reads "not available yet". The badges `Star leaving Sunday` and `Prices way above usual` are left out.
9. **Reports form and Refresh + PIN:** screens only, labeled "Not connected yet". Nothing leaves the page, the PIN isn't checked and it's cleared after you press the button.
10. **Added beyond the list, because it uses numbers we already have:** a chance-by-arrival-time chart on the details view. It helps the rubric's visualization points.

---

## 2026-11-06 00:02 ET — A converged fit, but the ticket ranges are too wide

**Did:** Rachel stopped the 4 stuck runs herself (I checked: all gone). I stopped my own older test, which used the old code, and started clean tests at 1.0, 1.4 and 1.8 tickets per person. I also wrote a new predictions file from a fit on all the data: **R-hat 1.003, sample size 554, 0 divergences, first attempt.** So the fix for stuck chains (starting from the middle of the priors) held up there.

**Result:** the numbers are now real model output, but **the ticket ranges are too wide to be useful.** Two Strangers on a Saturday: 80% range 14 to 239 tickets. The model's typical day is about 40 tickets, while stated counts have a median of 6 and 90% are 23 or below (91 stated days before the test months).

**Why:** this is the risk SPEC §5.2 warned about. 549 "at least" days push the estimate up with nothing pushing back, and only 138 stated days and 75 "at most" days pull down. The fitted day-to-day spread (phi about 1.3) lets a very high average still tolerate low stated counts.

**One more finding:** on the 39 days with both a stated count and a "got it at #p", the last reported position is typically about two-thirds of the stated count, and it's above the stated count on only 10 of them. That fits tickets per person between 1.0 and 1.4 better than 1.8.

**What I'm trying next:** one variant, a tighter prior on the spread (centered on phi = 3, was 5 with much more room). Before the test months, stated counts swing about 70% of the show's average within a show (median of 6 shows with 5+ stated days), which is roughly phi = 2 to 7. **The rule:** it runs on the same 9 test months and stays only if it beats the current version. If it wins on tickets but hurts the chance of a ticket, I'll say so.

**Fix:** today now counts as a prediction day until noon. The midnight rollover had dropped Nov 6 from the file.

---

## 2026-11-06 00:37 ET — Step 5, first real scores: the combo loses to the lookup table on tickets

**Did:** two of the clean tests finished (1.0 and 1.4 tickets per person, 9 test months). **All 18 fits converged:** worst R-hat 1.013, 0 divergences.

**Result so far. The combo doesn't beat the lookup table except on line length:**
| 9 test months | Combo at 1.4 | Combo at 1.0 | Lookup table | Always yes |
|---|---|---|---|---|
| Ticket error, 33 stated counts | 19.5 | 11.6 | **6.2** | |
| 80% ticket range held | 87.9% | 93.9% | 69.7% | |
| Width of that range, tickets | 95.7 | 57.6 | **11.5** | |
| Chance error (Brier, lower is better), 138 attempts | 0.114 | 0.107 | **0.097** | 0.103 for a flat rate |
| Yes/no right at 50% | 87.7% | 88.4% | 88.4% | 88.4% |
| Misses caught, of 16 | 1 | 1 | 0 | 0 |

Line length is unchanged: combo 4.73, lookup 5.82.

**What this means:** the ticket half floats too high, as SPEC §5.2 warned, and that also hurts the chance. It adds almost nothing over always saying yes, catching just 1 of 16 misses. **Lower tickets per person is better,** so 1.8 looks unlikely to help (that run is still going).

**Next:** the tighter-spread variant is running at both 1.4 and 1.0. I added the 1.0 run because 1.0 did better. Whichever way it comes out, I'll report these numbers.

---

## 2026-11-06 00:56 ET — Step 5 results: tickets per person chosen, the variant dropped, the combo doesn't beat the lookup table

**Did:** finished the tests at 1.0, 1.4 and 1.8 tickets per person, plus the tighter-spread variant at 1.4. **All converged:** worst R-hat 1.018, 0 divergences across 36 fits.

**Result (9 test months):**
| | 1.0 per person | 1.4 | 1.8 | 1.4, tighter prior | Lookup table | Flat rate / always yes |
|---|---|---|---|---|---|---|
| Ticket error (33 stated counts) | **11.6** | 19.5 | 29.0 | 19.1 | **6.2** | |
| 80% ticket range held | 93.9% | 87.9% | 87.9% | 87.9% | 69.7% | |
| Width of that range | 57.6 | 95.7 | 148.8 | 90.4 | 11.5 | |
| Chance error (Brier, 138 attempts) | **0.107** | 0.114 | 0.119 | 0.114 | **0.097** | 0.103 |
| Yes/no right at 50% | 88.4% | 87.7% | 87.7% | 87.7% | 88.4% | 88.4% |
| Misses caught, of 16 | 1 | 1 | 1 | 1 | 0 | 0 |
| Line error | 4.73 | same | same | same | 5.82 | |
| 80% line range held | 86.5% | same | same | same | 58.8% | |
| Arrival-time error (min) | 102 | same | same | same | 95 | |

**Plainly: the combo beats the lookup table on line length and on honest line ranges. It does NOT beat it on ticket counts, on the chance of a ticket, or on arrival time.** On the chance of a ticket it's also worse than a flat rate, and it's no better than always saying yes on yes/no accuracy. Its one small win there is catching 1 of 16 misses, which is too few to mean much. And 33 stated counts and 16 misses are small samples.

**The "got a ticket" check is rough either way:** losses are under-reported, so the share who got one is likely too high.

**Verdicts at the placeholder thresholds (1.0 per person), scored on the chance when each person really arrived:** GO worked out 109 of 118 times (92%), Maybe 12 of 18 (67%), Stay home 1 of 2. The order is right but the sample is small, and "Stay home" barely ever fires, so the top of the range is doing almost no work.

**Choices made for Rachel:**
1. **1.0 tickets per person.** It wins on every measure of tickets and chance. Caveat: it's the lowest value tried, and buyers report about 1.8 each. One possible reason: not everyone ahead of you buys a rush ticket. That belongs with the "learn tickets per person" level-up.
2. **The tighter prior is dropped.** The fitted spread barely moved (1.32 to 1.36) and scores barely changed. I stopped its run at 1.0 because the 1.4 result already answered the question. So this isn't a tuning problem: stated counts and "got it at #p" reports disagree.
3. **I kept the combo rather than falling back to the regressions.** It isn't broken: it converges, and the fallback was for that. You asked to be told if it doesn't beat the lookup, and this is me telling you.
4. **The details page now warns on every full prediction** that the ticket count is a rough guess, quoting these test numbers from the file, so it updates itself if the model improves.

**Most useful next steps, for when you pick level-ups:** use the sold-out-time and "tickets remain" reports, which add upper bounds and are the most direct help for the ceiling problem; then learn tickets per person; then look at whether stated counts mean what we think (many may be partial, like "6 left"). I haven't tested any of these.

**Also finished:** final predictions file at 1.0 per person (R-hat 1.004). Final click-through: **106 of 106 checks passed at 390 and 1280 pixels, 0 page errors.** I read the screenshots, and fixed the last small things they showed: Hadestown's standing room price ($39), Harry Potter's Friday Forty, no gold on the "width" rows, a note explaining the gaps in the charts, and the chart scale adjusting to the data.

---

## 2026-11-06 01:07 ET — Final pass: clean training times, docs, and what's left

**Did:** ran the 1.0 test again with the laptop otherwise idle, to get fair times, and rebuilt the predictions file the same way. Updated `SPEC.md` (status, §5.2, §5.2a, §5.2b, §5.3, §8, §9), `interview-notes.md` and `claude-notes.md`. Reran the click-through on the final file.

**Training times, measured (replacing the estimates in SPEC §5.2b):**
| Model | One test month | All 9 test months |
|---|---|---|
| Lookup table | 0.03 seconds | under a second |
| LightGBM line | 0.7 seconds (1.8 on all data) | under 10 seconds |
| Bayesian cutoff, faster fit | 55 seconds (69 on all data) | about 8 minutes |
| **Whole combo** | under a minute | **8.4 minutes** |

Twelve months would take about 11 minutes. That's scaled up, not run, because 3 months are locked. My earlier estimate was about an hour. The slow runs earlier in this log came from competing jobs and bad settings, not from the model.

**Checks:**
- The idle run matched the earlier 1.0 test exactly, so the results repeat (same seed, 8 vs 2 LightGBM threads).
- Final click-through: **106 of 106 checks passed at 390 and 1280 pixels, 0 page errors.**
- Every number on the accuracy page comes from the test file, and every unavailable item says so.

**Still not confirmed: the daily snapshot job.** At 06:06 UTC the data repo's latest commit is still the manual run from 21:52 UTC Nov 5. The run due at 23:07 UTC never landed, nearly 7 hours later. I can't see the Actions tab. The next run is due at 12:07 UTC. Rachel needs to check.

**Things Rachel should know:**
- Her 23:56 commit holds the bad predictions file (R-hat 28.5). Her next commit replaces it. `data/processed/backtest_fast1.4*` from the failed run are also in the repo and safe to delete.
- The schedule is the Nov 5 Ticketmaster snapshot, so the site covers Nov 6–12 only, then says it's out of date.
- I released the "don't sleep" hold. The local web server I started is still running on port 8000.

**Not done, as instructed:** no commits, deploys, accounts, API money or new scrapes by me. No level-ups, cast news or comparison rows. The report form and Refresh + PIN are screens only.

**Next, for Rachel to decide:** which level-ups to do first, real GO and Maybe thresholds, the verdict's fixed comparison, the wording for standing-room shows (new SPEC §9 question 20). Charts and the presentation still aren't on the schedule, and they're worth 17 of the 50 points.

---

## 2026-11-06 01:27 ET — Chicago gets a full prediction; a flaw in the "enough data" rule

**Did:** Rachel asked "can you show chicago on there?" It was already listed, in the second section with no numbers, because it has 0.98 reports a week against the §8 cutoff of 2. **My reading: she wants its full prediction.** I added a one-show exception (`ALWAYS_FULL` in `predict.py`, one line to undo), rewrote the predictions file and reran the click-through: **106 of 106 checks passed, 0 page errors.** Fit unchanged (R-hat 1.004).

**Result:** Chicago now shows a full prediction on the 6 days it plays in the file; it isn't on Ticketmaster for Nov 11. Friday Nov 6: ranked 10 of 15, 79% if you arrive at 9:00, get there by 8:45, 3 to 41 tickets.

**How much to trust it:** 81 line reports and 11 days with ticket information, but **0 stated counts,** so its ticket number comes only from "at least" and "at most" labels. In the 9 test months its line error was 4.58 against 4.38 for the lookup table, on 22 points, so about the same. It had no outcomes or stated counts in those months, so its chance of a ticket wasn't tested at all.

**Found while checking:** the "enough data" rule (reports per running week, my choice of how to measure it) favors brand-new shows. **Wanted gets a full prediction from 3 line reports and 0 ticket days, and 860 from 9 and 0.** Both carry the Low confidence badge, but those numbers rest mostly on what's typical across shows. Chicago had far more data and got none. I didn't change the rule: it's in §8 and it's Rachel's call. Added as SPEC §9 question 21.

**Also from Rachel:** she finds the fonts ugly and will deal with that later. No change made.

---

## 2026-11-06 01:33 ET — Spec: tile filters, sorting and plain wording (no code)

**Did:** added SPEC §2.2a at Rachel's request: rush-type labels on tiles; filters for rush type, days showing, runtime, high-profile stars, and play or musical; sorts for rush price, typical ticket price, runtime and latest arrival; and words in place of "__% full". Added questions 23–25 to §9. The site wasn't changed.

**Why:** "% full" made no sense to Rachel, let alone a typical user. People planning weeks ahead also need to find shows by the days they play, not just by a date in the next 7 days.

**Result (data checked first):**
- **Have now:** rush types (14 in person, 10 online, 5 student, 25 lottery, 6 standing room), play or musical, rush price, average paid ticket, seats sold.
- **Runtime has a source:** Playbill's production page says "Running Time: 2 hours and 45 minutes, including one intermission". Checked on Wicked only, using a few requests. Log these pages in `registry/sources.csv` before collecting them.
- **Days showing is partly covered:** Ticketmaster shows 27 of 37 theaters with the same weekly pattern (no Monday show), but it only looks 8 days ahead, there are only 2 snapshots so far, and two shows aren't on it.
- **Stars aren't collected:** they need cast news, which still waits on Rachel's go-ahead.

**Choices I made for Rachel, all listed in the spec:**
- **Median price:** a true median non-rush price isn't available, because the grosses only give average and top price. I used the median of the last 4 weekly averages, labeled "Typical ticket price". It includes rush and discounted tickets.
- **Star rule:** billed above the title, or a Tony, Oscar, Emmy or Grammy win.
- **Word cutoffs for how full a show is:** 98%, 90% and 75%. Placeholders.
- **Runtime bands:** placeholders.
- **Lottery and Standing room in the rush-type filter:** added, though they aren't rush, because the site already lists them.
- **"Any day" mode:** a new choice on the day picker, showing facts with no chance or arrival time, because predictions stop at 7 days.

**Didn't work / dropped:** a check command of mine was blocked because it included a needless delete of a temp file. It never ran, so nothing was created or removed; I reran the check without it.

**Next:** build when Rachel says. The parts with data on hand come first; runtime needs collecting, and stars need cast news.

---

## 2026-11-06 01:36 ET — "Enough data" rule changed: 35 line reports or 2 comments a week

**Did:** Rachel said to use "__ minimum reports OR 2 comments/week", leaving the number for me. Changed `predict.py`, rewrote the predictions file and reran the click-through: **106 of 106 checks passed, 0 page errors.** Fit unchanged (R-hat 1.004). The accuracy page doesn't change, because the tests score every show regardless of group. Chicago's one-show exception is gone: it qualifies under the new rule.

**How I picked the number:** line error in the 9 test months, grouped by how many line reports the show had before each test month (each show-day counted once):
| Line reports before the month | Test points | Combo error | Lookup error | 80% range held |
|---|---|---|---|---|
| 0 | 133 | 3.86 | 5.72 | 85% |
| 1–9 | 59 | 4.31 | 5.65 | 79% |
| 10–19 | 104 | 6.20 | 5.80 | 75% |
| 20–34 | 129 | 5.66 | 5.05 | 75% |
| 35–49 | 160 | 5.24 | 6.07 | 86% |
| 50–99 | 244 | 4.93 | 5.52 | 87% |
| 100–199 | 128 | 4.13 | 5.68 | 92% |
| 200+ | 550 | 4.44 | 6.14 | 90% |

**Choices made for Rachel:**
1. **35 line reports.** That's where the combo starts beating the lookup and its range starts holding. It's also the Low confidence cutoff already in use. Any number from 23 to 81 picks the same shows today, so the exact value isn't fragile. The 0 and 1–9 rows look good, but those are mostly new shows with short lines (5–6 people on average) and few points, so I don't read them as "no data is fine".
2. **"Comments" taken literally:** distinct daily-thread comments per running week, not extraction rows as before. One comment can give several rows, so this is stricter. **It's what moves 860 and Wanted down;** on the old row count they sat at exactly 2.0.

**Result:**
- **Moved up to full predictions:** Chicago (81 line reports), Stranger Things (104).
- **Moved down to "limited data":** Paranormal Activity (22 line reports, 1.92 comments a week), 860 (9, 1.80), Wanted (3, 1.67).
- **Full predictions now:** 13 shows, 2 to 13 per day (only 2 on Monday). No full prediction carries the Low confidence badge now.

**A problem this creates, not changed:** the second section says "Limited data, probably easy", which came from quiet shows being less full. 860 and Paranormal Activity were about 99% full, and Hadestown 95%, so it's probably wrong for them. It's Rachel's §8 wording, so I asked her (SPEC §9 question 20).

---

## 2026-11-06 01:38 ET — Spec: days showing, runtime and "seats sold" corrected (no code)

**Did:** changed SPEC §2.2a after Rachel corrected my 01:33 entry. No code in this chat; Rachel said nothing gets built here.

**Why:** I overcomplicated two things.
- **Days showing** just means which weekdays a show plays (Just in Time doesn't play Monday or Wednesday), and show websites have that. Ticketmaster isn't needed.
- **"__% seats sold"** makes sense as it is, so the word labels and their cutoffs aren't needed.

**Result:**
- Days showing and runtime are now simple facts, looked up once per show into `registry/show_facts.csv` and reviewed by Rachel.
- The tile says "92% seats sold last week", capped at 100% because standing room can push it just past that (the cap is my choice).
- §9 question 24, about pulling Ticketmaster further ahead, is dropped.
- I kept "Any day" on the day picker: once a specific date is picked, the days-showing filter has nothing left to do.

**Didn't work / dropped:** the 01:33 word labels ("Almost sold out") and the Ticketmaster plan for days showing.

**Next:** nothing to build from this chat. Another chat is working in `web/` and `predict.py`, so §2.2a is there for whichever chat builds it.

---

## 2026-11-06 01:40 ET — Spec: wider site, lighter background, font later (no code)

**Did:** changed SPEC §2.4 and §8 at Rachel's request, and wrote a prompt for the build chat to reread the spec. Nothing built in this chat.

**Why:** the site is a centered column capped at 1040 pixels (`web/styles.css`), which looks like half the screen on a big monitor. Rachel doesn't like dark mode, but thinks white would look bad. Rachel also wants a better font, later.

**Result:**
- **Width:** at least 7/8 of the screen at every size, with tiles adding columns to use the room.
- **Background:** a clearly lighter purple, with `#B9A5E6` as a starting point (my pick).
- **Font:** stays until Rachel picks a new one (§9 question 22).

**Found:** lighter purple breaks other parts of the look, by my contrast math on the current colors.
- The current light text would be about 2:1 on that purple, so I changed the spec to dark purple body text, with glow only as an accent. This drops the original neon-text idea, so Rachel should check it.
- Gold and gray would be about 1.4:1 and 1.6:1, so the worth-it bar needs a dark outline.

**Next:** Rachel sends the prompt to the build chat.

---

## 2026-11-06 01:42 ET — Correction: reports, not comments

**Did:** Rachel meant reports when she wrote "comments". I'd taken it literally in the entry above, so that part was wrong. Counting reports again: **a full prediction needs 35+ line reports OR 2+ daily-thread reports per running week.** The 35 stands. Rewrote the predictions file and reran the click-through.

**Result compared with the entry above:** Paranormal Activity, 860 and Wanted go back to full predictions, each with the Low confidence badge. Chicago and Stranger Things stay full through the 35-report route. Downstate, & Juliet, Hadestown, It's a Wonderful Life, Six and Wicked stay "limited data".

**Parked for the next session, at Rachel's request:** other features for limited-data shows (SPEC §9 question 23). Nothing built. The "probably easy" wording on Hadestown (question 20) goes with that talk, so I left it as is.

---

## 2026-11-06 01:46 ET — Site update, step 1: new look (§2.4)

**Did:** Rachel changed `SPEC.md` from another chat and asked for the site to match. I reread §1, §2.1, §2.2, §2.2a, §2.4, the §8 lines, §9 questions 22–25, and the 01:33, 01:38 and 01:40 entries first. Then I rewrote `web/styles.css`: 92% of the screen wide at every size (spec minimum is 7/8, 87.5%), tiles adding columns as room grows, a `#B9A5E6` background, dark text, no dark mode, and a dark outline on the worth-it bar. Fonts unchanged, per Rachel.

**Conflicts found, and how I handled them (told Rachel):**
1. **Two question 23s in §9:** mine (limited-data shows) and the other chat's (Any day). Renumbered mine to 26, and fixed the two references to it.
2. **Hadestown and Six:** §8 treats standing room as in-person, but §2.2a's `In person` label means General Rush only. I follow both: they stay in the second group, labeled `Standing room`. That section is retitled "At the box office, not enough reports".
3. **Standing-room prices:** §2.2a's rush price is in-person, or online if there's none, and doesn't mention standing room. I still show Hadestown's $39, labeled "standing room", and sort it with the others. For Rachel to review.

**Choices made for Rachel:**
- **Contrast, computed:** dark ink is 8.2:1 on the background and 15.5:1 on tiles; the lightest text color (`#46306F`) is 5.0:1 on the background and 9.5:1 on tiles. The spec's minimum is 4.5:1.
- **Tiles are a pale purple (`#F1ECFB`), not the background color,** so text and bars have somewhere to sit.
- **Gold and gray stay as fills with dark outlines, never as text,** because they're under 1.6:1 on the background. Selected chips are dark with white text.
- **Chart lines changed to darker gold (`#A06F00`) and teal (`#127FA0`).** They pass all 5 color checks on the tile color, including color-blind separation. The lookup line stays dashed as a second cue.
- **Gold on the accuracy table is now a highlight behind the best value,** because gold text doesn't read. Key numbers in the details view get a gold underline instead of a glow.
- **Glow:** kept only as a soft white glow on the logo and page title.
- **Tiles start at 270 pixels wide** (was 290), which gives about 4 columns at 1280 pixels, 6 at 1920 and 8 at 2560. Paragraphs stop at about 78 characters so lines don't stretch.

**Next:** "% seats sold", then the labels, filters, sorts and "Any day".

---

## 2026-11-06 01:57 ET — Site update, steps 2 and 3: seats sold, rush-type labels, filters, sorts, Any day

**Did:** added new fields to the predictions file (rush types, play or musical, typical ticket price, seats sold) and rebuilt the home and details pages in `web/app.js`. The model didn't change: the fit is the same (R-hat 1.004), and I only reran `predict.py` to write the new fields.

**What's on the site now:**
- **"__% seats sold" everywhere,** including the "why this prediction" lines: "57% seats sold last week", rounded and capped at 100%. It names the week once the data is over 2 weeks old. No "% full" or "capacity" is left on any page; a test checks this.
- **Rush-type labels on tiles.** Counts match §2.2a exactly: In person 14, Online 10, Student 5, Lottery 25, Standing room 6, plus 7 `In person (reported)`.
- **Filters:** rush type and play or musical. Any selected option within a filter counts, and a show must match all filters. There's a "12 of 33 shows" count, a clear-all button and "hidden: not known" notes. Filters are open by default on desktop and closed on phones.
- **Sorts:** best chance (default), latest arrival, rush price, typical ticket price. Tapping a sort again reverses it, and unknown values always go last.
- **Any day** on the day picker: facts only, with no chance, bar or arrival time, "Check back within 7 days of your date", and a note to confirm before going.

**Choices made for Rachel:**
1. **Every sort except best chance shows one flat list,** so the sort means something across groups. Best chance keeps the three group sections.
2. **Tiles show a small facts line** (play or musical, typical ticket) on dates too, not just in Any day. §2.2 doesn't list it, but a sort is confusing if you can't see what it's sorting by.
3. **Rush price order:** listed in-person price, then a reported show's last listed price (with its date), then online (marked "online"), then standing room (marked). Paranormal Activity now shows "$40 online" instead of "price not listed". The details sentence won't call an online or standing-room price the in-person price.
4. **The `In person` filter also finds `In person (reported)`.**
5. **Hadestown gets both `In person (reported)` and `Standing room`.** It's on Playbill's list only for standing room and lottery, but has 3+ recent in-person reports. I read "doesn't list" as "doesn't list General Rush".
6. **Any day sorts by rush price by default,** since best chance isn't available there. It lists all 35 shows that appear on any day in the file.
7. **Other deals (Friday Forty and so on) moved to the details view,** with "Other deals in the details" on a tile if that's all the show has.
8. **Typical ticket price with under 4 weeks of data** uses what there is and says so in the details ("only 1 week so far"). Much Ado has 1 week.
9. **Stars aren't on Any day tiles,** though §2.2a lists them there, because that needs cast news.

**Didn't work, then fixed:** a stray word "null" appeared beside the show count. My check had missed it because I'd loosened the check while debugging, and I only saw it in a screenshot. I fixed the bug and made the check strict again. The white dot on the chance chart was also invisible on the lighter tiles, so it's dark now.

**Next:** step 4, days showing and runtime.

---

## 2026-11-06 02:02 ET — Back to dark

**Did:** Rachel changed her mind partway through this work: "change it back to dark mode". Put back the deep purple background and glowing light text. **Kept, because she only mentioned the colors:** the 92% width with extra tile columns, and all the new labels, filters, sorts and Any day. Updated SPEC §2.4 and §8 to match, and left the lighter version struck through so the history shows. The 01:46 look entry is superseded by this one.

**Choices made for Rachel:**
- **Worth-it bar:** a light outline, as before, since a dark one would disappear and the black end needs to show. Her "dark outline" instruction belonged to the lighter background.
- **Chart lines:** gold darkened a little to pass all 5 color checks on the dark tile, because the earlier dark version just missed the lightness limit. Teal `#2F9FC0` is unchanged.
- **Selected sort and filter chips are gold with dark text.** The accuracy table's best values go back to gold text.
- **Contrast, computed:** the lightest text is 5.3:1 at worst, on a hovered tile.

**Next:** back to step 4.

---

## 2026-11-06 02:13 ET — Site update, step 4: days showing and runtime

**Did:** logged the sources in `registry/sources.csv` first, then looked up all 35 shows into `registry/show_facts.csv`, and added the days-showing and runtime filters and the runtime sort. Reran `predict.py` to add the fields; the model didn't change (R-hat 1.004).

**Result:** days for 35 of 35 shows, runtime for 34 of 35 (Downstate's page has none, so it shows as not available). **6 rows are flagged for Rachel's review:** Downstate, Here There Are Blueberries, It's a Wonderful Life, Much Ado About Nothing, The Fantasticks and Wanted. All have 1 or 2 weeks of schedule history. The reasons are in the file's `note` column. About 45 requests in total, spaced 3 to 5 seconds apart.

**Didn't work, then fixed:**
1. **Playbill's show pages have runtime but no days.** They do link to its "Weekly Schedule of Current Broadway Shows", which lists every show's times, so that became the source for days.
2. **One week was misleading.** The live page covers Nov 2–8, and 10 shows disagreed with Ticketmaster. Nov 3 was Election Day, and several shows swapped Tuesday for Monday. So I added past copies of the same page from the Internet Archive and took the usual pattern across 8 weeks (logged first). Aladdin, Harry Potter, The Lion King, The Lost Boys and Hadestown all then play Tuesday 7 of 8 weeks.
3. **Two Playbill links on the rush list were dead (404): Hadestown and Harry Potter.** I found their pages through their grosses pages instead, and a note in the file says so. A cached page then hid this in a later run, so Hadestown's source briefly showed the dead link. I caught it in a screenshot and fixed it.
4. **My theater check gave false alarms** on The Great Gatsby ("Broadway Theatre") and The Fantasticks ("Hayes Theater"), because it was too strict about names. Fixed.

**Conflict with the spec, not resolved by me:** §2.2a says Just in Time doesn't play Monday or Wednesday. Playbill shows Wednesday in all 8 weeks and Ticketmaster agrees; it's dark Monday only. The site follows the data, and I asked Rachel (SPEC §9 question 27).

**Choices made for Rachel:**
1. **Days come from Playbill's schedule page, not "show websites or show pages" as she asked.** Runtime does come from show pages. One Playbill page beats 35 sites that would each need a rules check.
2. **Ticketmaster is only a cross-check.** The spec says it isn't needed for days. It flags rows; it never sets them.
3. **A day counts if the show played at least half the weeks.** A tie counts as playing, because wrongly hiding a show from a filter is worse than wrongly including it.
4. **Runtime bands:** exactly 90 minutes goes in "90 min–2 hrs", exactly 2 hours too, and exactly 2.5 hours in "2–2.5 hrs".
5. **A flagged show says on its details page that we're not sure.** Tiles look the same either way.
6. **Blueberries and It's a Wonderful Life are labeled Play,** inferred from the credits on their pages, because the catalog has no type for them yet. Both are flagged.
7. **Shows not on Ticketmaster (A Few Good Men, The Imaginary Invalid) no longer appear on days the facts say they're dark.** They still say "Schedule not confirmed".
8. **The site says "Playbill, checked Nov 6, 2026".** Full links are in the file.
9. **The lookup script was one-time,** in my temp folder, not the repo. Its pages are cached in `data/raw/playbill/show_pages/` (git-ignored).

**One thing for Rachel to judge:** Playbill's robots.txt blocks AI training crawlers by name, including Anthropic's, and says `ai-train=no, use=reference`. This lookup isn't training, and it used the project's own identifying User-Agent, like her existing Playbill scrapers. A script kept only the facts, and pages weren't sent to an AI model. These facts drive site filters, not the model.

---

## 2026-11-06 02:13 ET — Site update, step 5: final click-through

**Did:** extended the headless Chrome test and ran it on the final file, then read the screenshots. The browser pane still isn't available in this session.

**Result: 195 of 195 checks passed, 0 page errors.** Covers phone (390 pixels) and desktop (1280): every day, every kind of tile, details, slider, chart hover, picks, rush-type and play-or-musical filters including combinations and clear-all, all five sorts and reversing them with unknowns last, Any day and its details, days and runtime filters, greyed-out days on a date, the accuracy page, the report form and Refresh + PIN. No "% full" or "capacity" remains on any page checked.

**Width:** 92% of the screen at 320, 390, 768, 1280, 1920, 2560 and 3840 pixels, with 1, 1, 2, 4, 6, 8 and 12 tile columns, and no sideways scroll.

**Not covered:** real phones and Safari; nothing here tests whether the numbers are right, only that they appear and behave.

**Still not confirmed, the daily snapshot job:** at 07:13 UTC Nov 6 the data repo's latest commit is still the manual run from 21:52 UTC Nov 5. Rachel needs to check the Actions tab.

**Not done, as instructed:** no stars filter, font unchanged, no retraining or model changes, no commits, deploys, accounts or API money. Other features for limited-data shows and the "probably easy" wording wait for the next talk (SPEC §9 questions 26 and 20).

---

## 2026-11-06 11:52 ET — Daily job check: two scheduled runs missing

Rachel asked what I need to get the daily data. Checked at 16:50 UTC (11:50 am EST) on Nov 6. The data repo's newest commit is still `cc2029d`, the manual run from 21:52 UTC on Nov 5. Two scheduled runs were due by then and added nothing: TKTS at 23:07 UTC on Nov 5 and Ticketmaster at 12:07 UTC on Nov 6.

The workflow file is on GitHub's `master`, and local and remote match, so an unpushed file isn't the cause. I can't tell whether the runs never started or started and failed. `broadway-rush` is private, so GitHub's API returned 404 without a login, `gh` isn't installed, and I don't use Rachel's stored git login for API calls. Asked Rachel to read the Actions tab and press Run workflow, which should also save a Nov 6 snapshot.

Also removed an empty `--help/shots` folder from the project root, which looks like a leftover from my click-through script being run with `--help` during last night's site work. It held no files.

---

## 2026-11-06 12:05 ET — Daily job: manual run saved today's snapshot

Rachel pressed Run workflow and GitHub reported success. Commit `61821ee` reached the data repo at 17:02 UTC (12:02 pm EST) with one Ticketmaster file (470 KB) and one TKTS board (51 KB), so Nov 6 has ticket data. I pulled it into the local clone, `../broadway-rush-data`.

Rachel asked whether this lands in a different folder. It does: the job saves to the data repo, not to this project's `data/raw`, which the model and site read. Nothing here copies the files across yet. That's the sync command the notes already planned, still not built.

This doesn't prove the schedule works, since it was a button press. Started a read-only check of the data repo until 18:15 UTC to see whether the 17:07 UTC scheduled run saves anything.

---

## 2026-11-06 12:29 ET — Sync command: getting snapshots to the model and site

Rachel said to build whatever gets the data in here. Built `src/broadway_rush/sync.py`, run with `.venv\Scripts\python -m broadway_rush.sync`. It pulls the local clone of the data repo, copies any snapshot this project doesn't have into `data/raw`, rebuilds `tkts.csv` and `ticketmaster_events.csv`, and updates predictions if the schedule date is newer. It sends no requests to ticket sites.

Choices I made:
- A plain and a gzipped copy of one snapshot count as the same file, so the 130-odd older plain files aren't doubled. Files already here are never overwritten.
- A pull that fails stops the run, instead of quietly carrying on with old data.
- It warns if the newest Ticketmaster snapshot is over 30 hours old, because the job has already gone quiet once.
- It runs only when someone starts it. I didn't add a scheduled task on the laptop.

Result: 2 new TKTS and 2 new Ticketmaster snapshots copied. No old row was lost or changed in either CSV (tkts 9,179 to 9,320 rows, Ticketmaster 773 to 1,599). The site now runs Nov 7-13 instead of Nov 6-12. Ad hoc tests of the copy and failure rules passed 10 of 10; they live in my scratchpad, not the repo.

Correction: I told Rachel this wouldn't retrain the model. That was wrong. `predict.py` refits the combo on every run. With the same reports and settings, the line spread, the cutoff checks (R-hat 1.004, ESS 564, 0 divergences), the accuracy numbers and every 9:00 line estimate came out identical, so the model didn't change, but it does refit, which takes 2 to 4 minutes (196-207 s today; the earlier "under 2 min" was on an idle laptop).

Two problems the first run showed, both fixed in `predict.py` date and seed handling. The fitted model is untouched:
1. A snapshot covers exactly 8 days, so today's midday run cut Nov 14 off partway, leaving 1 performance at 1 theater. The site would have shown that as a nearly empty day. A last date that gets cut off is now left out.
2. With no new information, 9:00 chances moved up to 2.8 points and The Outsiders on Nov 7 went from GO (70.6%) to Maybe (69.5%). All days shared one stream of random draws, so dropping Nov 6 shifted every later day, and a daily sync would have done this every day. Each day now has its own seed. Test: a run with the clock set to 1 pm on Nov 7 matched today's file exactly on all 171 show-days.

Changing seeds moved the numbers one last time. Against the file from 2:12 am, on the 79 show-days with a chance in both: chance at 9:00 moved 0.7 points on average and 2.1 at most, arrival time moved 15 minutes on 21 and not at all on 58, and one verdict changed (Oh, Mary! on Nov 11, Maybe 69.7% to GO 70.1%). That one sits right at the placeholder 70% line. The show lists and performance times didn't change.

The click-through crashed once, right after these runs, and failed again on the rerun. It wasn't the site: 30 timed page loads all worked with no page errors, 29 of them in about 50-300 ms and one in 2.2 s, and my test only waited a fixed 1 second. It now waits for the page. Three runs in a row then passed 195 of 195.

Still open: only manual runs have saved anything. Rachel says the Actions list shows 3 runs, but the data repo has only 2 job saves, so one saved nothing. Still 61821ee at 12:28 pm ET, 21 minutes after the 12:07 pm scheduled time. Runs can start late, so I'm watching until 1:15 pm.

---

## 2026-11-06 13:44 ET — Daily job: 12:07 pm scheduled run saved nothing

The watch on the data repo ended at 18:44 UTC (1:44 pm ET), about half an hour past its planned stop. A fresh check then still showed `61821ee`, Rachel's button press, as the newest commit. That's 1 hour 37 minutes after the 17:07 UTC scheduled time, so three scheduled runs in a row have saved nothing: 23:07 UTC Nov 5, 12:07 UTC Nov 6 and 17:07 UTC Nov 6. Two of the watch's checks failed with "Could not resolve host", so the network dropped briefly, which doesn't affect this result.

I still can't tell whether the runs never started or started and saved nothing. That depends on the third run in the Actions list, which I've asked Rachel about. Next scheduled run: 23:07 UTC (6:07 pm ET).

---

## 2026-11-06 14:26 ET — Daily job: a Ticketmaster-only snapshot appeared

Rechecked at 2:26 pm ET. Commit `c43f4a5` reached the data repo at 19:09 UTC (2:09 pm ET), after my 18:44 UTC check, with one Ticketmaster file and no TKTS board. That's a new clue, because a manual run does both scrapers.

So it's one of two things. It could be the 12:07 UTC scheduled run starting 7 hours late, since only that schedule runs Ticketmaster alone. That would mean the schedule fires but can't be trusted on time. Or it could be a manual run where the TKTS step failed, since the job still saves what it got. The Actions list shows which: a row says Scheduled or Manually run, and has a green check or a red X. Asked Rachel to read that row.

Also checked from here, and none of these is the cause: the job file is on GitHub's default branch (`master`), it matches local, and all three cron lines are there. I did not copy this snapshot into `data/raw`. Its schedule date is the same as the predictions, so the site wouldn't change.

---

## 2026-11-06 14:32 ET — Daily job: why data went missing, and backup run times

Rachel reports all 4 runs in the Actions list are green. The data repo has only 3 job saves, so one green run saved nothing. I still can't read the logs, so this is reasoning from the evidence, not a confirmed cause.

What the evidence points to:
1. GitHub starts scheduled runs late. The 2:09 pm snapshot has Ticketmaster and no TKTS. A green manual run would have saved both, and the board had shows in all 2 of the snapshots we have from that hour. So it's most likely the 7:07 am run, about 7 hours late. That assumes nobody pressed the button then, which I've asked Rachel.
2. A late TKTS run can find an empty board. Across the 44 snapshots since January 2026, by ET hour: 18 of 18 had shows from 12:00 to 6:59 pm, 1 of 16 before 11 am, and 1 of 7 from 10 pm to midnight. Almost nothing was sampled from 7 to 10 pm. `scrape_live` then logs a warning, saves nothing, and the run stays green. That's the likeliest story for the fourth run, probably the 6:07 pm run on Nov 5. GitHub's status page shows an incident covering Actions from 6:36 to 7:20 pm ET that evening.

No code in the job was broken, and one day isn't much evidence. GitHub also listed Actions incidents on Nov 4 and Nov 5, so this may have been a bad stretch.

Choice I made: backup times, not skip logic. Ticketmaster now also runs at 9:07 am, and TKTS at 2:07 and 4:07 pm. That's up to 6 runs a day instead of 3, and up to about 1.2 MB a day in the data repo. I left out "skip if today's already saved" because extra snapshots do no harm and it would be more code to get wrong. I also didn't use an outside timer, because that needs an account and a token, which is Rachel's decision if backups aren't enough.

Also changed `sync` to warn when TKTS goes quiet, not only Ticketmaster, because a changed page layout would look the same as an empty board: green runs and no data.

Checks: the file parses as YAML (PyYAML installed to my scratchpad only, not the project). I evaluated the `if:` lines for all 6 times and the button: each scheduled run does exactly one source, and the button does both. `sync` ran for real and copied the 2:09 pm snapshot, and the predictions stayed as they were because the schedule date matched. Copy tests still pass 10 of 10. None of this tests GitHub's timing. That only shows after Rachel pushes, and it takes a real day to judge. Success means a day with at least 1 Ticketmaster and 1 TKTS snapshot and no button press.

---

## 2026-11-06 14:36 ET — Daily job: backup times pushed; limited-data numbers pulled

Rachel pushed the backup times as `029db5a` at 2:34 pm ET, and local and GitHub match. Rachel remembers pressing the button only around noon, though not for certain. That fits the 12:02 pm run, so the 2:09 pm snapshot was most likely the 7:07 am scheduled run starting late. The real test is a day with at least 1 Ticketmaster and 1 TKTS snapshot and no button press. Not checked yet.

Moved on to the limited-data shows (SPEC 9, questions 20 and 26). Pulled these read-only numbers to start the talk, with nothing built. Across the 6 shows there are only 3 recorded outcomes, so nothing can be tested on them directly. The site says "Limited data, probably easy" on all 6, including Hadestown at 95% seats sold and It's a Wonderful Life, which has no reports or grosses at all.

Rough TKTS counts, matched by show name, Broadway section, on the 20 days with a board since January 2026: Six 19, & Juliet 17, Hadestown 14, Downstate 2, It's a Wonderful Life 2, Wicked 0. For comparison, Hamilton and The Lion King show 0 and most of the well-reported shows 11 to 18, so it does separate shows. Whether it says anything about rush lines hasn't been tested.

---

## 2026-11-06 14:37 ET — Limited-data shows parked for later

Rachel decided the limited-data work is for later and asked for it on the list. Added my three ideas to SPEC 9, question 26, marked as not decided: new wording, a standing-room message, and a rough label tested by hiding well-reported shows. Nothing built. The site still says "Limited data, probably easy" on all 6 shows until this is decided, and I told Rachel so.

Next on my suggested order is the charts, worth 7 rubric points. Asked Rachel for a go before starting.

---

## 2026-11-06 14:39 ET — Can the model get better, or do we wait for data?

Rachel asked. Checked with a read-only look at the first version's test results and data counts. Nothing retrained or changed, and the 3 locked months weren't touched.

Waiting won't help much. At the Aug-Oct pace, the 17 days to Nov 23 add about 90 line rows (1.5% of 6,060), 6 ticket show-days (0.8% of 762) and 5 outcomes (0.8% of 669).

Where the model is weak, on the 9 test months:
- Tickets: the combo's middle estimate is 18 against a stated 6 on the 33 stated counts. People may mention a count more often when it's small, so this overstates the gap by some unknown amount.
- Telling hits from misses: given one attempt that got a ticket and one that missed, the combo ranks them correctly 60% of the time and the lookup 64%. 9 of the 16 misses were rated GO, and 6 of the 16 were at one show, Just in Time.
- The line is stronger, and its largest errors come in the last hour before the box office opens (combo 6.56 people, lookup 8.20).

Added one idea to SPEC 5.2c: a last step that adjusts the chance using real got-or-missed reports. Recommended the ticket upgrades and that step first, after the charts. None of this is tested yet, and level-ups still need Rachel's go.

---

## 2026-11-06 14:41 ET — Spec: show search; font sets shown (no code)

**Did:** added a search box to SPEC §2.2a and §8 at Rachel's request: find shows as you type, by name, nickname or theater. Showed Rachel six font sets on a sample tile in the site's current colors, using sample numbers. No code and no site changes from this chat.

**Why:** Rachel wants to find a show directly, and finds the current fonts ugly.

**Result:** the font sets are Poster (Bebas Neue + Barlow), Playbill (Playfair Display + Source Sans 3), Art deco marquee (Limelight + Work Sans), Ticket stub (Alfa Slab One + IBM Plex), Modern elegant (DM Serif Display + DM Sans), and Neon sign (Monoton for the logo + Poppins). I recommended Poster, because long show names fit and its numbers read well. Nothing goes in the spec until Rachel picks.

**My choices, for Rachel to check:** search covers nicknames and theaters as well as show names. If a match isn't playing on the picked date, the page says so and offers Any day.

**Next:** Rachel picks a font set, then I write it into SPEC §2.4.

---

## 2026-11-06 14:45 ET — Spec: fonts chosen (no code)

**Did:** Rachel chose the Poster set for headings and the Neon sign set for body. The first inline preview didn't work for Rachel, so I saved one to `C:\Users\rache\Downloads\broadway-rush-fonts.html`, opened it in Rachel's browser, and published a private copy as an artifact. Wrote the choice into SPEC §2.4 and §8, and closed §9 question 22. The site wasn't changed.

**Result:** Bebas Neue for headings and Poppins for body.

**My choices, for Rachel to check:**
- The logo, show names and big numbers count as headings, so they use Bebas Neue.
- Monoton, the Neon sign set's logo font, isn't used.
- Bebas Neue only has capital letters, so show names appear in all caps.

**Not checked:** I couldn't view the preview page myself, and Rachel hasn't seen these two fonts together, because the preview shows them in separate sets.

**Next:** the build chat applies the fonts when Rachel asks.

---

## 2026-11-06 14:51 ET — Charts: Rachel picked 8, build on hold

Rachel asked to see the chart ideas and choose before anything was built. Picked 8: line growth over time, show-by-day grid, predicted vs. actual, what drives the line, chance vs. what happened, cleaning funnel, rush savings, and reports per show. Not picked: seats sold vs. line, line vs. tickets, and the model vs. lookup scoreboard.

Where they go isn't decided (site, slide images or both). Rachel asked me to hold off until another prompt arrives, so nothing is built.

---

## 2026-11-06 15:12 ET — Fonts: Bebas Neue and Poppins

Rachel added the fonts to SPEC 2.4 and asked for them on the site. Bebas Neue now covers the logo, headings, show names and big numbers (chance %, prices, arrival time). Poppins covers everything else. Both load from Google Fonts.

Choices I made: base text went from 16 to 15 px because Poppins runs wide. Headings got larger because Bebas runs small. Bold is turned off on Bebas text because it has only one weight and browsers fake the rest. Fallbacks are Impact and Segoe UI, with Arial removed, since Rachel can't stand it. Without internet the site falls back to those.

One problem came from this: Poppins' width made the phone chart labels run together ("3:00 AM4:45 AM"). I spotted it in a screenshot, not from a check, and widened the label spacing.

---

## 2026-11-06 15:12 ET — Charts: show pages and Nerd stats

Rachel picked 8 charts and asked for plain ones on the show page plus a very organized "nerd stats" section built onto the accuracy page.

Show pages now have how the line builds (with its likely range and the arrival time marked), which days are busiest, and what you'd save.

The accuracy page is now Nerd stats, with jump buttons and five sections: the short version, how rush lines behave (line growth, show-by-day grid, rush savings), where the data comes from (cleaning funnel, reports per show), what the model looks at (what moves the line, how it's built), and how good it is (everything that was already on the page, plus predicted vs. real and chance vs. what happened). The old #/accuracy link still works.

New module `model/site_charts.py` counts the numbers for `predict.py` to add to the predictions file, so the site still reads only that file.

Choices I made:
- The name "Nerd stats" over "Learn more".
- Slide images weren't made, because Rachel's message didn't ask for them. Screenshots work for now.
- The show-by-day grid counts each past day once, however many people posted. So it differs from the preview I gave Rachel: 80 of 112 squares filled at 3+ past days, not 78 at 5+ reports, and Just in Time on Saturday is 29, not 25.
- Days a show isn't playing now show a dash, even if it played them in the past, like Just in Time on Mondays.
- Shows with fewer than 3 filled days are listed in a note, not as nearly empty rows: Wanted, 860, Paranormal Activity.
- Reports per show covers only the 22 shows with in-person rush.
- Any day mode shows savings but not busiest days, because that comes too close to the weekday numbers SPEC 9, question 23 holds back.
- The funnel's bars start at 18,412 reports, not 139,584 comments. They're different units, and the comments bar would have shrunk everything else.

Failures and fixes:
- The first install command was too long for the shell (ENAMETOOLONG), so I wrote the code to files.
- A stray bracket in the show-by-day grid broke the page code. `node --check` caught it, after the predictions had already been regenerated. That run wasn't wasted, because the module it depends on was fine.
- Looking closely at screenshots, I found my summary line on the chance chart quoted the best-looking band and skipped the weak one. When the model said about 97%, only 73% got a ticket (15 attempts). The line now states the worst band. Same kind of fix on predicted vs. real: it now says that when the model predicts 18-20, the real line is about 24, and when the lookup predicts 18-20, about 11.
- A note said shows with "fewer than 35" reports lost to the lookup. Only 10 to 34 were tested, so I corrected it.
- Other small fixes: 0-report shows drew a sliver of a bar, "Nov 25" read like a date (now Nov '25), and tall panels left holes (the page now fills columns).

Checks: 241 of 241 click-through checks pass, 0 page errors, at 390 and 1280 pixels; that's the earlier 195 plus new ones for fonts and charts. Chart colors passed the palette validator on the dark card (protan delta E 19.9), and the text on grid squares has contrast of at least 5.3. All 206 show-days match the predictions from before this work, so adding charts changed no prediction. Not tested on a real phone or in Safari.

---

## 2026-11-06 15:55 ET — Nerd stats tab and fonts didn't show for Rachel: browser kept old files

Rachel reported that the Nerd stats tab wasn't working and the font hadn't changed, right after I'd reported both as done. My mistake was in how I tested. Every test opens a brand-new Chrome profile with nothing saved, so it can't show what happens in a browser that already has the old site.

Reproduced it in Chrome, starting from the site before the charts (`029db5a`). After a normal refresh with the new files, the page came through new but the browser kept its saved old `app.js` and `styles.css`. The tab said "Nerd stats", the font was still Segoe UI, and clicking the tab landed on the home page because the old code didn't know that page. That matches both of Rachel's symptoms, though I can't see Rachel's screen, so it isn't confirmed there.

Telling Rachel to press Ctrl+Shift+R wasn't a fix. `web/index.html` now loads `styles.css?v=20261106b` and `app.js?v=20261106b`, so the browser treats them as new files. In the same test, a normal refresh then gave Poppins and the Nerd stats page. **The version has to change whenever those files change.** The click-through still passes 241 of 241.

My first run of this test was invalid. Rachel had committed the charts by then, so the "old" site already had the new code, and the test showed no problem. I reran it from the older commit.

---

## 2026-11-06 16:19 ET — Nerd stats: model vs. ground truth

Rachel asked to see the test results against the ground truth. We have them: the test saved every prediction next to what was reported. Added a sixth Nerd stats section with three charts (line, stated tickets, got a ticket or not), each with a Model / Lookup table switch, plus a table to look up any result by show or month, biggest miss first. Locked months aren't in these files, so they stay unscored.

Choices I made: dots are nudged slightly so they don't hide each other, and the page says so. One report over 60 people isn't drawn on the line chart, and the page says that too. The rows hold numbers only, with no usernames or comment text. The predictions file grew to about 1 MB; 15 timed loads had a median of 78 ms and a maximum of 420 ms on this laptop.

Problems found in screenshots and fixed: on phones the table cut off the model, real and miss columns (now fewer columns, with the date under the show name); dots in the attempts chart sat on the axis labels; there was a big gap beside the first chart (the attempts chart now runs the full width).

Findings:
- Every one of the 42 line misses of 20+ people was a real line longer than predicted. At 10+ it's 187 of 196. The model misses surges and doesn't badly overshoot.
- Tickets have a second side. On 33 stated counts the middle estimate is 18 against a stated 6, but on 122 "at least" days it cleared the minimum 95% of the time, and the lookup 62%.
- Of the 16 misses, 9 still had standing room, 5 sold out first and 2 had only full price left.
- Some ground truth looks wrong. Oh, Mary! on Mar 4, 2026 has 9 people, then 79 about 1.4 hours later. The Lost Boys on May 27 has 15 and 50 at the same time. Other big ones look real, like Schmigadoon! on Jun 6 with two reports at 55 and 60. I checked the numbers only and haven't read the comments. Nothing was removed.

Checks: 263 of 263 click-through checks pass, 0 page errors, at phone and desktop widths. All 206 show-days match the predictions from before this work. File versions are bumped to `20261106d`, so a normal refresh gets the new page.

Daily job: still at `c43f4a5` from 2:09 pm. The backup times were pushed at 2:34 pm, and the 4:07 pm TKTS backup hasn't saved anything as of 4:19 pm. Runs can start late, so the first real test is tomorrow.

---

## 2026-11-06 17:28 ET — Data cleaning, part 1: a full re-extraction failed its test, so a checker replaced it

Rachel asked for the data to be cleaned as well as possible and for as much data as possible, approving up to $5 of API money. "Don't care where it's from" doesn't override the rule on legal sources, because breaking a site's terms could put the competition entry at risk, and I told Rachel so. The budget is a hard cap in the code: $6.49 project total, which is the $1.49 already spent plus $5.

Where reports were being lost (15,728 in-person rush reports, 4,001 with no show):
- 2,999 had no show at all. The first pass saw only a comment and its parent, never the post title ("Oh Mary rush tix") or the rest of the reply chain.
- 867 had a show as written ("Buena Vista", "Dorian", "EBT") but a blank cleaned-up title, and the matcher only read the title. The nickname list already knew many of them. Fixed in `catalog.py`, for free.

First attempt, which failed: re-extract all comments with the extra context. Tested on the human-reviewed labels before the full run, for about 2 cents. Precision on observations fell from 80% to 61% on the hand labels (148 predicted vs. 101 real) and held at 77% on the holdout. Show accuracy fell on both sets. Reading the errors showed it was inventing reports: "only 5 people for the outsiders?" became a line count, against the prompt's own rule. Scrapped before spending the roughly $2.

Second attempt: keep the first pass and ask only for a verdict on each report (keep, fix or drop). It can't add reports. Scores on the human-reviewed labels:
- Hand labels: precision 73% to 82%, recall 87% to 84%.
- Holdout labels: precision 79% to 93%, recall 93% to 93%.
- Sonnet 5.5 cost about 8 times as much and wasn't clearly better (holdout 92% and 85%), so I used Haiku 5.5.
- Show accuracy looks flat or slightly lower, but several of those "errors" are shows filled in from context the human labelers never saw.

One guard came from reading its changes: it moved already-stated dates and was wrong as often as right, so it may only fill blank dates now. Every verdict and reason is kept in `label_audit.csv`, and the first pass stays untouched.

Submitted the check of all 10,396 comments with reports: estimate $1.14.

More data, from the already approved Arctic Shift archive: Reddit refreshed through today (+50 comments), and added fan subreddits r/Hadestown, r/wicked, r/SixTheMusical, r/andjuliet, r/hamiltonmusical, r/TheOutsidersMusical, r/BroadwayTickets and r/theatre, because the limited-data shows barely appear in the daily threads.

Not yet known: whether any of this makes the model better. The test will compare new and old on the same test reports, because cleaning the test answers would otherwise flatter the score.

---

## 2026-11-06 19:28 ET — Data cleaning, part 2: the checked data barely moved the model's scores

Checked all 10,396 comments with reports for $1.16. Results: 10,339 reports kept, 4,457 fixed or filled, 3,596 dropped (1,641 quoted from the parent, 835 not a report, 460 other, 353 vague, 227 questions, 45 hypothetical, 28 plans, 7 jokes). Project spend $2.85.

I read random samples myself; these are my reads, not human-reviewed labels. About 23 of 24 sampled drops looked right. The main finding is that the first pass had been copying the parent's numbers into replies ("How were your seats?" became a line count). Fixes also caught invented show names (BOOP became Bells Are Ringing, HK became Hadestown, lost boys became Peter Pan Goes Wrong) and morning times read as evening. Two bad habits got guards: shifting stated dates and filling blank times with the posting time.

Free rule added: a report can't describe a time later than when it was posted, so "16:45" posted at 9:30 that morning is 4:45 am. It fixed 42 reports.

Also fixed a mistake of mine. I told Rachel the Oh, Mary! Mar 4 line of 79 looked like a bad report. The comments say "around 80th in line! $5 tickets secured" and "They had 165 $5 tickets", so it's real: a special $5 day. The checker kept it. This is why reports must not be deleted for looking surprising.

Data after the check and nickname fallback: line reports 6,060 to 6,618, ticket show-days 762 to 948, attempts with a known result 669 to 865, share who got a ticket 87.3% to 85.7%. A bug in my collect step crashed partway, so I removed its 20 partial ledger rows and 195 partial results before re-collecting; the spend is counted once.

Test on the same 9 months, tag `clean1`. It took 1 hour 54 minutes against 8.4 minutes before, and I piped its output so its progress was hidden, repeating an earlier mistake. Compared on identical test reports, so cleaned answers can't flatter it:
- Line error: 4.74 to 4.69 on 1,408 shared reports (lookup 5.87 to 5.85). Within 3 people: 55.5% to 55.0%. Range held: 86.6% to 86.5%.
- Stated tickets: 11.72 to 11.93 on 29 shared counts (lookup 6.34 to 5.38).
- Chance: Brier 0.090 to 0.091, ranking 0.598 to 0.580 on 127 shared attempts (11 misses).

As each test scored itself, on its own rows: arrival-time error 102 to 93 minutes (lookup 95 to 101), so the model now beats the lookup on arrival time. These are different rows, so that's weaker evidence. The test now has 182 attempts and 20 misses, up from 138 and 16.

Plain conclusion: cleaning made the data more correct and larger, but it didn't make the model meaningfully more accurate. The model's misses aren't mainly caused by label noise. Keeping the cleaned data anyway, because it's more truthful and no score got meaningfully worse.

r/theatre stalled (about 1,000 posts in 70 minutes, low yield), so I dropped it. Stopping the wrapper left its python process running. My attempt to stop that process was blocked by the permission system, so I asked Rachel to stop it.

---

## 2026-11-06 21:47 ET — Data cleaning, part 3: added sources, final test, site updated

Added sources: seven show-fan subreddits and BroadwayWorld's forum (47 rush threads, 232 posts, found through its public sitemap because the search page is disallowed). Registered in `registry/sources.csv` before fetching threads. Talkin' Broadway's All That Chat is skipped: bot protection. The overlapping fetches left about 6,000 duplicate comment rows, which I removed. My stop command on the scan left its child process running and a second fetch started when it ended, which is where the duplicates came from.

New first-pass and check runs cost $0.07 for 3,266 comments, of which only 75 held any report. Sample of 1,000 comments the pre-filter skipped: 9 had anything, 4 of those general rush with a number, and the examples I read looked mostly false. The filter stands; reading all 91,000 would cost about $2.60 for mostly junk. Project spend $2.95, which is $1.46 of the $5 approved.

Not gathered: Reddit before June 2024. It exists in the archive but needs grosses and calendar backfilled too, and the results below suggest little gain. Rachel can overrule this.

Final test, tag `more1`, 56 minutes, progress visible this time. Added data: +66 line reports, +8 ticket show-days, +7 attempts, on top of cleaning. Hadestown 15 to 22 line reports, 860 9 to 17; no show changed prediction group.

Compared with the first test on identical reports: line error 4.74 to 4.69 (lookup 5.87 to 5.84), within 3 people 55.4% both, 80% range held 86.6% to 86.1%; stated tickets 11.72 to 11.50 (lookup 6.34 to 5.38); Brier 0.090 both, ranking 0.598 to 0.578 on 127 attempts with 11 misses. Compared with `clean1`, nothing moved: the added sources did nothing measurable.

On its own reports (1,711 line reports, 42 stated counts, 182 attempts, 20 misses): line 4.71 vs. lookup 5.96; arrival 96 vs. 100 minutes, a win it didn't have before; tickets 15.8 vs. 8.5; right at 50% 87.9% vs. always yes 89.0%; Brier 0.105 vs. 0.093.

Decision: use this data. It's more truthful and larger, and no score got meaningfully worse. The ranking drop is about 2 points on 11 misses, which is within noise but is the one number to watch.

Site regenerated with `predict --backtest more1`. Compared with the file before cleaning, on 94 show-days: chance moved 3.0 points on average and 11.2 at most, arrival moved 13 minutes on average and 60 at most, and 4 verdicts changed (Chicago on Nov 7 and 9 and The Lost Boys on Nov 7 to Maybe; Operation Mincemeat on Nov 11 to GO). The line spread went from 1.40 to 1.81. Cutoff fit passed its checks: R-hat 1.012, ESS 497, 0 divergences, and it now takes about 8 minutes.

Two stale hard-coded numbers replaced with values from the data: "139,584 comments" (now 152,801 comments and forum posts) and "89%" (the wider count is now 87.1% of 1,493). The panel is renamed "The always-yes problem". File versions bumped to `20261106e`. Click-through 263 of 263, 0 page errors.

The stay-awake hold had never worked: `0x80000001` fails a cast in PowerShell on every call. Fixed with `[uint32]2147483649`, confirmed from its return value, and stopped now that the run is done.

## 2026-11-08 ET — Daily job confirmed; model upgrades on hold

The daily job passed its test on Nov 7: with no button press (Rachel confirmed), it saved Ticketmaster at 12:40 and 1:35 pm ET and TKTS at 3:48, 5:41 and 7:29 pm ET. GitHub started the 7:07 and 9:07 am runs about 5 hours late, which doesn't matter because the schedule doesn't change during the day. One TKTS slot saved nothing (skipped by GitHub or an empty board; the Actions log is private).

Ran `broadway_rush.sync`: 5 new snapshots copied in, predictions refit in 7 minutes (R-hat 1.012, ESS 497, 0 divergences, phi 1.81), site now Nov 8–14. Nov 9 has 4 performances because it's a Monday. Click-through 263 of 263, 0 page errors.

Rachel put model upgrades on hold to wait for more data. Note for when they restart: the daily job collects ticket snapshots, which the model doesn't use yet; new rush reports only come from refreshing Reddit, which is by hand until the weekly job. Upgrades were scheduled for Nov 17–19 anyway.

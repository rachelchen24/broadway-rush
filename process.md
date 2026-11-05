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
2. **Step 4 done** (4a source check, 4b grosses + policies, 4c show catalog, 4d policy history + website scope decision). Weekly refresh: `.venv\Scripts\python -m broadway_rush.scrapers.playbill grosses`, `... playbill policies`, `... broadwayworld grosses`, then `.venv\Scripts\python -m broadway_rush.catalog build`. After any `batch reports`, re-run `catalog build` (it adds show_id to reports.csv). **Step 5 (baseline model) waits for Rachel's go-ahead.**
2b. **Step 6 started early** (ticket-site rules + TKTS scraper; see the step 6 entry). TKTS + Ticketmaster scrapers built, daily job written (2026-11-05 entry below). Waiting on Rachel: commit both repos, add the token and secrets, run the first test. Then the remaining data sources, then step 5 (model). The data refresh plan changed on 2026-11-02 (SPEC §6; entry below).
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

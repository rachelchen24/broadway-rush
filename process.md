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

**Next:** re-run `full` after the scraper finishes (new comments + 2 failed chunks). Then step 4 (weekly grosses + rush policies + show catalog), after checking the sources' robots.txt/ToS.

---

## ▶ Open items (as of 2026-10-22 ~12:45)
1. **Reddit comments scraper still running** as a detached Windows process (started 11:35; ~1,300 keyword posts were left, ~3 h). Check progress: last lines of `data/raw/_state/scrape.log`. If it stopped, resume with `.venv\Scripts\python -m broadway_rush.scrapers.reddit comments` (run only one copy at a time; skipped/failed posts are retried automatically).
2. **When it finishes:**
   - `.venv\Scripts\python -m broadway_rush.extraction.batch full --dry-run`, then `full` (new comments + 2 failed chunks; ~$0.15), then `collect`, then `reports`.
   - Run `.venv\Scripts\python -m broadway_rush.scrapers.reddit summary` and write the final step-1 numbers here and in interview-notes.md.
3. **Step 4 is waiting on Rachel's go-ahead.** First task: check robots.txt + ToS for Playbill, BroadwayWorld, IBDB, and log them in `registry/sources.csv` (free, nothing scraped). Then backfill weekly grosses + rush policies + build the show catalog (it also canonicalizes the 346 show-name variants in `reports.csv`).
4. **Notes for future sessions:**
   - LLM spend ledger: `data/interim/llm_spend.csv`; hard stop $8, $1.34 spent.
   - API key lives in `.env` (git-ignored); the variable name must be `ANTHROPIC_API_KEY` (underscores).
   - Never run `data/labels/claude_prelabels*.py` again: they overwrite the reviewed label sheets (the holdout one refuses; the first one does not).

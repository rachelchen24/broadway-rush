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

**Next:** Rachel reviews the labels → re-score (free). Score v2 on a fresh held-out set → full run via the Batches API (step 3).

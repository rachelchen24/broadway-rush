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

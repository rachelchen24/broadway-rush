# Broadway Rush

**Is it worth getting up early for Broadway rush tickets, and which box office gives you the best shot?**

## About the project

Broadway Rush predicts whether it's worth getting up early for rush tickets: the $40–50 same-day seats some Broadway shows sell when the box office opens. No dataset of rush lines existed, so I built one. I scanned 153,378 Reddit comments from r/Broadway (June 2024 to November 2026) and used a large language model (Claude Haiku, about $3) to turn them into structured reports like "12 people in line at 8:30" or "got one at spot #9." I checked the extraction against human-reviewed labels and cleaned it into 15,044 reports across 108 shows, joined with box-office grosses, schedules, rush policies and TKTS discount boards.

The model has two parts:
- **Line length:** gradient-boosted trees (LightGBM) predict how long the line is at each hour before opening.
- **Ticket count:** a Bayesian negative-binomial model (NumPyro) estimates how many rush tickets a show releases. It learns from stated counts and from "at least" and "at most" clues.

Together they give your chance of a ticket at any arrival time. I tested each group of inputs by removing it and kept 14 of 37. Every score comes from a rolling backtest that trains only on earlier months and is compared against a simple lookup-table baseline.

---

## Results

Two scores, both from rolling backtests where each month is predicted using only earlier months. All choices were made on the 9 test months. Three months (Dec 2025, Apr 2026, Aug 2026) were locked away until the end, then scored once on the final model.

| Measure | Model, 9 test months | Lookup, 9 test months | **Model, 3 locked months** | **Lookup, 3 locked months** |
|---|---|---|---|---|
| Line length, average miss | **4.53 people** | 5.93 | **4.60 people** | 5.67 |
| Real lines inside the 80% range | 86% | 59% | 87% | 63% |
| Tickets, average miss on stated counts | 9.9 | **5.2** | 8.9 | **4.1** |
| "Got one at spot #N": estimate was at least N | **95%** | 70% | **92%** | 75% |

The test months have 1,707 line reports, 41 stated counts and 160 "got one at #N" days. The locked months have 648, 15 and 73.

- **The line model clearly beats the baseline,** in every locked month too. Its error barely moved from the test months to the locked ones, so the choices weren't luck.
- **Tickets are mixed:**
  - Stated counts skew small, because people mostly post a count when it's low ("only 6!"). That rewards the lookup table's low guesses.
  - On the far more common "got one at #N" days, the model is right far more often.
- **What the site shows:**
  - The ticket number comes from the lookup table, because it's closer on stated counts.
  - The model's ticket estimates drive the chance of a ticket.
- **Sold-out clues:** adding "sold out at 10:30, with N people in line shortly before" as "at most N" clues cut the model's ticket error by 11%.

## How it works

```
Reddit comments ──► LLM extraction ──► cleaning + checks ──► 15,044 reports
                     (Claude Haiku,      (second-pass checker,
                      batch API)          special days removed)
                                                  │
grosses, schedules, rush policies, TKTS, ──► daily features (only what's known
holidays, cast changes, transit, foot traffic     7 days ahead: no peeking)
                                                  │
                          ┌───────────────────────┴───────────────────────┐
                 line model (LightGBM)                     ticket model (Bayesian NB, NumPyro)
                 people in line by hour                    rush tickets released that day
                          └───────────────────────┬───────────────────────┘
                                   chance of a ticket at each arrival time
                                                  │
                                    website: shows ranked for each day
```

1. **Data collection** (`src/broadway_rush/scrapers/`):
   - Reddit (via the Arctic Shift archive)
   - Playbill (grosses, rush policies, weekly schedules)
   - Ticketmaster Discovery API (performances)
   - the TKTS discount board, collected by a GitHub Actions job several times a day
   - MTA subway ridership
   - Times Square Alliance pedestrian counts
   - Wikimedia page views and BroadwayWorld casting news (stars and cast changes)
   - NYC permitted events, weather and school calendars
2. **Extraction** (`src/broadway_rush/extraction/`): the Claude Haiku Message Batches API reads each comment with its parent and returns typed observations:
   - line counts, arrival times and line positions
   - outcomes
   - stated ticket counts and sell-out times

   I scored it against a hand-reviewed answer key. On 50 held-out comments it was right about whether a comment held a report 94% of the time, with 77% precision and 87% recall on individual observations. Reading the errors led to prompt fixes, and a second-pass checker raised precision further.
3. **Cleaning** (`src/broadway_rush/catalog.py`, `model/table.py`):
   - show-name matching
   - date and a.m./p.m. fixes
   - removing duplicates
   - removing one-off events such as dress rehearsals and $5 days (`registry/special_rush_days.csv`)
4. **Features** (`model/table.py`): every input uses only information available 7 days before the date. Grosses are at least 9 days old.
5. **Models** (`model/line.py`, `model/cutoff.py`):
   - LightGBM for the line.
   - A hierarchical negative-binomial model for tickets, fitted with NUTS. Shows share information, so thin shows borrow strength from the rest. It learns from exact counts plus censored ("at least" and "at most") labels.
6. **Evaluation** (`model/backtest.py`, `model/compare.py`, `model/dropone.py`):
   - rolling-origin backtest
   - identical test reports for every model compared
   - drop-one tests for every input group
   - a "keep" rule: removing an input has to hurt by more than the month-to-month noise
7. **Website** (`web/`): a static site that ranks shows by your chance of a ticket. It has a 7-day view, filters, show pages, and a "Nerd stats" page with the test results and charts.

## Repository layout

```
src/broadway_rush/   scrapers, extraction, model, site build
registry/            hand-kept facts: show names, special days, deals, stars, sources and their terms
data/processed/      cleaned tables and backtest results (no usernames, no comment text)
data/interim/        extraction outputs and test logs
web/                 the website (static HTML/CSS/JS + predictions.json)
docs/                labeling guide, slides
presentation/        poster, slides and visuals for the NYU Project Expo
```

## Running it

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[model]"   # Python 3.12+
python -m broadway_rush.model.table                    # build the model tables
python -u -m broadway_rush.model.backtest --per-person 1.0 --features v2 --cutoff v1 \
    --drop $(cat data/interim/lean_drop.txt) --soldout --tag lean_so2   # test on past months (~1 h)
python -m broadway_rush.model.compare lean_so2 more1   # compare runs on identical reports
# same backtest command plus --final scores the 3 locked months instead (run once)
python -m broadway_rush.model.predict --per-person 1.0 --backtest lean_so2 --final final_locked
python -m broadway_rush.sync                           # pull new snapshots and refresh predictions
python -m http.server 8000 --directory web             # view the site
```

API keys for re-scraping or re-extracting go in a `.env` file: `ANTHROPIC_API_KEY` and `TICKETMASTER_API_KEY`. The published tables are enough to run the model without them.

## Data, privacy and credits

- **Reddit:**
  - Reports come from public r/Broadway comments.
  - The repository doesn't include usernames or comment text. Comment IDs are kept so that each report can be traced to its public source.
  - Raw scrapes are not included.
- **Times Square Alliance:** daily pedestrian counts shared with permission, on the condition that they're credited and the raw counts aren't published. Only derived inputs appear here.
- **Ticketmaster:** performance schedules and show images come from the Discovery API. Images are linked from Ticketmaster's servers, not stored.
- **Other sources:** Playbill, BroadwayWorld, TDF (TKTS), MTA, Wikimedia, NYC Open Data. Every source and its terms are listed in `registry/sources.csv`.

Built by Rachel Chen for the NYU Center for Data Science Project Expo, 2026.

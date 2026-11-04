# Broadway Rush — Spec (draft)

> Status (2026-11-02): build steps 1–4 are built (Reddit scrape → labeled extraction pilot → full extraction into `data/processed/reports.csv` → grosses, rush policies + history, show catalog). Step 6 was moved up: the TKTS and Ticketmaster snapshot scrapers are built, but the daily schedule isn't set up yet. Steps 5 (model) and 7 (website) aren't started. What was built, and how, is in `process.md`. ~~Struck~~ text was replaced; anything not marked built is still a plan.
> Standalone project: nothing is reused from previous projects.

## 1. Concept

**Is it worth going to the box office this morning for rush, and which show gives me the best shot?**

**Why / who**
- Built for me: I love shows but never know what to expect at the rush line.
- A **portfolio ML project**.
- Used by family and friends if it proves accurate. Not designed for a large user base, so no need to optimize for scale, accounts or heavy spam protection.
- **Used now and then:** I might not check it every day, or even every week, so nothing should depend on someone visiting daily (§6).

**Product:** a **website**. No sign-in, no accounts, no notifications.

**Shows covered:** **Broadway only**, musicals **and plays**. No off-Broadway.

**Scope**
- **In-person general rush** (main output) and **digital rush** (secondary output, §3.5). **SRO** is collected in user reports (§3.10) but not predicted (yet). Lotteries and student rush are out of scope.
- **Horizon: the next 7 days.** Predicting weeks out would be extrapolation and isn't the point of the app.
- **Day-of use is fine:** if someone checks at 8 am on the day, show everything (the latest snapshot, recommended arrival time, digital rush).

## 2. User flow & UI

### 2.1 Flow
1. **Pick a day** (any of the next 7). No time yet.
2. See **every show playing that day as tiles**, ranked **top to bottom by likelihood of getting rush**.
3. *(Optional)* check the shows you're interested in to filter or pin them. Predictions are precomputed by the weekly job (§6.1), so this is instant and there's **no need for a 5-show limit**. Refresh (§6.3) re-checks ticket data for all shows at once in seconds, so it doesn't need a limit either.
4. Tap a tile → details for that show's performance(s) that day (matinee vs. evening, if both).

### 2.2 Tile (one per show)
- Show name (+ theater, small)
- **Rush price** (e.g. $49.50; per show, §3.4)
- **Worth-it bar** + verdict word (GO / Maybe / Stay home)
- Chance of getting a ticket (e.g. "72%")
- Recommended arrival time ("Get there by 9:20")
- Small badges: `Digital rush 9 AM`, `Star leaving Sunday`, `Low confidence`, `Prices way above usual`

### 2.3 Details view
> We're **__%** confident there will be **__ ± __** rush tickets at **$__**.
> Get there by **__:__** for the best chance of getting one.

- **Always show the arrival time**, even when it's absurd (e.g. 6 am). A 6 am time almost certainly means the bar is red, but people who want it badly enough deserve to know.
- **Confidence slider (hidden by default):** an "Adjust confidence" button reveals a slider (e.g. 50%–95%) that widens or narrows the ± range live. Hidden so casual users only see the verdict and a default (e.g. 80%). It's cheap to build: the model outputs a full distribution, so the slider just reads different quantiles.
- **Digital rush section** (only for shows that offer it):
  > Digital rush opens at **9:00 AM** on **TodayTix** for **$__**.
  > Usually sells out in **__ min**. Be in the app **__ minutes early**: it opens right at 9.

  "__ minutes early" is fixed advice, not predicted. Only the sellout time comes from the model.
- **Why this prediction:** a few plain-English drivers ("On the TKTS board at 40% off today → softer demand", "Saturday matinee, school break → longer lines").
- **Combo hint:** a user can do the 9 AM digital rush for one show and *then* walk to another show's box office.

### 2.4 Look & feel
- **Purple theme** (deep purple), with text in **glowing / illuminated light colors** (neon-marquee feel).
- **Worth-it bar: red → blue.** Red = stay home, blue = GO. Fits the purple theme better than red → green, with purple in the middle as "Maybe."

### 2.5 Report button
- A **floating button on the side** with a **form icon**, labeled **"Report rush availability"**.
- Opens the report form (§3.10).

### 2.6 Accuracy page ("How accurate have we been?")
- Public page tracking predictions vs. verified outcomes over time.
- Shows the results table (§5.3), e.g. "our 80% ranges contained the real number 78% of the time" and "GO verdicts worked out 8 out of 10 times," plus a chart of accuracy over time.
- Great for the portfolio, and tells family and friends whether to trust it.

### 2.7 Shows with no data
- **Skip a show if there's genuinely no data** (no reports, no prices, no grosses). It just isn't shown for now.
- Shows with *some* data (e.g. prices + grosses but no Reddit reports) still get a prediction, labeled `Low confidence` (§5.1).

## 3. Data sources

**Principles**
- This is an ML project: **find out as much as physically possible**, from **June 2024 onward**. Older data is out of scope: rush policies differed, and earlier years are distorted by COVID.
- **Scrape every ticket site that is legal to scrape** (§3.11 decides that per site).

### 3.0 Show & performance catalog (the backbone) ✅ history built · next-7-days schedule partly built
A dataset of **every show playing and every performance** for the next 7 days, plus history back to June 2024.
- **Fields:** show, theater, address, open/closing dates, each performance's date/time, which seller sells it (Telecharge / Ticketmaster / other), official site URL, rush policy link.
- **Sources:**
  - **Playbill's "Weekly Schedule of Current Broadway Shows"** grid: shows × days with performance times (and "DARK" days). Scrape weekly.
  - **Each show's official site and seller calendar:** the source of truth for exact performances, including holiday changes and cancellations. Playbill itself says to confirm there.
  - ~~**Broadway League / IBDB:** show list, theater, opening and closing dates.~~ **Skipped (2026-10-22):** both sites' ToS forbid automated harvesting. Show list and theaters come from the weekly grosses tables instead (§3.3).
  - **Ticketmaster Discovery API (official):** lists events, venues and dates for Ticketmaster-sold theaters. Cross-check.
    - **Built 2026-10-22** (`scrapers/ticketmaster.py snapshot`): next 8 days → 362 Broadway performances at 40 of 43 theaters (missing: Sondheim, Todd Haimes, Vivian Beaumont), with sale status. No prices or seat counts for Broadway. Daily for now; only on Refresh after launch (§6.2).
- **Built 2026-10-22 (history part):** `broadway_rush/catalog.py` → `data/processed/shows.csv`: 118 productions with `show_id`, theater, Musical/Play, first/last grosses week, seats, and Playbill + BroadwayWorld IDs. Free-text show names (Reddit reports, policies) are mapped to `show_id` by normalized name + hand aliases (`registry/show_aliases.csv`) + close spelling, and only count if the show was on Broadway that date: 97% of named reports are mapped. The forward-looking performance schedule (next 7 days) is still to build.
- **History:** grosses (§3.3) say which shows ran each week since June 2024. The weekly Playbill grid can be backfilled from archived copies if available.

### 3.1 Reddit testimony ✅ verified accessible
- **What:** r/Broadway's **daily rush reporting threads** (posted by u/BroadwayRushReport under 25+ title formats), June 14, 2024 onward: **790 threads, ~13.6k comments** (median 14 per thread).
- **How (built, `broadway_rush/scrapers/reddit.py`):** reddit.com blocks unauthenticated API calls (403). The **Arctic Shift** archive (`arctic-shift.photon-reddit.com/api`) serves posts and comments without credentials.
  - Daily threads = every r/Broadway post by u/BroadwayRushReport (author search). Title search was unreliable and was dropped.
  - Keyword posts = a date scan of each subreddit, with keywords matched locally (whole words, title + body).
  - Comments: `GET /comments/search?link_id=<post id>`, paged.
  - Rate limit: about 10 requests/min. Its "Timeout. Maybe slow down a bit" error comes back as **HTTP 422**; wait for `x-ratelimit-reset`. Survives Wi-Fi drops, laptop sleep and server outages. Resumable.
- **Widen the net (June 2024+):** keywords `rush, lottery, standing room, SRO, digital rush, TodayTix, box office, line` across r/Broadway, r/musicals, r/AskNYC, r/nyc (~251k posts scanned → 11.3k keyword posts). Comments are fetched only for title matches or non-"line" body matches; in r/nyc and r/AskNYC the post must also look theater-related.
- **Output:** `data/raw/posts.csv`, `data/raw/comments.csv` (git-ignored). **Complete as of 2026-10-22:** 12,123 posts → 139,584 comments.
- **Then:** LLM extraction into structured rows (§4).
- **Ongoing:** re-scrape **weekly** (changed 2026-11-02), then extract the new comments and retrain (§6.1).

### 3.1b Other testimony (June 2024+)
- **BroadwayWorld forums:** long-running per-show rush and lottery threads. Public HTML, so scrape gently.
- **TikTok / Instagram / X:** lots of "I got rush" content, but most ToS forbid scraping. Use official APIs only, or skip.

### 3.2 Primary seller availability ⚠️ no history exists
- Ticketing sites only show current inventory, so past availability can't be looked up.
- ~~**Plan:** for every performance in the next 7 days, snapshot seats available (by section and price) at T−7d … T−1d, plus morning-of.~~ **Not possible legally (2026-10-22, §3.11):** Telecharge, Broadway Direct and Lucky Seat block bots, and Ticketmaster's website bans automated access. Ticketmaster's Discovery API is allowed but has **no seat counts or prices for Broadway**, only each performance's sale status (`onsale` / `offsale` / `cancelled`) and sales end time.
- **What we snapshot instead:** Ticketmaster sale status for the next 8 days (an early `offsale` may mean sold out; to test) and the TKTS same-day board (§3.8).
- **When:** daily for now, to build training data; after launch only when someone clicks Refresh (§6.2).
- **Sellers:** Telecharge (Shubert theaters), Ticketmaster (Nederlander, Jujamcyn/ATG and others), show official sites, Broadway Direct. Map each theater to its seller in §3.0.

### 3.3 Capacity / grosses — historical demand proxy
- **What:** the Broadway League's **weekly grosses per show**: gross $, attendance, **capacity %**, **average paid admission**, **top ticket price**, number of performances. Covers all of June 2024 → now.
- **How:** Playbill and BroadwayWorld republish the weekly table as HTML. Backfill every week since June 2024, then keep scraping weekly.
  - **Checked 2026-10-22:** `playbill.com/grosses?week=YYYY-MM-DD` (week-ending Sunday) serves any week back to 1985 as one HTML table: show + theater, gross / potential, avg / top ticket, seats sold / seats in theater, perfs / previews, % capacity. About 125 requests for June 2024 → now. BroadwayWorld (`/grosses.php`) is the backup; its Excel export is disallowed by robots.txt, so we never use it.
  - **Built 2026-10-22** (`scrapers/playbill.py grosses`, `scrapers/broadwayworld.py grosses`): 125 weeks × ~32 shows = 4,024 rows from each, agreeing to within 0.02% on weekly totals. BroadwayWorld adds show type (Musical/Play). Output: `data/raw/grosses_playbill.csv`, `data/raw/grosses_bww.csv`.
- **Why it matters extra:** average paid admission and top price are a **price history back to June 2024**, which the snapshot sources can't give us (§3.8).
- **Limits:** weekly, not per performance.

### 3.4 Rush policies per show (price varies!) ✅ built
- **What:** per show: **rush price** (often $49.50, **but not always**), box office open time, tickets per person, which performances offer rush, cash/card, seat location, **SRO policy**, digital rush details (§3.5).
- **How:** ~~BroadwayWorld's listing as the main source~~ **Playbill's "Broadway Rush, Lottery, and Standing Room Only Policies" article** is the main source (2026-10-22: no dedicated BroadwayWorld page found). It lists per show: theater, type (rush / digital lottery / SRO), price, how, time, payment, ID, tickets per person, seat locations, special policies. Cross-check with each show's official site. Re-scrape weekly.
  - **Built 2026-10-22** (`scrapers/playbill.py policies`): one row per show × policy type (price, how, where, time, payment, ID, limit, seats, tickets available, special policies) → `data/raw/policies_playbill.csv`. First snapshot: 56 policies, 28 shows. Each run keeps a dated copy, so history builds up from here.
  - **History (built 2026-10-22):** `playbill.py policies-history` pulls monthly Internet Archive captures (public CDX API) back to June 2024: 30 snapshots. Finding: in-person rush prices were nearly constant (median $45 every month; 5 of 61 shows changed), so `effective_from` = the snapshot date is enough. What changes and matters is **whether** a show offers in-person rush (Harry Potter dropped it, & Juliet and Wicked added it). See `process.md` step 4d.
- **Keep history:** store each policy with an `effective_from` date so old reports match the policy in force at the time.
- **Data quality:** flag source disagreements for manual review; show "last verified" next to the price.

### 3.5 Digital rush
- **What it is:** first-come, first-served rush sold in an app on the day of the performance. Mostly **TodayTix**. Not the same as a digital *lottery* (Telecharge, Broadway Direct, Lucky Seat), which is out of scope.
- **Timing:** most often **9 AM day-of** on TodayTix; varies by show, so store it per show (§3.4). Check whether TodayTix still requires a one-time social share to "unlock" rush.
- **Price/limits:** around $49–53, 2 per person, credit card, ID at pickup. Per show.
- **Columns:** `has_digital_rush`, `digital_rush_platform`, `digital_rush_time`, `digital_rush_price`.
- **What to predict:** P(getting one if you're in the app at open), and how fast it sells out.
- **Labels:** Reddit ("gone in 20 seconds", "got it at 9:03"), and, if TodayTix's terms allow, checking the show page right after 9 AM to record when it flips to sold out. Never any automated purchasing or queue jumping. **TodayTix is on hold (2026-10-22, §3.8):** its terms ban automated downloading, so ask them before any scheduled use.
- **Expect thin data.**

### 3.6 Calendar features
- Day of week, **day of month**, matinee/evening, holidays, school breaks (NYC public schools, colleges), Tonys week, weeks since opening, closing announced.
- **Weather:** historical daily weather and 7-day forecasts from free APIs (Open-Meteo, NOAA).

### 3.7 Later-in-day releases ("come back later") 💡 idea
- **Observation (from a box office visit):** told "no tickets right now, but come back later today, there might be some."
- **Why:** held seats get released during the day: house seats / producer holds, press and VIP holds, unsold group blocks, returns, and cleared blocked seats.
- **Open question:** released at rush price or only full price? **Ask at the box office on the next rush run.** Also mine Reddit for it.
- **Possible v2 feature:** a "second chance" line ("Morning rush likely gone by 10:15. Returning around __ pm has a __% chance").
- **Online signal:** ~~day-of snapshots may show seats reappearing~~ no legal source shows seat counts (§3.2). Maybe a Ticketmaster performance flipping from `offsale` back to `onsale`; otherwise only Reddit and user reports.

### 3.8 Prices vs. historic highs & lows ⭐ narrowed: no legal resale source
- **Idea:** compare a performance's current prices with that show's own history. "Resale is at its lowest since March" = soft demand = shorter line. "Prices at all-time high" = hot.
- ~~**Sources to snapshot daily:** resale (StubHub, SeatGeek, Vivid Seats, Gametime, TickPick), primary (Ticketmaster, Telecharge, official sites), discount (TodayTix, TKTS); SeatGeek and Ticketmaster APIs first.~~ All ruled out by the rules check below, except TKTS.
- **Rules check (2026-10-22, `registry/sources.csv`):** every resale site is out. StubHub and TickPick ban scrapers in their terms; SeatGeek, Vivid Seats and Gametime are blocked or disallowed. Telecharge, Broadway Direct and Lucky Seat block bots. **Usable:** TKTS board (scraped: `scrapers/tkts.py`, plus 117 archived days since June 2024), Ticketmaster Discovery API (sale status only: **no price ranges for Broadway**, checked 2026-10-22), TodayTix MCP (on hold: terms vs. agent guide; at most for user-initiated refresh).
- **So the price signals are:** **average paid admission and top ticket price from the weekly grosses (§3.3)**, back to June 2024, plus **TKTS discounts** (which shows are on the board, and how much off).
- **Features:** `avg_ticket_vs_show_median`, `top_ticket_percentile_in_show_history`, `on_tkts_today`, `tkts_discount_pct`, `share_of_days_on_tkts_30d` (needs regular snapshots, §6.2). ~~`resale_listing_count_change_7d`~~ (no legal source).

### 3.9 NYC context ("what's going on in the city")
There's **no single site that lists everything** happening in NYC, so combine several:
- **NYC Open Data — "NYC Permitted Event Information"** (dataset `tvpp-9vvx`, Socrata API): approved permitted events (street fairs, parades, races, film shoots that close streets) for the next month. A **historical version** (`bkfu-528j`) goes back to 2008, so it covers June 2024+ for training. Official open data, so it's legal and has an API.
- **Ticketmaster Discovery API:** all ticketed events in NYC (concerts, MSG games, other theater) by date and venue. Gives "big concert at MSG tonight," "Knicks home game."
- **SeatGeek API:** same idea, for cross-checking.
- **Javits Center events calendar:** big conventions = tourist and business-traveler surges.
- **NYC Tourism + Conventions (nyctourism.com):** event calendar plus monthly tourism stats and seasonality.
- **Hand-maintained annual list:** Marathon, UN General Assembly week, Fashion Week, Thanksgiving parade, New Year's Eve, Pride, US Open, etc.
- **Features:** `major_event_midtown_today`, `msg_event_tonight`, `javits_convention_today`, `tourism_index_month`.

### 3.10 User-submitted reports (verified) 🆕
**Entry:** the floating "Report rush availability" button (§2.5).

**Big notice at the top of the form:**
> ⚠️ **Only fill this out AFTER you've been to the box office.** This is for reporting what actually happened, not for asking about availability.

**Fields**
- **Date you went to the box office** (required; must be today or in the past)
- Show (required) + performance you were trying for (matinee/evening)
- **Time you arrived** (required)
- **Number of people in line ahead of you**
- **Number of rush tickets available** (if known / if they said)
- Did you get tickets? (Yes / No / Only full price)
- How many tickets you bought, and price paid
- **Was SRO (standing room) offered?** (Yes / No / Don't know)
- Time rush sold out (if known)
- Notes (e.g. "understudy on", "told to come back at 5")
- **Photo of your ticket** (optional but encouraged; "cover the barcode")

**Verification (manual, by me)**
1. Submission is saved with `status = pending`. **Pending reports never enter the training data.**
2. An **email is sent automatically to me** with the report summary, the ticket photo, and **Approve / Reject links**.
   - **How:** a transactional email service (e.g. Resend, Postmark or SendGrid; free tiers are plenty at this volume). Each link carries a one-time signed token so only the email recipient can approve or reject, and each link works once.
   - My address is stored as a config secret (`ADMIN_EMAIL`), **not in the repo**, since this is a public portfolio project.
3. Clicking **Approve** sets `status = verified` → the row goes into the training table (`source = user_verified`). **Reject** discards it.
4. Photos stored privately and **deleted after review** (they may show names or seats).
- Light spam protection only (rate limit, honeypot field).
- Reports without a photo can still be approved if they look plausible. That's my call.

### 3.11 Source registry — "every site that is legal" ✅ built (`registry/sources.csv`)
Before any site is scraped, record it in a registry: `site, data type, has official API?, robots.txt allows?, ToS on automated access, decision (API / scrape / skip), notes, date checked`.
- **Rule of thumb:** official API or open data > public pages whose robots.txt and ToS allow it > skip. Never log in, bypass bot detection or CAPTCHAs, or hit sites hard.
- Candidates: Ticketmaster (Discovery API), Telecharge, Broadway Direct, show official sites, TodayTix, TKTS/TDF, StubHub, SeatGeek (API), Vivid Seats, Gametime, TickPick, Playbill, BroadwayWorld, IBDB, Broadway League, NYC Open Data, Javits, nyctourism.com, Open-Meteo.
- **Result for ticket sites (2026-10-22):** only TKTS (scrape) and Ticketmaster (official API) are usable; no resale site and no seat counts (§3.2, §3.8).
- "Legal" here means within each site's terms. This isn't legal advice. When a ToS forbids scraping, treat it as a no unless there's an API.

### 3.12 Cast & casting events
- **Track:** principals **joining / leaving**, **limited-run stars**, a beloved cast member's final weeks, opening / press nights, closing announcements, understudy-heavy days.
- **How:** scrape Playbill and BroadwayWorld casting news; LLM-extract `{show, person, event type, start date, end date}`. Show official sites and socials for "final performances" posts. Reddit comments for "X was out today".
- **Features:** `star_in_limited_run`, `days_until_star_leaves`, `principal_change_this_week`, `days_until_closing`.

## 4. Labels — what we're predicting

Two targets per performance:
1. **Number of rush tickets available**
2. **Arrival time needed to get one** (equivalently, line length when rush ran out)

People rarely post exact counts. They post things like:
- "8th in line, got tickets" → supply ≥ what the first ~8 parties bought (~8–16 tickets)
- "15th in line, sold out before me" → supply < ~15–30 tickets
- "arrived 6 am, 8th in line" → links **arrival time ↔ line position**
- "they had 26 rush seats today" → exact (rare, very valuable)

Most labels are **bounds** (interval-censored); the model must use them. Verified user reports (§3.10) are the cleanest labels.

How much a show's rush count swings day to day is unknown; the Reddit data should reveal it.

**Extraction (LLM over each comment) → one row per observation** (`line_count` / `attempt` / `supply`, per `docs/labeling-schema.md`; one comment can have several):
`show, performance date, matinee/evening, rush type, arrival time, line position, outcome (got / didn't / full price only), tickets bought, stated count, sellout time, SRO offered, return visit time/outcome, cast notes, comment timestamp, extraction confidence`

Validation: ~~hand-label ~100 comments first~~ done: a 100-comment answer key plus a 50-comment held-out set, pre-labeled by Claude and reviewed by me ("human-reviewed labels"). Results in §5.5.

## 5. Model (initial thinking)

**Tickets available:** negative binomial regression with an interval-censored likelihood; Bayesian hierarchical with show as a group effect. The predictive distribution gives "__% confident of __ ± __" at any confidence level (slider).

**Arrival time:** model line position vs. arrival time per show and day type; recommended time = latest arrival where expected line position < predicted supply with high probability. Always displayed, even if extreme.

**Verdict / worth-it bar:** P(get a ticket | arrive at the recommended time). If that time is extreme (e.g. 6 am), the verdict reflects how unrealistic it is (likely red), but the time is still shown.

**Ranking:** **P(get a ticket)**, highest first.

### 5.1 Low-data shows
- **No data at all → skip** (§2.7).
- **Some data (prices, grosses) but no reports →** predict from the hierarchical prior + popularity features (§3.3, §3.8, §3.12), labeled `Low confidence` with a wider range. Show-specific data takes over as reports arrive.

**Evaluation:** interval coverage (80% intervals contain the truth ~80% of the time), arrival-time error, verdict accuracy (did GO days work out?) on held-out recent months; plus real rush runs.

### 5.2 Models to try
Try several and let the backtest pick. All are evaluated on the same **time-based split** (train on older months, test on the most recent ones, never shuffled), so there's no leakage from the future.
| Model | Why try it |
|---|---|
| **Baseline:** per-show historical median (+ day-of-week) | The bar every other model must beat. If it can't be beaten, say so. |
| Poisson / negative binomial GLM | Simple, interpretable count model |
| **Bayesian hierarchical NB with interval-censored likelihood** (PyMC / NumPyro) | Handles bounded labels and sparse shows properly; gives full distributions |
| Gradient-boosted trees (LightGBM / XGBoost) + quantile or conformal intervals | Strong on tabular features; tests whether nonlinearity helps |
| *(maybe)* Survival / time-to-sellout model for arrival time | Natural fit for "when does rush run out" |

### 5.3 Results table (for the portfolio) 📊
Report a table that makes it easy to show how the model works and how well it does. Keep it in the README and on the accuracy page (§2.6). Example layout:

| Model | Features | MAE (tickets) | 80% interval coverage | Avg interval width | Verdict accuracy | Arrival-time error | Notes |
|---|---|---|---|---|---|---|---|
| Baseline | show, weekday | | | | | | |
| NB GLM | + capacity, prices | | | | | | |
| Bayesian hierarchical | all | | | | | | |
| LightGBM + conformal | all | | | | | | |
| *Ticket-data ablation:* with vs. without TKTS + Ticketmaster features | | | | | | | decides whether ticket data and the Refresh button stay (§6.2) |

Also include: a **feature-importance / ablation table** (what happens to accuracy when you remove prices, NYC context, cast changes, etc.), dataset size (reports, shows, date range), and a one-paragraph plain-English "how it works."

### 5.4 Training cadence
- **Retrain weekly**, right after the weekly Reddit scrape and extraction (§6.1), then write predictions for the next 14 days. (Changed 2026-11-02; was "weekly or less, with predictions updated nightly and every morning.")
- **Predictions change** when the model retrains and when someone clicks Refresh, which brings in today's ticket data (§6.3).
- **Training time:** measure at step 5. The simple models should take seconds; the Bayesian model is the slow one (maybe minutes to tens of minutes). Whatever it is has to fit in the weekly job.
- Watch interval coverage on the accuracy page; if it drifts, retrain sooner.

### 5.5 LLM extraction budget (Claude Haiku)
- **Model:** Claude Haiku 5.5 (`claude-haiku-5-5`) for extracting structured rows from Reddit and forum comments (§4) and casting news (§3.12).
- **Total budget: $8 for the whole project** (raised from $5 on 2026-10-22; $10 of credits loaded). The code enforces a hard stop at $8 across every run (`data/interim/llm_spend.csv`).
- **Actual so far:** $1.47 (pilot + held-out $0.04; full extraction of 46.8k comments $1.30 via Batches + caching; top-up of 7.4k comments $0.13). Result: 18,262 observations from 10,301 comments in `data/processed/reports.csv`. See `process.md` step 3 and its wrap-up.
- **Built:** `broadway_rush/extraction/` (prompt, sync pilot, Batches runner, scorer). Structured outputs were rejected because the 25-field schema is too complex for them, so the JSON is described in the prompt and validated plus auto-repaired in code. Effort low, thinking on (thinking off cost more and was less accurate).
- **Accuracy (held-out 50 comments):** report vs none 94%, observation precision 77% / recall 87%, key fields 83–95%. Labeling rules: `docs/labeling-schema.md`.
- **Pricing (as of Oct 2026):** $0.10 per 1M input tokens, $0.50 per 1M output tokens. The Batches API is 50% off; cached prompt reads are ~10% of the input price. Thinking tokens bill as output, so run at `effort: low`.
- **Rough cost estimate** (one request per thread, ~20 comments each, sharing one ~1.5K-token instruction prompt):
  | Scope | Comments | Est. cost (batch) |
  |---|---|---|
  | Daily reporting threads only | ~8.5K | **~$0.50** |
  | + other subreddits, BroadwayWorld forums, casting news | ~20–25K | **~$1–1.50** |
  | Re-runs after fixing the prompt (×2) | | **~$1–3 total** |

  (Original estimate; the real runs were ~54k comments for $1.43 in total.) Confirm with a pilot before any full run.
- **Staying under it:**
  - Pilot on ~100 comments first. Measure tokens per comment and accuracy vs. hand labels, then project the full cost before running everything.
  - Use the **Message Batches API** (discounted vs. real-time) and **prompt caching** for the shared instructions.
  - Batch several short comments per request; skip comments with no rush-related keywords.
  - Hard stop: track spend in the pipeline and halt at $8.
  - Only new comments get extracted on weekly runs; never re-extract old ones. At past rates a week of new comments (~440 after the keyword filter) costs about 1¢.

## 6. Data refresh: what runs when

> **Changed 2026-11-02.** The first plan was "scrape on a schedule, never on click". It assumed 6–10 sources per performance, including slow resale and seller sites: ~30–90 s per click, and repeated live hits are what get scrapers blocked. The rules check (§3.8, §3.11) ruled almost all of those out, and the two ticket sources left are fast. Also, I might not check the site every day or even every week, so ticket data only needs to be fresh when someone actually looks.

**One ticket-data refresh (all shows, next 8 days):**
| Source | Requests | Time (rough) |
|---|---|---|
| Ticketmaster Discovery API | ~4 (200 events per page, 1 s apart) | ~5–10 s |
| TKTS live board | 1 | ~1–3 s |
| **Total** | **~5** | **~10–15 s** |

Request counts are from the first snapshots (2026-10-22); times are estimates, to be timed when Refresh is built.

### 6.1 Weekly scheduled job
1. Reddit: scrape new posts and comments (§3.1).
2. Extract only the new comments with Haiku (~1¢ a week, §5.5).
3. Grosses (Playbill + BroadwayWorld) and rush policies (§3.3, §3.4); casting news once built (§3.12).
4. Rebuild the show catalog (`catalog build`).
5. Retrain the model (§5.4).
6. Write predictions for the **next 14 days**, so the site always has a full 7 days ahead until the next run, and republish the site (§9).
- Tiles read these precomputed predictions, so pages load instantly.

### 6.2 Ticket data: daily for now, on click later
- **Phase A, training collection (now → step 5):** a scheduled **daily** snapshot of TKTS + Ticketmaster (§3.2), whether or not anyone visits. The model can only learn what ticket data means from snapshots taken the same way every day, on days that also have Reddit reports.
  - How long: at least 2–3 months is a guess (~16 daily-thread reports a day → ~1,000–1,500 reports with ticket data). Decide at step 5.
  - Times: Ticketmaster in the morning (~7 am ET, when day-of users check); TKTS after the booths open (afternoon). Confirm from the boards' "Updated" times in `tkts.csv` first.
- **Phase B, after launch:** ticket data is fetched **only when someone clicks Refresh** (§6.3).
- **If step 5 shows the ticket features don't help** (ablation, §5.3), stop collecting them and drop the Refresh button.
- **Watch out for (moving to click-only):**
  - **Timing mismatch:** training snapshots are taken at fixed times; a click can come at any time. Define features so they mean the same whenever they're measured (e.g. "on the TKTS board today"), or record the time and train with it.
  - **History-based features need regular snapshots:** "share of the last 30 days on TKTS" or "went off sale early" can't be computed from occasional clicks. Either keep a cheap daily snapshot after launch or drop those features (§9).
  - **Clicks aren't random:** days when someone refreshed may differ from other days, so check before using click-only data for training.

### 6.3 Refresh button
- **One mode** (~10–15 s, all shows): pull today's TKTS + Ticketmaster, re-predict, cache. ~~Quick (~1–2 min) and deep (~4–5 min) modes~~ are gone: no slow sources are left.
- **Guardrails:** only registry-approved sources (§3.11); a **shared cache with a ~30-min cooldown** (if anyone refreshed recently, return that result instead of hitting the sites again); never retry aggressively; if a source errors or rate-limits, skip it and show the weekly data.
- **Access: PIN-protected + limited.**
  - Refresh requires a **PIN** that I hold and share with family and friends. Everyone else sees the weekly predictions.
  - The PIN is stored hashed as a config secret, never in the repo, and can be changed anytime.
  - **Only 2 PIN attempts.** After 2 wrong tries, that device/IP is blocked until midnight ET. Goal: randos can't burn my API quota.
- **Daily cap** = the tightest source's safe daily budget, minus what scheduled jobs use, ÷ requests per refresh, using only 50% of it. Ticketmaster's 5,000 calls/day ÷ ~4 per refresh leaves plenty; TKTS is one page per refresh, so the cooldown is what keeps it polite. Pause refreshes for the day if a source starts rate-limiting. Show what's left ("2 left today").
- It runs on the website's host (Vercel), so the Ticketmaster key goes in Vercel's environment settings, never in the repo.

## 7. Known risks

| Risk | Notes |
|---|---|
| No historical availability / price snapshots | §3.2, §3.8. No legal source has seat counts at all. Snapshots of what is legal (TKTS, Ticketmaster sale status) start once the daily job is scheduled; nothing was collected Oct 23 – Nov 1, 2026. Grosses are the proxy before that. |
| Labels mostly bounds | §4. Intervals will be wide early on. |
| Selection bias | People post wins and dramatic losses, not boring days: 3,382 "got rush" vs. 160 "sold out before me". |
| Policy drift | Policy history stored (§3.4). Prices barely move; whether a show offers rush does. |
| Uneven coverage | §5.1. 41 shows have 50+ reports, 34 have fewer than 10. |
| Scraping legality / blocks | §3.11 registry; APIs first; polite. Refresh is limited by PIN, a shared cooldown and a daily cap (§6.3). |
| Click-only ticket data (after launch) | Measured at different times than the training snapshots, and too irregular for history-based features (§6.2). |
| Many features, little data | Regularization/priors; honest feature selection. |
| Ticket photos contain personal info | Private storage, delete after review, ask users to cover the barcode. |
| Going public with Reddit data | `data/labels/hand_labels.xlsx` (100 full comments + parents) and `reports.csv` (`author` column) are committed. Clean up before the repo goes public (§9). |

## 8. Decisions log

- **Product:** web app. Personal use + portfolio + family and friends. Not built for scale. Nothing reused from earlier projects.
- **Usage (2026-11-02):** I might not check it every day, or even every week. Nothing should depend on daily visits.
- **Flow:** pick a **day** → **tiles of all shows** ranked by likelihood of rush, each with **price** → optional checkboxes to focus on chosen shows → tap a tile for performance details.
- **Look:** purple theme, glowing light text; worth-it bar **red → blue**.
- In-person rush is the main output; digital rush is secondary; SRO is collected in reports.
- Horizon: next 7 days; day-of (e.g. 8 am) checks show everything.
- **Output:** worth-it bar + verdict, chance %, ticket count ± at a confidence level, price, arrival time; confidence slider hidden behind a button.
- **Arrival time always shown**, even 6 am.
- **Ranking:** highest chance of getting a ticket.
- **No data at all → skip the show.** Some data → low-confidence prediction.
- **Data:** as much as possible from June 2024 on; every site that's legal (§3.11). **Rules check done 2026-10-22:** among ticket sites only TKTS (scrape) and Ticketmaster (official API) are usable; no resale prices, no seat counts.
- **Prices vs. historic highs/lows** is still a key idea, **narrowed** to what's legal: weekly grosses (avg/top ticket) + TKTS discounts (§3.8).
- ~~**Scrape on a schedule, never on click.**~~ **Replaced 2026-11-02 (§6):**
  - **Weekly scheduled job:** Reddit scrape → Haiku extraction of new comments → grosses + policies → catalog → **retrain** → predictions for the next 14 days.
  - **Ticket data (TKTS, Ticketmaster):** **scheduled daily for now**, to build training data; **after launch, only when someone clicks Refresh.** Dropped entirely if step 5 shows it doesn't help.
- **User reports:** floating "Report rush availability" button, "only after the box office" warning, ticket photo, manual Approve/Reject **by email**; only verified reports are used.
- **Refresh:** one mode (~10–15 s, all shows), PIN with **2 attempts, then blocked for the day**, shared ~30-min cache, daily cap derived from source budgets (§6.3). ~~Quick and deep modes~~ dropped 2026-11-02.
- **Ticketmaster Discovery API key:** set up by me 2026-10-22, in `.env`. Limits confirmed: 5,000 calls/day, 5 per second.
- **Website, no sign-in, no notifications.** No in-app prompting for reports; I'll tell family and friends about the report button myself.
- **Broadway only** (musicals + plays); no off-Broadway.
- **ML:** try multiple models (§5.2); report a results table (§5.3); **retrain weekly**, after the weekly Reddit scrape (§5.4).
- **LLM:** Claude Haiku 5.5, **$8 total budget** (§5.5; raised from $5 on 2026-10-22).
- **Labels:** one row per observation (`line_count` / `attempt` / `supply` / `none`), per `docs/labeling-schema.md`. The 100-comment answer key and the 50-comment held-out set were pre-labeled by Claude and reviewed by Rachel ("human-reviewed labels").
- **Stack so far:** Python 3.14 venv, package in `src/broadway_rush/`, data in `data/` (`raw/` and `labels/` git-ignored, though `hand_labels.xlsx` and `sample_manifest.csv` were committed before that rule), source registry in `registry/sources.csv`. **Website deploys on Vercel** (2026-11-02). Rachel handles all git commits.
- **Repo (2026-11-02):** private on GitHub for now; probably **public when the project is done**, so interviewers can see it. Before then, remove Reddit comment text and usernames from what's committed (§7, §9). Private notes stay git-ignored.
- **Which shows get predictions (2026-10-22), three groups, decided per show and per date from the policy history:**
  1. **In-person rush + enough data** (≥2 daily-thread reports per running week; ~11 shows now): full prediction (tickets, range, arrival time).
  2. **In-person rush, little data** (~5 now: Chicago, Six, Hadestown SRO, & Juliet, Wicked): no number; "limited data, probably easy" plus the policy and recent % capacity. (Quiet in-person shows run ~84% full vs. 94% for busy ones; `process.md` step 4d.)
  3. **No in-person rush** (lottery / digital only, e.g. Hamilton, Lion King, Book of Mormon): listed with lottery and digital-rush info only, no line prediction. Few Reddit posts here does *not* mean low demand: these shows are 94–99% full.
- **Build order:** 1 Reddit → CSV ✅ · 2 labels + Haiku pilot ✅ · 3 full extraction ✅ · 4 grosses + rush policies + show catalog ✅ · 6 snapshot scrapers (moved up because ticket data has no history; TKTS + Ticketmaster built 2026-10-22, daily schedule not set up yet) · 5 baseline model + results table · 7 website. Don't skip ahead without asking.
- **Accuracy page:** yes (§2.6).
- **Docs:** `SPEC.md` (this file), `process.md` (what was built and how, kept up to date during coding), `interview-notes.md` (private talking points, **git-ignored**), `claude-notes.md` (Claude's working notes between sessions, **git-ignored**).

## 9. Open questions

1. Worth-it thresholds: what probability counts as "GO"? Decide after step 5, from the backtest.
2. **Where the scheduled jobs run** (daily snapshots now, the weekly job later): GitHub Actions (runs with the laptop off; free minutes cover it) or Windows Task Scheduler on the laptop (only runs if it's awake)? Leaning GitHub Actions.
3. **Where the daily snapshot data is saved,** if jobs run on GitHub Actions (each run starts on a fresh machine, so git-ignored files vanish): a separate private data repo (stays private when this repo goes public), this repo, or cloud storage? Leaning separate private repo.
4. **Snapshot times:** Ticketmaster ~7 am ET, TKTS in the afternoon? Check the TKTS boards' "Updated" times first.
5. **How long Phase A (daily ticket collection, §6.2) runs** before switching to click-only. Guess: at least 2–3 months; decide at step 5.
6. **After launch, keep a cheap daily ticket snapshot anyway?** It keeps history-based features ("days on TKTS in the last 30") and adds training data that isn't skewed toward days someone clicked, at ~5 requests a day. Or go click-only as planned.
7. **Before making the repo public:** git history keeps every old version, so deleting files isn't enough. Scrub `hand_labels.xlsx` and the `author` column of `reports.csv` out of the history, or publish a fresh copy with one clean starting commit? Also check whether Ticketmaster's API terms allow publishing its data.
8. **Website build (step 7, on Vercel):** Next.js (Vercel's own) or a plain static site? How the weekly predictions reach the site (e.g. the weekly job writes a predictions file, then triggers a Vercel redeploy)? The report form (§3.10) also needs a free database and an email service.
9. Hosting budget: likely **$0** now. The old worry was a nightly headless-browser scrape; the legal sources are one API and one plain page.
10. Design phone-first? (Likely used at 7–8 am on a phone.)
11. TodayTix: ask them for permission to use their data (§3.8), or drop it?
12. Does the NYC Open Data permitted-events feed include the Marathon and other major races and parades? Verify against a past year (e.g. Nov 2024); the hand-maintained list (§3.9) covers them either way.
- ~~Confirm Ticketmaster Discovery API free-tier limits.~~ Done 2026-10-22: 5,000 calls/day, 5 per second.

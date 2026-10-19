# Broadway Rush — Spec (draft)

> Status: brainstorming / feasibility. No code yet. Each section describes what we want and how it could be done; nothing here has been built.
> Standalone project: nothing is reused from previous projects.

## 1. Concept

**Is it worth going to the box office this morning for rush, and which show gives me the best shot?**

**Why / who**
- Built for me: I love shows but never know what to expect at the rush line.
- A **portfolio ML project**.
- Used by family and friends if it proves accurate. Not designed for a large user base, so no need to optimize for scale, accounts or heavy spam protection.

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
3. *(Optional)* check the shows you're interested in to filter or pin them. Because results are precomputed (§6), this is instant and there's **no need for a 5-show limit**. The limit would only be needed if we scraped live per request, which we won't.
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
- **Why this prediction:** a few plain-English drivers ("Resale prices are 40% below this show's usual → lower demand", "Saturday matinee, school break → longer lines").
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

### 3.0 Show & performance catalog (the backbone) 📝 must build
A dataset of **every show playing and every performance** for the next 7 days, plus history back to June 2024.
- **Fields:** show, theater, address, open/closing dates, each performance's date/time, which seller sells it (Telecharge / Ticketmaster / other), official site URL, rush policy link.
- **Sources:**
  - **Playbill's "Weekly Schedule of Current Broadway Shows"** grid: shows × days with performance times (and "DARK" days). Scrape weekly.
  - **Each show's official site and seller calendar:** the source of truth for exact performances, including holiday changes and cancellations. Playbill itself says to confirm there.
  - **Broadway League / IBDB:** show list, theater, opening and closing dates.
  - **Ticketmaster Discovery API (official):** lists events, venues and dates for Ticketmaster-sold theaters. Cross-check.
- **History:** grosses (§3.3) say which shows ran each week since June 2024. The weekly Playbill grid can be backfilled from archived copies if available.

### 3.1 Reddit testimony ✅ verified accessible
- **What:** r/Broadway's **daily "Broadway Rush Community Reporting Thread"** (posted by u/BroadwayRushReport), going back to **June 2024**. That's about 850 threads at roughly 5–15 comments each, plus one-off posts with "rush" in the title.
- **How:** reddit.com blocks unauthenticated API calls (403). The **Arctic Shift** archive (`arctic-shift.photon-reddit.com`) serves posts and comments without credentials:
  - `GET /api/posts/search?subreddit=Broadway&title=Rush Community Reporting Thread` (paginate with `after`=last `created_utc`, `limit=100`, `sort=asc`)
  - `GET /api/comments/search?link_id=<post id>` for each thread's comments
  - Rate limited ("Timeout. Maybe slow down a bit"): about 1 request/sec with retry and backoff.
- **Widen the net (June 2024+):** keyword searches ("rush", "box office", "line", "SRO", "TodayTix") across r/Broadway, r/musicals, r/AskNYC and r/nyc.
- **Output:** `posts.csv`, `comments.csv` (thread id/title/date, comment id, parent, author, timestamp, score, body, subreddit).
- **Then:** LLM extraction into structured rows (§4).
- **Ongoing:** re-scrape daily.

### 3.1b Other testimony (June 2024+)
- **BroadwayWorld forums:** long-running per-show rush and lottery threads. Public HTML, so scrape gently.
- **TikTok / Instagram / X:** lots of "I got rush" content, but most ToS forbid scraping. Use official APIs only, or skip.

### 3.2 Primary seller availability ⚠️ no history exists
- Ticketing sites only show current inventory, so past availability can't be looked up.
- **Plan:** start **snapshotting now**. For every performance in the next 7 days, record seats available (by section and price) at fixed offsets: T−7d … T−1d, plus **morning-of (~7–8 am)** so day-of users see the freshest numbers.
- **Sellers:** Telecharge (Shubert theaters), Ticketmaster (Nederlander, Jujamcyn/ATG and others), show official sites, Broadway Direct. Map each theater to its seller in §3.0.
- **Whether we can scrape each one is decided by §3.11.** Ticketmaster and Telecharge ToS restrict scraping. Where scraping isn't allowed, use official APIs (e.g. Ticketmaster Discovery for listings and price ranges) or skip.

### 3.3 Capacity / grosses — historical demand proxy
- **What:** the Broadway League's **weekly grosses per show**: gross $, attendance, **capacity %**, **average paid admission**, **top ticket price**, number of performances. Covers all of June 2024 → now.
- **How:** Playbill and BroadwayWorld republish the weekly table as HTML. Backfill every week since June 2024, then keep scraping weekly.
- **Why it matters extra:** average paid admission and top price are a **price history back to June 2024**, which the snapshot sources can't give us (§3.8).
- **Limits:** weekly, not per performance.

### 3.4 Rush policies per show (price varies!) 📝 must scrape
- **What:** per show: **rush price** (often $49.50, **but not always**), box office open time, tickets per person, which performances offer rush, cash/card, seat location, **SRO policy**, digital rush details (§3.5).
- **How:** BroadwayWorld's "Rush, Lottery and SRO Policies" listing as the main source; cross-check with Playbill's list and each show's official site. Re-scrape weekly.
- **Keep history:** store each policy with an `effective_from` date so old reports match the policy in force at the time.
- **Data quality:** flag source disagreements for manual review; show "last verified" next to the price.

### 3.5 Digital rush
- **What it is:** first-come, first-served rush sold in an app on the day of the performance. Mostly **TodayTix**. Not the same as a digital *lottery* (Telecharge, Broadway Direct, Lucky Seat), which is out of scope.
- **Timing:** most often **9 AM day-of** on TodayTix; varies by show, so store it per show (§3.4). Check whether TodayTix still requires a one-time social share to "unlock" rush.
- **Price/limits:** around $49–53, 2 per person, credit card, ID at pickup. Per show.
- **Columns:** `has_digital_rush`, `digital_rush_platform`, `digital_rush_time`, `digital_rush_price`.
- **What to predict:** P(getting one if you're in the app at open), and how fast it sells out.
- **Labels:** Reddit ("gone in 20 seconds", "got it at 9:03"), and, if TodayTix's terms allow, checking the show page right after 9 AM to record when it flips to sold out. Never any automated purchasing or queue jumping.
- **Expect thin data.**

### 3.6 Calendar features
- Day of week, **day of month**, matinee/evening, holidays, school breaks (NYC public schools, colleges), Tonys week, weeks since opening, closing announced.
- **Weather:** historical daily weather and 7-day forecasts from free APIs (Open-Meteo, NOAA).

### 3.7 Later-in-day releases ("come back later") 💡 idea
- **Observation (from a box office visit):** told "no tickets right now, but come back later today, there might be some."
- **Why:** held seats get released during the day: house seats / producer holds, press and VIP holds, unsold group blocks, returns, and cleared blocked seats.
- **Open question:** released at rush price or only full price? **Ask at the box office on the next rush run.** Also mine Reddit for it.
- **Possible v2 feature:** a "second chance" line ("Morning rush likely gone by 10:15. Returning around __ pm has a __% chance").
- **Online signal:** day-of snapshots (§3.2) may show seats reappearing.

### 3.8 Prices vs. historic highs & lows ⭐ likely one of the best features
- **Idea:** compare a performance's current prices with that show's own history. "Resale is at its lowest since March" = soft demand = shorter line. "Prices at all-time high" = hot.
- **Sources to snapshot daily for the next 7 days of performances (legal ones only, §3.11):**
  - **Resale:** StubHub, SeatGeek, Vivid Seats, Gametime, TickPick. Collect listing count and min / median / max price.
  - **Primary:** Ticketmaster, Telecharge, official sites. Lowest available price per section.
  - **Discount:** TodayTix (lowest price, discounts, "selling fast"), **TKTS** same-day board (on TKTS = soft demand).
  - **APIs first:** SeatGeek has a public developer API that includes per-event listing counts and prices; Ticketmaster Discovery includes price ranges. Prefer these over scraping.
- **History problem:** snapshot prices only exist from when collection starts. Before that, use **average paid admission and top ticket price from weekly grosses (§3.3)**, which go back to June 2024.
- **Features:** `price_vs_show_median`, `price_percentile_in_show_history`, `days_since_price_low`, `resale_listing_count_change_7d`, `on_tkts_today`.

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

### 3.11 Source registry — "every site that is legal" 📝
Before any site is scraped, record it in a registry: `site, data type, has official API?, robots.txt allows?, ToS on automated access, decision (API / scrape / skip), notes, date checked`.
- **Rule of thumb:** official API or open data > public pages whose robots.txt and ToS allow it > skip. Never log in, bypass bot detection or CAPTCHAs, or hit sites hard.
- Candidates: Ticketmaster (Discovery API), Telecharge, Broadway Direct, show official sites, TodayTix, TKTS/TDF, StubHub, SeatGeek (API), Vivid Seats, Gametime, TickPick, Playbill, BroadwayWorld, IBDB, Broadway League, NYC Open Data, Javits, nyctourism.com, Open-Meteo.
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

**Extraction (LLM over each comment) → one row per report:**
`show, performance date, matinee/evening, rush type, arrival time, line position, outcome (got / didn't / full price only), tickets bought, stated count, sellout time, SRO offered, return visit time/outcome, cast notes, comment timestamp, extraction confidence`

Validation: hand-label ~100 comments and measure extraction accuracy first.

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
| *Refresh backtest:* nightly vs. quick vs. deep | | | | | | | keep or scratch (§6) |

Also include: a **feature-importance / ablation table** (what happens to accuracy when you remove prices, NYC context, cast changes, etc.), dataset size (reports, shows, date range), and a one-paragraph plain-English "how it works."

### 5.4 Training cadence
- **Retrain weekly** (possibly less often, since Broadway demand is fairly stable). **Predictions** still update nightly and on the morning refresh, because the *features* (prices, availability, events) change daily even when the model doesn't.
- Watch interval coverage on the accuracy page; if it drifts, retrain sooner.

### 5.5 LLM extraction budget (Claude Haiku)
- **Model:** Claude Haiku for extracting structured rows from Reddit and forum comments (§4) and casting news (§3.12).
- **Total budget: $5 for the whole project.**
- **Staying under it:**
  - Pilot on ~100 comments first. Measure tokens per comment and accuracy vs. hand labels, then project the full cost before running everything.
  - Use the **Message Batches API** (discounted vs. real-time) and **prompt caching** for the shared instructions.
  - Batch several short comments per request; skip comments with no rush-related keywords.
  - Hard stop: track spend in the pipeline and halt at $4 to leave headroom.
  - Only new comments get extracted on weekly runs; never re-extract old ones.

## 6. Scraping: how long does it take? (estimates)

**Scale:** ~40 Broadway shows × ~8 performances/week ≈ **~45 performances per day**. About **6–10 sources per performance** (primary seller, TodayTix, 3–5 resale sites, TKTS), so **~300–450 page loads or API calls per day of calendar**.

**Per-request time:** API calls ~0.5–1 s. Plain HTML pages ~1–3 s. JavaScript-heavy ticketing pages that need a headless browser ~5–10 s. Plus a **polite delay** (~2–5 s between hits to the same site).

| Job | Estimate |
|---|---|
| **One date, all shows, all sites** (sites in parallel, each site sequential and polite) | **~5–15 min** |
| **All 7 days** | **~30–90 min** |
| One user's 5 shows, scraped live on click | **~30–90 s**: too slow, and repeated live hits are what get scrapers blocked |

**Conclusion: never scrape when the user clicks.** A scheduled job does the scraping and the user just reads precomputed results:
- **Nightly (e.g. 1–3 am):** full scrape of the next 7 days, re-run predictions, cache tile results.
- **Morning-of refresh (~7–8 am):** re-scrape today's performances only (~5–15 min) so day-of users see fresh numbers.
- **Weekly:** grosses, policies, Playbill schedule, casting news.
- **Daily:** Reddit, NYC events, weather.
- **Page loads instantly** (< 1 s) for any day and any number of shows, so there's **no 5-show limit**.
- These are rough; real numbers come from timing the first prototype scrapers.

**Optional "Refresh for latest" (wait up to 1–2 min) 💡**
- I *might* be willing to wait 1–2 minutes for more accurate results, but **not at the risk of getting blocked**.
- Design: a "Refresh for latest" button on a tile or details view does a **targeted live re-scrape of just the chosen shows' performances**, then re-predicts. The user sees a progress state ("Checking 4 of 7 sites…").
- **Anti-blocking guardrails:**
  - Only for sources marked OK in the registry (§3.11); **APIs first** (SeatGeek, Ticketmaster Discovery), which are fast and don't get you blocked.
  - **Shared cache with a cooldown:** if a show was refreshed in the last ~30 min (by anyone), return the cached result instead of hitting sites again.
  - **Global rate limit per site** (same polite delays as the scheduled job), and a cap on refreshes per hour across the whole app.
  - Never retry aggressively. If a site errors or rate-limits, skip it and show the scheduled data for that source.
- With a tiny user base (me + family and friends), refreshes will be rare, which keeps the risk low.

**Access: PIN-protected + limited**
- Refresh requires a **PIN** that I hold and can share with family and friends. Everyone else just sees the scheduled results.
- The PIN is stored hashed as a config secret, never in the repo. It can be changed anytime (e.g. if it gets passed around too far).
- **Only 2 PIN attempts.** After 2 wrong tries, that device/IP is **blocked from trying again for the rest of the day** (resets at midnight ET). Goal: randos can't burn my API calls or scraper budget.
- **Refresh cap = what the scrapers can safely absorb.** Don't pick a number out of the air. Compute it from the source registry (§3.11):
  - For each source, record its **safe daily budget** (API quota, e.g. Ticketmaster's free tier, or the request rate a site tolerates without blocking, found by careful testing and its robots.txt crawl-delay).
  - Subtract what the **scheduled jobs already use** that day.
  - Refreshes allowed per day = the leftover budget of the **tightest** source ÷ the requests one refresh needs, with a safety margin (e.g. use only 50% of the leftover).
  - Recompute automatically if a source starts returning rate-limit errors (and pause refreshes that day).
- Show remaining refreshes ("2 left today").

**Two depths, only if they earn it**
| Mode | Wait | What it does |
|---|---|---|
| **Quick refresh** | ~1–2 min | APIs + the fastest polite sources for the chosen shows |
| **Deep refresh** | up to ~4–5 min | Every registry-approved source, including slow headless-browser pages |

- **Must backtest before shipping.** Compare predictions made with (a) nightly data, (b) quick-refresh data and (c) deep-refresh data against real outcomes (verified reports + Reddit). Metrics: interval coverage, ticket-count error, verdict accuracy (§5).
- **If refreshes don't clearly beat nightly data, scratch the feature entirely.** It isn't worth the wait or the extra scraping. Record the result in the results table (§5.3) either way.
- Possible middle ground: show the scheduled result immediately, then update the tile live as fresh sources come in. The wait then becomes optional rather than blocking.

## 7. Known risks

| Risk | Notes |
|---|---|
| No historical availability / price snapshots | §3.2, §3.8. Snapshots start now; grosses are the proxy until then. |
| Labels mostly bounds | §4. Intervals will be wide early on. |
| Selection bias | People post wins and dramatic losses, not boring days. |
| Policy drift | Store policy history (§3.4). |
| Uneven coverage | §5.1. |
| Scraping legality / blocks | §3.11 registry; APIs first; polite and scheduled, never on click. |
| Many features, little data | Regularization/priors; honest feature selection. |
| Ticket photos contain personal info | Private storage, delete after review, ask users to cover the barcode. |

## 8. Decisions log

- **Product:** web app. Personal use + portfolio + family and friends. Not built for scale. Nothing reused from earlier projects.
- **Flow:** pick a **day** → **tiles of all shows** ranked by likelihood of rush, each with **price** → optional checkboxes to focus on chosen shows → tap a tile for performance details.
- **Look:** purple theme, glowing light text; worth-it bar **red → blue**.
- In-person rush is the main output; digital rush is secondary; SRO is collected in reports.
- Horizon: next 7 days; day-of (e.g. 8 am) checks show everything.
- **Output:** worth-it bar + verdict, chance %, ticket count ± at a confidence level, price, arrival time; confidence slider hidden behind a button.
- **Arrival time always shown**, even 6 am.
- **Ranking:** highest chance of getting a ticket.
- **No data at all → skip the show.** Some data → low-confidence prediction.
- **Data:** as much as possible from June 2024 on; scrape every site that's legal (§3.11).
- **Prices vs. historic highs/lows** is a key feature (§3.8).
- **Scrape on a schedule, never on click** (§6).
- **User reports:** floating "Report rush availability" button, "only after the box office" warning, ticket photo, manual Approve/Reject **by email**; only verified reports are used.
- **Optional live refresh:** PIN-protected, limited per day; quick (~1–2 min) and deep (~4–5 min) modes, each kept **only if backtests show it improves accuracy** (§6).
- **Ticketmaster Discovery API key:** I'll sign up for and set up this myself.
- **Refresh access:** PIN with **2 attempts, then blocked for the day**; daily cap derived from scraper/API budgets. **Scratch refresh entirely** if backtests don't show a clear gain.
- **Website, no sign-in, no notifications.** No in-app prompting for reports; I'll tell family and friends about the report button myself.
- **Broadway only** (musicals + plays); no off-Broadway.
- **ML:** try multiple models (§5.2); report a results table (§5.3); retrain weekly at most.
- **LLM:** Claude Haiku, **$5 total budget** (§5.5).
- **Accuracy page:** yes (§2.6).
- **Docs:** `SPEC.md` (this file), `process.md` (what was built and how, kept up to date during coding), `interview-notes.md` (private talking points, **git-ignored**).

## 9. Open questions

1. Worth-it thresholds: what probability counts as "GO"?
2. Tech stack for the website, scheduled scrapers and model (Python for scraping and ML is the natural fit).
3. Hosting budget: $0 free tiers only, or a few $/month? The nightly headless-browser scrape is the part most likely to need paid hosting.
4. Design phone-first? (Likely used at 7–8 am on a phone.)
3. Does the NYC Open Data permitted-events feed include the Marathon and other major races and parades? Verify against a past year (e.g. Nov 2024); the hand-maintained list (§3.9) covers them either way.
4. Confirm Ticketmaster Discovery API free-tier limits on the official developer portal (I'm doing this).

# Broadway Rush — Spec (draft)

> Status (2026-11-05): build steps 1–4 are built (Reddit scrape → labeled extraction pilot → full extraction into `data/processed/reports.csv` → grosses, rush policies + history, show catalog). Step 6 was moved up: the TKTS and Ticketmaster snapshot scrapers are built, and the daily GitHub Actions job works (manual run succeeded 2026-11-05; ~~first scheduled run still to confirm~~ scheduled runs confirmed 2026-11-07). Calendar, weather and NYC permitted events were added 2026-11-05. **Updated 2026-11-06: a first model (step 5) and a first website (step 7) are built and run locally, not deployed.** The simple combo beats the lookup table on line length but not on ticket counts or the chance of a ticket (§5.2a, §5.3). The report form and Refresh + PIN are screens only, not connected. **Added 2026-11-08:** the This week view (§2.2b), local only. Level-ups, cast news and comparison rows aren't built. What was built, and how, is in `process.md`. ~~Struck~~ text was replaced; anything not marked built is still a plan.
> Standalone project: nothing is reused from previous projects.

## 1. Concept

**Is it worth going to the box office this morning for rush, and which show gives me the best shot?**

**Why / who**
- Built for me: I love shows but never know what to expect at the rush line.
- A **portfolio ML project**, and my entry in a **data project competition**: ~~due 2026-11-17~~ complete by **2026-11-23**, turned in **2026-11-24**, presented **2026-12-07**. I want to win.
- Used by family and friends if it proves accurate. Not designed for a large user base, so no need to optimize for scale, accounts or heavy spam protection.
- **Used now and then:** I might not check it every day, or even every week, so nothing should depend on someone visiting daily (§6).

**Product:** a **website**. No sign-in, no accounts, no notifications.

**Shows covered:** **Broadway only**, musicals **and plays**. No off-Broadway.

**Scope**
- **In-person general rush** (main output) and **digital rush** (secondary output, §3.5). **SRO** is collected in user reports (§3.10) but not predicted (yet). Lotteries and student rush aren't predicted, but they're shown and can be filtered on (§2.2a).
- **Horizon: the next 7 days.** Predicting weeks out would be extrapolation and isn't the point of the app.
- **Day-of use is fine:** if someone checks at 8 am on the day, show everything (the latest snapshot, recommended arrival time, digital rush).

### 1.1 Judging rubric (50 points, received 2026-11-05)
| Criterion | Points | What it asks |
|---|---|---|
| Data Preprocessing / Data Cleaning | 8 | Is the data from a reliable source? What cleaning was necessary, and what was done? Were new columns added for processing? What other preparation was done? |
| Data Processing | 10 | Do the techniques make sense? Is bias/overfitting accounted for? Are the technologies innovative? Are there mistakes? |
| Visualization | 7 | Does the project include visualizations? Are they relevant to the results? Do they show important relationships in the data? Were the techniques effective in getting the point across? |
| Presentation | 10 | Is it clear? Presentation skills, such as interaction with the audience. Quality of the slides and the audio. Did all team members speak an equal amount? |
| Results | 7 | Does it address a significant problem or question? Do the results have practical applications and support meaningful decisions? Is the broader relevance well articulated and demonstrated? |
| Creativity | 8 | Are the approaches creative and innovative? Does it tackle a unique issue? |

### 1.2 Still to do for the rubric (mine to take care of)
Compared against the project on 2026-11-05.
| Criterion | Points | Where it stands | Still to do |
|---|---|---|---|
| Data Preprocessing | 8 | Strong: source rules check, new columns, extraction tested on held-out comments, grosses from two sites agreeing within 0.018% | Show why Reddit reports can be trusted. Make a clear cleaning funnel: 139,584 comments → 18,412 observations → the rows the model uses. |
| Data Processing | 10 | Not built. The plan fits: bounds for one-sided labels, tests in time order | Build the model. Show the bias and overfitting checks, including the score against the lookup table and the 89% "always yes". Explain the step that joins the combo's two parts. |
| Visualization | 7 | Built 2026-11-06: plain charts on show pages, full ones on Nerd stats (§2.6) | ~~Make charts of how lines grow by time, chance vs arrival time, predicted vs actual, and what drives line length.~~ Decide whether to use screenshots or image files in the slides. |
| Presentation | 10 | Not on the schedule | Make slides, set aside rehearsal time, plan audience interaction, and get good audio. |
| Results | 7 | The question is clear, but there's no working site or real-world check yet | Get a working demo and do real rush runs. Explain the bigger point: rush costs about $45, against average tickets of $148–$200 at shows like The Outsiders and Just in Time. |
| Creativity | 8 | Strong: unusual topic, AI-extracted labels from Reddit, predicting when to show up | Say this clearly in the presentation. |

Also to do:
- Put charts and the presentation on the schedule (§8). Together they're worth 17 points, and neither has time set aside. Doing them before the report form, Refresh and PIN would be the better order: those stay in scope but earn no direct points.
- Find out what has to be turned in on Nov 24, whether this is solo or a team, and whether Dec 7 is live or recorded (§9, question 13).

## 2. User flow & UI

### 2.1 Flow
1. **Pick a day** (any of the next 7), **This week** to find the best day (§2.2b), or **Any day** when planning further ahead (§2.2a). No time yet.
2. See **every show playing that day as tiles**, ranked **top to bottom by likelihood of getting rush**.
3. *(Optional)* check the shows you're interested in to filter or pin them. Predictions are precomputed by the weekly job (§6.1), so this is instant and there's **no need for a 5-show limit**. Refresh (§6.3) re-checks ticket data for all shows at once in seconds, so it doesn't need a limit either.
   *(Optional)* filter and re-sort the tiles (§2.2a).
4. Tap a tile → details for that show's performance(s) that day (matinee vs. evening, if both).

### 2.2 Tile (one per show)
- Show name (+ theater, small)
- **Rush types offered** as small labels: `In person`, `Online`, `Student` and so on (§2.2a)
- **Rush price** (e.g. $49.50; per show, §3.4)
- **Worth-it bar** + verdict word (GO / Maybe / Stay home)
- Chance of getting a ticket (e.g. "72%")
- Recommended arrival time ("Get there by 9:20")
- Small badges: `Digital rush 9 AM`, `Star leaving Sunday`, `Low confidence`, `Prices way above usual`
- **__% seats sold** ("92% seats sold last week"), in place of "__% full" (§2.2a)

### 2.2a Filters, sorting and plain wording (added and built 2026-11-06, except high-profile stars)
**Rush types on the tile.** Each tile shows what the show offers. The same labels drive the first filter.
| Label | Policy types it covers (§3.4) | Shows now (Nov 5 snapshot) | Predicted? |
|---|---|---|---|
| In person | General Rush | 14 | Yes |
| Online | Digital Rush | 10 | Secondary output (§3.5) |
| Student | Student Rush, Student Tickets | 5 | No |
| Lottery | Digital Lottery and variants | 25 | No |
| Standing room | Standing Room and variants | 6 | No |

- A show Playbill doesn't list, but with 3+ in-person reports in 30 days, gets `In person (reported)`.
- Other deals (The Friday Forty, $30 Under 30, Ponyboy Seat, Military Tickets) stay in the details view, with no filter.

**Search (added 2026-11-06; not built).** A search box above the tiles finds shows as you type, by show name, nickname ("Mincemeat", from `registry/show_aliases.csv`) or theater. It works together with the filters, in Any day mode and in the This week view (§2.2b). If a matching show isn't playing on the picked date, the page says so instead of showing nothing, and offers Any day.

**Filters.** Within a filter, any selected option counts. Across filters, a show has to match all of them. Everything runs in the browser, so it's instant. More filters can be added the same way.
| Filter | Options | Data | Status |
|---|---|---|---|
| Rush type | In person, Online, Student, Lottery, Standing room | Rush policies (§3.4) | Have it |
| Days showing | M, T, W, Th, F, S, Su | Which weekdays the show plays (for example, Just in Time doesn't play Monday or Wednesday; see §9 question 27) | Built: 8 weeks of Playbill's weekly schedule |
| Runtime | Under 90 min, 90 min–2 hrs, 2–2.5 hrs, Over 2.5 hrs | Playbill's show pages | Built: 34 of 35 shows |
| High-profile stars | Has a high-profile star | Hand-kept list (below) | Not collected; needs cast news (§3.12) |
| Play or musical | Play, Musical | Show catalog (§3.0) | Have it |

**Days showing and runtime are simple show facts.** Claude looks them up once per show into a hand-kept file, `registry/show_facts.csv` (show, days, runtime, source, date checked, plus a review flag and note), and I review it. **Done 2026-11-06:** days come from Playbill's weekly schedule page over 8 weeks, using past copies on the Internet Archive, because one week can mislead (Election Day week had several shows swapping Tuesday for Monday). Ticketmaster is only a cross-check: where it disagrees, the row is flagged. 6 of 35 rows are flagged for me. The date picker's performance times still come from Ticketmaster (§3.0).

While a filter is on, shows with an unknown value are hidden, and the page says so ("3 shows hidden: runtime not known"). The page also shows the count ("12 of 33 shows") and a clear-all button.

**Days showing and the date picker do different jobs.**
- **Date picker:** a specific date in the next 7 days, with predictions. Days showing is greyed out here, because the date already decides.
- **This week + Days showing:** means "days I can go". Only those days are compared (§2.2b).
- **Any day + Days showing:** for planning weeks ahead ("what plays on Tuesdays?"). Tiles show facts only: rush types, rush price, typical ticket price, runtime, stars, play or musical, how full. They show no chance or arrival time, because predictions stop at 7 days (§1). In their place: "Check back within 7 days of your date."
- **Schedules change:** a show could close before someone's date, and closing news isn't built yet (§3.12), so Any day mode says to confirm before going.

**High-profile stars.** A show counts if a current principal is billed above the title, or has won a Tony, Oscar, Emmy or Grammy. Claude pre-fills `registry/stars.csv` (show, person, start date, end date, reason) and I review it. The dates make a star drop off when they leave. The same list drives the `Star leaving Sunday` badge and the model's star features (§3.12).

**Sorting.** Tap the same sort again to reverse it. Unknown values always go last.
| Sort | Shown first | Data | Notes |
|---|---|---|---|
| Best chance (default) | Highest | Model | Shows without a number stay at the bottom. Not available in Any day mode. |
| Latest arrival time | Latest | Model | The latest you can arrive and still probably get a ticket. Only for shows with a prediction on the picked date; not available in Any day mode. |
| Rush price | Lowest | Rush policies (§3.4) | In-person price, or the online price if there's no in-person rush |
| Typical ticket price | Lowest | Weekly grosses (§3.3) | See below |
| Runtime | Shortest | Show facts file (above) | Built |

**"Typical ticket price" instead of median non-rush price.** No legal source gives a true median or leaves out rush tickets: the weekly grosses only give the average paid per ticket and the top price (§3.3, §3.8). The closest honest number is the median of the last 4 weekly averages, labeled "Typical ticket price (average paid, recent weeks)". It includes rush and discounted tickets, so it runs a little below full price.

**"__% full" becomes "__% seats sold".** The tile says "92% seats sold last week", from the latest grosses week, rounded to a whole number. It names the week once the data is more than 2 weeks old ("92% seats sold, week ending Nov 1"). Standing room can push the figure just past 100%, so it's capped at 100%.

All of this goes in the predictions file, so the site still reads only that file (§5.2a).

### 2.2b This week view (added and built 2026-11-08, my request; local only, not deployed)
**For someone who wants to rush a show this week but hasn't picked a day:** which day gives me the best shot? Not everyone decides the night before.

- **Where:** a **This week** button in the day picker, next to the 7 dates and Any day. It covers the same 7 days as the picker (today and the next 6), because predictions stop at 7 days (§1). There's no "next week": a later week is Any day mode, with facts only (§9, question 23).
- **Days are compared by arrival time (decided 2026-11-08):** the latest time you can get there and still probably get a ticket (§5.2a). A later time means an easier day. The chance shown is the same number as in the day view, so one show on one day never shows two different chances.
- **Sunday mark:** box offices open at noon on Sundays and at 10 am on other days, so Sunday times run about 2 hours later. Every Sunday time gets an asterisk, with a note: "* Box office opens at noon on Sundays (10 am other days)." Sunday tiles in the day view get the same mark. If a show ever opens at another unusual time, that day gets the same mark with its own time.
- **Day strip at the top:** the 7 days in date order. Each shows how many of the shows that pass the filters have a prediction that day, and how many of those are GO ("14 of 15 GO"). The day with the most GO shows is marked (ties are all marked). Tapping a day opens that day's normal view.
- **One tile per show, not one per show-day.** A list of every show-day would put the same show at the top several times, because the show matters more than the day. Each tile shows:
  - the show's **best day**: its latest arrival time and that day's chance ("Best day: Tue Nov 10 · get there by 9:00 · 78%"). Days with the same time count as tied ("Best days: Tue, Thu or Fri", in date order, with a chance range if they differ). If every day is tied: "Every day about the same: Any day it plays" ("Any of your days" when Days showing is on) (placeholder, §9 question 28).
  - a row of all 7 days with each one's arrival time, colored like the worth-it bar, and "Dark" on days it doesn't play.
- **Sorting:** Latest arrival time by default, using each show's best day. Tap it again for earliest first (§2.2a). The other sorts work as in the day view. Best chance uses each show's best day.
- **Filters and search work as usual.** Searching for one show turns the page into "which day for this show?". **Days showing** means "days I can go" here: only those days are compared, in the strip and on the tiles. That covers fitting rush around a schedule.
- **Limited-data and lottery-only shows** go below, as in the day view, with the days they play and no chance.
- **Today** counts until that show's box office opens, then greys out (by the viewer's own clock, like the rest of the site).
- **Show pages** opened from this view have a back link to it.
- **Matinee vs evening:** one chance per show-day, as everywhere else (§5.2).
- **No model change:** the predictions file already holds each show-day's arrival time, chance and box office opening time.

**Why a mark, and what it will show (checked 2026-11-08 on the Nov 8–14 predictions, the 16 shows with a full prediction).**
- Every Sunday opening in the file is noon, and every other day's is 10 am.
- By latest arrival time, Sunday is the best day for 14 of 16 shows. Operation Mincemeat ties Sunday, Tuesday and Thursday, and Wanted doesn't play Sundays. So the mark will sit on most best days, and the note is what explains it.
- Also tried: comparing every day at the same head start, 1 hour before that day's opening. That flips the answer: Sunday is the best day for none of the 16, and Saturday or Sunday is the hardest day for all of them (Oh, Mary! 68% on Sunday vs. 78% on Tuesday). I kept arrival time, because it's the number people act on, and the mark tells them why Sunday's times are later.
- **Rubric:** Results asks whether the work supports meaningful decisions (§1.1). This view answers the question people actually plan around.

### 2.3 Details view
> We're **__%** confident there will be **__ ± __** rush tickets at **$__**.
> Get there by **__:__** for the best chance of getting one.

- **Always show the arrival time**, even when it's absurd (e.g. 6 am). A 6 am time almost certainly means the bar is black, but people who want it badly enough deserve to know.
- **Confidence slider (hidden by default):** an "Adjust confidence" button reveals a slider (e.g. 50%–95%) that widens or narrows the ± range live. Hidden so casual users only see the verdict and a default (e.g. 80%). It's cheap to build: the model outputs a full distribution, so the slider just reads different quantiles.
- **Digital rush section** (only for shows that offer it):
  > Digital rush opens at **9:00 AM** on **TodayTix** for **$__**.
  > Usually sells out in **__ min**. Be in the app **__ minutes early**: it opens right at 9.

  "__ minutes early" is fixed advice, not predicted. Only the sellout time comes from the model.
- **Why this prediction:** a few plain-English drivers ("On the TKTS board at 40% off today → softer demand", "Saturday matinee, school break → longer lines").
- **Combo hint:** a user can do the 9 AM digital rush for one show and *then* walk to another show's box office.

### 2.4 Look & feel
- **Width: at least 7/8 of the screen** at every screen size (changed 2026-11-06). It was a centered column capped at 1040 pixels, which looks like half the screen on a big monitor. Tiles use the extra room by adding columns, so lines of text don't stretch too long.
- **Purple theme** (deep purple), with text in **glowing / illuminated light colors** (neon-marquee feel). ~~A lighter purple background with dark text and no dark mode~~ was tried on 2026-11-06, and I changed it back to dark the same night.
- **Worth-it bar on dark:** it has a light outline, so the black end still shows.
- **Fonts (chosen and on the site 2026-11-06):** Bebas Neue for the logo, headings, show names and big numbers (like the chance %). Poppins for everything else: body text, labels and buttons. Both are free on Google Fonts. Bebas Neue only has capital letters, so show names appear in all caps.
- **Worth-it bar: black → gray → gold** (~~red → purple → blue~~, changed 2026-11-05). Black = stay home, gray = Maybe, gold = GO.

### 2.5 Report button
- A **floating button on the side** with a **form icon**, labeled **"Report rush availability"**.
- Opens the report form (§3.10).

### 2.6 Nerd stats page (~~Accuracy page, "How accurate have we been?"~~; renamed and expanded 2026-11-06)
- Public page tracking predictions vs. verified outcomes over time.
- Shows the results table (§5.3), e.g. "our 80% ranges contained the real number 78% of the time" and "GO verdicts worked out 8 out of 10 times," plus a chart of accuracy over time.
- Great for the portfolio, and tells family and friends whether to trust it.
- **Organized by question, with jump buttons that stay on screen (built 2026-11-06):**
  - **The short version:** four headline numbers.
  - **How rush lines behave:** how fast the line grows, a show-by-day grid, and how much rush saves.
  - **Where the data comes from:** the cleaning funnel and reports per show.
  - **What the model looks at:** what moves the line most, and how it's built.
  - **How good it is:** the scoreboard, predicted vs. real line, chance vs. what happened, the always-yes problem and verdicts, error and range by month, and real trips.
  - **Model vs. ground truth (added 2026-11-06, my request):** every test result next to what was reported: 1,507 line reports, 33 stated ticket counts and 138 attempts, each with a switch between the model and the lookup table, plus a table to look up any result by show or month, biggest miss first. Ground truth here means Reddit reports, so it isn't verified. Numbers only, with no usernames or comment text.
- **Show pages get the plain versions (built 2026-11-06):** how the line builds that morning, which days are busiest for that show, and what you'd save. Any day mode shows only the savings, because the other two come too close to the weekday numbers §9 question 23 holds back.
- **Every number comes from the predictions file.** The chart numbers are counted from the model tables and the finished test by `src/broadway_rush/model/site_charts.py`.

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
    - **Built 2026-10-22** (`scrapers/ticketmaster.py snapshot`): next 8 days → about 300 unique Broadway performances at 36 theaters (2026-11-05), with sale status. Many shows are listed twice under two venue IDs, so remove duplicates by theater + date + time. (First written as 362 at 40; that counted duplicates. The real Oct 22 figure was 263 at 29.) No prices or seat counts for Broadway. Daily for now; only on Refresh after launch (§6.2).
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
- **BroadwayWorld forums (built 2026-11-06):** threads found through the public sitemap, because the search page is disallowed. 47 rush threads and 232 posts since June 2024 (`scrapers/bww_forum.py`). Few posts, but public and allowed.
- **Show-fan subreddits (added 2026-11-06):** r/Hadestown, r/wicked, r/SixTheMusical, r/andjuliet, r/hamiltonmusical, r/TheOutsidersMusical and r/BroadwayTickets, through the same archive. r/theatre stalled and was dropped. Talkin' Broadway's All That Chat is skipped: it's behind bot protection.
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
- **Built 2026-11-05:**
  - `broadway_rush/calendar_features.py` → `data/processed/calendar_daily.csv`: one row per date, June 2024 → Jan 2027 (rule-based dates plus the sourced list in `registry/calendar_events.csv`). Adds Broadway Week, which cuts prices, and the 2026 World Cup, a one-off whose effect can't be separated from summer 2026.
  - `scrapers/weather.py` → `data/raw/weather_nyc.csv` (886 days, no gaps) and `weather_forecast_nyc.csv` (16 days), with morning-line hours kept separate. Modeled values, not station readings: the Jan 25, 2026 storm reads ~7.8 in. against 11.4 reported at Central Park. The website must credit Open-Meteo (CC BY 4.0).
  - **Not built:** college breaks. Only one could be verified (Mar 16–20, 2026), and a feature with holes would mark most real breaks as "not a break". Closing announcements and weeks since opening come with the cast and grosses work.

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
- **Built 2026-11-05:** `scrapers/nyc_events.py` → `data/processed/nyc_events_daily.csv` (full street closures and parades in the theater district, parades and races in Manhattan), and the hand-kept list in `registry/calendar_events.csv`. Raw counts mislead: ~157k of 212k Manhattan rows are sports permits, and parade grandstands are listed three weeks early. **Unknown, not zero:** Sept–Oct 2026 and anything over a month ahead aren't published yet, and July 3–7, 2026 can't be told apart from a lull; these days have `permits_complete = 0` and blank counts.
- **Not built:** Ticketmaster NYC events, SeatGeek, Javits, nyctourism.com.

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

How much a show's rush count swings day to day: first look (2026-11-05), among the 13 shows with 5+ stated counts, the typical swing is about half the show's average (coefficient of variation: median 0.49, from 0.13 for Every Brilliant Thing to 0.88 for John Proctor Is the Villain). Some of that is extraction noise.

**Extraction (LLM over each comment) → one row per observation** (`line_count` / `attempt` / `supply`, per `docs/labeling-schema.md`; one comment can have several):
`show, performance date, matinee/evening, rush type, arrival time, line position, outcome (got / didn't / full price only), tickets bought, stated count, sellout time, SRO offered, return visit time/outcome, cast notes, comment timestamp, extraction confidence`

Validation: ~~hand-label ~100 comments first~~ done: a 100-comment answer key plus a 50-comment held-out set, pre-labeled by Claude and reviewed by me ("human-reviewed labels"). Results in §5.5.

## 5. Model (initial thinking)

**Tickets available:** negative binomial regression with an interval-censored likelihood; Bayesian hierarchical with show as a group effect. The predictive distribution gives "__% confident of __ ± __" at any confidence level (slider).

**Arrival time:** model line position vs. arrival time per show and day type; recommended time = latest arrival where expected line position < predicted supply with high probability. Always displayed, even if extreme.

**Verdict / worth-it bar:** P(get a ticket | arrive at the recommended time). If that time is extreme (e.g. 6 am), the verdict reflects how unrealistic it is (likely black), but the time is still shown.

**Ranking:** **P(get a ticket)**, highest first.

**Problem found 2026-11-05:** the chance at the recommended time comes out about the same for every show, because that time is chosen to hit a target chance. So the verdict and ranking need a fixed comparison, such as the chance if I arrive at 9:00 (§9, question 16).

### 5.1 Low-data shows
- **No data at all → skip** (§2.7).
- **Some data (prices, grosses) but no reports →** predict from the hierarchical prior + popularity features (§3.3, §3.8, §3.12), labeled `Low confidence` with a wider range. Show-specific data takes over as reports arrive.

**Evaluation:** interval coverage (80% intervals contain the truth ~80% of the time), arrival-time error, verdict accuracy (did GO days work out?) on ~~held-out recent months~~ rolling monthly test windows over the last 12 months (§5.2: recent months alone have too few labels); plus real rush runs.

### 5.2 Model options (evaluated 2026-11-05; combo chosen)
Replaces the first "Models to try" table, which listed the same families without checking them against the data. Of these, only Option 4's first version is built (§5.2a); the rest stay as written. Accuracy notes on the other options are expectations.

**Decision (2026-11-05): the combo (Option 4) for both the first model and the final model, because it's more fun to talk about.** The first version stays simple, so I can see the whole site working on it. The final version is a leveled-up combo (~~full Bayesian or an improved combo~~). First version built 2026-11-05/06; how it works and how it scored are in §5.2a.
- **Keeping the first version simple:** LightGBM for the line and the Bayesian model for the cutoff, with a small set of features and one fitted spread on the line side.
- **What it's compared against:** the per-show lookup table stays as the bar to beat.
- **Other first models considered:** Claude suggested the penalized regressions as the quickest first model. They stay as the fallback in the stop rule below and as a comparison row. Boosted trees alone would likely overstate the chance of a ticket.
- **Cost:** this isn't the quickest possible first model (about 2–3 days to build, against about 1 for the regressions), but the work carries over into the final version. With about a day of shared groundwork, that fills the Nov 8–10 slot, so starting earlier helps.

**Every option predicts the same two things:**
1. **Line:** how many people are in line at time *t*, for this show on this day.
2. **Cutoff:** how many people in line get a rush ticket that day.

P(get a ticket if I arrive at *t*) = P(line at *t* is shorter than the cutoff). Arrival time, verdict and ranking all come from that (§5). The ticket count comes from the cutoff, converted from people to tickets: stated counts are in tickets, line positions are in people, and buyers report about 1.8 tickets each.

**What the labels look like** (in-person rush, mapped to a show, counted 2026-11-05: 11,588 rows, 100 shows, 4,493 show-days):
| Part | Amount | What it means for the model |
|---|---|---|
| Line | 7,973 time + count points before 10:00, on 3,397 show-days across 82 shows; 1,854 of those days have 2+ points | The strongest data by far. The spread is about 5.7× what a Poisson model allows (8:00–9:30), so negative binomial, not Poisson. |
| Cutoff | 1,064 show-days: 207 with a stated count, 686 with only a lower bound ("got it at #7"), 81 with only an upper bound (sold out, or SRO / full price only), 11 with both, 79 with only a sold-out time | Almost entirely one-sided. The model must use bounds, and something has to set the ceiling for shows that only have lower bounds. |
| Outcomes | 1,133 attempts with an arrival time and a known outcome: 89% got a ticket | People post their wins. A model that always says "yes" scores 89%. |
| Matinee vs evening | 91% of rows don't say | Predict per show-day. Matinee vs evening can only be a small adjustment, so the details view (§2.1) may show one prediction for both. |
| What explains line length at 8:00–9:30 | Show alone 24%, show + weekday 42%, show + quarter 37% (measured on the same data, so optimistic) | A lot stays unexplained. Expect wide ranges from any model. |
| Line vs tickets | Rank correlation (0 = unrelated, 1 = move together) on the 125 show-days with both: 0.09 within a show (100 days, 14 shows), 0.29 pooled, 0.24 between shows (21 shows) | Mostly separate questions. Being good at predicting the line says little about predicting tickets. |
| Line vs popularity | Across 38 shows: 0.57 with % capacity, 0.43 with average ticket price. 45% of shows moved by 1.5× or more between the first and second half of their reports | Related, not the same. Popularity also drifts, so every model needs a "recent line level" input. |

**The options: pros and cons.** Build times are after about a day of shared groundwork, with 6 model days in total (Nov 8–10 and Nov 17–19, §8). Build and fit times are estimates; accuracy notes are expectations until the backtest runs. Each row lists one pro and one con; a pro and a con on the same row aren't related.
| Option | Pros | Cons |
|---|---|---|
| **1. Bayesian hierarchical** (NumPyro) | Treats "got it at #7" as "at least 7", which is all that most cutoff days offer (686 of 1,064). | Longest build of the single models: ~2 days, and the most uncertain. |
| | Shows with only lower bounds borrow a ceiling from other shows. | The fit could be slow or fail to converge. Weekly fit ~10–40 min. |
| | New and thin shows start from similar shows, and their ranges widen by themselves, so `Low confidence` is computed (8 of the 22 shows reported in the last 45 days have under 35 rows). | We choose the shape of the line curve up front, and a wrong shape hurts every show. |
| | Five reports from one morning count as one busy day, not five separate facts (1,854 days have 2+ points). | For shows with only lower bounds, the cutoff is an informed guess. |
| | Slider, chance of a ticket and arrival time all read off the same simulations. | May lose to trees on plain line error. |
| | Each factor is a plain multiplier on the line, so "why this prediction" is easy. Refresh on Vercel is arithmetic on saved results. | New heavy packages (numpyro, jax), not yet run on this laptop. The math takes more explaining. |
| | Strongest competition story: biased, one-sided labels handled openly, with proof the ranges are honest. | Slow to test: 12 monthly test windows at 10–40 min each is about 2–8 hours per backtest, repeated for every with/without row in §5.3. A faster fit cuts that, with less reliable ranges. |
| **2. Boosted trees** (LightGBM + XGBoost) | Quick: ~1 day to build, under a minute to fit. | Cutoffs will likely float too high: 686 lower bounds vs 81 upper, and nothing pulls them down. The app then says GO too often, and the 89% "always yes" score would hide it. |
| | Likely the best at predicting line length. | A new show gets an average of similar rows, with no wider range to warn anyone. |
| | Finds combinations by itself (this show + Saturday + school break), with no curve shape to choose. | Same-day reports look like separate evidence, unless we weight each show-day to count once. |
| | Handles many features and messy data with little setup. | The slider needs one model per confidence level, or a distribution on top, and separate levels can contradict each other. |
| | Standard tools that interviewers know. Per-feature contributions can explain each prediction. | Trees can't easily run on Vercel, so the weekly job has to save predictions for the few cases Refresh can change (on TKTS or not, on sale or not). |
| | | Needs two libraries, because LightGBM can't take bounds (XGBoost's AFT objective does the cutoff). A familiar story that stands out less. |
| **3. Penalized negative binomial regressions** (SciPy) | Quick: ~1 day to build, seconds to fit. | Ranges run narrow because they ignore uncertainty in the model's own estimates, most of all for thin shows. |
| | Easiest to explain: every coefficient is a plain multiplier. | No busy-day effect, so same-day reports look like separate evidence. Weighting each show-day to count once helps; a real busy-day effect would make it a mixed model and lose the simplicity. |
| | Takes bounds as bounds. | The penalty is a blunter ceiling than Option 1's, so shows with only lower bounds may still float high. |
| | The penalty stops thin shows from going wild. | A new show falls back to the average, with no wider range. |
| | Only needs SciPy. Refresh on Vercel is plain arithmetic. | Misses combinations unless we add them by hand. |
| | Shares its likelihood with Option 1, so it's also Option 1's fallback. If it ties Option 1, it's the simpler thing to ship. | We write the bounds likelihood ourselves (statsmodels has none), which leaves room for bugs. A plain competition story. |
| **4. Mix** (trees for the line, Bayesian for the cutoff; rescored 2026-11-05, first version was too harsh) | Each part gets the tool that fits its labels: full numbers for trees, bounds for Bayesian. | Longest build: ~2.5–3 days of the 6 available. |
| | Possibly the most accurate overall. | Two systems to debug, plus the step that joins them. |
| | Keeps Option 1's cutoff, which avoids the trees' too-rosy GO problem. The ticket range and slider come straight from it. | Joining assumes line and cutoff are unrelated once the features are known. First check: 0.09 within a show, so it looks safe, but on only 100 show-days. |
| | Quick to test: trees fit in under a minute, and the cutoff model is much smaller than Option 1 (1,064 labeled days, no line curve, no busy-day effect for each of 3,397 line days), so minutes rather than 10–40. That makes the results and with/without tables practical. | Thin and new shows get no pull toward similar shows on the line side. `Low confidence` would be set by rule, and thin shows' spread calibrated separately. |
| | The line needs no curve shape chosen up front. | No popularity number comes straight out of the line side. We'd compute one by predicting each show on a standard day, with no error bars. |
| | Three new packages: lightgbm, numpyro, jax (no XGBoost needed). | Trees can't easily run on Vercel, so the weekly job has to save predictions for the few cases Refresh can change. |
| | A clean story: demand has full numbers, supply has bounds, so each gets the tool that fits. | The busy-day effect isn't modeled directly on the line side, so same-day reports are weighted to count once. The joining step takes explaining. |

**Ruled out:**
| Model | Pro | Con |
|---|---|---|
| Direct "got it / didn't" classifier | The most direct answer to "will I get one?", and quick to build. | 89% of known outcomes are wins, so it would mostly learn who posts. It can't give a ticket count. |
| Poisson regression | The simplest count model. | The line's spread is about 5.7× what it allows, so its ranges would be far too narrow. |
| Survival on clock time (time to sellout) | A natural fit for "when does rush run out?" | Only 134 show-days have a sold-out time. Counted by line position instead, survival is already the cutoff part of Options 1 and 3. |

**Recommendation: Option 4** (changed 2026-11-05; ~~Option 1~~). Working through it showed the first scoring was too harsh: it charged the combo for the full Bayesian model's fit time, but its Bayesian part covers only the cutoff, the smaller part. Testing speed decides it: the results and with/without tables (§5.3) need many full backtests, which is practical with the combo and slow with Option 1. Option 1 keeps two advantages: thin shows on the line side, and one joined model with no independence assumption. Trees winning on the line is still an expectation, so the comparison rows have to test it before the model freezes. **Stop rule:** if the cutoff model isn't working by the end of Nov 10, fit it a faster way, then use Option 3's cutoff, so a delay can't reach the website stage. **The model is frozen at turn-in, Nov 24 (§8).**

**Same for every option:**
- **The lookup table stays:** per-show median by weekday and time window (the first version of this spec called it the baseline). It's the bar to beat. If nothing beats it, say so.
- **Test windows:** rolling monthly windows over the last 12 months, training only on earlier data, never shuffled. A single last-3-months test would hold only 3 stated counts and 5 negative outcomes; 12 months has 80 and 52, plus 2,467 line counts and 485 wins. Keep some windows untouched for the final score, so that picking winners doesn't become overfitting: the last few, or every fourth month, since the last 3 months are thin on ticket labels.
- **Only what's known at prediction time:** grosses lag at least a week (published after the week ends), TKTS is the previous day's, forecasts replace modeled weather, blank permit counts stay unknown.
- **Line points only from before the box office opens.** After that the line shrinks as tickets sell (1,260 rows at or after 10:00). Opening times vary by show and day, and many box offices open at noon on Sundays (§3.4), so measure time from that show's opening that day. The counts above used a flat 10:00 cutoff, so the real numbers will shift a little.
- **Dates:** 1,135 in-person rows come from keyword posts and have only a comment date, which may not be the visit date, so test with and without them. Drop impossible dates (1900, "2025-06-00", anything before June 2024).
- **Cast features plug in later:** cast + closing news isn't built yet (§3.12). Any option can take it as one more feature, so the model doesn't have to wait.
- **Digital rush is separate and simple:** 443 rows, only 143 tied to a Broadway show, almost no sell-outs. A pooled estimate labeled low confidence, under any choice.
- **Installs:** a dry run on Python 3.14 + Windows found ready-made packages for all of these (numpyro 0.22, jax 0.12, lightgbm 4.7, xgboost 3.4, scikit-learn 1.9, scipy 1.18), but none has been run yet. Only SciPy is installed so far (in `.venv`, not in `pyproject.toml`). The combo needs lightgbm and numpyro (which brings jax). Avoid `lifelines`: it would force pandas 3 back to 2.3.

### 5.2a The combo: how it works (first version built 2026-11-06)
| On the page | Comes from |
|---|---|
| "__ ± __ rush tickets" and the confidence slider | The Bayesian cutoff |
| Arrival time, chance %, worth-it bar, ranking | Both parts, joined |
| "Why this prediction" | Trees for line reasons, Bayesian for ticket reasons |

1. **Line (LightGBM):** predicts how many people are in line for each show-day, at each time before the box office opens. The line can never shrink as opening approaches, so arrival times make sense. Each show-day counts once in training. One fitted spread turns the prediction into a range of possible line lengths.
2. **Cutoff (Bayesian negative binomial, NumPyro):** stated counts go in as exact numbers, and "got it at #7" goes in as "at least". Shows are pulled toward what's typical across shows. Its simulated draws give the ticket range at any confidence level.
3. **Join:** on a 15-minute time grid, the chance of a ticket is how often the line comes out shorter than the cutoff across the draws. This assumes the two are unrelated once the features are known (first check: 0.09 within a show, on 100 show-days).
4. **Arrival time:** the latest time that still reaches the target chance. Always shown, even if extreme.
5. **One fixed predictions file:** the site reads only this file, so the model can be leveled up without touching the site.
6. **Refresh:** trees can't easily run on Vercel, so the weekly job saves predictions for the few cases Refresh can change (on TKTS or not, on sale or not).

**First version's features:** show, time before opening, weekday, calendar, recent line level, and last available grosses. ~~Weather~~ is out: a best-case test using what really happened added nothing (4.73 either way), and no past forecasts are on disk for a fair one. Cast news, TKTS and NYC events come later, one test at a time. Step 6 (Refresh) isn't built.

**What the build changed from the plan (code in `src/broadway_rush/model/`):**
- **Faster fit:** 4 chains run together, 300 warmup + 300 kept steps, target 0.8, tree depth up to 7, starting from the middle of the priors, up to 3 attempts. Heavier settings with chains on separate CPU devices didn't finish one window in 11 minutes on this laptop. The code won't write predictions unless R-hat is 1.05 or lower.
- **Tickets per person:** fixed at 1.0, the best of 1.0, 1.4 and 1.8 in the tests, and the lowest tried. Buyers report about 1.8 each, so this isn't settled.
- **Verdict and ranking:** the chance if you arrive at 9:00. **Placeholders:** GO at 70%+, Maybe at 40%+, target chance for the arrival time 80% (§9, questions 1 and 16).
- **Who counts as having in-person rush:** General Rush or Standing Room on Playbill's list, or 3+ in-person reports in the last 30 days. Playbill's list misses shows with real lines, including Rocky Horror, the most-reported show.

**Test result, first version (9 test months: Nov 2025, Jan, Feb, Mar, May, Jun, Jul, Sep, Oct 2026; Dec, Apr and Aug are locked for the final score). All numbers are in §5.3.**
- **Better than the lookup table:** line length (in all 9 months) and honest line ranges.
- **Worse than the lookup table:** ticket counts, the chance of a ticket, and slightly on arrival time. On the chance it's also worse than a flat rate, and on yes/no it ties always saying yes, catching 1 of 16 misses.
- **Why:** the ticket model floats high, as §5.2 warned. Its typical day is about 27 tickets against a median stated count of 6, because 549 "at least" days far outnumber the 75 with an upper bound. A tighter prior on the spread barely changed anything, so this is the labels, not the prior: stated counts and "got it at #p" reports disagree.

### 5.2b Training times (combo and lookup table measured 2026-11-06)
Measured on this laptop (16 cores, plugged in), with nothing else running, using the faster fit (§5.2a). A window is one month's test. **The 12-window time is scaled up from 9 real windows:** the 3 locked months weren't run.
| Model | One training run | Full test |
|---|---|---|
| Per-show lookup table | 0.03 seconds per window (measured) | Under a second (measured) |
| LightGBM line alone | 0.7 seconds per window (measured); 1.8 seconds on all data | Under a minute (measured) |
| Bayesian cutoff alone | 55 seconds per window (measured); 69 seconds on all data | |
| **Combo** | 0.9 minutes per window (measured) | **8 minutes for 9 windows (measured); about 11 minutes for 12 (scaled up)** |
| Penalized regressions | Seconds (estimate, not built) | A few minutes (estimate) |
| Boosted trees alone | Under a minute (estimate) | Under 15 minutes (estimate) |
| Full Bayesian | 10–40 minutes (estimate, not built) | 2–8 hours (estimate) |

The first estimate for the combo was "a few minutes" per run and "about an hour or less" for the full test. A slower, heavier fit would take longer than these numbers. The full test repeats for every with/without row in §5.3.

### 5.2c Ways to level up the combo (for the final version; I'll decide later)
Best first. None has been tested: benefits are expectations, and effort is an estimate.
| Level-up | What it does | Main benefit | Effort |
|---|---|---|---|
| **Borrow across shows on the line side** | Gives the trees a "show level" pulled toward similar shows | Better predictions for thin and new shows, which is full Bayesian's main advantage | Half a day |
| **Use the reports the ticket model ignores** | Turns sold-out times and "2 left at 6 pm" reports into extra ticket labels (79 show-days have only a sold-out time, and hundreds of reports say tickets remained) | More labels for the weakest part of the data | About a day |
| **Learn from real outcomes directly** (added 2026-11-06) | Adds a last step that adjusts the chance using reports of who got a ticket and who missed (669 outcomes, 85 of them misses, using only earlier months in each test). The ticket model uses these only indirectly, as rough limits | Better chances, and it may catch more misses | Estimate: about half a day |
| **Learn tickets per person** | Estimates how line positions convert to tickets, instead of assuming (buyers report about 1.8 each) | Could shift every ticket number on the site | A few hours |
| **Give thin shows wider ranges** | Measures the line's uncertainty separately for thin and well-reported shows | More honest chances | A few hours |
| **Add features one test at a time** | Tests cast news, TKTS and NYC events one by one, keeping only what helps | Accuracy, and it fills the with/without table | Under a day |
| **Model the reporting bias directly** | Accounts for wins getting posted more often than losses | Speaks directly to the rubric's "is bias accounted for?", and would be the most impressive | 1–2 days; riskiest, and may not work with so few reported losses |
| **Add clean labels from real trips** | Feeds in verified reports, including my own trips and any losses | Best long-term accuracy for my own show-going | Already planned with the report form (§3.10) |

- **Suggested order:** the first four in the Nov 17–19 slot, then features as time allows, and the reporting-bias model only if there's time left.
- **What the first version's test results point to (checked 2026-11-06, 9 test months):**
  - **Waiting won't fix it.** At the Aug–Oct pace, the 17 days to Nov 23 add about 90 line rows (1.5%), 6 ticket show-days (0.8%) and 5 outcomes (0.8%).
  - **Tickets look like the weak part.** On the 33 stated counts, the combo's middle estimate is 18 against a stated 6, though people may mention a count more often when it's small.
  - **Telling hits from misses is weak.** Given one attempt that got a ticket and one that missed, the combo ranks them correctly 60% of the time and the lookup 64% (a coin flip is 50%). 9 of the 16 misses were rated GO, and 6 of the 16 were at Just in Time.
  - **The "too high" ticket result has a second side.** On the 122 test days with only an "at least" report, the combo's middle estimate cleared that minimum 95% of the time, and the lookup 62%.
  - **Big line misses all go one way.** Every one of the 42 misses of 20+ people was a real line longer than predicted. Some may be bad reports, not bad predictions: Oh, Mary! on Mar 4, 2026 has reports of 9 people and, about 1.4 hours later, 79. The Lost Boys on May 27 has 15 and 50 at the same time. Read the comments before removing anything, and never remove a report just because the model missed it.
  - **So do the ticket upgrades and outcome step first.** 16 misses is a small test, so one or two can swing a result, and "always yes" may look better than it is because wins get posted more than losses. Judge upgrades on catching misses and ranking as well as overall accuracy.
- **Not worth doing now:** modeling a link between line and tickets. The 0.09 correlation suggests little to gain.
- **Tried 2026-11-06, didn't help:** a tighter prior on the ticket spread (§5.2a).
- **Keep it honest:** keep an upgrade only if it beats the previous version on the rolling tests, and report the final score on the untouched windows (§5.2).
- **Timing:** design changes have to land before the Nov 24 freeze. Clean labels can keep helping after that through weekly retraining (§9, question 19).

### 5.2d Questions worked out 2026-11-05 (expectations, untested)
**Does being best at line length mean best at predicting tickets?** No. The line is how many people show up; tickets are what the theater has to sell. Trees should do well on the line because those labels are complete numbers. On tickets they'd likely be the weakest, because most labels only say "at least X".

**Why does only full Bayesian treat same-day reports as a busy day?** It gives each show-day a hidden "how busy" number, estimated from all that morning's reports. Trees look at one row at a time and have nowhere to keep that number. Regressions could add it, but they'd lose their simplicity. This matters less than it first looked: weighting reports so each show-day counts once fixes the over-counting, and ranges calibrated on later days already include day-to-day swings.

**Which is quickest on the frontend?** They're the same for page loads and the slider, because the site reads saved predictions. Only Refresh differs, and most of its 10–15 seconds is fetching TKTS and Ticketmaster.

**Which measures show popularity best?** Full Bayesian: each show gets a line level with error bars, after adjusting for weekday and weather. The combo can compute one by predicting each show on a standard day, without error bars. Across all shows, grosses are the better measure, because shows without in-person rush (like Hamilton) have no line.

**Is the combo more accurate than full Bayesian?** Unknown until tested.
| What's predicted | Combo vs full Bayesian |
|---|---|
| Ticket count | About the same: it's the same kind of Bayesian model |
| Line length, shows with lots of reports | Combo probably a little better |
| Line length, new or thin shows | Full Bayesian probably better |

**Will the combo score better with judges?** The choice mainly affects Data Processing, 10 of 50 points (§1.1), and no criterion scores accuracy by itself. Full Bayesian would likely score about the same. The join is where a judge is most likely to find a mistake, so it needs a clear explanation.

**How do I explain the combo?** "Line counts are full numbers, so trees predict them. Ticket counts are mostly 'at least 7', so a Bayesian model handles those and borrows across shows. Then I combine them into a chance of a ticket at each arrival time."
- **Hard question:** "Why assume line and tickets are unrelated?" Answer: 0.09 correlation within a show, though on only 100 show-days.
- **Still need to know:** priors and convergence checks, because the ticket part is Bayesian.
- **For comparison, full Bayesian:** "One model of the whole morning: each show has its own level, pulled toward similar shows, each day has a busy-day effect, and ticket labels go in as bounds." It stands out more, but it's riskier under questioning about convergence and curve shape.

**What should impress judges and interviewers?** The thinking more than the model's name:
- Catching that always saying "yes" scores 89%, so not training a simple got-it/didn't classifier.
- Treating "got it at #7" as "at least 7".
- Testing in time order, checking that ranges hold up, and reporting the score against a simple lookup table even if it's unflattering.
- Testing the AI extraction on held-out comments checked by a human.

### 5.3 Results table (for the portfolio) 📊
Report a table that makes it easy to show how the model works and how well it does. Keep it in the README and on the accuracy page (§2.6). Example layout:

| Model | Features | MAE (tickets) | 80% interval coverage | Avg interval width | Verdict accuracy | Arrival-time error | Notes |
|---|---|---|---|---|---|---|---|
| Lookup table (bar to beat) | show, weekday | **6.2** | 69.7% | 11.5 | 88.4% | **95 min** | Line error 5.82; 80% line range held 58.8%; chance error 0.097; 0 of 16 misses caught |
| Combo, first version | small set | 11.6 | 93.9% | 57.6 | 88.4% | 102 min | **Line error 4.73; 80% line range held 86.5%**; chance error 0.107; 1 of 16 misses caught |
| *Always say yes* | none | | | | 88.4% | | Flat rate's chance error 0.103 |
| NB GLM | + capacity, prices | | | | | | |
| Bayesian hierarchical | all | | | | | | |
| LightGBM + conformal | all | | | | | | |
| Final model | all | | | | | | |
| *Ticket-data ablation:* with vs. without TKTS + Ticketmaster features | | | | | | | decides whether ticket data and the Refresh button stay (§6.2) |

Also include: a **feature-importance / ablation table** (what happens to accuracy when you remove prices, NYC context, cast changes, etc.), dataset size (reports, shows, date range), and a one-paragraph plain-English "how it works."

**After data cleaning (2026-11-06, test tag `more1`; the site now uses this).** The table below is still the first test (`n1.0`). Scored on identical test reports, so cleaned answers can't flatter it: line error 4.74 to 4.69 people (1,407 reports), stated-ticket error 11.72 to 11.50 (29 counts), Brier 0.090 to 0.090 and ranking 0.598 to 0.578 (127 attempts). On each test's own reports, which now number 1,711 line reports, 42 stated counts and 182 attempts with 20 misses: line error 4.71 vs. the lookup's 5.96, 80% line range held 85.5%, arrival-time error 96 vs. 100 minutes (the model now wins this), ticket error 15.8 vs. 8.5, right at 50% 87.9% vs. always yes 89.0%, Brier 0.105 vs. 0.093. Cleaning made the data more correct and larger, but not the model much more accurate. Wider always-yes count: 87.1% of 1,493 attempts (~~89% of 1,133~~, before cleaning).

First two rows and "always say yes": real results, 9 test months (33 stated counts, 138 attempts, 1,507 line points), measured 2026-11-06. Verdict accuracy here is yes/no at 50%. The other rows aren't built.

**Verdict accuracy needs a comparison:** always show it next to the "always say yes" score (89% on the wider count of known outcomes, §5.2; 87.3% with stated dates only; 88.4% on the attempts in the test months), and report how often the model catches the days people missed out, not just the overall score.

**Comparison rows:** by default the NB GLM, Bayesian hierarchical and LightGBM rows stay as lighter fits, so the table shows what the combo beat. That's about 1 extra day (§9, question 17).

### 5.4 Training cadence
- **Retrain weekly**, right after the weekly Reddit scrape and extraction (§6.1), then write predictions for the next 14 days. (Changed 2026-11-02; was "weekly or less, with predictions updated nightly and every morning.")
- **Predictions change** when the model retrains and when someone clicks Refresh, which brings in today's ticket data (§6.3).
- **Training time:** measure at step 5. The simple models should take seconds; the Bayesian model is the slow one (maybe minutes to tens of minutes). Whatever it is has to fit in the weekly job. Estimates by model are in §5.2b.
- Watch interval coverage on the accuracy page; if it drifts, retrain sooner.

### 5.5 LLM extraction budget (Claude Haiku)
- **Model:** Claude Haiku 5.5 (`claude-haiku-5-5`) for extracting structured rows from Reddit and forum comments (§4) and casting news (§3.12).
- **Total budget: $8 for the whole project** (raised from $5 on 2026-10-22; $10 of credits loaded). The code enforces a hard stop at $8 across every run (`data/interim/llm_spend.csv`).
- **Actual so far:** $1.49 (pilot + held-out $0.04; full extraction of 46.8k comments $1.30 via Batches + caching; top-up of 7.4k comments $0.13; catch-up of 576 comments $0.02 on 2026-11-05). Result: 18,412 observations from 10,396 comments in `data/processed/reports.csv`. See `process.md` step 3 and its wrap-up.
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
  - How long: at least 2–3 months is a guess. Daily-thread reports ran ~6–11 a day in Sep–Oct 2026 (13 a day since May), about three-quarters naming a show, so three months may give ~450–750 usable reports with ticket data. (First written as ~16 a day → 1,000–1,500.) Decide at step 5.
  - Times (`.github/workflows/snapshots.yml`): Ticketmaster at 7:07 am EST, when day-of users check, with a backup at 9:07; TKTS at 12:07 and 6:07 pm EST, with backups at 2:07 and 4:07 (backups added 2026-11-06, because GitHub started one run about 7 hours late). **Added 2026-11-09:** early TKTS runs at 8:07 and 10:07 am EST, because on Nov 7–8 TKTS runs started 3.5 to 4 hours late and on Nov 8 the 4:07 and 6:07 pm runs saved nothing. At those delays the early runs land around noon and 2 pm; on time, they find an empty board and save nothing. All are an hour later on the clock during daylight time. Archived boards were updated 10 am – 8 pm, so a morning TKTS snapshot wouldn't help; cut to one a day once we see when the board settles.
  - A day-of morning prediction can't see that day's TKTS board yet, so it would have to use the previous day's. Settle at step 5.
- **Getting snapshots to the site (built 2026-11-06):** the job saves to the data repo, not to this project's `data/raw`, which the model and site read. `.venv\Scripts\python -m broadway_rush.sync` pulls the local clone, copies any missing snapshots, rebuilds the two CSVs and updates predictions if there's a newer schedule. It sends no requests to ticket sites, never overwrites a file, and runs only when started by hand. Only Ticketmaster changes the site for now: it sets which shows play when. The model doesn't use TKTS yet.
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
| No historical availability / price snapshots | §3.2, §3.8. No legal source has seat counts at all. Snapshots of what is legal (TKTS, Ticketmaster sale status) start once the daily job is scheduled; nothing was collected Oct 23 – Nov 4, 2026, except one archived TKTS board. Grosses are the proxy before that. |
| Labels mostly bounds | §4, §5.2. 686 show-days have only a lower bound, 81 only an upper bound, 207 a stated count. Intervals will be wide early on. |
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
- **Look (changed 2026-11-06):** purple theme, glowing light text (~~lighter background with dark text~~, tried and changed back the same night), at least 7/8 of the screen width, Bebas Neue headings and Poppins body (~~font to be replaced later~~); worth-it bar **black → gray → gold** (~~red → blue~~, changed 2026-11-05).
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
- **Tile search, filters and sorting (2026-11-06):** a search box finds shows by name, nickname or theater. Tiles show rush types. Filters: rush type, days showing, runtime, high-profile stars, play or musical. Sorts: best chance, latest arrival, rush price, typical ticket price, runtime. Days showing and runtime are looked up online. The site says "__% seats sold" instead of "__% full" (§2.2a). Built 2026-11-06, except the stars filter, which needs cast news.
- **This week view (2026-11-08, my request):** a This week button shows which of the next 7 days is best: a day strip on top, then one tile per show with its best day and every day's arrival time. Days are compared by arrival time, latest first (tap again for earliest). Box offices open at noon on Sundays and 10 am on other days, so Sunday times get an asterisk and a note, in both views (§2.2b). Built 2026-11-08, ahead of the Nov 11–16 website slot, at my go; local only.
- **Model (2026-11-05):** the combo (trees for the line, Bayesian for the cutoff) for both the first and final models, because it's more fun to talk about. The first version stays simple, to see the whole site working; the final version is a leveled-up combo (§5.2, §5.2a, §5.2c). Not started.
- **Deadline and scope (2026-11-05):** data project competition entry. ~~Due 2026-11-17.~~ **Complete by 2026-11-23, turn in 2026-11-24, present 2026-12-07** (corrected by me the same day). Between turn-in and the presentation, only small tweaks and improvements, **no model changes**. Everything stays in: cast + closing news, NYC permitted events, Refresh + PIN, report form + email approval, weekly automatic job, digital rush predictions. Cutting these was proposed and rejected. Core first (data, model, site), so a delay only moves an add-on. Schedule (stretched to the new dates by Claude, not yet reviewed by me):
  - **Nov 5–7:** data: catch-up, calendar, weather, NYC permitted events, cast + closing news.
  - **Nov 8–10:** first model: the simple combo and the lookup table to beat, with rolling tests.
  - **Nov 11–16:** website on that model: day picker, tiles, details, accuracy page; filters, sorting and plain wording (§2.2a); This week view (§2.2b); then report form + email approval, Refresh + PIN.
  - **Nov 17–19:** final model: level up the combo, refit, digital rush, comparison rows, results and with/without tables.
  - **Nov 20:** weekly automatic job and a full end-to-end test.
  - **Nov 21–22:** repo cleanup, README, competition write-up.
  - **Nov 23:** buffer; project complete.
  - **Nov 24:** turn in. The model's design is frozen from here; it keeps retraining weekly on new data.
  - **Nov 25 – Dec 6:** small tweaks only. The weekly job keeps running, so the accuracy page builds up real results for the presentation.
  - **Dec 7:** present.
- **Scheduled jobs (2026-11-05):** GitHub Actions runs the daily ticket snapshots, so they run with the laptop closed. Snapshots are saved to a separate private repo, `broadway-rush-data`, which stays private when this repo goes public. The job commits to that repo by itself, using a deploy key (secret `DATA_REPO_SSH_KEY`); Rachel still does all commits to this repo.
- **Which shows get predictions (2026-10-22), three groups, decided per show and per date from the policy history:**
  1. **In-person rush + enough data** (~~≥2 daily-thread reports per running week; ~11 shows~~ 35+ line reports or 2+ daily-thread reports per running week; 16 shows on Nov 6: Oh, Mary!, The Outsiders, Operation Mincemeat, Just in Time, Maybe Happy Ending, The Great Gatsby, Rocky Horror, Schmigadoon!, The Lost Boys, Buena Vista Social Club, Two Strangers, Stranger Things, Chicago, Paranormal Activity, 860, Wanted): full prediction (tickets, range, arrival time).
  2. **In-person rush, little data** (~~~5: Chicago, Six, Hadestown SRO, & Juliet, Wicked~~ 6 on Nov 6: Six, Hadestown SRO, & Juliet, Wicked, Downstate, It's a Wonderful Life): no number; "limited data, probably easy" plus the policy and __% seats sold (§2.2a). (Quiet in-person shows run ~84% full vs. 94% for busy ones; `process.md` step 4d.)
  3. **No in-person rush** (lottery / digital only, e.g. Hamilton, Lion King, Book of Mormon): listed with lottery and digital-rush info only, no line prediction. Few Reddit posts here does *not* mean low demand: these shows are 94–99% full.
- **First model and website (2026-11-06, built unattended at my request; each choice is in `process.md`):** the simple combo with the faster fit, 1.0 ticket per person, 9:00 verdict with placeholder thresholds (§5.2a). Three test months locked for the final score. Plain HTML/CSS/JS in `web/`, reads only `web/data/predictions.json`; report form and Refresh + PIN are labeled "Not connected yet". Worth-it thresholds and the verdict comparison are still mine to decide (§9).
- **"Enough data" rule changed (2026-11-06, my decision):** a full prediction needs **35+ line reports OR 2+ daily-thread reports per running week.** Claude picked 35 from the tests: shows with 10–34 line reports before the test month lost to the lookup table (80% range held 75%), and shows with 35+ beat it (86–92%). Any cutoff from 23 to 81 picks the same shows today.
- **Daily data reaches the site by one command (2026-11-06):** `broadway_rush.sync` (§6.2). The site now runs Nov 7–13 from the Nov 6 snapshot. ~~Whether the schedule fires on its own is still unconfirmed: only manual runs have saved anything so far.~~ Confirmed 2026-11-07: with no button press it saved 2 Ticketmaster and 3 TKTS snapshots, though the morning runs started about 5 hours late. The Nov 7 sync moved the site to Nov 8–14.
- **Build order:** 1 Reddit → CSV ✅ · 2 labels + Haiku pilot ✅ · 3 full extraction ✅ · 4 grosses + rush policies + show catalog ✅ · 6 snapshot scrapers (moved up because ticket data has no history; TKTS + Ticketmaster built 2026-10-22, daily job working 2026-11-05) · 5 first model (simple combo) + results table · 7 website · final model (leveled-up combo). Don't skip ahead without asking.
- **Accuracy page:** yes, now called Nerd stats (§2.6).
- **Charts (2026-11-06, my picks):** line growth, show-by-day grid, predicted vs. real, what drives the line, chance vs. what happened, cleaning funnel, rush savings, reports per show. Plain ones go on show pages, and everything else goes on Nerd stats (§2.6).
- **Docs:** `SPEC.md` (this file), `process.md` (what was built and how, kept up to date during coding), `interview-notes.md` (private talking points, **git-ignored**), `claude-notes.md` (Claude's working notes between sessions, **git-ignored**).

## 9. Open questions

1. Worth-it thresholds: what probability counts as "GO"? Decide after step 5, from the backtest. **Placeholder for now: GO at 70%+, Maybe at 40%+, target chance for the arrival time 80%.** In the tests GO worked out 109 of 118 times, Maybe 12 of 18, Stay home 1 of 2, so "Stay home" almost never fires.
2. ~~Where the scheduled jobs run.~~ Decided 2026-11-05: GitHub Actions (§8). TKTS accepts GitHub's machines (tested 2026-11-05).
3. ~~Where the daily snapshot data is saved.~~ Decided 2026-11-05: private repo `broadway-rush-data` (§8).
4. ~~Snapshot times.~~ Set 2026-11-05 (§6.2).
5. **How long Phase A (daily ticket collection, §6.2) runs** before switching to click-only. Guess: at least 2–3 months; decide at step 5.
6. **After launch, keep a cheap daily ticket snapshot anyway?** It keeps history-based features ("days on TKTS in the last 30") and adds training data that isn't skewed toward days someone clicked, at ~5 requests a day. Or go click-only as planned.
7. **Before making the repo public:** git history keeps every old version, so deleting files isn't enough. Scrub `hand_labels.xlsx` and the `author` column of `reports.csv` out of the history, or publish a fresh copy with one clean starting commit? Also check whether Ticketmaster's API terms allow publishing its data.
8. **Website build (step 7, on Vercel):** ~~Next.js (Vercel's own) or a plain static site?~~ First version is a plain static site in `web/`, which reads one predictions file. It still needs a way to run the report form and Refresh. How the weekly predictions reach the site (e.g. the weekly job writes a predictions file, then triggers a Vercel redeploy)? The report form (§3.10) also needs a free database and an email service.
9. Hosting budget: likely **$0** now. The old worry was a nightly headless-browser scrape; the legal sources are one API and one plain page.
10. Design phone-first? (Likely used at 7–8 am on a phone.)
11. TodayTix: ask them for permission to use their data (§3.8), or drop it?
12. ~~Does the NYC Open Data permitted-events feed include the Marathon and other major races and parades?~~ Checked 2026-11-05: yes, but the Marathon is listed through Parks setup permits and shows 0 in the daily table on race day, so its date comes from the hand-kept list. Thanksgiving, Pride and St. Patrick's parades show up on the right days.
13. **Competition rules:** ~~what are judges scoring?~~ Rubric received 2026-11-05 (§1.1). Still unknown: what has to be turned in on Nov 24 (public repo, live site, write-up?), whether this is solo or a team (the rubric asks whether all team members spoke equally), and whether the presentation is live or recorded (the rubric scores audio quality).
14. **Refresh by the deadline:** there will only be about 18 days of daily snapshots by Nov 23 (about 32 by the Dec 7 presentation, after the model is frozen), so the with/without test in §6.2 can't settle whether ticket data helps. Proposal: keep Refresh for the competition. It shows today's TKTS board and sale status, and changes a prediction only if the model has evidence for it, using the 118 archived TKTS days. The §6.2 rule about dropping Refresh waits until there's enough data.
15. **Thin shows, the spec disagrees with itself:** §2.7 and §5.1 say they get a low-confidence prediction; §8 says in-person shows with little data get no number ("limited data, probably easy"). Decide after the backtest shows whether thin-show ranges are honest.
16. **Verdict and ranking:** what fixed comparison should they use (§5)? For example, the chance if I arrive at 9:00. **The first model uses that as a placeholder.** On Sundays 9:00 is three hours before a noon opening, so Sundays look better. **This week view (decided 2026-11-08, §2.2b):** days are compared by arrival time, and Sunday times are marked because box offices open at noon. The same mark goes on Sunday tiles here. The day view's 9:00 comparison is unchanged and still a placeholder.
17. **Comparison rows:** keep the NB GLM, Bayesian hierarchical and LightGBM rows in the results table as lighter fits (the default, about 1 extra day), or show only the lookup table and the combo?
18. **Cast + closing news:** waiting on my go-ahead (§3.12). The model can start without it, because cast features can be added later.
19. **After the Nov 24 freeze:** does weekly retraining on new data continue? Assumed yes (§8): it's the same model on new data, and it lets the accuracy page build up real results for the presentation.
20. **"Limited data, probably easy" on a nearly sold-out show:** "probably easy" came from quiet shows being less full. It doesn't fit standing-room shows: standing room sells only when the show sells out, and Hadestown was 95% full on Nov 1. Goes with question 26.
21. ~~"Enough data" rule.~~ Decided 2026-11-06 (§8).
22. ~~**Fonts:** I don't like them. Fix later.~~ Decided 2026-11-06: Bebas Neue + Poppins (§2.4).
23. **Any day mode, later dates:** should a tile show a rough number for the weekday ("Usually on Tuesdays: get there by 8:40")? Default no, because §1 limits predictions to the next 7 days and calls anything further extrapolation.
24. ~~**Real dates further ahead:** the weekly job could pull Ticketmaster's schedule about 5 weeks out.~~ Dropped 2026-11-06: days showing comes from show websites (§2.2a).
25. **Filter choices to review (§2.2a):** the high-profile star rule, the runtime bands, and whether Lottery and Standing room belong in the rush-type filter, since they aren't rush. Also from the build: a standing-room price counts as the rush price when a show has nothing else (Hadestown $39, Six $49), and Hadestown gets `In person (reported)` as well as `Standing room`.
26. **Limited-data shows (parked 2026-11-06, to figure out later):** look at other features for them. Nothing built, and the site still says "Limited data, probably easy" on all 6 until this is decided. Only 3 recorded outcomes exist across the 6, so nothing can be tested on them directly. Ideas from Claude, not decided:
    - **Wording:** replace "probably easy" with "Not enough reports to predict". It's on Hadestown at 95% seats sold and on It's a Wonderful Life, which has no reports or grosses.
    - **Standing room:** it sells only when a show sells out, so for a show where it's the only in-person option (Six, 60% seats sold), the question is whether the show sells out at all, not how long the line is.
    - **A rough label:** "usually easy" or "usually busy", with no percentage, from things that don't need rush reports: seats sold, typical ticket price, days on TKTS, how much Reddit talks about the show, and cast news once collected. Test: hide each of the 16 well-reported shows in turn and check whether the label predicts its real lines. If it doesn't beat treating every show the same, keep the neutral wording.
    - **Downstate** may not need any of this: it's at 1.5 reports a week, and 2 gives it a full prediction.
27. **Just in Time's days:** §2.2a's example says it doesn't play Monday or Wednesday. Playbill's schedule (Wednesday in all 8 weeks) and Ticketmaster both show it playing Wednesdays, dark Monday only. The site follows the data. Was the example about something else?
28. **This week view, tie rule (§2.2b):** days with the same arrival time count as tied (placeholder). Times are on a 15-minute grid. On Nov 8–14 this gives 14 of 16 shows a single best day (Sunday); Operation Mincemeat ties Sunday, Tuesday and Thursday, and Wanted ties all 5 days it plays. A wider window (say, within 15 minutes) would name more ties.
- ~~Confirm Ticketmaster Discovery API free-tier limits.~~ Done 2026-10-22: 5,000 calls/day, 5 per second.

# Broadway Rush — Spec (draft)

> Status (2026-11-05): build steps 1–4 are built (Reddit scrape → labeled extraction pilot → full extraction into `data/processed/reports.csv` → grosses, rush policies + history, show catalog). Step 6 was moved up: the TKTS and Ticketmaster snapshot scrapers are built, and the daily GitHub Actions job works (manual run succeeded 2026-11-05; ~~first scheduled run still to confirm~~ scheduled runs confirmed 2026-11-07). Calendar, weather and NYC permitted events were added 2026-11-05. **Updated 2026-11-06: a first model (step 5) and a first website (step 7) are built and run locally, not deployed.** The simple combo beats the lookup table on line length but not on ticket counts or the chance of a ticket (§5.2a, §5.3). The report form and Refresh + PIN are screens only, not connected. **Added 2026-11-08:** the This week view (§2.2b), local only. Level-ups, cast news and comparison rows aren't built. **🆕 Added 2026-11-11: six items are decided and waiting to be built, all listed in §2.8 (build queue):** Montserrat Black header font, theater name opens Google Maps, typical ticket price next to the rush price, links to digital lottery and digital rush sites, high-profile stars (rule decided, cutoff still to pick), and NYC hotel occupancy as a tourist gauge (source not found yet). Then N7–N10: show buzz, shows playing, show stage, two-show days, measuring and cutting inputs, and a special-deal flag. N11 is the NYU calendar as one input. The three-tier order for all new model inputs is just above the "Not adding" line in §2.8. §10 (new) lists ideas outside this project's scope. **Updated 2026-11-11 (scheduled run, local only):** N1–N4, N10 and the site half of N8 are built; the new inputs' data is collected (two-show days, shows playing, show stage, Midtown subway riders, attendance history, show buzz) and their model inputs are built but not tested; ~~the stars list (32 at 20,000) and the 50-article star-history test wait for my review;~~ stars reviewed and switched on, star history read on 2026-11-12 ($0.18; 1,387 runs in 113 shows; 33 stars with join and leave dates); Times Square monthly foot traffic and hotel occupancy collected 2026-11-17; ~~the NYU calendar~~ NYU input built from the calendar I pasted; model work hasn't started (Nov 17–19). What was built, and how, is in `process.md`. ~~Struck~~ text was replaced; anything not marked built is still a plan.
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
  - The theater name is a link to Google Maps directions (added 2026-11-11, ✅ built 2026-11-11: §2.8 N2).
- ~~Typical ticket price next to the rush price, crossed out, with the saving (§2.8 N3).~~ **Removed 2026-11-12 (my decision): no typical ticket price on tiles at all.** It made the site look like a discount shopping site. The show page keeps it.
- `2 shows today: 2 pm & 8 pm` on two-show days, and a `Special deal` badge when the policy list has one (✅ built 2026-11-11: §2.8 N8, N10).
- **Rush types offered** as small labels: `In person`, `Online`, `Student` and so on (§2.2a)
- **Rush price** (e.g. $49.50; per show, §3.4)
- **Worth-it bar** + verdict word (GO / Maybe / Stay home)
- Chance of getting a ticket (e.g. "72%")
- Recommended arrival time ("Get there by 9:20")
- **Colors lightened a step (my request 2026-11-12):** background and tiles are lighter purples, still a dark theme; text contrast checked.
- **Filters simplified (my decision 2026-11-12):** Days showing works on every view, including a single date (keeps shows that play on the picked weekdays); its "Pick This week or Any day" note is gone. The 2-show day filter is removed. Show time (Matinee / Evening) has no note and no Matinee/Evening sections: neither picked = all shows; one picked = only shows with that showtime; both picked = only shows playing twice that day. In This week, a show counts if it matches on one of your days. Any day has no Show time row.
- **Page headlines in sentence case (my decision 2026-11-12):** "Is rush worth it this morning?" and "Nerd stats", not all caps. Show names stay in caps.
- **Typical ticket price sort removed (my decision 2026-11-12).** Sorts: best chance, latest arrival, rush price, runtime.
- **Favorites (my request 2026-11-12, ✅ built):** the tile's "Interested" checkbox is now a star button (☆, gold ★ once favorited), and "Only my picks" is now a "★ Show favorites (N)" filter button that shows just the favorited shows. Favorites stay in that browser only, and earlier picks carry over.
- 📝 **Later: make the site look less "vibe-coded"** (my request 2026-11-12). I don't know exactly what that means yet; Claude to propose concrete options.
- ~~High-profile star label with the star's name on the tile.~~ **Removed 2026-11-12 (my decision):** stars are a trait of the show, shown on the show page ("Key appeals"), not on tiles, and not a filter.
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
| High-profile stars | Has a high-profile star | `registry/stars.csv`, by Wikipedia page views (below) | ✅ built 2026-11-11 (local): 32 stars in 19 shows (§2.8 N5) |
| Play or musical | Play, Musical | Show catalog (§3.0) | Have it |

**Days showing and runtime are simple show facts.** Claude looks them up once per show into a hand-kept file, `registry/show_facts.csv` (show, days, runtime, source, date checked, plus a review flag and note), and I review it. **Done 2026-11-06:** days come from Playbill's weekly schedule page over 8 weeks, using past copies on the Internet Archive, because one week can mislead (Election Day week had several shows swapping Tuesday for Monday). Ticketmaster is only a cross-check: where it disagrees, the row is flagged. 6 of 35 rows are flagged for me. The date picker's performance times still come from Ticketmaster (§3.0).

While a filter is on, shows with an unknown value are hidden, and the page says so ("3 shows hidden: runtime not known"). The page also shows the count ("12 of 33 shows") and a clear-all button.

**Days showing and the date picker do different jobs.**
- **Date picker:** a specific date in the next 7 days, with predictions. Days showing is greyed out here, because the date already decides.
- **This week + Days showing:** means "days I can go". Only those days are compared (§2.2b).
- **Any day + Days showing:** for planning weeks ahead ("what plays on Tuesdays?"). Tiles show facts only: rush types, rush price, runtime, play or musical, how full. They show no chance or arrival time, because predictions stop at 7 days (§1). In their place: "Check back within 7 days of your date."
- **Schedules change:** a show could close before someone's date, and closing news isn't built yet (§3.12), so Any day mode says to confirm before going.

**High-profile stars (rule decided 2026-11-11; not collected or built yet: §2.8 N5).** ~~A show counts if a current principal is billed above the title, or has won a Tony, Oscar, Emmy or Grammy.~~ Replaced: awards counted too many stage regulars, and billing missed celebrity replacements in long-running shows.
- **The rule: a high-profile star is a current principal who was already famous before joining the show, measured by Wikipedia page views.** Their Wikipedia page's typical monthly views, over the 12 months before their casting was announced, must pass a cutoff. Using the months before the announcement keeps the show's own buzz out of the number.
- **Typical = the median month,** so one news spike doesn't make someone a star. If the announcement date isn't known, use the 12 months ending 3 months before their first performance.
- **The cutoff is mine to pick, from the data.** Claude pulls the number for every current principal and shows me the ranked list; I choose where stars start. Check: Aaron Tveit in Moulin Rouge has to land above the line. No Wikipedia page means not a star.
- **Cutoff: 20,000 median monthly views (my decision 2026-11-11).** What I want: someone who'd make you go to a show you'd never heard of, just because they're in it (like Jeremy Jordan). Eva Noblezada and Reeve Carney must pass; Megan Hilty and Helen J. Shen shouldn't (I only knew them after they were on the poster). 20,000 does all four. **Confirmed after seeing the people just below the line:** I know about half of them, but I wouldn't go to a show just to see them, so they rightly don't count.
  - **Near the line, from a second look at 42 more performers (2026-11-11, same window as below):** just above: Tituss Burgess 22k, Brian d'Arcy James 21k. Just below: Norbert Leo Butz 17k, Alex Brightman 16k, Ramin Karimloo 16k, Patrick Page 14k, Santino Fontana 14k, Kelli O'Hara 11k. Also above: Jordan Fisher 34k, Phillipa Soo 40k, Corbin Bleu 39k, Michael Urie 42k, Andrew Barth Feldman 40k, Christian Borle 29k, Annaleigh Ashford 28k, Laura Benanti 49k, Darren Criss 56k, Ben Platt 59k, Leslie Odom Jr. 57k, Bernadette Peters 60k, Josh Groban 75k, Nicole Scherzinger 188k.
  - **Megan Hilty sits at 19,613, right on the line.** She fails at 20,000 as I want, but only by 400. People that close to the line get flagged in `stars.csv` for me to look at.
  - **Check once the real window is used:** these numbers cover Jan 2023 to Oct 2026, including time in their shows. The real rule uses the 12 months before casting was announced, which may move people. Eva Noblezada (28k) and Reeve Carney (24k) clear 20,000 by a small margin, so if either drops under it in the real window, mark them as hand overrides rather than moving the cutoff.
- **First look at the numbers (2026-11-11), used to pick the cutoff.** 48 hand-picked performers, median monthly views from January 2023 to October 2026. This is not the final window (it includes their time in the show), and it's not the real cast list.

  | Median monthly views | Who |
  |---|---|
  | 250,000+ | Keanu Reeves 557k, Robert Downey Jr. 291k, Jake Gyllenhaal 290k, George Clooney 289k, Denzel Washington 285k, Hugh Jackman 261k |
  | 100,000–250,000 | Rachel Zegler 202k, Kieran Culkin 168k, Nick Jonas 165k, Mia Farrow 152k, Bob Odenkirk 138k, Jonathan Groff 126k, Sadie Sink 122k, Idina Menzel 103k, Kristin Chenoweth 100k, Bill Burr 100k |
  | 50,000–100,000 | Tom Felton 94k, Adam Lambert 93k, Sutton Foster 86k, Sarah Snook 83k, Betty Gilpin 72k, Lea Michele 64k, Kit Connor 60k, Patti LuPone 52k |
  | 15,000–50,000 | Aaron Tveit 37k, Michelle Williams (singer) 37k, Audra McDonald 35k, Jeremy Jordan 34k, Jinkx Monsoon 32k, Eva Noblezada 28k, Cole Escola 24k, Reeve Carney 24k, Tituss Burgess 22k, Megan Hilty 20k |
  | Under 15,000 | Helen J. Shen 11k, Tom Francis 10k, Shoshana Bean 8k, Gracie Lawrence 8k, Adrienne Warren 7k, Christopher Sieber 5k, Jennifer Simard 5k, Jasmine Amy Rogers 5k, Jak Malone 5k, Nicholas Christopher 4k, Joy Woods 4k, Andrew Durand 4k, Jordan Litz 2k, Lencia Kebede 1k |

  - ~~**Cutoff options from Claude:**~~ (replaced by my 20,000 pick above) 15,000 (recommended: it sits in the widest gap, between Megan Hilty at 20k and Helen J. Shen at 11k, so few people are borderline, and Aaron Tveit clears it easily); 30,000 (Tveit, Audra McDonald and Jeremy Jordan only just pass; Eva Noblezada and Reeve Carney don't); 50,000 (household names only; Aaron Tveit fails, so it breaks my check).
  - **Why the "before they joined" window matters:** Cole Escola's lowest month was 3,200 and highest 603,000. Oh, Mary! made them famous, so they weren't a star when it opened. Sadie Sink's last 12 months run at 276k against 122k overall.
  - Brody Grant and Sky Lakota-Lynch have no Wikipedia page, so they count as not stars. 5 lookups were refused for going too fast (Nicole Scherzinger, Darren Criss, Jordan Fisher, Natasha Hodgson, Jessica Vosk) and were not retried.
- **I can override anyone by hand,** either way, with a one-line reason.
- **Source:** Wikimedia's official page-views service: free, no key, daily numbers back to July 2015, people only (bots filtered out). Add it to `registry/sources.csv` before the first fetch.
- **Kept in `registry/stars.csv`,** pre-filled by Claude and reviewed by me, one row per person per stint: show, person, role, exact Wikipedia page title, date the casting was announced, first performance, last performance (blank while open-ended), date the last performance was announced, monthly views, the 12-month window used, star yes/no, override, reason, source, date checked. The dates make a star drop off the site when they leave, and stop the model's tests from using a departure before it was public.
- **Used for (my decision 2026-11-11, changed 2026-11-12):** the show page's "Key appeals" section (which also gives each star's final performance) and the model's star inputs (§3.12). ~~Tile label, filter and `Star leaving` badge~~ removed 2026-11-12: nothing about stars on tiles. Stars raise demand and ticket prices, most of all when their run is almost over.

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
- **Fonts (chosen and on the site 2026-11-06; display font replaced 2026-11-11, below):** ~~Bebas Neue~~ Montserrat Black for the logo, headings, show names and big numbers (like the chance %). Poppins for everything else: body text, labels and buttons. Both are free on Google Fonts. Bebas Neue only has capital letters, so show names appear in all caps.
  - **Changed (decided 2026-11-11, ✅ built 2026-11-11: §2.8 N1):** Bebas Neue is too narrow. Montserrat Black (weight 900), all caps, replaced it everywhere; display sizes are about 20% smaller. Poppins stays.
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
    - 🆕 **Replacing "What moves the line most" (my request 2026-11-11, not built: §2.8 N9):** a chart of how much every input affects the outcome: the line, the tickets and the chance, which way each one pushes, and how much the score drops without it. Tap an input for its effect curve. Inputs that were cut stay on the chart, grayed out. Today's chart covers only the line and gives only the average size of the push, not its direction, so rare days like holidays look small.
  - **How good it is:** the scoreboard, predicted vs. real line, chance vs. what happened, the always-yes problem and verdicts, error and range by month, and real trips.
  - **Model vs. ground truth (added 2026-11-06, my request):** every test result next to what was reported: 1,507 line reports, 33 stated ticket counts and 138 attempts, each with a switch between the model and the lookup table, plus a table to look up any result by show or month, biggest miss first. Ground truth here means Reddit reports, so it isn't verified. Numbers only, with no usernames or comment text.
- **Show pages get the plain versions (built 2026-11-06):** how the line builds that morning, which days are busiest for that show, and what you'd save. Any day mode shows only the savings, because the other two come too close to the weekday numbers §9 question 23 holds back.
- **Every number comes from the predictions file.** The chart numbers are counted from the model tables and the finished test by `src/broadway_rush/model/site_charts.py`.

### 2.7 Shows with no data
- **Skip a show if there's genuinely no data** (no reports, no prices, no grosses). It just isn't shown for now.
- Shows with *some* data (e.g. prices + grosses but no Reddit reports) still get a prediction, labeled `Low confidence` (§5.1).

### 2.8 🆕 Build queue: decided, not built yet (started 2026-11-11)
**This is the one place to look for new website work.** Everything here is decided by me and ready to build, apart from the waits marked in the table; none of it is on the site yet. N1–N4 are site-only changes (`web/index.html`, `web/styles.css`, `web/app.js`): no model, data or scraper changes, except N4's last-resort lookup, which isn't needed today. When an item is built, mark it ✅ with the date here, and update the older section it points to.

| # | Item | Added | Status |
|---|---|---|---|
| N1 | Header font: Montserrat Black replaces Bebas Neue | 2026-11-11 | ✅ built 2026-11-11 (local) |
| N2 | Theater name opens Google Maps | 2026-11-11 | ✅ built 2026-11-11 (local) |
| N3 | Typical ticket price shown next to the rush price | 2026-11-11 | ✅ built 2026-11-11 (local) |
| N4 | Links to each show's digital lottery and digital rush (site link, app mention) | 2026-11-11 | ✅ built 2026-11-11 (local): 25 of 25 lotteries, 10 of 10 online rushes link |
| N5 | High-profile stars: collect the list, label and filter on the site, model inputs | 2026-11-11 | 🔶 steps 1–4 ✅ (2026-11-11/12): list reviewed and switched on (local); star history read; `stars.csv` now has join and leave dates for 245 of 445 principals, and the 11 replacements are scored on the 12 months before their casting was announced. **33 stars** (32 by the rule + Reece Weaver): Ryan McCartan moved above the line (18,530 → 20,776). 29 show on the site today; Matthew Morrison left Nov 8, Reece Weaver leaves Nov 15. Model inputs from the runs: N9, Nov 17–19 |
| N6 | Tourist traffic for the model: Times Square foot traffic (I ask the Alliance for daily counts) and Midtown subway riders, both; airport passengers as a spare (hotel occupancy has no public monthly data) | 2026-11-11 | 🔶 subway riders collected 2026-11-11 (daily, Jan 2022 to Oct 29, 2026) and their four inputs built; **Times Square monthly reports collected 2026-11-17 (my call on the terms: monthly only, show derived results with credit, never the raw counts)**: 33 months, Jan 2024 to Sep 2026, average daily pedestrians plus Times Square hotel occupancy (found in the same reports, so ~~hotel occupancy has no public monthly data~~ it does), three inputs built; **daily counts received from the Alliance 2026-11-17** (input `ts_peds_daily_vs_last_year`); not tested yet (N9, Nov 17–19) |
| N7 | New model inputs: show buzz (Wikipedia), shows playing that day, show stage | 2026-11-11 | 🔶 data collected and inputs built 2026-11-11 (show buzz views for 112 shows, shows playing, previews and days since opening); closing dates need cast news; not tested yet |
| N8 | Two-show days: in the model, and on the site | 2026-11-11 | ✅ site built 2026-11-11 (local); model input `two_shows_today` built 2026-11-11, not tested yet (N9, Nov 17–19) |
| N9 | Measure how much each input affects the outcome, chart it on Nerd stats, then cut the weak ones | 2026-11-11 | 🔶 2026-11-18: special days removed (my call); tickets per person 1.0 best (1.4, 1.8 worse); drop-one line tests done: a lean 14-input set has line error 4.61 vs 4.75 first model. Lean set kept (my call, Nov 18: 14 line inputs + the original 4 ticket inputs; 7- and 10-input sets tested, all within noise, 14 picked). 2026-11-23: sold-out caps (2 h) added to ticket training; site ticket number = lookup (my rule: fix first, then closest). ✅ Locked-month score: line 4.60 vs lookup 5.67; tickets model 8.9 vs lookup 4.1 (15 days) |
| N10 | Special-deal flag on the site (not in the model) | 2026-11-11 | ✅ built 2026-11-11 (local) for the 4 deals on the policy list; dated deals file is empty |
| N11 | NYU calendar, one model input (~~six schools, four inputs~~) | 2026-11-11 | 🔶 input built 2026-11-11 from the calendar I pasted (`nyu_session`: 0 break, 1 classes, 2 finals, 3 free and in town: one-day holidays and the 3 days before a term, my call 2026-11-11; summer counts as a break); not tested yet (N9, Nov 17–19) |
| N12 | Nerd stats visual upgrade: 8 charts in the cleaning-funnel slide's marquee style (picked 2026-11-12, list below) | 2026-11-12 | 📝 not built, waiting for my go |
| N13 | UI feedback round (my review of the live site, 2026-11-23): bigger centered title, calendar-style day strip filling the width, tidier sort/view/filters, "Star in the cast" filter, 3D carousel, Nerd stats as a dashboard, Nerd stats colors on the customer side, cleaner show page with picture | 2026-11-23 | ✅ 2026-11-23: all seven pieces built (a title, b calendar strip, c sort/view/filters + "Star in the cast", d 3D coverflow, e Nerd stats dashboard, f gradient text and colors, g show page dashboard). Each piece has a switch in `web/app.js` (`const N13`) and its own commented CSS/JS blocks, so any one can be undone |
| N14 | UI feedback round 2 (my review after N13, 2026-11-23): gold marquee title, bigger sort/view/filter text, favorites next to sort/view, same-size show images, show page leads with the predictions (no savings), narrower show page, Nerd stats as a real interactive dashboard | 2026-11-23 | 📝 written down, not built. Same revertable-pieces rule as N13 |

N1–N4 and N10 are website work. **N5–N9 are data and model work**: their model parts belong to the final-model slot (Nov 17–19). N8 also changes the site.

**N1. Header font: Montserrat Black (replaces Bebas Neue in §2.4)**
- Why: Bebas Neue's letters are too narrow. I picked Montserrat Black from 15 wider options on 2026-11-11.
- What: everything that uses the display font today (logo, headings, show names, prices, the chance %, other big numbers) switches to **Montserrat, weight 900, all caps**. Poppins stays for everything else.
- How:
  - In `web/index.html`, swap `Bebas+Neue` for `Montserrat:wght@900` in the Google Fonts link.
  - In `web/styles.css`, change `--font-display` to Montserrat with a wide, heavy fallback (for example `"Arial Black"`), never plain Arial.
  - Bebas Neue only has capitals, so nothing set uppercase before. Montserrat has lowercase, so every display-font rule now needs `text-transform: uppercase`.
  - Every display-font rule hard-codes `font-weight: 400` (a Bebas rule). Change them all to 900, or the browser shows thin Montserrat.
  - Set letter-spacing to 0 on those rules; the extra spacing was for Bebas.
  - Montserrat is much wider, so size the display text down (start around 15–20% smaller) until long show names like "Buena Vista Social Club" and the tile's price and chance still fit at phone width without overflowing.
  - Change `?v=` on both files in `web/index.html`.
  - Delete `web/font-preview.html` (the temporary page I picked from).
- Done when: no Bebas Neue is left anywhere, nothing overflows a tile at phone or desktop width, and the Nerd stats and show pages look right too.

**N2. Theater name opens Google Maps**
- Why: to see how far the theater is from you.
- What: the theater name is a link, on tiles (§2.2), in the This week view (§2.2b) and in the details view (§2.3). It opens Google Maps **directions to the theater** in a new tab. Maps fills in your location itself, so the site never asks for or stores where you are.
- How: link to `https://www.google.com/maps/dir/?api=1&destination=` plus the URL-encoded theater name followed by ", New York, NY" (use the street address instead if the predictions file has one). `target="_blank"` with `rel="noopener"`.
- Tapping the theater name opens Maps only; tapping anywhere else on the tile still opens the details. No link when the theater is unknown.
- Done when: every theater name on the three views opens the right theater in Maps, and the link is reachable by keyboard.

**N3. Typical ticket price next to the rush price**
- Why: so the rusher sees they're getting a deal without opening the details.
- What: wherever the rush price shows on a tile (day view, This week view, Any day), show the typical ticket price right beside it, crossed out, with the saving. Example: **$45** rush · ~~$148~~ typical · save about $103.
- The number is `typical_ticket`, already in the predictions file and already used by the "what you'd save" panel on show pages (`savingsPanel` in `web/app.js`). Reuse its math and wording so the tile and the panel always agree.
- Keep it honest: typical ticket is the average paid over recent weeks, which already includes rush and discounted tickets, so the real saving against a full-price seat is bigger. Say this in a tooltip or small note on the tile, as the show page already does.
- Leave the comparison out (rush price alone) when the show has no typical price, no rush price, or rush isn't cheaper.
- The tile's facts line already says "Typical ticket $__"; remove it there so the price doesn't appear twice. The "Typical ticket price" sort (§2.2a) stays.
- Done when: every tile with both prices shows the pair and the saving, the numbers match the show page's savings panel, and nothing wraps badly at phone width (check after N1, since the font changes the widths).

**N4. Links to each show's digital lottery and digital rush**
- Why: for shows with a digital lottery or digital rush, get from the site to the page (or app) where you enter or buy in one tap.
- What: where a show has a digital lottery, the site links to where you enter it, opening in a new tab:
  - **Tile:** the `Lottery` rush-type label becomes the link.
  - **Details view:** the "Digital lottery" row in the policy panel gets an "Enter the lottery" link.
  - **Lottery-only shows** (group 3, §8) get the same link, since the lottery is the main thing they offer.
- The address is already in the predictions file: `policy.lottery.where`, from Playbill's policy list (§3.4). On the Nov 5 list, 22 of 25 lotteries have one: rush.telecharge.com (13), lottery.broadwaydirect.com (6), LuckySeat.com, HamiltonMusical.com and TodayTix (1 each); 3 are blank.
- The values are messy, so clean them in `web/app.js`: take the first web address in the text, add `https://` when it's missing, and link only if what's left is a plain web address. Examples: `Lottery.BroadwayDirect.com/Show/The-Lion-King` has no `https://`, and `HamiltonMusical.com or download the Hamilton App.` is a sentence (link HamiltonMusical.com, keep the rest as text). When no step below finds an address, show the lottery as now, with no link. Never guess an address.
- **Every lottery gets a link, not only the ones with a tidy address (added 2026-11-11, my request).** Fill the gaps in this order, and stop at the first that works:
  1. `policy.lottery.where`, as above.
  2. `policy.lottery.how`. The 3 lotteries with a blank `where` on Nov 5 all have the address there: Aladdin (`AladdinTheMusical.com/lottery`), The Book of Mormon and Other Desert Cities (both on luckyseat.com). So today this covers 25 of 25 with no scraping.
  3. Other lottery-style offers that Playbill lists under a different name, in `policy.other` (for example Harry Potter's "The Friday Forty"): link them the same way when they carry an address.
  4. Only if a show has a lottery and none of the above gives an address: look it up once on the show's official website and save it by hand, with the source and date, in new columns of `registry/show_facts.csv` (`lottery_url`, `lottery_url_source`), the same way days and runtime were collected (§2.2a). `predict.py` passes it through to the predictions file. Check `registry/sources.csv` before fetching anything, and never log in or get around bot protection. This is the only part that isn't site-only, and it isn't needed today.
- Run the address check each time the policy list updates, and list any lottery left without a link, so a new show doesn't quietly go without one.
- **Digital rush gets the same treatment (confirmed 2026-11-11, my request): link the site, or mention the app.**
  - On the Nov 5 list all 10 digital rushes have an address in `policy.digital.where`: todaytix.com (6) and rush.telecharge.com (4). Clean and link it the same way as lotteries, with the same `how` fallback.
  - **Tile:** the `Online` rush-type label becomes the link. **Details view:** the digital rush section (§2.3) gets a link, for example "Open TodayTix".
  - **Mention the app when there is one:** TodayTix rush is bought in the TodayTix app, so next to the link say "or in the TodayTix app". Take the app's name from the policy text (`how`, for example "Available through the TodayTix app"); don't invent one for sites that have no app, such as Telecharge.
  - If a digital rush ever has no address but the text names an app, show the app mention alone, with no link.
- Links only. Lotteries stay out of the predictions (§3.5), and the site never enters one or fetches those pages.
- Done when: every show with a lottery or digital rush links to the right page from the tile and the details view, TodayTix rushes also mention the app, the 3 with a blank `where` link through `how`, and no link is broken or points at a sentence.

**N5. High-profile stars**
- Why: stars raise demand and ticket prices (Aaron Tveit in Moulin Rouge), most of all when their run is almost over. I want them labeled on the site and in the model.
- The rule is decided and written in §2.2a: fame before joining, measured by Wikipedia page views, with my cutoff and hand overrides. The model inputs are in §3.12.
- Steps, in order. **Stop after step 2 and wait for me:**
  1. Add Wikimedia's page-views service to `registry/sources.csv`. List the principals of every show now running, from sources the registry already allows. Playbill pages go through a script that keeps only the facts and are never sent to an AI model.
  2. Pull each principal's monthly page views (3 seconds or more apart) and fill `registry/stars.csv` (columns in §2.2a). Mark star yes/no with the 20,000 cutoff, flag anyone within 15% of it, and give me the ranked list so I can mark overrides.
  3. Site: `predict.py` passes each show's current stars to the predictions file. **The show page gets a star section (my request 2026-11-11).** **Called "Key appeals" (my decision 2026-11-11, for now)** (~~Claude's "The draw"~~; other ideas were "Why people go", "Who's in it"). It lists each high-profile star with their role, when they joined, and their last performance once announced ("Final performance January 4"), with a "leaving soon" highlight in the last 14 days. It can also hold other draws the site already knows, such as an announced closing date. No star and nothing else to say means no section. Tiles get a `★ Name` label, the "Has a high-profile star" filter (§2.2a) is switched on, and the `Star leaving Sunday` badge shows when a last performance within 14 days has been announced.
  4. History, for the model: add star runs back to June 2024, including shows that have closed, with the dates their casting and departures were announced. **Required, not optional (my decision 2026-11-11): I want to see just how much a high-profile star draws in an audience.**
     - **Two measurements, because rush reports alone may be too few:**
       - **Rush:** the star inputs in the line and ticket models (§3.12): how much longer the line is, and how the chance changes, with a star and in their final weeks.
       - **Overall audience, from the weekly grosses (§3.3):** for each star run, compare the show's % seats sold and average ticket price in the weeks before, during and after, against the same weeks for similar shows without a change. 127 weeks of grosses for every show make this much better supplied than rush reports, and it answers "how much does a star draw" for tickets bought ahead.
     - **Show the answer:** a "What's a star worth?" chart on Nerd stats (§2.6), for example "with a high-profile star: seats sold up about __ points, average ticket up $__, rush line about __% longer, and more in their final 2 weeks", each with its range and how many star runs it's based on. Also a slide for the presentation. If the effect can't be told apart from noise, say that.
  5. Model (final-model slot, Nov 17–19): add the star inputs from §3.12 and report a with/without row in the results table (§5.3).
- Steps 1–3 work without 4–5, so the label and filter can ship first.
- Keeping it current: the weekly job (§6.1) re-checks casts, and cast news (§3.12) supplies joining and leaving dates once it's collected. Until then, dates are filled by hand.
- Done when: every running show's principals are in `stars.csv` with their views, my cutoff is recorded in the file's notes and in §8, the tile label, filter and badge work, and the results table has the with/without stars row.

**N6. NYC hotel occupancy as a tourist gauge**
- Why: fuller hotels mean more tourists, and more tourists mean more Broadway demand, both tickets bought ahead and rush lines. The calendar (§3.6) only knows the dates of holidays and school breaks; this would measure how busy the city really is.
- **"If we can get it": finding a legal source is step 1, and nothing is confirmed yet.** Places to check, none verified:
  - NYC Tourism + Conventions' published tourism statistics (already listed in §3.9).
  - City or state government reports that publish hotel occupancy, and NYC Open Data, including hotel room occupancy tax collections as a stand-in.
  - The industry's standard numbers come from a paid data company (STR, part of CoStar). Don't scrape or copy those from behind a paywall; a figure quoted in a public government report is fine to use from that report.
- **Sources found 2026-11-11 (web search only, nothing fetched; check each against `registry/sources.csv` before use). I want a tourist measure badly, more than college calendars, so this goes first among the new inputs.**
  0. **Main pick, changed the same day (my decision): Times Square foot traffic (the Times Square Alliance's pedestrian counts, item 3 below).** Many tourists walk there, or take a train to another nearby station, so pedestrians in Times Square measure them better than riders at one station.
     - Public: monthly reports with the average daily count, plus a weekly operations report. **Ask the Alliance's policy and data team for the day-by-day counts** from June 2024 on; their page invites data requests. I send that request myself; Claude can draft it. Check the site's terms before downloading any reports.
     - Inputs: `ts_peds_vs_last_year` (latest published period against the same period a year earlier) and `ts_peds_season` (the usual level for that time of year, from earlier years). With monthly counts only, these are monthly; with daily counts, weekly.
     - Leave out or mark bad periods, such as April 2024 when the counters were being upgraded.
     - **Use both foot traffic and Midtown subway riders (my decision 2026-11-11, later the same day),** not one as a backup for the other. Foot traffic catches people who walk in; subway riders give day-by-day numbers even if the Alliance never sends daily counts. N9 tests each one, and keeps one or both.
  1. **Also used: subway ridership at the Midtown stations near the theaters** (~~Main pick~~, then backup; now used alongside foot traffic). Sum the stations around the theater district, not just Times Sq–42 St, because many tourists get off at a nearby station. Inputs: `midtown_riders_vs_last_year`, `midtown_riders_season`. The MTA publishes hourly riders for every station on New York's official open data site (data.ny.gov, a Socrata API like the NYC permits data): 2017–2019, 2020–2024 and 2025 onward. Times Sq–42 St is the Broadway district's own station, so this measures crowds right where the box offices are, by day, back to before June 2024.
     - Commuters use it too. Separate tourists from commuters by using weekend and midday hours, and by comparing against the same hours at a mostly-commuter station. Exact station names and how soon new days are published: not yet checked.
     - ~~Inputs: `ts_riders_vs_last_year`, `ts_riders_season`~~ (replaced by the Midtown versions above): the latest published weeks against the same weeks a year earlier (is Midtown busier than usual?), and the usual level for that week of the year, from earlier years.
  2. **Airport passengers, monthly:** the Port Authority publishes monthly passenger counts for JFK, LaGuardia and Newark, including international passengers. A good gauge of visitors arriving, but monthly, published weeks later, and in PDF reports.
  3. **Times Square pedestrian counts, monthly:** the Times Square Alliance publishes monthly reports with average daily pedestrians from automated counters (about 228,000 a day in June 2024). Monthly PDFs only; day-by-day counts are available on request from their data team. Counts were off in April 2024 while counters were upgraded.
  - **Hotel occupancy, checked:** public numbers are yearly only (84.1% in 2025, State Comptroller). Monthly numbers come from STR, a paid service. So hotels drop to last; use the three above instead.
- What the source has to offer: NYC-wide occupancy (the share of hotel rooms filled), monthly or better, weekly if it exists, from June 2024 to now. Add it to `registry/sources.csv` with its terms before fetching.
- Two things to design around:
  - **It's published late.** Occupancy for a month comes out weeks afterwards, so a prediction for next Saturday can't use that week's real number. The input has to be something known in advance: the same week or month last year, and the latest published month against the same month a year earlier (is the city running busier or quieter than usual?).
  - **It may repeat what the model already knows.** Season, holidays and weekly grosses (seats sold, §3.3) already track tourist season. So this goes in as a with/without row in the results table (§5.3), and stays only if it helps.
- Proposed inputs: `hotel_occ_same_period_last_year`, `hotel_occ_latest_vs_last_year`.
- **Past data is fine (my decision 2026-11-11): learn the pattern from history.** From past years, work out which weeks of the year, and which parts of a month, have the most tourists and the highest Broadway attendance, and give the model that as a "how busy is this time of year usually" number: `tourist_season_index` and `attendance_season_index`.
  - The attendance half needs no new source: weekly attendance is already in the grosses files (127 weeks, §3.3), and Playbill's grosses go back to 1985, so more years can be added for a steadier pattern (leave out the 2020–21 shutdown).
  - Weekly numbers can't show which days within a week are busy; the day-of-week and holiday inputs (§3.6) already cover that.
  - Build each index only from years before the date being predicted, so the tests don't peek.
  - This part can be built even if no hotel source turns up.
- If no legal source with history exists, write that down here and in §8 and drop it; don't replace it with a guess.
- Done when: either the source is in the registry, the numbers are in `data/raw/` and joined to the model table, and the results table has the with/without row; or this item is marked "no legal source" with what was checked.

**N7. New model inputs (my picks 2026-11-11, from Claude's list)**
Each one goes through N9: tested one at a time, kept only if it helps.
- **Show buzz, from the show's own Wikipedia page.** `show_buzz`: the show page's daily views over the last 7 days, against its own usual level, using only days before the prediction date. Catches viral moments, nominations and big news. Same Wikimedia source as N5 (already in the registry); one request per show per refresh, 3 seconds or more apart. Each show's exact page title goes in a new `wiki_title` column of `data/processed/shows.csv`, filled by Claude, checked by me.
- **How many shows are playing that day.** `shows_playing_today`, and `rush_shows_today` (how many of them have in-person rush). On dark days like Monday, rushers crowd into fewer shows. No new data: comes from the Ticketmaster and Playbill schedules. My expectation: small effect, but it's free.
- **Show stage.** `in_previews`, `days_since_opening` and `days_until_closing` (closing only once announced; it was already listed in §3.12). Opening and first-preview dates come from the grosses and Playbill; closing from cast and closing news (§3.12). I don't know how much this matters; the model finds out.

**N8. Two-show days (my request 2026-11-11: I hadn't considered them yet)**
On Wednesdays, Saturdays and some Sundays, many shows play a matinee and an evening. Rush may be sold for both, which changes the line and the tickets.
- **Model:** `two_shows_today` (yes/no, from the schedules) for both the line and the cutoff. 91% of reports don't say which performance (§5.2), so the model still predicts per show-day.
- **Rush for both, or one at a time?** Check each show's policy text (§3.4) for whether the box office sells rush for both performances at opening, or the evening's only later. Record it per show in `registry/show_facts.csv` (`two_show_rush`: both at opening / separately / unknown). Where unknown, the site says so rather than guessing.
- **Site (my design 2026-11-11; Claude's write-up of what I said, and I'll fix anything it got wrong later):**
  - **Filter:** a new "2-show day" option that keeps only shows playing twice that day.
  - **Matinee / Evening:** when the tiles on screen include 2-show days, the filter also offers Matinee and Evening, to see just one performance time.
  - **Otherwise, sections:** with no Matinee or Evening choice, the day view splits into a Matinee section and an Evening section. A 2-show show appears in both, with its time in each.
  - Tiles say "2 shows today: 2 pm & 8 pm" on 2-show days, in the day view and the This week view, which also marks 2-show days in its day strip.
  - Details view (§2.3): show both performances, and say plainly that the prediction covers the whole day's rush, since reports rarely say which show. Where rush for the two is sold separately, say when each goes on sale.
  - ~~Claude's earlier proposal: a Matinee / Evening / Any filter, always shown~~ (replaced by the design above).
- Done when: the input is in the model and tested (N9), every two-show day on the site shows both times, and the filter works.

**N9. Measure how much each input matters, then cut (my request 2026-11-11)**
After all the new inputs are in, measure each one's role and remove the ones that don't earn their place. Do this before the Nov 24 freeze.
- **Two measures, because they answer different questions:**
  - **How much the model leans on it** (importance): for the line trees, SHAP values averaged over each test month; for the ticket model, the size of each input's effect and its range. Shows what the model uses.
  - **Whether removing it hurts** (drop-one test): refit without that input on the same rolling test months, compare the scores. This is the one that decides cuts, because an input can be used a lot and still add nothing that another input doesn't already give.
- **Test every idea, all 27, and show it (my request 2026-11-11).** I want to be able to say "I tested 27 ideas and here's what actually moves a Broadway rush line", with a table and chart of every one: what it is, its grade going in, what the test found, kept or cut. How, so it doesn't mean 27 full trainings:
  1. **One full model with everything** that has data by Nov 17, scored on the 9 open test months.
  2. **Drop-one on the line side, trees only:** for each of the ~12 input groups, refit without that group and rescore. A tree fit takes under a minute, so 12 groups × 9 months is roughly 1–2 hours. Then split the groups that mattered into their single inputs.
  3. **Ticket side, only the 6–8 candidates** (§2.8 tier list's ticket limit): the ticket model is the slow part, so test only those with a reason to be there.
  4. **One full test of the final set,** then **one score on the locked months.** If that score drops a lot against step 1, the picks were luck, and the write-up says so.
  - Ideas with no data by Nov 17 go in the table as "not tested: data not ready", with what's missing.
- **Same design, retrained (my question 2026-11-11, answered):** no new model design. The final model is the same combo (trees for the line, Bayesian for the tickets, §5.2a), retrained on the new data with the new inputs. **Keep the bones of the current model; no major upgrades until there's more Reddit and TKTS data (my decision 2026-11-11).** Use whatever training and testing is best within that design: tuning settings, refitting, and small calibration fixes are fine (for example learning tickets per person, or wider ranges for thin shows). Structural level-ups from §5.2c (borrowing across shows on the line side, a new outcome step, modeling the reporting bias) wait. List every change in `process.md`.
- **Compare against the first model (my request 2026-11-11):** keep the first model's results as they are (test tag `more1`, scores in §5.2a); never overwrite those files, and give every new run its own tag. Report first model vs final model side by side in the results table (§5.3) and on Nerd stats: line error, 80% range coverage, ticket error, chance accuracy, misses caught, plus the lookup table and "always yes". **Score both on the identical test reports:** new Reddit reports and fixes change the answers, so score the first model again on the new test set too, the same check used for the data cleaning.
- **Keep it affordable:** a full test takes about an hour, mostly the ticket model. Run drop-one tests on the line side with the trees alone (minutes each). Group inputs that belong together (all holidays, all weather, all star inputs) and test the group first. Re-run the full test only for the final set.
- **What "better" means (my decision 2026-11-17):** first, **ticket counts closer to the real number**; second, **smaller line error**. Arrival time and the GO / Maybe / Stay call matter less to me ("that's kinda how rush is"), so keep and cut decisions and upgrades are judged on ticket error, then line error; chance accuracy and misses caught are still reported, not optimized.
- **I make the calls (2026-11-17):** Claude shows the numbers; I decide keep or cut on each input, read the worst misses and decide what each one is, set the GO / Maybe / Stay cutoffs, and run the key training commands myself. Claude walks me through the model before the tests.
- **Cut rule:** drop an input if removing it doesn't make the score worse by more than the month-to-month noise. Ties go to the simpler model.
- **I want to see how much each input affects the outcome (my request 2026-11-11), with a chart on Nerd stats (§2.6).** "Outcome" means all three things the site predicts: the line, the tickets, and the chance of getting one. For each input, show:
  - **Which way and how much:** for example "Saturday: line about 35% longer", "on TKTS: about 10% shorter", "star in final 2 weeks: chance down 8 points". Not just a ranking.
  - **How much the score drops without it,** from the drop-one test, so viewers can tell "used a lot" from "actually needed".
  - **Its effect curve,** for inputs that are numbers (temperature, page views, days until closing): a small chart of the prediction as that input goes from low to high, on tap.
  - **Cut inputs too,** grayed out with "removed: didn't help", so the chart shows what was tried.
- **Report it:** that chart, and every cut, with its numbers, as a with/without row in the results table (§5.3). Removed inputs stay listed with the reason, so the write-up can say what was tried.
- The locked months (§5.2) stay untouched throughout.

**N10. Special-deal flag on the site, not in the model (my decision 2026-11-11)**
- **Special days are out of the model.** $5 ticket days, anniversaries and similar deals are too rare to train on. ~~A special-day input as a possible model upgrade~~ is dropped.
- **Instead, flag them on the site:** a badge on the tile and a line in the details view, for example `Special deal today`, with what the deal is and a link. ~~Hamilton has one now.~~ (ignore, my call 2026-11-11)
- **Source:** first check Playbill's rush policy article, which already lists some special offers as their own rows ("The Friday Forty", "$30 Under 30", "Ponyboy Seat"). Then Playbill news (scrape list C7). The predictions stay as they are on those days; the site just says the day may be busier or cheaper than predicted.
- Done when: every deal on the current policy list shows on its show's tiles and details, with dates where known.

**N11. NYU calendar, one input only (final decision 2026-11-11, after going back and forth the same day).** ~~Dropped for now~~ → brought back small: **NYU only, one input, tier 3.**
- **The input:** `nyu_session`: NYU classes in session, finals week, or break (one input with three values). Source: NYU's official academic calendars, June 2024 to May 2027, kept in `registry/college_calendars.csv`. About an hour of work.
- **Why so small:** most college breaks line up with holidays and school breaks the model already has, and each NYU event has happened only about twice since June 2024, so a bigger version would mostly learn luck. One input keeps the NYU story for the presentation at little cost. If N9 cuts it, the write-up says so.
- ~~The fuller plan below (four inputs, six schools)~~ is not being built; kept for reference.
- Why: students are a big part of rush lines, and many come from outside NYC. In session they're in town but busy; on breaks, out-of-town students leave. The model learns which way each one goes. I'm presenting at an NYU competition, so the judges may like seeing their own calendar in the model.
- Inputs: `college_in_session` (classes running), `college_finals` (exam weeks), `college_break` (winter, spring, Thanksgiving and summer breaks), and `college_move_in` (the week classes start). NYC public-school breaks (`is_school_break`) are already in the model and stay separate.
- Schools, in order: **NYU first**, then Columbia, The New School, FIT, Fordham and Juilliard, which draw the most students from outside NYC. CUNY mostly serves New Yorkers, so it comes last if at all. Where schools disagree, use the share of these schools in session, weighted by enrollment, rather than yes/no.
- Source: each school's official published academic calendar, June 2024 to May 2027 (C11). Hand-kept in `registry/college_calendars.csv` (school, term, event, start, end, source, date checked), filled by Claude, reviewed by me, like `registry/calendar_events.csv`. This replaces the old note that college breaks were left out because only Mar 16–20, 2026 could be verified.
- No citywide count of out-of-area students was found (2026-11-11). For the write-up: NYU had about 57,000 students and Columbia about 35,000 in fall 2023 (NYC government report), and a quarter of New York State's first-time students in 2022 were from out of state (State Comptroller).
- Goes through N9 like every other input. If it doesn't help, say so in the write-up; that's still a result.

**Order for the new model inputs (agreed 2026-11-11): three tiers, by when the data can be ready, not by guessing which matter.** The input list is final for now; no more inputs unless I add them. Whatever isn't ready by Nov 17 isn't cut: the write-up lists it as "planned, not enough data yet". Every input goes through N9.

| Tier | When | Inputs (count) |
|---|---|---|
| 1 | Data already here: test first | Weather (3; **already tested 2026-11-06 as a best case with actual weather: added nothing, 4.73 either way**, so it counts as tested and stays out unless the final set changes that), shows playing that day (2), two-show days (1), show stage: previews and days since opening (2), price history from the grosses: ticket price against the show's usual and top-ticket rank (2), Broadway attendance season pattern from past grosses (1) |
| 2 | Quick to collect, hours each, before Nov 17 | Midtown subway riders (2), Times Square foot traffic (2), show buzz from the show's Wikipedia page (1), stars in current casts (2) |
| 3 | Needs cast news or slower collection | **Star history first: required, my top priority** (final weeks, days until leaving, limited run, cast changes: 4), days until closing (1), TKTS: on the board, discount, how often on the board (3; still collecting daily), NYU calendar (1) |

27 new inputs, about 47 in total with today's 20. **Ticket model limit:** at most about 6–8 inputs, each either helping on the line side first or with a clear reason to change ticket supply (two-show days is the obvious one).

**N12. Nerd stats visual upgrade (picked 2026-11-12)**
- Why: the plain charts look generic; I want the look of `docs/slides/cleaning-funnel.html` (marquee bulbs, glowing gold, one bold headline that states the point). Charts and presentation are 17 of 50 rubric points (§1.1).
- Upgrades to charts already there: (a) the cleaning funnel from the slide, bulbs and gold funnel, replacing the plain one; (b) reports per show as little marquee signs, lit bulbs = reports; (c) line growth as a queue of people figures outside a box office door, 3 am to 10 am; (d) the show-by-day grid as a light board, busier = brighter gold.
- New: (e) a calendar heatmap of every day since June 2024 colored by line length, with callouts (Tonys, Thanksgiving, the Jan 2026 blizzard, World Cup); (f) a theater district map (hand-drawn SVG of the streets, each theater a glowing dot sized by the day's line and colored GO / Maybe / Stay, click opens the show); (g) a star cast board: when high-profile stars joined and left, with the show's line underneath; (h) a morning race: animated bars of every show's predicted line from 3 am to 10 am, re-sorting as they grow.
- Not picked: 100 mornings, why-this-day waterfall, report card as ticket stubs, Reddit activity timeline, weather, rush clock, final-weeks bump, seasons and tourists.
- **Nerd stats is FAQ-style (my request 2026-11-12, ✅ built):** every chart is a closed question; click to open. Section headings, jump buttons and the short-version scores stay visible. So many charts don't bombard the viewer. I'm reviewing which current charts to scratch before the new ones are built.
- **Changes 2026-11-12 (my review of the current charts):** "How much does rush save?" removed from Nerd stats (not substantial). "Which shows and days are busiest?" moved to the top of the page and starts open. The cleaning funnel is rebuilt like my slide (6 steps, centered gold bars to scale, numbers inside): item (a) ✅. Chart yellow brightened (`--series-1` #b98a0c → #f0b829). The Key appeals footnote about the 20,000-views rule is removed from show pages.
- **No-data shows (my decision 2026-11-12):** a show with in-person rush but 0–6 line reports gets no tile on any home view and no bar in "How many reports does each show have?". Each place lists them in one quiet line at the bottom: "No data for: …". Today that's Downstate, It's a Wonderful Life, Wanted and Wicked. Shows with no in-person rush line (lottery-only, like Hamilton) keep their tiles.
- **Still to decide (me, later):** the bottom half of Nerd stats ("How good is it?" and "Model vs. ground truth") doesn't make sense to me yet: Claude explains each chart better or we cut them.
- Same rules as the other charts: numbers come only from the predictions file, readable at phone width, text contrast checked, and a plain table or text for screen readers.

**N13. UI feedback round (my review, 2026-11-23; ✅ built 2026-11-23, all pieces a–g)**
Big picture: the customer side is boring and too much of it hugs the left edge. More color, less text, centered layouts, and dashboards instead of one long scroll. Rule for the whole site: **if a block sits all on the left with empty space on the right, center it or spread it across the width.** Stays dark purple (never black, §2.4). Each piece below is separate, so any one can be reverted without touching the others.

*a. Header / title ("Broadway Rush")*
- **Much bigger**, and **centered** (I went back and forth; final: centered).
- **Taller header bar** (more padding top and bottom).
- **Stars around the title** (sparkle/star shapes on either side or around it, marquee feel). Nav links stay usable at phone width.
- Use the Nerd stats gradient text on the title (see f).

*b. Home page heading and day strip*
- **Center** the page question ("Is rush worth it this morning?" / "Which day should you go?" / "What's playing when you can go?") and the day strip under it.
- **The day strip fills the full width.** Today it covers about half the screen and the rest is empty. We can't predict many more days (TKTS limits how far ahead we go), so fill the width mainly by **making each day box bigger**; adding 1–2 more days is fine if the data allows, but don't invent days we can't predict.
- **Each day box looks like a calendar date,** like the Apple Calendar app icon: month on top in a colored band (e.g. "NOV"), the date number big underneath, weekday small. Selected day stands out (gradient band or glow).

*c. Sort, View and Filters*
- **Sort and View sit side by side** on one row.
- **Filters box:** today the box is very wide but its contents fill only about half of it. Fix by putting filter groups side by side (a grid of groups), so the box is filled, or narrowing the box. No empty half.
- **Filter chips/buttons use the Nerd stats colors** (magenta, violet, teal, gold gradients) instead of plain ones.
- ~~New filter: Classic vs. New show~~ dropped (my call 2026-11-23: no clean rule for "classic").
- **One new filter: "Star in the cast"** (Claude's pick, 2026-11-23; build it so I can see it, revertable). One button: show only shows with a high-profile star performing on the chosen day (same `starsOn` check the tile's star label and Key appeals use, so the 20,000-views rule from N5 decides). In the This week view, a star on any of your days counts. Uses data already on the site; no new collection.
- Backup ideas if I don't like it (not to build): "Closing soon" (announced closing in the next ~30 days, from `closing_date`), rush price bands (e.g. under $40 / $40+).

*d. Carousel view*
- Today's carousel (a flat sliding row) is boring. Replace with a **3D carousel**: one tile (or three) shown big in the middle, the neighbors **fold/tilt away to the sides** in perspective, and swiping/arrows rotate to the next one. Like a component I liked on 21st.dev.
- ✅ **Reference received 2026-11-23:** the 21st.dev "Glassy Coverflow Carousel". Geometry, input rules and what to skip are in [`docs/reference/glassy-coverflow-carousel.md`](docs/reference/glassy-coverflow-carousel.md). It's a React/Tailwind/TypeScript component; **our site is plain JS, so rebuild the effect in `web/app.js` + `web/styles.css`. Don't add React.**
- How it looks: the center card is full size and flat. Two cards on each side step back, shrink about 8% each, tilt up to 42° away, and get darker. Drag/swipe or ← → to rotate. It wraps around. Under it: the center show's name, plus a pill with `03 / 12` and ‹ › buttons.
- For us: each card is the show's tile (picture on top). Clicking a side card brings it to the center; clicking the center card opens the show page. One coverflow per group, like today's one row per group. Colors from our dark purple + Nerd stats palette, not its light default. No autoplay, trailers or logo.
- Keep the current sort order inside the carousel (I like how they're sorted). Keyboard arrows + swipe work; respects reduced motion.

*e. Nerd stats page → dashboard*
- When I shared the 21st.dev / Gradient Able UI, I meant **its layout**, not mainly its colors. The colors look good; keep them.
- **Center the jump buttons** (the "what do you want to see" buttons); today they sit on the left and look bad.
- **Dashboard layout:** panels arranged left / center / right and top / bottom, so you see several charts at once, instead of one column you scroll down that fills about 2/3 of the left half. Use the full width; panels of different sizes in a grid.

*f. Nerd stats colors on the customer side*
- I really like the **gradient text** on Nerd stats (pink → violet → gold section titles). Bring it to the customer pages: title, page question, section headings on show pages.
- Bring in more of the Nerd stats colors (magenta #ff4fb3, violet #a42cf0, teal #19d3c5, gold #ffd25a) for filter buttons, accents and panel edges. More color overall.

*g. Show page (clicking a show)*
- Too little color, too much small text, one long scroll. Make it **a dashboard of panels**, with color from f.
- **Less text on screen.** This is client-facing; don't overwhelm people. Keep the key numbers big; move the detail to Nerd stats. Bigger text where text stays.
- **Rush policy:** content is good. Make its panel **span the full width** (centered across the page, not just the left side). Text can go in two columns inside it.
- **About the show** (category + info rows) → a **streamlined table**, with color.
- **About and Key appeals side by side.**
- **Show picture** (the Ticketmaster image we already have) on the **right, above Key appeals**.
- **Link to Nerd stats from every show page**, clearly visible (a button, not just the small line at the bottom). If possible it opens Nerd stats on that show (the ground-truth table can already look up by show).
- Keep everything else I asked for on show pages before.

*Done when:* each piece matches the above at desktop and phone width (no sideways scroll, 16px side gutters), text contrast still passes on dark purple, `?v=` bumped on `app.js` and `styles.css`, and nothing from earlier builds is lost.

**N14. UI feedback round 2 (my review of N13, 2026-11-23; not built)**
N13 looks great overall: the bigger centered title, the filters and the 3D carousel stay. This round fixes what's left. **Same rules as N13:** one lettered piece at a time, each in its own commented CSS/JS block (and an `N14` switch like `N13`'s) so I can revert any piece; dark purple, never black; check at desktop and phone width.

**The feeling I want (applies to everything):** someone who loves Broadway and loves data opens this and thinks "this is everything I ever wanted to know about rush tickets", the way I felt the first time I opened the Garmin app. Beautiful, with personality, Broadway marquee charm. **Not generic, not "AI-looking"** (no Gemini-style sparkles, no default gradients everywhere).

*a. Title: a gold marquee sign*
- Color: **mostly yellow/gold**, with only a little pink and purple (today it's mostly pink and purple).
- **Replace the moving side stars** (they look like the Gemini logo, very AI). Instead, **put the whole headline inside a Broadway marquee sign**: a frame with light bulbs all around the edge.
- The bulbs **blink or chase gently**, never distracting (slow, soft). Reduced motion: bulbs stay lit, no blinking.

*b. Sort, View, Filters and Show favorites*
- Filters: no complaints, keep them.
- Sort and View get lost next to the big calendar strip: make the **text on Sort, View and Filters a bit bigger** (a little, not a lot).
- **Show favorites moves next to Sort and View** on the same row. Today it hangs by itself under Filters.

*c. Same-size show images*
- Every tile, carousel card and show page image is **the same size and shape** (one fixed aspect ratio, cropped to fill).
- **A show with no picture gets a generic theater image** (stage, curtain, people on stage), the same one for every such show. Any image is fine, but it must be **free to use**: a public-domain / CC0 photo (e.g. Wikimedia Commons or Unsplash, credited if the license asks), or a stage/curtain illustration we draw ourselves in SVG. Don't grab a random picture from a Google search (copyright). Saved in `web/`, not hotlinked.

*d. Show page: the predictions come first*
- ⚠️ Biggest fix: **today's show page shows only show details and none of the machine learning.** That's the whole point of the app. "Move the detail to Nerd stats" (N13 g) meant the boring stuff, not the predictions.
- **First thing on the page, at the top:** the **expected number of rush tickets ± range** (with the chance of getting one), and **right next to it, the line length / how the line builds over the morning** (the line-over-time chart, with the arrival time to beat). Big and clear.
- Then, below: the data confidence ("Limited data", "Probably easy"), About the show, Key appeals, Rush policy, etc.
- **Remove everything about "how much you'd save"** everywhere on the site: the savings panel, "what you'd save", and the typical ticket price shown as a saving. It looks like a coupon-clipping app; this is a Broadway rush machine-learning app. (~~§2.6 "show pages get … what you'd save"~~ and N3's savings wording are retired. The typical ticket price can stay only as a plain fact in About the show, if at all.)
- **Colors:** the show name (e.g. "Hadestown") keeps the gradient. **The panel headings ("Limited data", "Probably easy", "About this show", "Key appeals", etc.) go back to the earlier gold.** Too much color right now.
- **The pink vertical line on the left of every panel:** remove it, or make every one gold. No pink stripes.
- **No blank holes:** panels side by side must end at the same height, or the layout reflows to fill the space. Example today (Hadestown): name, picture and Key appeals on the right, About the show on the left, and empty space under About the show. Fill it (move a panel up, stretch, or rearrange).
- **Width: the show page takes up the middle 2/3 of the screen or less** (centered), not the full width. Phone stays full width with gutters. (This page only; the home page stays wide.)

*e. Nerd stats: top of the page*
- The **jump buttons are too small; make them bigger.**
- **Refresh button moves to the top-right corner as an icon** (circular-arrow refresh icon). On hover it says "Refresh". Only I use it, so it doesn't need to explain itself to viewers.

*f. Nerd stats: "Which shows and days are busiest?" grid*
- **Hover today turns the cell dark/black; don't.** On hover the cell changes to a **light pink** and you can still tell how busy it was (the level still shows).
- **The hover box covers the numbers.** Keep its information (it's useful), but show it **somewhere that doesn't cover the grid** (e.g. a fixed info line or side panel next to the grid).
- **The hover box color: pink**, not the current brown.
- **The Show column: bigger text, less blank space.**

*g. Nerd stats: a real dashboard, interactive*
- **Every question heading is gold.**
- **N13 e didn't go far enough:** it still reads as one long scroll. I want **left / center / right panels and top / bottom**, several things visible at once.
- **Small boxes don't get a full row.** Any box with lots of empty space moves to the side and pairs with another. Examples: "What did it cost?" (huge empty middle) → half width or less; "Final score, 3 locked months" sits **side by side with "Does it beat the simple lookup table?"**. Bigger text, less blank space in both.
- Charts with the right amount of space (the graph panels) stay as they are; that's the good spacing.
- **"How fast does the line grow?"** takes about half the width, with its legend / options on the side.
- **Order: most accurate and most impressive results at the top,** less accurate, less important, less impressive ones further down.
- **Interactive everywhere:** this is a data science project, not just a customer page. Viewers can click and hover to dig in: switch which lines or shows a chart shows, hover the cleaning funnel steps for what was dropped and why, click a bar in "How many reports per show?" to see that show, and so on. Goal: **you can find out literally everything about the project by clicking around.** Some charts get more options than others, but never so many that it gets busy.

*Done when:* all of the above at desktop and phone width, nothing from N13 lost apart from what's replaced here, and the site feels like a Broadway data fan's dream, not an AI template.

**Not adding (my decision 2026-11-11):** the deal size (typical ticket minus rush price), subway disruptions, and rush policy changes.

Build N1 first: it changes text widths, and N2, N3 and N5's star label all add text to the tile.

#### Things to scrape or collect for the build queue (listed 2026-11-11; collected 2026-11-11 where marked)
Check `registry/sources.csv` before each one, and add a row for anything new. Same rules as always: no logging in, no getting around bot protection, polite gaps between requests.

| # | What | For | Where from | Status |
|---|---|---|---|---|
| C1 | Current principal cast of every running show: person, role | N5 | For the site: Playbill production pages. For the model: Wikipedia and official show sites. 47 are already saved in `data/raw/playbill/show_pages/` from the runtime lookup on Nov 6; check whether they hold the cast before fetching again. Official show sites as a cross-check | ✅ 2026-11-11 for the site: 445 current principals in 33 shows, from the Playbill pages cached Nov 6 (no new requests). Model-side casts come with C2 |
| C2 | Star runs since June 2024, including closed shows: who joined and left, and the dates each was announced | N5 model inputs, "What's a star worth?", `Star leaving` badge | Wikipedia show articles first, then BroadwayWorld casting news and official show sites (not Playbill, see below). About $0.30–$3 of AI reading, which I approve first | ✅ 2026-11-12: full run, one pass, **$0.18** (batch service): 976 BroadwayWorld casting articles + 93 Wikipedia cast sections → 3,219 changes → **1,387 runs in 113 shows** (1,100 with a join date, 275 with a leave date) in `data/interim/star_stints.csv`; review sheet `data/labels/casting_review.csv` (3,633 rows, 604 flagged; the 130 rows on current stars are at the top, 24 flagged ones pre-filled by Claude) |
| C3 | Monthly Wikipedia page views for every principal from C1 and C2 | N5 cutoff and `star_views` | Wikimedia's page-views service (in the registry since 2026-11-11) | ✅ 2026-11-11 for current principals: 149 of 445 have a page; monthly views cached |
| C4 | Tourist traffic: Times Square Alliance pedestrian counts (monthly reports; daily counts by request, which I send) and MTA hourly riders at the Midtown stations (2017 on), both; Port Authority monthly airport passengers as a spare | N6 | data.ny.gov open data API; panynj.gov reports; timessquarenyc.org reports. Hotel occupancy: no public monthly source | 🔶 MTA collected 2026-11-11 (`data/raw/mta_midtown_daily.csv`); ✅ Times Square monthly reports 2026-11-17: 33 PDFs → `data/raw/timessquare_monthly.csv` (`scrapers/timessquare.py`); the weekly operations report shows only the latest week; ✅ **daily counts received 2026-11-17** (the Alliance answered my email the same day): Jun 1, 2024 to Nov 16, 2026, totals and 23 cameras → `data/raw/timessquare_daily.csv`; airport passengers not fetched (spare) |
| C5 | More years of weekly Broadway attendance, for the seasonal pattern | N6 | Playbill grosses, already an approved source (back to 1985); 127 weeks are already saved | ✅ 2026-11-11: 465 more weeks, Jan 2014 to May 2024 (`data/raw/grosses_history_playbill.csv`) |
| C6 | A lottery's web address, only when the policy list has none | N4 | The show's official site | Not needed today (25 of 25 covered) |
| C7 | Special deals: what, which show, which dates | N10 | Playbill's rush policy article first (already scraped), then Playbill news | 🔶 2026-11-11: the policy list's 4 deals are on the site; dated deals file `registry/special_deals.csv` is empty (Playbill news can't be read by AI) |
| C8 | Each show's Wikipedia page title, then its daily page views | N7 | Wikimedia (in the registry) | ✅ 2026-11-11: 112 of 121 titles in `registry/show_wiki_titles.csv` (for me to check), daily views cached |
| C9 | Opening, first preview and closing dates | N7 | Grosses and Playbill (already approved); closing from cast news (§3.12) | 🔶 first preview and opening weeks from the grosses (2026-11-11); **42 production end dates** from run-extension news in `data/interim/show_end_dates.csv` (2026-11-12); closing announcements not yet separated from extensions |
| C11 | NYU academic calendars, June 2024 to May 2027 (~~also Columbia, The New School, FIT, Fordham, Juilliard~~) | N11 | NYU's official published calendars | ✅ 2026-11-11: I pasted NYU's calendar (Mar 2024 to Jan 2028, 506 events) into `data/raw/nyu/nyu_calendar_paste.txt`; `python -m broadway_rush.nyu_calendar` turns it into 51 periods in `registry/college_calendars.csv` |
| C10 | Whether rush is sold for both performances on two-show days | N8 | The policy text already scraped (§3.4); official show sites only if it doesn't say | 🔶 2026-11-11: the policy text never says, so 34 of 35 are "unknown" (Hadestown's standing room: separately); official show sites not in the registry yet |

**Decided 2026-11-11: Playbill cast facts are for the site only** (its pages say `ai-train=no`). **The model's star and cast inputs come from other sources**, checked in the registry first:
- **Wikipedia show articles:** cast lists and "notable replacements" sections, often with dates. Wikipedia text is CC BY-SA, so it's fine to use with credit; read through Wikipedia's official API, the same service as the page views. The best start for star history (C2).
- **BroadwayWorld casting news:** already in the registry as allowed (`broadwayworld.com`, "casting news"). Joining and leaving announcements, with dates.
- **Official show websites and press releases:** current cast, final performances.
- Not usable: IBDB and the Broadway League (their terms ban automated collection), SeatGeek (blocked, §3.8).
- **Ticket demand** needs no new site: weekly grosses (seats sold, average ticket), the show's Wikipedia page views (N7), TKTS and Ticketmaster (collecting daily).

**Cost of reading casting news with AI (estimated 2026-11-11, not approved yet):** Claude Haiku 5.5 is $0.10 per million tokens in and $0.50 per million out, half that with the batch service. A casting article is roughly 1,500 tokens in and 200 out, about $0.0003 each, or $0.00013 batched. 2,000–5,000 articles since June 2024 come to about **$0.30–$1.50**, or up to about **$3 with a second checking pass** like the Reddit cleaning. Wikipedia replacement lists for about 120 shows add a few cents. Spent so far: $2.96 of the $8 project cap, so it fits.
- **Approved 2026-11-11: hard cap $2.50 for all star-history AI reading, aim for about $1,** so a full redo still fits under $8 if I don't like the results. Use any legal source needed for star and demand data (registry rules still apply).
- **How to stay under it:** Wikipedia replacement lists first (cents). Then only read articles whose titles or first lines are about casting, joining or leaving. Use the batch service and cache the instructions. Test on about 50 articles first and check them against answers Claude pre-fills and I review, as with the Reddit extraction, before the full run. **One pass only (my decision 2026-11-11): no second checking pass,** even on uncertain results; flag those for me to review instead. Log every call in `data/interim/llm_spend.csv`, and stop if the next step would pass $2.50.

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
- **Features:** ~~`major_event_midtown_today`, `msg_event_tonight`, `javits_convention_today`, `tourism_index_month`~~. **Dropped from the model (my decision 2026-11-11):** the tourist numbers (§2.8 N6) measure how busy Midtown is directly, so event inputs aren't needed. The permit data already collected stays on disk, and the hand-kept calendar (§3.6, which includes the Marathon and the Thanksgiving parade) stays in the model. Ticketmaster NYC events, SeatGeek and Javits won't be collected.
- **Built 2026-11-05:** `scrapers/nyc_events.py` → `data/processed/nyc_events_daily.csv` (full street closures and parades in the theater district, parades and races in Manhattan), and the hand-kept list in `registry/calendar_events.csv`. Raw counts mislead: ~157k of 212k Manhattan rows are sports permits, and parade grandstands are listed three weeks early. **Unknown, not zero:** Sept–Oct 2026 and anything over a month ahead aren't published yet, and July 3–7, 2026 can't be told apart from a lull; these days have `permits_complete = 0` and blank counts.
- **Not built:** Ticketmaster NYC events, SeatGeek, Javits, nyctourism.com.
- 🆕 **Hotel occupancy as a tourist gauge (added 2026-11-11, my idea; not built, source not found yet: §2.8 N6).** How full NYC's hotels are says how many tourists are in town. In tourist-heavy seasons Broadway demand goes up, both for tickets bought ahead and for rush lines. This is the real number behind `tourism_index_month` above.

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
- **Star inputs (decided 2026-11-11, not built: §2.8 N5).** "Star" follows the Wikipedia page-views rule in §2.2a, from `registry/stars.csv`:
  - `has_star`: a high-profile star is in the show on that date.
  - `star_views`: how famous the show's biggest current star is (their monthly page views, on a log scale), so a household name counts for more than someone just over the cutoff.
  - `days_until_star_leaves` and `star_final_weeks` (last 2 weeks of their run): my expectation is that lines and prices climb most when a star's run is almost over.
  - Each is computed only from what was public on the prediction date. A departure counts from the day it was announced, not before.
  - **Needs history to test.** The model can only learn a star effect from past star runs, so `stars.csv` has to cover June 2024 on (for example Aaron Tveit in Moulin Rouge), not only today's casts. There may be too few star runs with enough rush reports to measure it. Report it as a with/without row in the results table (§5.3) whichever way it comes out, and keep the tile label and filter even if the model inputs don't help.
  - Average ticket price is already a model input (§3.3), so some of a star's effect may already show up through prices. The with/without row measures what stars add on top.

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
- **Build queue (2026-11-11, my requests, none built yet; details in §2.8):** N1 header font changes from Bebas Neue to Montserrat Black, all caps, because Bebas is too narrow. N2 clicking the theater name opens Google Maps directions to that theater in a new tab, so you can see how far it is from you; the site doesn't ask for your location. N3 the typical ticket price shows next to the rush price, crossed out, with the saving, so the deal is obvious. N4 shows with a digital lottery or digital rush link to the page where you enter or buy, and mention the app when there is one. Also added §10, ideas outside this project's scope.
- **High-profile star rule (2026-11-11, my decision; replaces Claude's placeholder of above-the-title billing or a major award):** a star is a current principal whose Wikipedia page passed a monthly view count in the 12 months before their casting was announced. Claude ranks everyone, I pick the cutoff and can override by hand. **Cutoff picked the same day: 20,000 median monthly views**, so Jeremy Jordan, Eva Noblezada and Reeve Carney count, and Megan Hilty and Helen J. Shen don't. Stars get a label on the tile, the filter, the `Star leaving` badge, and model inputs, because stars raise demand and prices, most of all near the end of their run (§2.2a, §3.12, §2.8 N5). Not collected or built.
- **More model inputs (2026-11-11, my picks from Claude's list; §2.8 N7–N10):** adding show buzz from the show's Wikipedia page, how many shows play that day, show stage (previews, since opening, until closing), and two-show days, which also change the site. Then measure how much each input matters and cut the weak ones before the freeze. Special days are out of the model (too rare to train on); the site flags special deals instead. Not adding: deal size, subway disruptions, rush policy changes. College calendars: added the same day, NYU first, since I'm presenting at an NYU competition (N11), then ~~added~~ dropped for now in favor of tourist traffic, then brought back as one NYU-only input in tier 3 (final, same day).
- **Open details settled (2026-11-11):** 2-show days get a "2-show day" filter, Matinee / Evening options when 2-show days are on screen, and Matinee and Evening sections otherwise (§2.8 N8). The star section is called "Key appeals". Playbill cast facts are for the site only; the model's cast and star inputs come from Wikipedia, BroadwayWorld casting news and official show sites. Reading casting news with AI: approved with a hard cap of $2.50, aiming for about $1, so a redo still fits under the $8 project cap.
- **Input list and order final for now (2026-11-11):** three tiers by data readiness (§2.8); star history is my top priority in tier 3. No more inputs unless I add them.
- **Tourist traffic comes first among new inputs (2026-11-11, my call: more substantial than college calendars).** Sources: Times Square foot traffic from the Times Square Alliance and subway riders summed over the Midtown stations near the theaters, both (Times Square station alone would miss tourists who walk in or use nearby stations). Airport passengers as a spare. **College calendars dropped for now** the same day.
- **NYC events dropped from the model (2026-11-11, my decision):** the tourist numbers cover how busy Midtown is, so Midtown events, Madison Square Garden and Javits inputs aren't needed (§3.9). The permit data already collected stays; the hand-kept calendar stays in the model. This changes the Nov 5 "everything stays in" list for NYC permitted events. **Star history stays and is required:** I want to measure how much a high-profile star draws in an audience, from rush reports and from weekly grosses (§2.8 N5). Hotel occupancy has only yearly public numbers (§2.8 N6).
- **Hotel occupancy (2026-11-11, my idea):** if a legal source exists, use NYC hotel occupancy as a measure of how many tourists are in town, since tourist season raises demand for both tickets bought ahead and rush. No source confirmed yet; tested as a with/without row and kept only if it helps (§3.9, §2.8 N6).
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
- **Build queue, scheduled run of 2026-11-11 (Claude's choices while I was away; mine to review, §2.8 and `process.md`):**
  - **Matinee = a performance starting before 5 PM.** Matinee and Evening sections appear only when a 2-show day is on screen; inside each, the three show groups stay. Matinee / Evening is a day-view filter only.
  - ~~Typical price stays in the facts line~~ No typical price on tiles (2026-11-12).
  - **One tile per show by default (my decision 2026-11-12).** A 2-show day shows one tile with "2 shows today: 2 pm & 8 pm". Matinee or Evening alone filters to that showtime; picking both splits the day into Matinee and Evening sections, where a 2-show show appears in both.
  - **Dated special deals** go in `registry/special_deals.csv`; standing deals come from the policy list.
  - **Show Wikipedia titles** live in `registry/show_wiki_titles.csv`, not `shows.csv` (which `catalog build` rewrites).
  - **Current cast for stars = the first cast list on each cached Playbill page** (the current cast), principals only. Stars' windows: originals use the 12 months ending 3 months before the show's first preview; replacements use the last 12 months, marked provisional until cast news gives their join date. A Wikipedia page that doesn't describe a performer is never counted.
  - **Times Square foot traffic and the NYU calendar are on hold, not dropped** (terms and site access: questions 29–30). NYU: I'll supply the dates myself (2026-11-11).
  - **Star history test:** one Haiku pass on 50 BroadwayWorld articles cost $0.018; the full run waits for my review of the sheet.
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
25. **Filter choices to review (§2.2a):** ~~the high-profile star rule~~ (decided 2026-11-11: Wikipedia page views, §2.2a; cutoff picked: 20,000 median monthly views, §2.2a), the runtime bands, and whether Lottery and Standing room belong in the rush-type filter, since they aren't rush. Also from the build: a standing-room price counts as the rush price when a show has nothing else (Hadestown $39, Six $49), and Hadestown gets `In person (reported)` as well as `Standing room`.
26. **Limited-data shows (parked 2026-11-06, to figure out later):** look at other features for them. Nothing built, and the site still says "Limited data, probably easy" on all 6 until this is decided. Only 3 recorded outcomes exist across the 6, so nothing can be tested on them directly. Ideas from Claude, not decided:
    - **Wording:** replace "probably easy" with "Not enough reports to predict". It's on Hadestown at 95% seats sold and on It's a Wonderful Life, which has no reports or grosses.
    - **Standing room:** it sells only when a show sells out, so for a show where it's the only in-person option (Six, 60% seats sold), the question is whether the show sells out at all, not how long the line is.
    - **A rough label:** "usually easy" or "usually busy", with no percentage, from things that don't need rush reports: seats sold, typical ticket price, days on TKTS, how much Reddit talks about the show, and cast news once collected. Test: hide each of the 16 well-reported shows in turn and check whether the label predicts its real lines. If it doesn't beat treating every show the same, keep the neutral wording.
    - **Downstate** may not need any of this: it's at 1.5 reports a week, and 2 gives it a full prediction.
27. **Just in Time's days:** §2.2a's example says it doesn't play Monday or Wednesday. Playbill's schedule (Wednesday in all 8 weeks) and Ticketmaster both show it playing Wednesdays, dark Monday only. The site follows the data. Was the example about something else?
28. **This week view, tie rule (§2.2b):** days with the same arrival time count as tied (placeholder). Times are on a 15-minute grid. On Nov 8–14 this gives 14 of 16 shows a single best day (Sunday); Operation Mincemeat ties Sunday, Tuesday and Thursday, and Wanted ties all 5 days it plays. A wider window (say, within 15 minutes) would name more ties.
29. ~~**Times Square foot traffic:** the Alliance's terms say personal, noncommercial use and no derivative works. Use the monthly reports anyway, send the drafted request (it asks permission too), or skip it? Nothing downloaded.~~ Answered 2026-11-17: use the monthly reports (done); the daily request is still mine to send.
30. ~~**NYU calendar:** nyu.edu blocks Anthropic's crawlers by name and bulletins.nyu.edu failed certificate checks here. Paste the dates, allow one fetch with a facts-only script, or skip it?~~ Answered 2026-11-11: I pasted the calendar; built (N11).
31. ~~**Hamilton's special deal (N10):** no dated Hamilton deal is on the policy list or found by search. What is it?~~ Dropped 2026-11-11: I said to ignore it.
32. ~~**Stars (N5):** review the 32 stars and 8 near the line in `registry/stars.csv` (column `override`, with a one-line `reason`), then I switch the site parts on. 11 of the 32 are replacements with provisional numbers. The show titles in `registry/show_wiki_titles.csv` also need a check.~~ Answered 2026-11-11: good to go; switched on.
33. ~~**Star history (C2):** review `data/labels/casting_test_review.csv`, then a go for the full run (about $0.35, one pass).~~ Answered 2026-11-11: go (one pass, $2.50 hard cap).
- ~~Confirm Ticketmaster Discovery API free-tier limits.~~ Done 2026-10-22: 5,000 calls/day, 5 per second.

## 10. Extrapolation opportunities (outside this project's scope)

Ideas for where this could go next. **None of these are planned, scheduled or to be built for the competition.** They're here so they aren't lost, and as "what I'd do next" material for the presentation. Don't build anything from this section without a new decision from me.

1. **An agent that enters digital lotteries for you (added 2026-11-11).** The site already knows which shows have a lottery and where to enter (§2.8 N4). An agent could enter the ones you pick each day, with your details, and tell you when you win.
   - Why it's out of scope: this project predicts in-person rush. Lotteries are luck, not lines, and they were left out of the predictions from the start (§3.5).
   - What would have to be settled first: lottery sites generally allow one entry per person and may ban automated entries in their terms, so the first step is reading each site's rules (Telecharge, Broadway Direct, Lucky Seat, TodayTix). This project's rule is legal sources only, with no logging in and no getting around bot protection (§3.11), and that rule would apply here too. It would also mean storing people's names, emails and maybe payment details, which this site deliberately avoids (no sign-in, §8).
   - A version that stays inside the rules: a daily reminder with one-tap links to every lottery you follow, so you still enter each one yourself.

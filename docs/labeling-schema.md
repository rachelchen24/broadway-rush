# Labeling schema: Reddit rush reports (step 2)

Used for **both** the ~100 hand labels and the Haiku extraction, so accuracy can be compared field by field. Based on SPEC §4.

## Unit: one row per observation

A comment yields **0 to n rows**. Most comments are questions or chat (0 rows, labeled `kind = none`). One comment can describe several shows, or one show at several times, so each gets its own row.

| `kind` | What it records | Example |
|---|---|---|
| `line_count` | How many people were in line at a show at a given time | "about 13 people in line at Outsiders by 6:00" |
| `attempt` | The writer's own (or a friend's) visit: arrival, position, outcome | "4th in line, got there at 5am… only sold one student ticket" |
| `supply` | Anything about how many rush tickets existed or when they ran out | "they said they had 2 left" (6pm), "sold out by 10:15", "they had 26 rush seats" |
| `none` | No usable observation (question, chat, joke, ticket-swap offer) | "where does the rush line start for just in time?" |

A single sentence can produce several rows. Example: "Was #6 at Gypsy 9:25. 8 people by the time BO opened. Other lines: Gatsby 6/7, DBH 12" → 1 `attempt` (Gypsy) + 1 `line_count` (Gypsy, 10:00, 8) + 2 `line_count` rows (Gatsby, DBH at 9:18–9:25).

## Rules for common cases (added while pre-labeling; the Haiku prompt has the same list)

- **Own arrival = one `attempt`.** "Got there at 8:40 and was 10th" doesn't also get a `line_count` that repeats the same fact.
- **Someone else's arrival = `line_count`**, with the count set to that person's place: "first at 7:30" → count 1 at 07:30; "the two ahead of me got there at 7:30" → count 2 at 07:30.
- **"N in line when the box office opened"** → `line_count` with a blank `time`.
- **"now", or no time given** → the comment's posting time.
- **"Evening sold out at the 17th person (arrived 9am)"** → a secondhand `attempt`: arrival 09:00, position 17, `sold_out_before_me`.
- **A reply only gets what it says itself.** Data that's only in the parent belongs to the parent comment. A reply that just asks a question or says thanks is `none`.
- **The comment may be about a different day than the thread** (posted after midnight, "yesterday", "I'm here on 3/19") → `perf_date` = the day it describes.

## Fields

**All kinds**

| Field | Values | Rules |
|---|---|---|
| `comment_id` | Reddit id | |
| `kind` | `line_count` / `attempt` / `supply` / `none` | |
| `show_text` | Text as written | "DBH", "the Imperial", "r+j" |
| `show` | Canonical show name | Expand nicknames and theater names when clear for that date (DBH → Death Becomes Her; Imperial in 2026 → its show then). Blank if unsure. A show catalog (SPEC §3.0) will validate these later. |
| `perf_date` | YYYY-MM-DD | Thread date by default; shift for "yesterday", "tomorrow", "Saturday". |
| `perf` | `matinee` / `evening` / `unknown` | Only if stated or obvious ("for the 2pm show"). |
| `rush_type` | `general` / `digital` / `student` / `sro` / `lottery` / `other` / `unknown` | `general` = in-person box office rush. Out-of-scope types are still labeled so they can be filtered out later. |
| `secondhand` | `true` / `false` | "from a friend", "1st in line said he got there at 5". |
| `confidence` | `high` / `medium` / `low` | `low` for jokes, sarcasm, heavy guessing ("12th-ish… I think"). |
| `needs_context` | `true` / `false` | The row only makes sense with the parent comment ("First four got there at 2:30"). |

**`line_count`**

| Field | Rules |
|---|---|
| `time` | HH:MM, 24-hour ET. "around 8" → 08:00. "by the time BO opened" → that show's opening time if known, else blank. |
| `count` | Number of people. "6/7" or "5 or 6" → lower number + `approx`. "50+" → 50 + `at_least`. "a couple dozen" → 24 + `approx`. |
| `count_qual` | `exact` / `approx` / `at_least` / `at_most` |

**`attempt`**

| Field | Rules |
|---|---|
| `arrival_time` | When they joined the line (HH:MM). |
| `line_position` | Their place, as written ("4th" → 4, "#6" → 6). Counts **people**, not parties, unless the text says parties. *Why:* if a party of 2 is counted as 2 people, the line looks longer, so the app errs toward "arrive earlier". Better to miss a ticket we'd have said was likely gone than to send someone to a line that's already too long. |
| `outcome` | `got_rush` / `sro_only` / `full_price_only` / `sold_out_before_me` / `left` / `unknown` |
| `tickets` | Number bought. |
| `seat` | Free text: "balcony", "stage seats", "orch J 9&11". |
| `window_time` | When they reached the box office window, if given. |

**`supply`**

| Field | Rules |
|---|---|
| `time` | When the statement applied (e.g. 18:00 for "2 left" at 6pm). |
| `stated_count` | Number of rush tickets stated ("26 rush seats", "2 left"). |
| `stated_qual` | `total` (whole day's rush allotment) / `remaining` (left at that time). **`remaining` with a blank `stated_count` = "still available, count unknown"** ("they had tickets for both shows at 11:30"). That still tells the model supply hadn't run out by then. |
| `sold_out_time` | HH:MM when rush ran out, if given. |
| `sro_offered` | `yes` / `no` / `unknown` |
| `late_release` | `true` if "come back later" / tickets released later in the day (SPEC §3.7). |

**Optional on any row:** `cast_note` (e.g. "Audra is out"). This feeds the cast features (SPEC §3.12).

## Context given to the labeler (you or Haiku)

For each comment: the thread title, thread date, the comment, **its parent comment** (if it's a reply) and the comment time (ET). Replies like "Did you get in?" → "Yes, 2 balcony" only make sense together.

## Hand-labeling sheet (step 2b)

`data/labels/hand_labels.csv` has one row per observation, with the columns above. Context columns (`thread_date`, `parent_body`, `body`) come pre-filled. For a comment with nothing usable, fill one row with `kind = none`. For a comment with 3 observations, copy the row 3 times.

Sample: about 100 daily-thread comments. About 70 are picked from ones that look like reports (contain a number, a time or "line"), so the hard cases get enough examples, and about 30 at random, so we can measure how well `none` is detected. The seed is fixed so the sample can be reproduced.

## Scoring (step 2c)

- **Per comment:** is `none` vs. not-`none` correct; is the number of rows right.
- **Per matched row** (matched on show + kind): exact-match accuracy for categorical fields; times within ±10 min; counts exact, and within ±1.
- **Headline numbers:** precision/recall of observations, and accuracy on the model-critical fields (`show`, `line_position`, `outcome`, `count`, `time`).

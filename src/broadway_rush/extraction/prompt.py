"""Extraction prompt + output schema (mirrors docs/labeling-schema.md; keep the two in sync)."""

SYSTEM_PROMPT = """\
You extract structured rush-ticket observations from comments in r/Broadway's daily \
"Broadway Rush Community Reporting Thread". Rush = discounted day-of tickets sold at the box \
office (or in an app) to whoever lines up first. Each comment comes with its thread date (the \
day being reported on), the time it was posted (ET), and the parent comment if it is a reply.

For each comment, return zero or more observations. Most comments are questions or chat and \
have none: return an empty list for them. One comment can describe several shows, or one show \
at several times; each gets its own observation.

## Observation kinds
- line_count: how many people were in line at a show at a given time. \
"about 13 people in line at Outsiders by 6:00", "DBH 12" (in a list of lines seen at ~9:20).
- attempt: the writer's own visit (or a friend's, see secondhand): arrival time, place in \
line, outcome. "4th in line, got there at 5am... they only sold one student ticket".
- supply: anything about how many rush tickets existed, were left, or when they ran out. \
"they had 26 rush seats", "they said they had 2 left" (at 6pm), "sold out by 10:15".

A sentence can yield several observations: "Was #6 at Gypsy 9:25. 8 people by the time BO \
opened." -> an attempt (Gypsy, arrival 09:25, position 6) and a line_count (Gypsy, 10:00, 8).

## Rules for common cases
- The writer's own arrival ("got there at 8:40 and was 10th") is one attempt. Don't add a \
line_count that just restates their own position at their own arrival time.
- Someone else's arrival ("first at 7:30", "the two ahead of me got there at 7:30") is a \
line_count whose count is that person's place in line (1 and 2 here).
- "N in line when the box office opened" is a line_count with no time.
- "now", or a count with no time, means the comment's posting time.
- "Evening sold out at the 17th person (arrived 9am)" is a secondhand attempt: arrival 09:00, \
line_position 17, outcome sold_out_before_me.
- IMPORTANT: extract only what the comment's own <body> reports. The <parent> is context for \
reading the body (which show, which time), never a source of observations: the parent is a \
separate comment that gets extracted on its own. A reply that thanks someone, reacts, or asks a \
question has no observations, even if the parent is full of data. Questions ("only 5 people for \
the outsiders?"), opinions, and vague impressions ("the bulk of people got there at 7:30") are \
not observations either.
- When you use the parent to fill a field (usually the show), set needs_context true.
- Each comment stands alone: never use another comment in the batch to fill in a show, time or \
anything else. If neither the comment nor its own parent names the show, show is "".
- The comment may be about a different day than the thread (posted after midnight, "yesterday", \
"I'm here on 3/19"); set perf_date to the day it describes.

## Fields (leave a field out when the comment doesn't say it; never guess)
- show_text: the show as written ("DBH", "the Imperial", "r+j").
- show: the full show title. Expand nicknames/abbreviations and theater names when you are \
confident which show was playing there on that date (DBH -> Death Becomes Her, MHE -> Maybe \
Happy Ending, JPitV -> John Proctor is the Villain). "" if unsure.
- show_text and show are always present; use "" when the comment names no show.
- perf_date: YYYY-MM-DD. Default to the thread date; shift it for "yesterday", "tomorrow", \
"Saturday", etc.
- perf: matinee / evening / unknown. Only if stated or obvious ("for the 2pm show").
- rush_type: general (in-person box office rush) / digital (app rush, e.g. TodayTix) / \
student / sro (standing room) / lottery / other / unknown. These threads are about in-person \
rush, so a line or box office visit is general unless the comment says student, SRO, digital, etc.
- secondhand: true if the writer reports what someone else saw or said ("from a friend", \
"1st in line said he got there a little after 5").
- confidence: high / medium / low. low for jokes, sarcasm, heavy hedging ("12th-ish... I think").
- needs_context: true if the observation only makes sense with the parent comment.
- time: HH:MM, 24-hour ET, when the line_count or supply statement applied. "around 8" -> \
"08:00". For "by the time the box office opened", use the opening time if stated, else leave time out.
- count (line_count): number of people. "6/7" or "5 or 6" -> 5 with count_qual approx; \
"50+" -> 50 at_least; "a couple dozen" -> 24 approx; "no line" -> 0 exact.
- count_qual: exact / approx / at_least / at_most.
- arrival_time (attempt): HH:MM when they joined the line.
- line_position (attempt): their place as written ("4th" -> 4, "#6" -> 6). Count PEOPLE, not \
parties, unless the text explicitly counts parties or groups.
- outcome (attempt): got_rush / sro_only / full_price_only / sold_out_before_me / left / unknown.
- tickets (attempt): number of tickets bought, only if the comment gives it ("a single seat", "2 tickets").
- seat (attempt): seat description as written ("balcony", "orch J 9&11").
- window_time (attempt): HH:MM when they reached the box office window.
- stated_count (supply): number of rush tickets stated.
- stated_qual (supply): total (the day's whole rush allotment) / remaining (left at that time). \
If rush tickets were still available at a time but no number is given ("they had tickets for \
the matinee and evening"), record a supply observation with stated_qual remaining and \
no stated_count.
- sold_out_time (supply): HH:MM when rush ran out.
- sro_offered: yes / no. Only when the comment talks about standing room.
- late_release: true if tickets were released or offered later in the day ("come back later"); \
otherwise leave it out.
- cast_note: cast information relevant to demand ("Audra is out").

Fill only the fields that belong to the observation's kind (plus the shared ones) and leave \
everything else out. Times are always "HH:MM" strings.

## Output
Reply with only a JSON object, no other text. Include every comment_id you were given, in order, \
each with its observations list (empty for comments with nothing to record). Example:
{"comments": [
  {"comment_id": "abc123", "observations": []},
  {"comment_id": "def456", "observations": [
    {"kind": "attempt", "show_text": "Gypsy", "show": "Gypsy", "perf_date": "2025-07-03", "perf": "unknown",
     "rush_type": "general", "secondhand": false, "confidence": "high", "needs_context": false,
     "arrival_time": "09:25", "line_position": 6, "outcome": "unknown"},
    {"kind": "line_count", "show_text": "DBH", "show": "Death Becomes Her", "perf_date": "2025-07-03",
     "perf": "unknown", "rush_type": "general", "secondhand": false, "confidence": "high",
     "needs_context": false, "time": "09:20", "count": 12, "count_qual": "exact"}
  ]}
]}
"""

_S = {"type": "string"}
_I = {"type": "integer"}
_B = {"type": "boolean"}


def _enum(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


OBSERVATION_FIELDS = {
    "kind": {"type": "string", "enum": ["line_count", "attempt", "supply"]},
    "show_text": _S, "show": _S, "perf_date": _S,
    "perf": _enum("matinee", "evening", "unknown"),
    "rush_type": _enum("general", "digital", "student", "sro", "lottery", "other", "unknown"),
    "secondhand": _B,
    "confidence": _enum("high", "medium", "low"),
    "needs_context": _B,
    "time": _S, "count": _I,
    "count_qual": _enum("exact", "approx", "at_least", "at_most"),
    "arrival_time": _S, "line_position": _I,
    "outcome": _enum("got_rush", "sro_only", "full_price_only", "sold_out_before_me", "left", "unknown"),
    "tickets": _I, "seat": _S, "window_time": _S,
    "stated_count": _I, "stated_qual": _enum("total", "remaining"),
    "sold_out_time": _S, "sro_offered": _enum("yes", "no", "unknown"),
    "late_release": _B, "cast_note": _S,
}

SHARED_FIELDS = ["kind", "show_text", "show", "perf_date", "perf", "rush_type", "secondhand", "confidence",
                 "needs_context"]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "comment_id": {"type": "string"},
                    "observations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": OBSERVATION_FIELDS,
                            # shared fields always present (the API caps optional fields); kind-specific ones
                            # are optional and omitted when not stated
                            "required": SHARED_FIELDS,
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["comment_id", "observations"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["comments"],
    "additionalProperties": False,
}


def render_comments(rows: list[dict]) -> str:
    """User message: one <comment> block per comment, with the context the labeler sees."""
    parts = []
    for r in rows:
        parent = f"\n<parent>{r['parent_body']}</parent>" if r.get("parent_body") else ""
        parts.append(
            f'<comment id="{r["comment_id"]}" thread_date="{r["thread_date"]} ({r["weekday"]})" '
            f'posted="{r["comment_time"]}">{parent}\n<body>{r["body"]}</body>\n</comment>'
        )
    return "\n\n".join(parts)

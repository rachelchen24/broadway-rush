"""NYU academic calendar -> registry/college_calendars.csv and the model input `nyu_session` (SPEC 2.8 N11, C11).

Source: NYU's official academic calendar, pasted by Rachel on 2026-11-11 into data/raw/nyu/nyu_calendar_paste.txt
(nyu.edu blocks Anthropic's crawlers, so nothing was fetched).

`nyu_session` per day: 0 = break (students away), 1 = classes in session, 2 = finals (reading day through the last
exam day), 3 = free and in town.
Breaks: summer (very few students enrolled, Rachel 2026-11-11), winter recess and January (through the day before
spring classes), spring break and Thanksgiving, each with its weekends.
Free and in town (Rachel 2026-11-11: she rushes on one-day holidays and in the days before a term starts): one-day
holidays inside a term (Labor Day, Presidents' Day, MLK Day, the fall-break Monday) and the 3 days before the first
class of each fall and spring term. "Legislative" days are class days on another day's schedule: they stay classes.

    python -m broadway_rush.nyu_calendar          # rebuild the registry file from the paste
"""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PASTE = ROOT / "data" / "raw" / "nyu" / "nyu_calendar_paste.txt"
OUT = ROOT / "registry" / "college_calendars.csv"
SOURCE = "NYU academic calendar (official), pasted by Rachel 2026-11-11: data/raw/nyu/nyu_calendar_paste.txt"
CHECKED = "2026-11-11"
COVER = (date(2024, 6, 1), date(2027, 12, 21))  # what the paste supports end to end (through Fall 2027 finals)
NYU_FEATURES = ["nyu_session"]
CODES = {"break": 0, "classes": 1, "finals": 2, "free": 3}
FREE = "free, in town"
PRE_TERM_DAYS = 3
HOLIDAY_RE = r"^(Labor Day|Presidents.? Day|Martin Luther King.*|Fall Break)$"


def events() -> list[tuple[date, str]]:
    lines = PASTE.read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines[:-1]):
        m = re.match(r"^[A-Z][a-z]+day, ([A-Z][a-z]{2} \d{1,2}, \d{4})$", line.strip())
        if m:
            out.append((datetime.strptime(m.group(1), "%b %d, %Y").date(), lines[i + 1].strip()))
    return sorted(out)


def _sat_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() - 5) % 7 or 7) if d.weekday() != 5 else d


def _sun_after(d: date) -> date:
    return d + timedelta(days=(6 - d.weekday()) % 7)


def periods() -> pd.DataFrame:
    ev = events()

    def on(pattern):
        return [d for d, n in ev if re.search(pattern, n)]

    rows = []

    def add(term, event, start, end):
        rows.append({"school": "NYU", "term": term, "event": event, "start": start, "end": end,
                     "source": SOURCE, "date_checked": CHECKED})

    years = sorted({d.year for d, _ in ev})
    for y in years:
        for term in ("Spring", "Fall"):
            begin = on(rf"^{term} {y} Classes Begin$")
            last = on(rf"^Last Day of {term} {y} Classes$")
            if not last:
                continue
            exams = [d for d in on(r"^Final Exam Period$") if last[0] < d <= last[0] + timedelta(days=14)]
            if begin:
                add(f"{term} {y}", "classes", begin[0], last[0])
            if exams:
                add(f"{term} {y}", "finals", last[0] + timedelta(days=1), max(exams))
    # Breaks between terms come from the class and finals rows: after finals until the next term's first class
    t = pd.DataFrame(rows)
    terms = t[t.event == "classes"].sort_values("start")
    fin = t[t.event == "finals"].set_index("term").end
    for prev, nxt in zip(terms.itertuples(), terms.iloc[1:].itertuples()):
        after = fin.get(prev.term, prev.end) + timedelta(days=1)
        name = "summer (very few students enrolled)" if prev.term.startswith("Spring") else "winter recess and January"
        add(f"{prev.term} to {nxt.term}", name, after, nxt.start - timedelta(days=1))
    # The summer before the first term in the paste (Spring 2024 has no "Classes Begin": it's before March 2024)
    sp24 = fin.get("Spring 2024")
    if sp24 is not None:
        first_fall = terms[terms.term == "Fall 2024"].start.iloc[0]
        add("Spring 2024 to Fall 2024", "summer (very few students enrolled)", sp24 + timedelta(days=1),
            first_fall - timedelta(days=1))
    # Breaks inside a term (students leave), with their weekends: spring break Sat-Sun, Thanksgiving Thu-Sun
    for name, pattern in [("spring break", r"^Spring Break$"), ("Thanksgiving recess", r"^Thanksgiving Recess$")]:
        days = on(pattern)
        for chunk in _runs(days):
            start = _sat_before(chunk[0]) if name == "spring break" else chunk[0]
            add(f"{chunk[0].year}", name, start, _sun_after(chunk[-1]))
    # Free and in town (Rachel 2026-11-11): one-day holidays, and the days before each term's first class
    for d, n in ev:
        if re.search(HOLIDAY_RE, n):
            add(f"{d.year}", f"{FREE}: {n}", d, d)
    for r in terms.itertuples():
        add(r.term, f"{FREE}: {PRE_TERM_DAYS} days before classes begin", r.start - timedelta(days=PRE_TERM_DAYS),
            r.start - timedelta(days=1))
    df = pd.DataFrame(rows).drop_duplicates(["event", "start"])
    return df.sort_values(["start", "event"]).reset_index(drop=True)


def _runs(days: list[date]) -> list[list[date]]:
    out = []
    for d in sorted(days):
        if out and (d - out[-1][-1]).days <= 3:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def session_by_day(dates: pd.Series) -> pd.Series:
    """nyu_session for each date (NaN outside the calendar's coverage). Free beats breaks beats finals beats classes."""
    p = pd.read_csv(OUT, parse_dates=["start", "end"])
    d = pd.to_datetime(dates)
    out = pd.Series(np.nan, index=dates.index)
    inside = (d >= pd.Timestamp(COVER[0])) & (d <= pd.Timestamp(COVER[1]))
    out[inside] = CODES["break"]  # a day no period covers (e.g. between finals and commencement) is a break
    for kind in ("classes", "finals"):
        for r in p[p.event == kind].itertuples():
            out[(d >= r.start) & (d <= r.end) & inside] = CODES[kind]
    free = p.event.str.startswith(FREE)
    for r in p[~p.event.isin(["classes", "finals"]) & ~free].itertuples():
        out[(d >= r.start) & (d <= r.end) & inside] = CODES["break"]
    for r in p[free].itertuples():
        out[(d >= r.start) & (d <= r.end) & inside] = CODES["free"]
    return out


def main():
    df = periods()
    df.to_csv(OUT, index=False)
    days = pd.Series(pd.date_range(*COVER))
    s = session_by_day(days)
    print(f"wrote {OUT.name}: {len(df)} periods; days {COVER[0]}..{COVER[1]}: "
          + ", ".join(f"{k} {int((s == v).sum())}" for k, v in CODES.items()))


if __name__ == "__main__":
    main()

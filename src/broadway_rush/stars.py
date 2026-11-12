"""High-profile stars, steps 1-2 (SPEC 2.2a, 2.8 N5): current principals of every running show, their Wikipedia page
views, and the 20,000 cutoff. Writes registry/stars.csv for Rachel to review. The site doesn't use it until she has.

    .venv\\Scripts\\python -u -m broadway_rush.stars

Cast: Playbill production pages already cached on 2026-11-06 (data/raw/playbill/show_pages/, no new requests). The
first cast list on each page is the current cast, the second the opening cast. A script keeps only names and roles;
pages are never sent to an AI model. Playbill cast facts are for the site only (Rachel, 2026-11-11): the model's
star inputs come from Wikipedia show articles, BroadwayWorld casting news and official show sites (C2, later).
"""

import json
import logging
import re
import statistics
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from broadway_rush.scrapers import wikimedia

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "data" / "raw" / "playbill" / "show_pages"
OUT = ROOT / "registry" / "stars.csv"
CUTOFF = 20_000  # Rachel, 2026-11-11
NEAR = 0.15  # flag anyone within 15% of the cutoff
NOT_PRINCIPAL = re.compile(r"ensemble|swing|understudy|standby|stand-by|alternate|dance captain|u/s", re.I)
LAST_FULL_MONTH = "2026-10"
TODAY = date.today().isoformat()

log = logging.getLogger("stars")


def cast_lists(path: Path) -> tuple[list, list]:
    """(current cast, opening cast) as [(person, [roles])]. Roles keep Playbill's (Original)/(Replacement)."""
    s = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    lists = []
    for g in s.find_all("div", class_="gallery-module"):
        people = []
        for li in g.find_all("li"):
            parts = [x.get_text(" ", strip=True) for x in li.find_all("div", recursive=False)]
            parts = [p for p in parts if p]
            if len(parts) >= 2 and re.search(r"\((Original|Replacement)\)", " ".join(parts[1:])):
                people.append((parts[0], parts[1:]))
        if people:
            lists.append(people)
    current = lists[0] if lists else []
    opening = lists[1] if len(lists) > 1 else []
    return current, opening


def months(start: str, end: str) -> list[str]:
    p = pd.period_range(start, end, freq="M")
    return [str(x) for x in p]


def median_views(views: dict, start: str, end: str):
    vals = [views[m] for m in months(start, end) if m in views]
    return (round(statistics.median(vals)), len(vals)) if vals else (None, 0)


def true_first_weeks(shows: pd.DataFrame) -> dict:
    """show_id -> the production's first grosses week (its first previews), from all the grosses we have (2014 on).
    shows.csv's first_week starts at June 2024, which is wrong for shows already running then. A show already
    running in the first week of 2014 gets no date: it opened before page views began anyway."""
    frames = [pd.read_csv(ROOT / "data" / "raw" / "grosses_playbill.csv")]
    hist = ROOT / "data" / "raw" / "grosses_history_playbill.csv"
    if hist.exists():
        frames.append(pd.read_csv(hist))
    g = pd.concat(frames)
    first = g.groupby("production_id").week_ending.min()
    by_prod = shows.drop_duplicates("production_id").set_index("show_id").production_id
    start = g.week_ending.min()
    out = {}
    for sid, prod in by_prod.items():
        w = first.get(prod)
        if isinstance(w, str) and w > start:
            out[sid] = w
    return out


def window_for(status: str, first_week: str | None) -> tuple[str, str, str]:
    """The rule (SPEC 2.2a): 12 months before casting was announced; unknown, so 12 months ending 3 months before the
    first performance. For an original cast member that's the show's first preview. A replacement's first
    performance isn't known until cast news is read (C2), so the last 12 months stand in, flagged as provisional."""
    if status == "original" and first_week:
        first = pd.Period(first_week, freq="M")
        if first - 15 >= pd.Period("2015-07", freq="M"):
            return str(first - 14), str(first - 3), "12 months ending 3 months before the show's first preview (original cast)"
    last = pd.Period(LAST_FULL_MONTH, freq="M")
    if status == "replacement":
        rule = "last 12 months: join date unknown, so this includes time in the show; provisional"
    else:
        rule = "last 12 months: show opened before page views began (July 2015) or its first week isn't known; provisional"
    return str(last - 11), LAST_FULL_MONTH, rule


def rescore():
    """Re-apply the window rule and cutoff to registry/stars.csv from cached views (no requests). Keeps Rachel's
    override and reason columns and every review note."""
    shows = pd.read_csv(ROOT / "data" / "processed" / "shows.csv")
    fw = true_first_weeks(shows)
    df = pd.read_csv(OUT, dtype=str, keep_default_na=False)
    for i, r in df.iterrows():
        w_start, w_end, rule = window_for(r.cast_status, fw.get(r.show_id))
        df.loc[i, ["window_start", "window_end", "window_rule"]] = [w_start, w_end, rule]
        if not r.wiki_title:
            continue
        path = wikimedia.CACHE / "monthly" / f"{wikimedia.safe(r.wiki_title)}.json"
        v = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        med, _ = median_views(v, w_start, w_end)
        not_counted = "not counted" in r.review_note
        df.loc[i, "views_median"] = "" if med is None else str(med)
        df.loc[i, "star"] = "yes" if med is not None and med >= CUTOFF and not not_counted else "no"
        df.loc[i, "near_cutoff"] = "yes" if med is not None and abs(med - CUTOFF) <= NEAR * CUTOFF and not not_counted else ""
    df["_v"] = pd.to_numeric(df.views_median, errors="coerce")
    df = df.sort_values(["_v", "person"], ascending=[False, True], na_position="last").drop(columns="_v")
    df.to_csv(OUT, index=False)
    log.info("rescored %s: %d stars, %d near the line", OUT.name, (df.star == "yes").sum(), (df.near_cutoff == "yes").sum())


def main():
    if "--rescore" in sys.argv:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
        rescore()
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout)])
    shows = pd.read_csv(ROOT / "data" / "processed" / "shows.csv")
    running = shows[shows.last_week == shows.last_week.max()]
    rows = []
    for s in running.itertuples():
        path = PAGES / f"{s.show_id}.html"
        if not path.exists():
            log.info("no cached page: %s", s.show_id)
            continue
        current, opening = cast_lists(path)
        opening_names = {p for p, _ in opening}
        for person, roles in current:
            principal = [r for r in roles if not NOT_PRINCIPAL.search(r)]
            if not principal:
                continue
            original = any("(Original)" in r for r in roles)
            rows.append({"show_id": s.show_id, "show": s.name, "person": person,
                         "role": "; ".join(re.sub(r"\s*\((Original|Replacement)\)", "", r) for r in principal),
                         "status": "original" if original or person in opening_names else "replacement",
                         "first_week": s.first_week})
    cast = pd.DataFrame(rows)
    log.info("%d current principals in %d shows", len(cast), cast.show_id.nunique())
    first_weeks = true_first_weeks(shows)

    client = wikimedia.Client()
    names = sorted(cast.person.unique())
    found = wikimedia.resolve(client, names)
    # Second try for missing, disambiguation or non-performer pages: the usual qualifiers
    retry = [n for n, f in found.items() if not f["title"] or f["disambiguation"]
             or not wikimedia.PERFORMER_RE.search(f["description"] or "")]
    variants = [f"{n} ({q})" for n in retry for q in ("actor", "actress", "singer", "entertainer", "performer")]
    alt = wikimedia.resolve(client, variants) if variants else {}
    match = {}
    for n in names:
        f = found[n]
        ok = (f["title"] and not f["disambiguation"] and wikimedia.PERFORMER_RE.search(f["description"] or "")
              and not wikimedia.NOT_A_PERSON_RE.search(f["description"] or ""))
        if ok:
            match[n] = (f["title"], f["description"], "")
            continue
        hit = next((alt[v] for v in [f"{n} ({q})" for q in ("actor", "actress", "singer", "entertainer", "performer")]
                    if alt.get(v, {}).get("title") and not alt[v]["disambiguation"]), None)
        if hit:
            match[n] = (hit["title"], hit["description"], "matched with a qualifier: check it's the right person")
        elif f["title"] and not f["disambiguation"]:
            match[n] = (f["title"], f["description"], "page found but its description doesn't say performer: check it")
        else:
            match[n] = ("", "", "no Wikipedia page found" if not f["title"] else "only a disambiguation page")
    log.info("titles: %d of %d people have a page", sum(bool(m[0]) for m in match.values()), len(names))

    views = {}
    for i, (n, (title, _, _)) in enumerate(sorted(match.items())):
        if title and title not in views:
            views[title] = wikimedia.monthly_views(client, title)
        if i % 25 == 0:
            log.info("views %d/%d (requests %d, refused %d)", i, len(match), client.n, client.refused)

    out = []
    for r in cast.itertuples():
        title, desc, note = match[r.person]
        v = views.get(title, {}) if title else {}
        notes = [note] if note else []
        w_start, w_end, rule = window_for(r.status, first_weeks.get(r.show_id))
        med, n_months = median_views(v, w_start, w_end) if title else (None, 0)
        alt23, _ = median_views(v, "2023-01", "2026-10") if title else (None, 0)
        last12, _ = median_views(v, str(pd.Period(LAST_FULL_MONTH, freq="M") - 11), LAST_FULL_MONTH) if title else (None, 0)
        if title and n_months < 6:
            notes.append(f"only {n_months} months of views in the window")
        # A page whose description doesn't say performer is probably someone else with the same name (the King of
        # Spain for Juan Carlos): never a star by the rule, only flagged for Rachel.
        maybe_wrong = note.startswith("page found but")
        star = bool(med is not None and med >= CUTOFF and not maybe_wrong)
        near = bool(med is not None and abs(med - CUTOFF) <= NEAR * CUTOFF and not maybe_wrong)
        if maybe_wrong:
            notes[0] = "probably a different person with the same name: not counted; " + notes[0]
        out.append({
            "show_id": r.show_id, "show": r.show, "person": r.person, "role": r.role, "cast_status": r.status,
            "wiki_title": title, "wiki_description": desc,
            "casting_announced": "", "first_performance": "", "last_performance": "", "last_announced": "",
            "views_median": med, "window_start": w_start, "window_end": w_end, "window_rule": rule,
            "views_last12": last12, "views_2023_2026": alt23,
            "star": "yes" if star else "no", "near_cutoff": "yes" if near else "", "override": "", "reason": "",
            "review_note": "; ".join(notes),
            "source": "Playbill current cast list (cached 2026-11-06); Wikimedia page views",
            "date_checked": TODAY,
        })
    df = pd.DataFrame(out).sort_values(["views_median", "person"], ascending=[False, True], na_position="last")
    df.to_csv(OUT, index=False)
    log.info("wrote %s: %d rows, %d stars at %d, %d near the line; %d requests, %d refused", OUT.name, len(df),
             (df.star == "yes").sum(), CUTOFF, (df.near_cutoff == "yes").sum(), client.n, client.refused)


if __name__ == "__main__":
    main()

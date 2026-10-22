"""Show catalog (SPEC §3.0): one row per Broadway production, plus mapping of free-text show names onto it.

    py -m broadway_rush.catalog build   # -> data/processed/shows.csv, show_names.csv; adds show_id to reports.csv
    py -m broadway_rush.catalog review  # top unmatched / ambiguous Reddit names, for the hand alias list

Inputs: weekly grosses (Playbill + BroadwayWorld), Playbill policies, Reddit reports, and two hand-curated files:
    registry/show_aliases.csv     alias,show_id    nicknames ("mincemeat", "mhe"); show_id "-" = known non-Broadway
    registry/show_overrides.csv   show_id,field,value   fixes (e.g. show_type for shows BroadwayWorld leaves blank)
"""

import argparse
import difflib
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REGISTRY = ROOT / "registry"
SHOWS_CSV = PROCESSED / "shows.csv"
NAMES_CSV = PROCESSED / "show_names.csv"
REPORTS_CSV = PROCESSED / "reports.csv"
ALIASES_CSV = REGISTRY / "show_aliases.csv"
OVERRIDES_CSV = REGISTRY / "show_overrides.csv"

NOT_BROADWAY = "-"  # alias target for shows we know aren't on Broadway (Off-Broadway, tours, West End)
FUZZY_CUTOFF = 0.88  # difflib ratio for typo matches ("Sterophonic")
DROP_WORDS = r"\b(the musical|a new musical|musical|on broadway|broadway|the play|a play)\b"


def norm(name) -> str:
    """'The Outsiders' / 'OUTSIDERS' / 'Oh, Mary!' -> 'outsiders' / 'outsiders' / 'oh mary'."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("'", "").replace("&", " and ").replace("+", " and ")
    s = re.sub(DROP_WORDS, " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"^\s*the\s+|\s+the\s*$", " ", s)
    return " ".join(s.split())


def slugify(name: str) -> str:
    return norm(name).replace(" ", "-") or "show"


# --- shows -------------------------------------------------------------------------------------

def build_shows() -> pd.DataFrame:
    pb = pd.read_csv(RAW / "grosses_playbill.csv")
    bw = pd.read_csv(RAW / "grosses_bww.csv")
    # Playbill and BroadwayWorld republish the same League numbers, so week + gross is an exact join key
    m = pb.merge(bw[["week_ending", "gross", "show_slug", "show_type"]], on=["week_ending", "gross"], how="left")
    g = m.sort_values("week_ending").groupby("production_id")
    shows = pd.DataFrame({
        "name": g.show.last(),
        "theater": g.theater.last(),
        "first_week": g.week_ending.min(),
        "last_week": g.week_ending.max(),
        "n_weeks": g.week_ending.nunique(),
        "seats": g.seats_in_theatre.max(),
        "show_type": g.show_type.agg(lambda s: s.dropna().mode().iat[0] if s.notna().any() else ""),
        "bww_slugs": g.show_slug.agg(lambda s: ";".join(sorted(set(s.dropna())))),
    }).reset_index()
    # readable unique id: name slug, plus the opening year when two productions share a name
    shows["show_id"] = shows.name.map(slugify)
    dup = shows.show_id.duplicated(keep=False)
    shows.loc[dup, "show_id"] += "-" + shows.loc[dup, "first_week"].str[:4]
    if OVERRIDES_CSV.exists():
        for o in pd.read_csv(OVERRIDES_CSV).itertuples():
            shows.loc[shows.show_id == o.show_id, o.field] = o.value
    cols = ["show_id", "name", "theater", "show_type", "first_week", "last_week", "n_weeks", "seats",
            "production_id", "bww_slugs"]
    return shows[cols].sort_values("first_week").reset_index(drop=True)


# --- name matching -----------------------------------------------------------------------------

def name_keys(shows: pd.DataFrame) -> dict[str, set[str]]:
    """normalized name -> show_ids. Uses each show's name, the part before a colon ('Six: The Musical' -> 'six'),
    BroadwayWorld slugs, and the hand alias list."""
    keys: dict[str, set[str]] = {}

    def add(key, sid):
        if key:
            keys.setdefault(key, set()).add(sid)

    for s in shows.itertuples():
        add(norm(s.name), s.show_id)
        add(norm(s.name.split(":")[0]), s.show_id)
        add(norm(re.sub(r"\(.*?\)", " ", s.name)), s.show_id)
        for slug in str(s.bww_slugs).split(";"):
            add(norm(slug.replace("-", " ")), s.show_id)
    if ALIASES_CSV.exists():
        for a in pd.read_csv(ALIASES_CSV).itertuples():
            add(norm(a.alias), a.show_id)
    return keys


def lookup(name, keys) -> tuple[set[str], str]:
    """Candidate show_ids for a free-text name: exact normalized name, then without (parentheses), then a close
    spelling ('Sterophonic', 'Shmigadoon') if exactly one key is that close."""
    key = norm(name)
    if not key:
        return set(), "unmatched"
    if key in keys:
        return keys[key], "name"
    bare = norm(re.sub(r"\(.*?\)", " ", name))
    if bare in keys:
        return keys[bare], "name"
    close = difflib.get_close_matches(key, keys, n=2, cutoff=FUZZY_CUTOFF)
    if len(close) == 1 or len(close) == 2 and keys[close[0]] == keys[close[1]]:
        return keys[close[0]], "fuzzy"
    return set(), "unmatched"


def match(name, when, keys, shows_by_id, last_scraped) -> tuple[str, str]:
    """Return (show_id or '', how). A show only matches if it was on Broadway at `when` (its first through
    last grosses week, plus a week's grace; shows still running at the last scrape count as open-ended). That
    also picks between same-name productions and rejects Off-Broadway runs of shows that later transferred."""
    cands, how = lookup(name, keys)
    if not cands:
        return "", how
    if cands == {NOT_BROADWAY}:
        return NOT_BROADWAY, "not_broadway"
    cands -= {NOT_BROADWAY}
    if not (isinstance(when, str) and re.match(r"\d{4}-\d{2}-\d{2}", when)):
        return (next(iter(cands)), how) if len(cands) == 1 else ("", "ambiguous:" + ";".join(sorted(cands)))
    week = _week_end(when)

    def running(c):
        s = shows_by_id[c]
        end = "9999-12-31" if s.last_week == last_scraped else _add_days(s.last_week, 7)
        return s.first_week <= week <= end

    on = [c for c in cands if running(c)]
    if len(on) == 1:
        return on[0], how + ("+date" if len(cands) > 1 else "")
    if not on:
        return "", "outside_run:" + ";".join(sorted(cands))
    return "", "ambiguous:" + ";".join(sorted(on))


def _week_end(day: str) -> str:
    """Grosses weeks end on Sunday; return the Sunday on or after `day`."""
    d = pd.Timestamp(day[:10])
    return (d + pd.Timedelta(days=(6 - d.weekday()) % 7)).date().isoformat()


def _add_days(day: str, n: int) -> str:
    return (pd.Timestamp(day) + pd.Timedelta(days=n)).date().isoformat()


def build():
    shows = build_shows()
    shows.to_csv(SHOWS_CSV, index=False)
    keys = name_keys(shows)
    by_id = {s.show_id: s for s in shows.itertuples()}
    last = shows.last_week.max()

    r = pd.read_csv(REPORTS_CSV, low_memory=False)
    # thread date for daily threads, else the comment's own date (perf_date is LLM output, so less trusted)
    when = r.thread_date.fillna(r.created_et.str[:10]).astype(str)
    res = [match(n, w, keys, by_id, last) for n, w in zip(r.show, when)]
    r["show_id"] = [sid for sid, _ in res]
    r["show_match"] = [how if isinstance(n, str) else "" for (_, how), n in zip(res, r.show)]
    r.to_csv(REPORTS_CSV, index=False)

    names = (r[r.show.notna()].groupby("show")
             .agg(reports=("show", "size"), show_id=("show_id", lambda s: s.mode().iat[0]),
                  how=("show_match", lambda s: s.mode().iat[0]))
             .sort_values("reports", ascending=False).reset_index())
    names.to_csv(NAMES_CSV, index=False)

    has = r.show.notna()
    print(f"shows.csv: {len(shows)} productions ({(shows.show_type == '').sum()} without a type)")
    print(f"reports with a show name: {has.sum():,}")
    print(r.loc[has, "show_match"].str.split(":").str[0].value_counts().to_string())
    matched = r.show_id.ne("") & r.show_id.ne(NOT_BROADWAY)
    print(f"-> {matched.sum():,} reports ({matched[has].mean():.1%} of named) mapped to {r.loc[matched, 'show_id'].nunique()} shows")

    pol = pd.read_csv(RAW / "policies_playbill.csv")
    pol_ids = {n: match(n, d, keys, by_id, last)[0] for n, d in zip(pol.show, pol.snapshot_date)}
    missing = sorted(n for n, sid in pol_ids.items() if not sid)
    print(f"policy shows matched: {sum(bool(v) for v in pol_ids.values())}/{len(pol_ids)}" +
          (f"; unmatched: {missing}" if missing else ""))


def review(n: int):
    names = pd.read_csv(NAMES_CSV, keep_default_na=False)
    todo = names[~names.how.isin(["name", "name+date", "not_broadway"])]
    print(f"{len(todo)} names ({todo.reports.sum():,} reports) to check (fuzzy/unmatched/ambiguous/outside run); top {n}:")
    print(todo.head(n).to_string(index=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "review"])
    ap.add_argument("-n", type=int, default=60)
    args = ap.parse_args()
    build() if args.cmd == "build" else review(args.n)


if __name__ == "__main__":
    main()

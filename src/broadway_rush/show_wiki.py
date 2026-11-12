"""Show buzz data (SPEC 2.8 N7, C8): each show's English Wikipedia page title, then its daily page views.

    .venv\\Scripts\\python -u -m broadway_rush.show_wiki

Titles go in registry/show_wiki_titles.csv (filled by Claude, checked by Rachel), not in data/processed/shows.csv as
the spec first said, because `catalog build` rewrites shows.csv and would drop a hand-checked column. Rows Rachel
has marked `checked = yes` are never changed. Daily views are cached in data/raw/wikimedia/daily/.
"""

import logging
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from broadway_rush.scrapers import wikimedia

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "registry" / "show_wiki_titles.csv"
STAGE_RE = re.compile(r"musical|play|broadway|stage|theat|revue|opera|comedy|drama|concert|show|solo", re.I)
FIRST_DAY, LAST_DAY = "20240401", "20261110"

log = logging.getLogger("show_wiki")


def string_title(s: str) -> str:
    """'SIX' -> 'Six', 'THE OUTSIDERS' -> 'The Outsiders', keeping short words lower case after the first."""
    small = {"a", "an", "and", "the", "of", "in", "on", "at", "to", "for", "or"}
    words = s.lower().split()
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout)])
    shows = pd.read_csv(ROOT / "data" / "processed" / "shows.csv")
    old = pd.read_csv(OUT, dtype=str, keep_default_na=False) if OUT.exists() else pd.DataFrame(columns=["show_id"])
    checked = set(old[old.get("checked", pd.Series(dtype=str)).eq("yes")].show_id) if len(old) else set()
    client = wikimedia.Client()
    names = {s.show_id: s.name for s in shows.itertuples() if s.show_id not in checked}
    tries = {}
    for sid, name in names.items():
        bases = []
        for b in (re.sub(r"\s*\(.*?\)\s*", " ", name).strip(), name.split(":")[0].strip()):
            for v in (b, b.title(), string_title(b)):
                if v and v not in bases:
                    bases.append(v)
        tries[sid] = [f"{b} ({kind})" for b in bases for kind in ("musical", "play", "Broadway production", "show")]
        tries[sid] += bases + [name]
    flat = sorted({t for v in tries.values() for t in v})
    found = wikimedia.resolve(client, flat)
    rows = []
    for sid, cands in tries.items():
        pick, note = "", "no page found"
        for t in cands:
            f = found.get(t, {})
            if f.get("title") and not f.get("disambiguation"):
                if STAGE_RE.search(f.get("description") or "") or "(musical)" in t or "(play)" in t:
                    pick, note = f["title"], f"from '{t}': {f.get('description') or 'no description'}"
                    break
                if note == "no page found":
                    # Never use a page that isn't about a stage work ("860" is a year, "Home" a residence): leave blank
                    note = f"no stage-work page; nearest was '{f['title']}' ({f.get('description')}): left blank"
        rows.append({"show_id": sid, "show": names[sid], "wiki_title": pick, "note": note, "checked": "",
                     "date_filled": date.today().isoformat()})
    new = pd.DataFrame(rows)
    keep = old[old.show_id.isin(checked)] if len(old) else old
    table = pd.concat([keep, new], ignore_index=True).sort_values("show_id")
    table.to_csv(OUT, index=False)
    log.info("titles: %d of %d shows have a page", (table.wiki_title != "").sum(), len(table))
    for i, t in enumerate(table.wiki_title[table.wiki_title != ""]):
        wikimedia.daily_views(client, t, FIRST_DAY, LAST_DAY)
        if i % 20 == 0:
            log.info("daily views %d (requests %d, refused %d)", i, client.n, client.refused)
    log.info("done: %d requests, %d refused", client.n, client.refused)


if __name__ == "__main__":
    main()

"""Site-only facts added to each show in the predictions file (SPEC 2.8 N4, N8, N10). No model numbers change.

    .venv\\Scripts\\python -m broadway_rush.model.site_extras          # patch web/data/predictions.json in place
    .venv\\Scripts\\python -m broadway_rush.model.site_extras --check  # only list offers left without a link

`predict.py` calls `extras()` for every show, so a fresh run has them too. The patch command exists so a registry
edit (a dated deal, how rush is sold on 2-show days) reaches the site without refitting the model.

Sources, all hand-kept and reviewed by Rachel:
- registry/special_deals.csv: dated deals (N10). Standing deals come from Playbill's policy list (`policy.other`).
- registry/show_facts.csv: `two_show_rush` (both at opening / separately / unknown) and `two_show_rush_note` (N8),
  `lottery_url` and `lottery_url_source` (N4's last resort, only when the policy list has no address).
- Show images (Rachel 2026-11-19): the show's own event image from the newest Ticketmaster Discovery API snapshot,
  linked from Ticketmaster's servers, never copied or stored (API terms: display event content in the app; don't
  use Ticketmaster as an image host or store content longer than needed). Credited in the site footer. Generic
  Ticketmaster placeholders (`fallback`) are skipped, so shows without their own image just show no picture.
"""

import argparse
import json
import re

import pandas as pd

from broadway_rush.model.table import ROOT

PRED = ROOT / "web" / "data" / "predictions.json"
DEALS = ROOT / "registry" / "special_deals.csv"
FACTS = ROOT / "registry" / "show_facts.csv"
DEAL_COLUMNS = ["show_id", "name", "detail", "price", "start", "end", "url", "source", "date_checked", "note"]
TWO_SHOW_VALUES = {"both at opening", "separately", "unknown"}
STARS = ROOT / "registry" / "stars.csv"
# Rachel reviewed the ranked list and marked overrides (SPEC 2.8 N5 step 2); she said go on 2026-11-11.
STARS_REVIEWED = True
# Same rule as cleanUrl in web/app.js: the first web address in the text, or nothing. Never a guess.
URL_RE = re.compile(r"((?:https?://)?(?:[a-z0-9-]+\.)+(?:com|org|net|nyc|co|us|io|info|show|theater|theatre)"
                    r"(?:/[^\s,;\"'()<>]*)?)", re.I)


def first_url(text) -> str | None:
    if not isinstance(text, str) or not text:
        return None
    m = URL_RE.search(text)
    if not m:
        return None
    u = m.group(1).rstrip(".,;:!?")
    return u if u.lower().startswith(("http://", "https://")) else "https://" + u


def load_deals() -> dict:
    if not DEALS.exists():
        return {}
    d = pd.read_csv(DEALS, dtype=str, keep_default_na=False)
    out = {}
    for r in d.itertuples():
        out.setdefault(r.show_id, []).append({
            "name": r.name, "detail": r.detail or None, "price": float(r.price) if r.price else None,
            "start": r.start or None, "end": r.end or None, "url": r.url or None,
        })
    return out


def load_facts() -> dict:
    if not FACTS.exists():
        return {}
    f = pd.read_csv(FACTS, dtype=str, keep_default_na=False)
    return {r["show_id"]: r for _, r in f.iterrows()}


def load_stars() -> dict:
    """show_id -> current high-profile stars for the site, after Rachel's review. `override` (yes/no) beats the rule."""
    if not (STARS_REVIEWED and STARS.exists()):
        return {}
    s = pd.read_csv(STARS, dtype=str, keep_default_na=False)
    final = s.override.str.lower().where(s.override.str.lower().isin(["yes", "no"]), s.star.str.lower())
    s = s[final == "yes"]
    out = {}
    for r in s.itertuples():
        out.setdefault(r.show_id, []).append({"name": r.person, "role": r.role or None, "joined": r.first_performance or None,
                                              "last_performance": r.last_performance or None})
    return out


def load_images() -> dict:
    """show_id -> image URL from the newest Ticketmaster snapshot. Venue is the key, as in predict.map_schedule."""
    from broadway_rush.scrapers.playbill import cached_files, read_cached
    from broadway_rush.scrapers.ticketmaster import CACHE, SHOWS_CSV, venue_key
    files = cached_files(CACHE, "*.json*")
    if not files:
        return {}
    shows = pd.read_csv(SHOWS_CSV)
    running = shows[shows.last_week == shows.last_week.max()]
    by_venue = {venue_key(r.theater): r.show_id for r in running.itertuples() if isinstance(r.theater, str)}
    out = {}
    for e in json.loads(read_cached(files[-1])):
        v = ((e.get("_embedded") or {}).get("venues") or [{}])[0]
        sid = by_venue.get(venue_key(v.get("name", "")))
        if not sid or sid in out:
            continue
        imgs = [i for i in e.get("images") or [] if not i.get("fallback") and i.get("url")]
        # A wide picture for the tile: 3:2 or 16:9, the smallest one at least 600 px wide (light on phones)
        wide = sorted((i for i in imgs if i.get("ratio") in ("3_2", "16_9") and (i.get("width") or 0) >= 600),
                      key=lambda i: (i.get("ratio") != "3_2", i.get("width") or 0))
        if wide:
            out[sid] = wide[0]["url"]
    return out


class Extras:
    def __init__(self):
        self.images = load_images()
        self.deals = load_deals()
        self.facts = load_facts()
        self.stars = load_stars()

    def __call__(self, show_id: str) -> dict:
        f = self.facts.get(show_id)
        get = (lambda k: (f.get(k) or "").strip()) if f is not None else (lambda k: "")
        how = get("two_show_rush") or "unknown"
        if how not in TWO_SHOW_VALUES:
            how = "unknown"
        return {
            "special_deals": self.deals.get(show_id, []),
            "two_show_rush": how,
            "two_show_rush_note": get("two_show_rush_note") or None,
            "lottery_url": get("lottery_url") or None,
            "stars": self.stars.get(show_id, []),
            "image": self.images.get(show_id),
        }


def link_check(days: dict) -> list[str]:
    """Lotteries and online rushes with no address to link (SPEC 2.8 N4). Run after every policy update."""
    missing = {}
    for entries in days.values():
        for e in entries:
            p = e.get("policy") or {}
            for kind, x in (("lottery", p.get("lottery")), ("online rush", p.get("digital"))):
                if not x:
                    continue
                saved = e.get("lottery_url") if kind == "lottery" else None
                if not (first_url(x.get("where")) or first_url(x.get("how")) or first_url(saved)):
                    app = re.search(r"\bthe\s+([A-Z][A-Za-z0-9]+)\s+[Aa]pp\b", f"{x.get('how')} {x.get('where')} {x.get('time')}")
                    missing[(e["show_id"], kind)] = "app mention only" if app else "no link"
    return [f"{sid}: {kind} has {what}" for (sid, kind), what in sorted(missing.items())]


LEDGER = ROOT / "data" / "interim" / "llm_spend.csv"
# Ledger run prefix -> what the money was for (Nerd stats, "What it cost")
SPEND_GROUPS = [("batch_checked", "Double-checking every report"), ("batch", "Reading Reddit comments into reports"),
                ("pilot", "Small tests before each big run"), ("star_history", "Reading casting news for star runs")]


def ai_spend() -> dict | None:
    """Total AI spend from the ledger, by purpose. Every call is logged by the code that made it."""
    if not LEDGER.exists():
        return None
    led = pd.read_csv(LEDGER)
    groups = []
    for prefix, label in SPEND_GROUPS:
        m = led.run.astype(str).str.startswith(prefix) & ~led.index.isin([i for g in groups for i in g[2]])
        groups.append((label, float(led.usd[m].sum()), list(led.index[m])))
    other = float(led.usd.sum()) - sum(g[1] for g in groups)
    items = [{"label": g[0], "usd": round(g[1], 2)} for g in groups if g[1] > 0]
    if other > 0.005:
        items.append({"label": "Other", "usd": round(other, 2)})
    return {"total_usd": round(float(led.usd.sum()), 2), "calls": int(len(led)), "items": items,
            "through": str(pd.to_datetime(led["at"].max()).date()), "cap_usd": 8.0}


def patch(path=PRED):
    data = json.loads(path.read_text(encoding="utf-8"))
    ex = Extras()
    for entries in data["days"].values():
        for e in entries:
            e.update(ex(e["show_id"]))
    data["has_stars"] = bool(ex.stars)
    data["ai_spend"] = ai_spend()
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="only list offers without a link; change nothing")
    a = ap.parse_args()
    data = json.loads(PRED.read_text(encoding="utf-8")) if a.check else patch()
    gaps = link_check(data["days"])
    print("offers without a link:", len(gaps))
    for g in gaps:
        print("  ", g)


if __name__ == "__main__":
    main()

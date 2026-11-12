"""Site-only facts added to each show in the predictions file (SPEC 2.8 N4, N8, N10). No model numbers change.

    .venv\\Scripts\\python -m broadway_rush.model.site_extras          # patch web/data/predictions.json in place
    .venv\\Scripts\\python -m broadway_rush.model.site_extras --check  # only list offers left without a link

`predict.py` calls `extras()` for every show, so a fresh run has them too. The patch command exists so a registry
edit (a dated deal, how rush is sold on 2-show days) reaches the site without refitting the model.

Sources, all hand-kept and reviewed by Rachel:
- registry/special_deals.csv: dated deals (N10). Standing deals come from Playbill's policy list (`policy.other`).
- registry/show_facts.csv: `two_show_rush` (both at opening / separately / unknown) and `two_show_rush_note` (N8),
  `lottery_url` and `lottery_url_source` (N4's last resort, only when the policy list has no address).
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


class Extras:
    def __init__(self):
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


def patch(path=PRED):
    data = json.loads(path.read_text(encoding="utf-8"))
    ex = Extras()
    for entries in data["days"].values():
        for e in entries:
            e.update(ex(e["show_id"]))
    data["has_stars"] = bool(ex.stars)
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

"""Fixed predictions file (SPEC 5.2a step 5): the only thing the website reads.

    .venv\\Scripts\\python -m broadway_rush.model.predict --per-person 1.4 --backtest pp1.4

Trains the combo on every labeled day, then predicts each show-day on the Ticketmaster schedule. Writes
web/data/predictions.json. The verdict and ranking use the chance if you arrive at 9:00 (SPEC 9, question 16), and
every threshold here is a placeholder until Rachel picks real ones.
"""

import argparse
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from broadway_rush.catalog import norm
from broadway_rush.model import cutoff as cutoff_model
from broadway_rush.model import join
from broadway_rush.model import line as line_model
from broadway_rush.model.backtest import GO, GRID, LOCKED, MAYBE
from broadway_rush.model.table import (
    CUTOFF_FEATURES, FALLBACK_OPENING, LINE_FEATURES, PROCESSED, RAW, ROOT, Features, clean_text, load_policies,
    load_tables, opening_lookup, tickets_bounds,
)
from broadway_rush.scrapers.ticketmaster import DAYS_AHEAD, venue_key

OUT = ROOT / "web" / "data" / "predictions.json"
TARGET_CHANCE = 0.80  # placeholder: the arrival time is the latest time that still reaches this
LEVELS = list(range(50, 100, 5))
# "Enough data" for a full prediction (SPEC 8, Rachel 2026-11-06): either of these.
MIN_REPORTS_PER_WEEK = 2.0  # daily-thread reports per running week
MIN_LINE_REPORTS = 35  # line reports in the model table. In the tests, 10-34 lost to the lookup table; 35+ beat it
RECENT_DAYS = 30
RECENT_ROWS = 3
THIN_LINE_POINTS = 35  # fewer line points than this gets the Low confidence badge
THIN_CUTOFF_DAYS = 5
DAY_CODES = ["M", "T", "W", "Th", "F", "S", "Su"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# On Ticketmaster, but with no rush policy, no grosses and no reports, so skipped for now (SPEC 2.7)
SCHEDULE_ALIASES = {"billy crystal": "860", "billy crystal 860": "860"}


def clock(hour: float) -> str:
    h = int(hour)
    return f"{h:02d}:{int(round((hour - h) * 60)):02d}"


def load_schedule() -> pd.DataFrame:
    t = pd.read_csv(RAW / "ticketmaster_events.csv")
    t = t[t.snapshot_utc == t.snapshot_utc.max()].copy()
    t["vkey"] = t.venue.map(venue_key)
    t = t.drop_duplicates(["vkey", "local_date", "local_time"])
    return t


def map_schedule(sched: pd.DataFrame, shows: pd.DataFrame, policies: pd.DataFrame) -> pd.DataFrame:
    """The venue is the reliable key, since one theater has one show at a time. Name matching catches the rest."""
    running = shows[shows.last_week == shows.last_week.max()]
    by_venue = {venue_key(r.theater): r.show_id for r in running.itertuples()}
    sched = sched.copy()
    sched["show_id"] = sched.vkey.map(by_venue).fillna("")
    latest = policies[policies.snapshot_date == policies.snapshot_date.max()]
    titles = {norm(s.split(":")[0]): s for s in latest.show.unique()}
    sched["policy_title"] = [titles.get(norm(str(a).split("(")[0].split(":")[0]), "") for a in sched.attraction]
    return sched


def policy_row(rows: pd.DataFrame, kind: str):
    q = rows[rows.policy_type.str.startswith(kind)]
    if q.empty:
        return None
    r = q.iloc[0]
    price = None if pd.isna(r.price) else float(r.price)
    return {
        "price": price, "price_text": clean_text(r.price_text), "time": clean_text(r.time), "how": clean_text(r.how),
        "where": clean_text(r["where"]), "limit": clean_text(r.tickets_per_person),
    }


def load_facts() -> dict:
    """Hand-kept show facts (SPEC 2.2a): days showing and runtime, looked up once per show. Empty if not collected."""
    path = ROOT / "registry" / "show_facts.csv"
    if not path.exists():
        return {}
    f = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {r.show_id: r for r in f.itertuples()}


def typical_prices(gross: pd.DataFrame) -> dict:
    """Median of the last 4 weekly average paid prices (SPEC 2.2a): show_id -> (price, weeks used)."""
    g = gross.dropna(subset=["show_id", "avg_ticket"]).sort_values("week_ending").groupby("show_id").tail(4)
    return {sid: (round(float(w.avg_ticket.median())), len(w)) for sid, w in g.groupby("show_id")}


def report_rates(shows: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Timestamp]:
    r = pd.read_csv(PROCESSED / "reports.csv", low_memory=False)
    r = r[(r.rush_type == "general") & r.show_id.notna() & (r.show_id != "-") & (r.confidence != "low")].copy()
    r["date"] = pd.to_datetime(r.perf_date, errors="coerce")
    r = r[r.date.notna() & (r.date >= "2024-06-01")]
    latest = r.date.max()
    daily = r[r.source == "daily_thread"]
    weeks = (pd.to_datetime(shows.last_week) - pd.to_datetime(shows.first_week)).dt.days / 7 + 1
    weeks.index = shows.show_id
    rate = daily.groupby("show_id").size().reindex(shows.show_id).fillna(0) / weeks
    recent = r[r.date > latest - pd.Timedelta(days=RECENT_DAYS)].groupby("show_id").size()
    return rate, recent, latest


def line_drivers(contrib: pd.Series, row: pd.Series) -> list[str]:
    """Plain-English reasons from the trees, compared with an average show-day."""
    out = []
    for f, c in contrib.drop(labels=["hours_before"], errors="ignore").sort_values(key=np.abs, ascending=False).items():
        if abs(c) < 0.06 or len(out) == 3:
            continue
        word = "longer" if c > 0 else "shorter"
        pct = f"{abs(np.exp(c) - 1) * 100:.0f}%"
        text = None
        if f == "show_code":
            text = f"This show's line usually runs {word} than most (about {pct})"
        elif f == "weekday":
            text = f"{WEEKDAYS[int(row.weekday)]}s run {word} (about {pct})"
        elif f == "recent_level":
            text = f"Lines over the past month have been {word} than typical (about {pct})"
        elif f == "pct_cap" and pd.notna(row.pct_cap):
            text = f"{min(row.pct_cap, 100):.0f}% seats sold in a recent week, which points to a {word} line (about {pct})"
        elif f == "avg_ticket" and pd.notna(row.avg_ticket):
            text = f"Average ticket of ${row.avg_ticket:.0f} in a recent week points to a {word} line (about {pct})"
        elif f == "weeks_since_first" and pd.notna(row.weeks_since_first):
            text = f"{row.weeks_since_first:.0f} weeks since its first listed week: {word} line (about {pct})"
        elif f == "seats" and pd.notna(row.seats):
            text = f"{row.seats:.0f}-seat theater: {word} line (about {pct})"
        elif f == "show_type_code":
            text = f"This type of show tends to have a {word} line (about {pct})"
        elif f == "is_school_break" and row.is_school_break == 1:
            text = f"NYC school break: {word} line (about {pct})"
        elif f == "is_federal_holiday" and row.is_federal_holiday == 1:
            text = f"Federal holiday: {word} line (about {pct})"
        elif f == "thanksgiving_week" and row.thanksgiving_week == 1:
            text = f"Thanksgiving week: {word} line (about {pct})"
        elif f == "christmas_new_year" and row.christmas_new_year == 1:
            text = f"Christmas and New Year's: {word} line (about {pct})"
        elif f == "broadway_week" and row.broadway_week == 1:
            text = f"Broadway Week: {word} line (about {pct})"
        elif f == "tonys_30d" and row.tonys_30d == 1:
            text = f"Within a month after the Tonys: {word} line (about {pct})"
        elif f == "recent_thin" and row.recent_thin == 1:
            text = "Few recent reports, so this leans on older days"
        if text:
            out.append(text)
    return out


def ticket_drivers(model: cutoff_model.CutoffModel, row: pd.DataFrame) -> list[str]:
    """Plain-English reasons from the Bayesian model, as multipliers on the expected ticket count."""
    s = model.samples
    x = model._x(row)[0]
    effects = {f: float((s["beta"][:, i] * x[i]).mean()) for i, f in enumerate(CUTOFF_FEATURES)}
    k = model.show_index.get(row.show_id.iloc[0])
    effects["show"] = float((s["sigma"] * s["z"][:, k]).mean()) if k is not None else 0.0
    out = []
    for f, c in sorted(effects.items(), key=lambda kv: -abs(kv[1])):
        if abs(c) < 0.08 or len(out) == 2:
            continue
        word = "more" if c > 0 else "fewer"
        pct = f"{abs(np.exp(c) - 1) * 100:.0f}%"
        r = row.iloc[0]
        text = {
            "show": f"This show has reported {word} rush tickets than typical (about {pct})",
            "weekend": f"{'Weekend' if r.weekend else 'Weekday'}: {word} rush tickets (about {pct})",
            "pct_cap": f"Recent % seats sold points to {word} rush tickets (about {pct})",
            "log_seats": f"Theater size points to {word} rush tickets (about {pct})",
            "is_musical": f"{'Musicals' if r.is_musical else 'Plays'} tend to have {word} rush tickets (about {pct})",
        }[f]
        out.append(text)
    return out


def accuracy_block(tag: str, funnel: dict, timings: dict) -> dict | None:
    """The accuracy page's numbers, straight from a finished test. None if that test hasn't finished."""
    if not (PROCESSED / f"backtest_{tag}.json").exists():
        return None
    res = json.loads((PROCESSED / f"backtest_{tag}.json").read_text(encoding="utf-8"))
    p = res["pooled"]
    windows = []
    for w in res["windows"]:
        windows.append({
            "month": w["month"],
            "line_mae_combo": w["line_combo"]["mae"], "line_mae_lookup": w["line_lookup"]["mae"],
            "line_cov_combo": w["line_combo"]["coverage80"], "line_cov_lookup": w["line_lookup"]["coverage80"],
            "points": w["line_combo"]["points"],
            "tickets_days": w["tickets_combo"]["days"],
            "attempts": (w.get("chance_combo") or {}).get("attempts", 0),
            "misses": (w.get("chance_combo") or {}).get("misses", 0),
        })
    return {
        "per_person": res["per_person"], "months": res["months"], "locked": res["locked"], "windows": windows,
        "line_combo": p["line_combo"], "line_lookup": p["line_lookup"],
        "tickets_combo": p["tickets_combo"], "tickets_lookup": p["tickets_lookup"],
        "bounds_combo": p["bounds_combo"], "bounds_lookup": p["bounds_lookup"],
        "chance_combo": p["chance_combo"], "chance_lookup": p["chance_lookup"],
        "chance_base_rate": p["chance_base_rate"], "always_yes_accuracy": p["always_yes_accuracy"],
        "always_yes_all_attempts": funnel["outcomes_share_got_a_ticket"],
        "always_yes_spec": 0.89,
        "verdict_combo": p["verdict_combo"], "calibration_combo": p["calibration_combo"],
        "funnel": funnel, "timings": timings,
        "live_results": None,  # nothing has been checked against real days yet
    }


def build(per_person: float, tag: str):
    started = time.time()
    t = load_tables()
    shows = t["shows"]
    funnel = json.loads((PROCESSED / "model_funnel.json").read_text(encoding="utf-8"))
    policies = load_policies(shows)
    opening = opening_lookup(policies)
    sched = map_schedule(load_schedule(), shows, policies)
    rate, recent, reports_through = report_rates(shows)
    feats = Features(shows, t["line"])

    t0 = time.time()
    lm = line_model.fit(t["line"], LINE_FEATURES)
    t1 = time.time()
    cm = cutoff_model.fit(tickets_bounds(t["cutoff"], per_person), per_person)
    if not cm.diagnostics["converged"]:
        raise SystemExit(f"Cutoff fit did not converge, so no predictions were written: {cm.diagnostics}")
    t2 = time.time()
    print("final fit: line", round(t1 - t0, 1), "s, cutoff", round(t2 - t1, 1), "s", cm.diagnostics, "phi", round(lm.phi, 2),
          flush=True)

    gross = pd.read_csv(RAW / "grosses_playbill.csv")
    by_prod = shows.drop_duplicates("production_id").set_index("production_id").show_id
    gross["show_id"] = gross.production_id.map(by_prod)
    latest_gross = gross.sort_values("week_ending").groupby("show_id").tail(1).set_index("show_id")
    typical = typical_prices(gross)
    facts = load_facts()
    latest_policy_date = policies.snapshot_date.max()
    current = policies[policies.snapshot_date == latest_policy_date]
    shows_by_id = shows.set_index("show_id")
    line_points = t["line"].groupby("show_id").size()
    cutoff_days = t["cutoff"].groupby("show_id").size()

    now = datetime.now(ZoneInfo("America/New_York"))
    today = pd.Timestamp(now.date())
    # Today still counts until noon, when the morning's rush is over
    dates = sorted(d for d in sched.local_date.unique()
                   if pd.Timestamp(d) > today or (pd.Timestamp(d) == today and now.hour < 12))
    # A snapshot covers exactly 8 days, so its last date can stop partway through and would list too few shows
    window_end = pd.Timestamp(sched.snapshot_utc.iloc[0]).tz_convert("America/New_York") + pd.Timedelta(days=DAYS_AHEAD)
    dates = [d for d in dates if pd.Timestamp(d).date() < window_end.date()]
    running = shows[shows.last_week == shows.last_week.max()]

    def describe(sid, title, day: pd.Timestamp, entry_name, theater):
        rows = current[current.show_id == sid] if sid else current[current.show == title]
        general, sro = policy_row(rows, "General Rush"), policy_row(rows, "Standing Room")
        digital, lottery = policy_row(rows, "Digital Rush"), policy_row(rows, "Digital Lottery")
        student = policy_row(rows, "Student Rush") or policy_row(rows, "Student Tickets")
        n_recent = int(recent.get(sid, 0)) if sid else 0
        by_reports = n_recent >= RECENT_ROWS and general is None
        in_person = general is not None or sro is not None or by_reports
        show_rate = float(rate.get(sid, 0.0)) if sid else 0.0
        n_line = int(line_points.get(sid, 0)) if sid else 0
        group = 3 if not in_person else (1 if show_rate >= MIN_REPORTS_PER_WEEK or n_line >= MIN_LINE_REPORTS else 2)
        gr = latest_gross.loc[sid] if sid and sid in latest_gross.index else None
        # Rush types on the tile (SPEC 2.2a). Other deals stay in the details view.
        labels = []
        if general:
            labels.append("In person")
        elif by_reports:
            labels.append("In person (reported)")
        if digital:
            labels.append("Online")
        if student:
            labels.append("Student")
        if lottery:
            labels.append("Lottery")
        if sro:
            labels.append("Standing room")
        known = ("General Rush", "Standing Room", "Digital Rush", "Digital Lottery", "Student Rush", "Student Tickets")
        other = [{"name": name, **policy_row(rows, name)} for name in sorted(set(rows.policy_type))
                 if not name.startswith(known)]
        # Rush price (SPEC 2.2a): in person, or online if there's no in-person price. Standing room only if nothing else.
        price, price_note = None, None
        source = "policy" if general or sro else ("reports" if by_reports else "none")
        older = policies[(policies.show_id == sid) & policies.policy_type.str.startswith("General Rush")] if sid else []
        older_priced = older[older.price.notna()] if len(older) else older
        if general and general["price"] is not None:
            price = general["price"]
        elif by_reports and len(older_priced):
            last = older_priced.sort_values("snapshot_date").iloc[-1]
            price = float(last.price)
            price_note = "last listed " + pd.Timestamp(last.snapshot_date).strftime("%b %Y")
        elif digital and digital["price"] is not None:
            price = digital["price"]
            price_note = "online"
        elif sro and sro["price"] is not None:
            price = sro["price"]
            price_note = "standing room"
        meta = shows_by_id.loc[sid] if sid else None
        fact = facts.get(sid or norm(title or entry_name).replace(" ", "-"))
        show_type = meta.show_type if meta is not None and meta.show_type in ("Play", "Musical") else None
        if show_type is None and fact is not None and fact.show_type in ("Play", "Musical"):
            show_type = fact.show_type
        cap = None if gr is None or pd.isna(gr.pct_cap) else min(round(float(gr.pct_cap)), 100)
        base = {
            "show_id": sid or norm(title or entry_name).replace(" ", "-"), "name": entry_name, "theater": theater, "group": group,
            "price": price, "price_note": price_note, "rush_source": source, "reports_per_week": round(show_rate, 2), "line_reports": n_line,
            "recent_reports": n_recent, "rush_labels": labels, "show_type": show_type,
            "typical_ticket": typical[sid][0] if sid in typical else None,
            "typical_ticket_weeks": typical[sid][1] if sid in typical else None,
            "days": fact.days.split() if fact is not None and fact.days else None,
            "runtime_minutes": int(fact.runtime_minutes) if fact is not None and fact.runtime_minutes else None,
            "runtime_text": fact.runtime_text if fact is not None and fact.runtime_text else None,
            "runtime_detail": fact.runtime_detail if fact is not None and fact.runtime_detail else None,
            "facts_review": bool(fact is not None and fact.needs_review.lower() == "yes"),
            "facts_source": f"Playbill, checked {pd.Timestamp(fact.date_checked).strftime('%b %d, %Y').replace(' 0', ' ')}" if fact is not None and fact.source else None,
            "policy": {"general": general, "standing_room": sro, "digital": digital, "lottery": lottery, "student": student,
                       "other": other},
            "seats_sold_pct": cap,
            "seats_sold_week": None if gr is None else gr.week_ending,
            "badges": [],
        }
        if digital:
            base["digital"] = {"opens": digital["time"], "price": digital["price"], "how": digital["how"],
                               "where": digital["where"], "sellout_minutes": None}
            m = re.match(r"(\d{1,2})\s*(am|pm)", digital["time"].lower())
            base["badges"].append(f"Digital rush {m[1]} {m[2].upper()}" if m else "Digital rush")
        return base

    days = {}
    for d in dates:
        day = pd.Timestamp(d)
        today_rows = sched[sched.local_date == d]
        entries = []
        for key, g in today_rows.groupby("vkey"):
            sid = g.show_id.iloc[0]
            title = g.policy_title.iloc[0]
            if sid:
                s = shows_by_id.loc[sid]
                name, theater = s["name"], s.theater
            elif title:
                name = g.attraction.iloc[0]
                theater = g.venue.iloc[0].strip()
            else:
                continue  # no policy, no grosses, no reports: SPEC 2.7 skips it
            e = describe(sid, title, day, name, theater)
            e["performances"] = sorted(str(x)[:5] for x in g.local_time.dropna().unique())
            e["schedule_known"] = True
            entries.append(e)
        on_schedule = {venue_key(str(x)) for x in today_rows.venue}
        have_schedule_at_all = {venue_key(str(x)) for x in sched.venue}
        for s in running.itertuples():
            if venue_key(s.theater) not in have_schedule_at_all and venue_key(s.theater) not in on_schedule:
                fact = facts.get(s.show_id)
                if fact is not None and fact.days and DAY_CODES[day.weekday()] not in fact.days.split():
                    continue  # not on Ticketmaster, but the show facts say it's dark this weekday
                e = describe(s.show_id, "", day, s.name, s.theater)
                e["performances"] = []
                e["schedule_known"] = False
                entries.append(e)

        ones = [e for e in entries if e["group"] == 1]
        if ones:
            ids = [e["show_id"] for e in ones]
            base = feats.build(pd.DataFrame({"show_id": ids, "date": day}))
            # Seeded per day, so a day's numbers don't shift just because an earlier day left the file
            tick = cm.draws(base, np.random.default_rng([11, int(d.replace("-", ""))]))
            for i, e in enumerate(ones):
                row = base.iloc[[i]]
                sid = e["show_id"]
                wd = day.weekday()
                open_hour = opening(sid, day).get(wd, FALLBACK_OPENING[wd])
                grid = row.loc[row.index.repeat(len(GRID))].copy()
                grid["hours_before"] = GRID
                mu = lm.mean(grid)
                td = np.repeat(tick[[i]], len(GRID), axis=0)
                ch = join.chance(mu, lm.phi, td, per_person)
                lo, hi = lm.interval(mu)
                med = lm.interval(mu, 0.0)[0]
                curve = [
                    {"time": clock(open_hour - h), "chance": round(float(c), 3), "line": float(m), "line_lo": float(a),
                     "line_hi": float(b)}
                    for h, c, m, a, b in zip(GRID, ch, med, lo, hi)
                ][::-1]
                nine = row.copy()
                nine["hours_before"] = max(open_hour - 9.0, 0.25)
                chance9 = float(join.chance(lm.mean(nine), lm.phi, tick[[i]], per_person)[0])
                reached = [p for p in curve if p["chance"] >= TARGET_CHANCE]
                arrival = reached[-1]["time"] if reached else curve[0]["time"]
                verdict = "GO" if chance9 >= GO else ("Maybe" if chance9 >= MAYBE else "Stay home")
                low_conf = int(line_points.get(sid, 0)) < THIN_LINE_POINTS or int(cutoff_days.get(sid, 0)) < THIN_CUTOFF_DAYS
                levels = {}
                for lv in LEVELS:
                    tail = (100 - lv) / 200
                    levels[str(lv)] = [int(np.quantile(tick[i], tail)), int(np.ceil(np.quantile(tick[i], 1 - tail)))]
                contrib = lm.contributions(nine).iloc[0]
                e.update({
                    "open_time": clock(open_hour),
                    "chance_9am": round(chance9, 3), "verdict": verdict, "arrival": arrival,
                    "arrival_reaches_target": bool(reached), "chance_by_time": curve,
                    "tickets": {"median": int(np.median(tick[i])), "levels": levels},
                    "line_at_9am": {
                        "median": float(lm.interval(lm.mean(nine), 0.0)[0][0]),
                        "lo": float(lm.interval(lm.mean(nine))[0][0]), "hi": float(lm.interval(lm.mean(nine))[1][0]),
                    },
                    "drivers": {"line": line_drivers(contrib, row.iloc[0]), "tickets": ticket_drivers(cm, row)},
                    "confidence": "low" if low_conf else "normal",
                    "data": {"line_points": int(line_points.get(sid, 0)), "cutoff_days": int(cutoff_days.get(sid, 0))},
                })
                if low_conf:
                    e["badges"].append("Low confidence")
        order = {1: 0, 2: 1, 3: 2}
        entries.sort(key=lambda e: (order[e["group"]], -e.get("chance_9am", 0), e["name"]))
        days[d] = entries

    timings = {"line_fit_seconds": round(t1 - t0, 1), "cutoff_fit_seconds": round(t2 - t1, 1),
               "whole_predictions_run_seconds": None}
    out = {
        "generated_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET"),
        "model": {"name": "Simple combo, first version", "line": "LightGBM", "cutoff": "NumPyro negative binomial (faster fit)",
                  "per_person": per_person, "line_spread": round(lm.phi, 3), "cutoff_checks": cm.diagnostics,
                  "fit": "faster fit: 4 chains run together, 300 + 300 steps", "fallback_used": False},
        "placeholders": {"go_at_or_above": GO, "maybe_at_or_above": MAYBE, "target_chance": TARGET_CHANCE,
                         "verdict_basis": "chance if you arrive at 9:00"},
        "data_through": {"reports": str(reports_through.date()), "policies": latest_policy_date,
                         "grosses_week": gross.week_ending.max(), "schedule": sched.snapshot_utc.iloc[0][:10]},
        "has_show_facts": bool(facts),
        "days": days,
        "accuracy": accuracy_block(tag, funnel, timings),
    }
    timings["whole_predictions_run_seconds"] = round(time.time() - started, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT, "days", len(days), {d: len(v) for d, v in days.items()}, "in", timings["whole_predictions_run_seconds"], "s")
    for e in days[dates[0]]:
        print(e["group"], e["name"][:30].ljust(30), e.get("verdict", ""), e.get("chance_9am", ""), e.get("arrival", ""),
              (e.get("tickets") or {}).get("levels", {}).get("80"), e["price"], e["rush_source"], e["badges"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-person", type=float, required=True)
    ap.add_argument("--backtest", required=True, help="tag of the backtest shown on the accuracy page")
    a = ap.parse_args()
    build(a.per_person, a.backtest)


if __name__ == "__main__":
    main()

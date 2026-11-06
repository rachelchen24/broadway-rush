/* Broadway Rush site. Reads only data/predictions.json. Never computes or invents a prediction. */
"use strict";

const state = { data: null, picksOnly: false };
const app = document.getElementById("app");
const footer = document.getElementById("footer");
const modal = document.getElementById("modal");
const tooltip = document.getElementById("tooltip");
const NOT_AVAILABLE = "Not available yet";

/* ---------- small helpers ---------- */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") throw new Error("no raw html");
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
const pct = (v, digits = 0) => (v === null || v === undefined ? NOT_AVAILABLE : `${(v * 100).toFixed(digits)}%`);
const num = (v, digits = 1) => (v === null || v === undefined ? NOT_AVAILABLE : Number(v).toFixed(digits));
const money = (v) => (v === null || v === undefined ? null : `$${Number.isInteger(v) ? v : Number(v).toFixed(2)}`);

function time12(t) {
  if (!t) return NOT_AVAILABLE;
  const [hh, mm] = t.split(":").map(Number);
  const suffix = hh >= 12 ? "PM" : "AM";
  const h12 = hh % 12 === 0 ? 12 : hh % 12;
  return `${h12}:${String(mm).padStart(2, "0")} ${suffix}`;
}
function parseDay(d) {
  const [y, m, day] = d.split("-").map(Number);
  return new Date(y, m - 1, day);
}
const dayName = (d, opts) => parseDay(d).toLocaleDateString("en-US", opts);
function localToday() {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
}
function monthName(m) {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

/* Picks live only in this browser. If storage is blocked, picks last until the page reloads. */
let picks = new Set();
try { picks = new Set(JSON.parse(localStorage.getItem("rush-picks") || "[]")); } catch { /* fine */ }
function savePicks() {
  try { localStorage.setItem("rush-picks", JSON.stringify([...picks])); } catch { /* fine */ }
}

/* ---------- pieces ---------- */
function verdictChip(v) {
  return h("span", { class: `verdict verdict-${v.split(" ")[0]}` }, v);
}
function worthBar(e) {
  return h("div", { class: "worth" },
    h("div", {
      class: "worth-track", role: "img",
      "aria-label": `Worth-it bar: ${e.verdict}, ${pct(e.chance_9am)} chance if you arrive at 9:00 AM`,
    }, h("span", { class: "worth-marker", style: `left:${Math.min(98.5, Math.max(1.5, e.chance_9am * 100))}%` })),
    verdictChip(e.verdict));
}
function priceBlock(e) {
  if (e.price === null || e.price === undefined) {
    return h("div", { class: "price" }, h("small", {}, "price not listed"));
  }
  let note = null;
  if (e.price_note === "standing room") note = "standing room";
  else if (e.price_note) note = e.price_note;
  return h("div", { class: "price" }, money(e.price), note ? h("small", {}, note) : null);
}
function badges(e) {
  const list = [...(e.badges || [])];
  if (e.schedule_known === false) list.push("Schedule not confirmed");
  if (!list.length) return null;
  return h("div", { class: "badges" }, list.map((b) => h("span", { class: `badge${b === "Low confidence" ? " low" : ""}` }, b)));
}
function pickBox(e) {
  const box = h("input", {
    type: "checkbox", checked: picks.has(e.show_id),
    onchange: (ev) => {
      if (ev.target.checked) picks.add(e.show_id); else picks.delete(e.show_id);
      savePicks();
      if (state.picksOnly) route();
      else updatePickCount();
    },
  });
  return h("label", { class: "pick" }, box, "Interested");
}
function updatePickCount() {
  const c = document.getElementById("pick-count");
  if (c) c.textContent = `Only my picks (${picks.size})`;
}
function tile(day, e) {
  const href = `#/show/${day}/${encodeURIComponent(e.show_id)}`;
  const head = h("div", { class: "tile-top" },
    h("div", { class: "tile-name" },
      h("a", { class: "tile-link", href }, e.name),
      h("span", { class: "theater" }, e.theater)),
    priceBlock(e));
  if (e.group === 1) {
    return h("article", { class: "tile" }, head, worthBar(e),
      h("div", { class: "stats" },
        h("span", { class: "chance" }, pct(e.chance_9am), " ", h("small", {}, "chance at 9:00 AM")),
        h("span", { class: "arrival" }, `Get there by ${time12(e.arrival)}`)),
      badges(e), pickBox(e));
  }
  if (e.group === 2) {
    return h("article", { class: "tile" }, head,
      h("div", { class: "simple-line" }, h("b", {}, "Limited data, probably easy.")),
      h("div", { class: "simple-line" }, policyLine(e)),
      h("div", { class: "simple-line" }, capacityLine(e)),
      badges(e), pickBox(e));
  }
  return h("article", { class: "tile" }, head,
    h("div", { class: "simple-line" }, otherOffers(e)),
    badges(e), pickBox(e));
}
function policyLine(e) {
  const p = e.policy || {};
  if (p.general) return `In-person rush: ${p.general.time}.`;
  if (p.standing_room) return `Standing room: ${p.standing_room.time}. ${p.standing_room.how}.`;
  if (e.rush_source === "reports") return "Not on Playbill's current rush list, but recent reports describe an in-person line.";
  return "In-person policy not listed.";
}
function capacityLine(e) {
  if (e.recent_pct_cap === null || e.recent_pct_cap === undefined) return "Recent % capacity: not available yet.";
  return `${e.recent_pct_cap}% full, week ending ${dayName(e.recent_pct_cap_week, { month: "short", day: "numeric" })}.`;
}
function otherOffers(e) {
  const p = e.policy || {};
  const parts = [];
  if (p.digital) parts.push(`Digital rush${p.digital.price ? ` ${money(p.digital.price)}` : ""}`);
  if (p.lottery) parts.push(`Digital lottery${p.lottery.price ? ` ${money(p.lottery.price)}` : ""}`);
  if (p.student) parts.push("Student rush");
  if (!parts.length) return "No in-person rush, lottery or digital rush listed.";
  return `No in-person rush. ${parts.join(" · ")}.`;
}

/* ---------- home ---------- */
function renderHome(selected) {
  const data = state.data;
  const all = Object.keys(data.days).sort();
  const today = localToday();
  const upcoming = all.filter((d) => d >= today);
  const stale = upcoming.length === 0;
  const dates = (stale ? all : upcoming).slice(0, 7);
  if (!dates.length) {
    app.replaceChildren(h("p", { class: "empty" }, "No predictions in the file yet."));
    return;
  }
  const day = selected && dates.includes(selected) ? selected : dates[0];
  const entries = data.days[day];
  const visible = state.picksOnly ? entries.filter((e) => picks.has(e.show_id)) : entries;
  const groups = [1, 2, 3].map((g) => visible.filter((e) => e.group === g));
  const picker = h("div", { class: "day-picker", role: "group", "aria-label": "Pick a day" },
    dates.map((d) => h("button", {
      type: "button", class: "day-chip", "aria-pressed": d === day ? "true" : "false",
      onclick: () => { location.hash = `#/day/${d}`; },
    }, h("b", {}, d === today ? "Today" : dayName(d, { weekday: "short" })), h("span", {}, dayName(d, { month: "short", day: "numeric" })))));

  const picksToggle = h("label", { class: "toggle" },
    h("input", { type: "checkbox", checked: state.picksOnly, onchange: (ev) => { state.picksOnly = ev.target.checked; route(); } }),
    h("span", { id: "pick-count" }, `Only my picks (${picks.size})`));

  app.replaceChildren(
    h("h1", {}, "Is rush worth it this morning?"),
    h("p", { class: "lede" }, "Pick a day. Shows are ranked by your chance of a ticket if you arrive at 9:00 AM."),
    stale ? h("p", { class: "notice" }, "These predictions are out of date: every day in the file has passed.") : null,
    picker,
    h("div", { class: "toolbar" }, picksToggle, h("span", { class: "hint" }, `${dayName(day, { weekday: "long", month: "long", day: "numeric" })}`)),
    groups[0].length ? h("section", {},
      h("h2", { class: "group-title" }, "Full predictions"),
      h("div", { class: "tiles" }, groups[0].map((e) => tile(day, e)))) : null,
    groups[1].length ? h("section", {},
      h("h2", { class: "group-title" }, "In-person rush, not enough reports"),
      h("p", { class: "group-note" }, "Too few reports for a number. Quiet shows like these tend to be less full, so a line is probably short."),
      h("div", { class: "tiles" }, groups[1].map((e) => tile(day, e)))) : null,
    groups[2].length ? h("section", {},
      h("h2", { class: "group-title" }, "No in-person rush line"),
      h("p", { class: "group-note" }, "Lottery and digital rush only, so there's no line to predict. Few reports here doesn't mean low demand."),
      h("div", { class: "tiles" }, groups[2].map((e) => tile(day, e)))) : null,
    visible.length ? null : h("p", { class: "empty" }, state.picksOnly
      ? "None of your picks are playing this day. Turn off \"Only my picks\" to see every show."
      : "No shows on the schedule for this day."));
}

/* ---------- details ---------- */
function ticketsPanel(e) {
  const levels = e.tickets.levels;
  const sentence = h("p", { class: "statement" });
  function paint(level) {
    const [lo, hi] = levels[String(level)];
    const mid = (lo + hi) / 2;
    const half = (hi - lo) / 2;
    const fmt = (x) => (Number.isInteger(x) ? String(x) : x.toFixed(1));
    const priceText = money(e.price);
    sentence.replaceChildren(
      "We're ", h("b", {}, `${level}%`), " confident there will be ",
      h("b", {}, `${fmt(mid)} ± ${fmt(half)}`), " rush tickets",
      priceText ? [" at ", h("b", {}, priceText)] : [" (price not listed)"], ".",
      h("span", { class: "muted", style: "display:block;font-size:.88rem;margin-top:2px" }, `That's ${lo} to ${hi} tickets.`));
  }
  paint(80);
  const output = h("output", {}, "80%");
  const slider = h("input", {
    type: "range", min: 50, max: 95, step: 5, value: 80, "aria-label": "Confidence level",
    oninput: (ev) => { paint(Number(ev.target.value)); output.textContent = `${ev.target.value}%`; },
  });
  const wrap = h("div", { class: "slider-wrap", hidden: true },
    h("label", { class: "muted" }, "Confidence: ", output), slider);
  const button = h("button", {
    type: "button", class: "link-button", "aria-expanded": "false",
    onclick: () => {
      wrap.hidden = !wrap.hidden;
      button.setAttribute("aria-expanded", String(!wrap.hidden));
      button.textContent = wrap.hidden ? "Adjust confidence" : "Hide confidence slider";
    },
  }, "Adjust confidence");
  return h("section", { class: "panel" }, sentence,
    h("p", { class: "statement" }, "Get there by ", h("b", {}, time12(e.arrival)), " for the best chance of getting one."),
    e.arrival_reaches_target ? h("p", { class: "muted" }, `That's the latest time that still gets a ${pct(state.data.placeholders.target_chance)} chance (placeholder target).`)
      : h("p", { class: "muted" }, `Even this early, the chance stays under the ${pct(state.data.placeholders.target_chance)} target (placeholder), because this show may have very few tickets.`),
    worthBar(e),
    h("p", { class: "muted", style: "margin-top:8px" }, `${pct(e.chance_9am)} chance if you arrive at 9:00 AM. Box office opens ${time12(e.open_time)}.`),
    badges(e), button, wrap);
}

function chancePanel(e) {
  const curve = e.chance_by_time;
  const panel = h("section", { class: "panel" }, h("h2", {}, "Chance of a ticket by arrival time"));
  const holder = h("div", { class: "chart" });
  panel.append(holder);
  const marks = [];
  const iArrival = curve.findIndex((p) => p.time === e.arrival);
  if (iArrival >= 0) marks.push({ i: iArrival, label: `By ${time12(e.arrival)}: ${pct(curve[iArrival].chance)}` });
  lineChart(holder, {
    x: curve.map((p) => time12(p.time)),
    series: [{ name: "Chance of a ticket", color: "var(--series-1)", values: curve.map((p) => p.chance * 100) }],
    yMax: 100, ySuffix: "%", yTicks: [0, 25, 50, 75, 100], marks, height: 210, labelEvery: 4,
    tipRows: (i) => [`${pct(curve[i].chance)} chance`, `Line about ${curve[i].line} (${curve[i].line_lo} to ${curve[i].line_hi})`],
  });
  panel.append(h("details", {}, h("summary", {}, "See the numbers"),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Arrive at"), h("th", {}, "Chance"), h("th", {}, "People in line (80% range)"))),
      h("tbody", {}, curve.map((p) => h("tr", {}, h("td", {}, time12(p.time)), h("td", {}, pct(p.chance)),
        h("td", {}, `${p.line} (${p.line_lo} to ${p.line_hi})`))))))));
  return panel;
}

function digitalPanel(e) {
  if (!e.digital) return null;
  const d = e.digital;
  const at = /todaytix/i.test(`${d.how} ${d.where}`) ? "on TodayTix" : (d.where ? `at ${d.where.replace(/^https?:\/\//, "").replace(/\/$/, "")}` : "online");
  return h("section", { class: "panel" }, h("h2", {}, "Digital rush"),
    h("p", {}, `Digital rush opens: ${d.opens}, ${at}`, d.price ? ` for ${money(d.price)}` : "", "."),
    h("p", {}, "Usually sells out in: ", h("span", { class: "not-available" }, NOT_AVAILABLE.toLowerCase()), "."),
    h("p", {}, "Be in the app a few minutes early: it opens right on time."),
    h("p", { class: "muted" }, "Combo idea: do a morning digital rush for one show, then walk to another show's box office."));
}

function policyPanel(e) {
  const p = e.policy || {};
  const row = (name, x) => x ? h("div", {},
    h("h3", {}, name, x.price ? ` · ${money(x.price)}` : ""),
    h("p", { class: "muted" }, [x.time, x.where, x.limit].filter(Boolean).join(" · "))) : null;
  const rows = [row("In-person rush", p.general), row("Standing room", p.standing_room), row("Digital rush", p.digital),
    row("Digital lottery", p.lottery), row("Student rush", p.student)].filter(Boolean);
  return h("section", { class: "panel" }, h("h2", {}, "Rush policy"),
    rows.length ? rows : h("p", { class: "not-available" }, "No policy listed."),
    e.rush_source === "reports" ? h("p", { class: "muted" }, "This show isn't on Playbill's current in-person rush list, but recent Reddit reports describe one. Check at the box office.") : null,
    h("p", { class: "muted" }, `From Playbill's list of ${dayName(state.data.data_through.policies, { month: "short", day: "numeric", year: "numeric" })}.`));
}

function renderDetails(day, id) {
  const entries = state.data.days[day] || [];
  const e = entries.find((x) => x.show_id === id);
  if (!e) {
    app.replaceChildren(h("a", { class: "back", href: "#/" }, "← Back to shows"), h("p", { class: "empty" }, "That show isn't on the schedule for this day."));
    return;
  }
  const head = h("div", { class: "detail-head" },
    h("div", { style: "min-width:0" }, h("h1", {}, e.name),
      h("p", { class: "muted", style: "margin:2px 0 0" }, `${e.theater} · ${dayName(day, { weekday: "long", month: "long", day: "numeric" })}`),
      h("p", { class: "muted", style: "margin:0" }, e.schedule_known === false
        ? "Schedule not confirmed: this show isn't on Ticketmaster. Check before you go."
        : `Performances: ${e.performances.map(time12).join(", ") || NOT_AVAILABLE}`)),
    priceBlock(e));
  const back = h("a", { class: "back", href: `#/day/${day}` }, "← Back to shows");

  if (e.group === 1) {
    const why = h("section", { class: "panel" }, h("h2", {}, "Why this prediction"),
      h("h3", {}, "The line"),
      e.drivers.line.length ? h("ul", { class: "reasons" }, e.drivers.line.map((t) => h("li", {}, t))) : h("p", { class: "muted" }, "Nothing stands out from an average day."),
      h("h3", {}, "The tickets"),
      e.drivers.tickets.length ? h("ul", { class: "reasons" }, e.drivers.tickets.map((t) => h("li", {}, t))) : h("p", { class: "muted" }, "Nothing stands out from a typical show."),
      h("p", { class: "muted" }, "Compared with an average day across shows. Built from ", String(e.data.line_points), " line reports and ", String(e.data.cutoff_days), " days with ticket information for this show."),
      h("p", { class: "muted" }, "One prediction per day: most reports don't say matinee or evening."));
    app.replaceChildren(back, head, h("div", { class: "detail-grid" },
      h("div", { class: "col" }, ticketsPanel(e), chancePanel(e)),
      h("div", { class: "col" }, why, digitalPanel(e), policyPanel(e))));
    return;
  }
  const note = e.group === 2
    ? h("section", { class: "panel" }, h("h2", {}, "Limited data, probably easy"),
      h("p", {}, "Too few reports for a prediction, so there's no number here."),
      h("p", {}, capacityLine(e)),
      h("p", { class: "muted" }, `${e.reports_per_week} reports a week, and a full prediction needs at least 2.`))
    : h("section", { class: "panel" }, h("h2", {}, "No in-person rush line"),
      h("p", {}, otherOffers(e)),
      h("p", {}, capacityLine(e)),
      h("p", { class: "muted" }, "No line to predict. Few reports here doesn't mean low demand."));
  app.replaceChildren(back, head, h("div", { class: "detail-grid" },
    h("div", { class: "col" }, note, policyPanel(e)), h("div", { class: "col" }, digitalPanel(e))));
}

/* ---------- accuracy ---------- */
function bestClass(a, b, smallerIsBetter = true) {
  if (a === null || b === null || a === undefined || b === undefined || a === b) return [null, null];
  const aWins = smallerIsBetter ? a < b : a > b;
  return aWins ? ["best", null] : [null, "best"];
}
function renderAccuracy() {
  const a = state.data.accuracy;
  const lc = a.line_combo, ll = a.line_lookup, tc = a.tickets_combo, tl = a.tickets_lookup;
  const cc = a.chance_combo, cl = a.chance_lookup, cb = a.chance_base_rate;
  const dev = a.months;
  const covGap = (x) => (x === null ? null : Math.abs(x - 0.8));
  const row = (label, combo, lookup, fmt, smaller = true, always = null) => {
    const [x, y] = bestClass(combo, lookup, smaller);
    return h("tr", {}, h("td", {}, label), h("td", { class: x }, fmt(combo)), h("td", { class: y }, fmt(lookup)), h("td", {}, always ?? "–"));
  };
  const covRow = (label, c, l) => {
    const [x, y] = bestClass(covGap(c), covGap(l));
    return h("tr", {}, h("td", {}, label), h("td", { class: x }, pct(c, 1)), h("td", { class: y }, pct(l, 1)), h("td", {}, "–"));
  };
  const table = h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Measure"), h("th", {}, state.data.model.name), h("th", {}, "Per-show lookup table"), h("th", {}, "Always say yes"))),
    h("tbody", {},
      row(`Line error, people (${lc.points} reports)`, lc.mae, ll.mae, (v) => num(v, 2)),
      covRow("80% line range held", lc.coverage80, ll.coverage80),
      row("Width of that range, people", lc.width80, ll.width80, (v) => num(v, 1)),
      row("Arrival-time error, minutes", lc.arrival_error_min, ll.arrival_error_min, (v) => num(v, 0)),
      row(`Ticket error, tickets (${tc.days} stated counts)`, tc.mae, tl.mae, (v) => num(v, 2)),
      covRow("80% ticket range held", tc.coverage80, tl.coverage80),
      row("Width of that range, tickets", tc.width80, tl.width80, (v) => num(v, 1)),
      row(`Yes/no right, at 50% (${cc.attempts} attempts)`, cc.accuracy_at_50, cl.accuracy_at_50, (v) => pct(v, 1), false, pct(a.always_yes_accuracy, 1)),
      row(`Misses caught, of ${cc.misses}`, cc.misses_caught_at_50, cl.misses_caught_at_50, (v) => String(v), false, "0"),
      row("Wins wrongly warned about", cc.wins_wrongly_warned_at_50, cl.wins_wrongly_warned_at_50, (v) => String(v), true, "0"),
      row("Chance error (Brier, smaller is better)", cc.brier, cl.brier, (v) => num(v, 3), true, `${num(cb.brier, 3)} (flat rate)`))));

  const slots = [];
  const start = new Date(2025, 10, 1);
  for (let i = 0; i < 12; i++) {
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
    slots.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  }
  const byMonth = Object.fromEntries(a.windows.map((w) => [w.month, w]));
  const series = (key) => slots.map((m) => (byMonth[m] ? byMonth[m][key] : null));
  const chartTitles = (i) => (byMonth[slots[i]] ? `${byMonth[slots[i]].points} line reports` : "Locked for the final score");

  const errorChart = h("div", { class: "chart" });
  const coverChart = h("div", { class: "chart" });
  const legend = () => h("div", { class: "legend" },
    h("span", {}, h("i", { style: "border-color:var(--series-1)" }), "Combo"),
    h("span", {}, h("i", { style: "border-color:var(--series-2);border-top-style:dashed" }), "Lookup table"));

  const beats = [];
  if (lc.mae < ll.mae) beats.push("line length");
  if (tc.mae !== null && tc.mae < tl.mae) beats.push("ticket counts");
  if (cc.brier < cl.brier) beats.push("the chance of a ticket");
  const loses = [];
  if (lc.mae >= ll.mae) loses.push("line length");
  if (tc.mae !== null && tc.mae >= tl.mae) loses.push("ticket counts");
  if (cc.brier >= cl.brier) loses.push("the chance of a ticket");
  if (lc.arrival_error_min >= ll.arrival_error_min) loses.push("arrival-time error");

  const live = a.live_results;
  const vc = a.verdict_combo;
  const vr = (name) => {
    const v = vc[name];
    return h("tr", {}, h("td", {}, name), h("td", {}, String(v.attempts)), h("td", {}, String(v.got)), h("td", {}, v.attempts ? pct(v.share_got) : NOT_AVAILABLE));
  };
  app.replaceChildren(
    h("h1", {}, "How accurate have we been?"),
    h("p", { class: "lede" }, `Each month below was predicted using only earlier days. These are ${dev.length} test months on past reports, not real trips yet.`),
    h("div", { class: "accuracy-grid" },
      h("section", { class: "panel" }, h("h2", {}, "Does it beat the simple lookup table?"),
        h("p", {}, beats.length ? `Better than the lookup table on: ${beats.join(", ")}. ` : "It doesn't beat the lookup table on the main measures. ",
          loses.length ? `Not better on: ${loses.join(", ")}.` : ""),
        table,
        h("p", { class: "muted", style: "margin-top:8px" }, "Gold marks the better of the combo and the lookup table. For ranges, better means closer to the 80% it promises. Ticket and outcome rows rest on few reports, so small gaps may be luck.")),
      h("section", { class: "panel" }, h("h2", {}, "The 89% problem"),
        h("p", {}, `People mostly post their wins. Across ${a.funnel.outcomes_arrived_before_opening_known_result} attempts with a known result, ${pct(a.always_yes_all_attempts, 1)} got a ticket (${pct(a.always_yes_spec)} on a wider count that includes reports without a stated date). On the ${cc.attempts} attempts in these tests, always saying yes is right ${pct(a.always_yes_accuracy, 1)} of the time.`),
        h("div", { class: "stat-row" },
          h("div", { class: "stat" }, h("b", {}, pct(cc.accuracy_at_50, 1)), h("span", {}, "combo right at 50%")),
          h("div", { class: "stat" }, h("b", {}, pct(a.always_yes_accuracy, 1)), h("span", {}, "always saying yes")),
          h("div", { class: "stat" }, h("b", {}, `${cc.misses_caught_at_50} of ${cc.misses}`), h("span", {}, "misses the combo caught"))),
        h("p", { class: "muted" }, "Treat this as a rough check: losses are under-reported, so no score here is the true rate."),
        h("h3", { style: "margin-top:10px" }, "Did the verdicts work out?"),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Verdict (placeholder)"), h("th", {}, "Attempts"), h("th", {}, "Got a ticket"), h("th", {}, "Share"))),
          h("tbody", {}, vr("GO"), vr("Maybe"), vr("Stay home")))),
        h("p", { class: "muted", style: "margin-top:8px" }, `Scored on the chance at the time each person really arrived, with GO at ${pct(state.data.placeholders.go_at_or_above)} and up and Maybe at ${pct(state.data.placeholders.maybe_at_or_above)} and up.`)),
      h("section", { class: "panel" }, h("h2", {}, "Line error by test month"),
        h("p", { class: "muted" }, "Average miss on the number of people in line. Lower is better."), legend(), errorChart),
      h("section", { class: "panel" }, h("h2", {}, "Did the 80% line range hold?"),
        h("p", { class: "muted" }, "Share of real counts inside the range. The goal is 80%, not 100%."), legend(), coverChart),
      h("section", { class: "panel" }, h("h2", {}, "Real trips"),
        live ? null : h("p", { class: "not-available" }, "Not available yet: no predictions have been checked against real rush days or verified reports.")),
      h("section", { class: "panel" }, h("h2", {}, "What's behind these numbers"),
        h("p", {}, `${a.funnel.comments_scanned.toLocaleString()} Reddit comments gave ${a.funnel.all_observations.toLocaleString()} observations. After cleaning, the model uses ${a.funnel.line_points_after_dropping_duplicates.toLocaleString()} line reports and ${a.funnel.cutoff_show_days.toLocaleString()} show-days with ticket information, from ${dayName(a.funnel.first_date, { month: "short", year: "numeric" })} to ${dayName(a.funnel.last_date, { month: "short", year: "numeric" })}.`),
        h("p", {}, `Test months: ${dev.map(monthName).join(", ")}. ${a.locked.map(monthName).join(", ")} are locked and unscored here, so they can give the final model an honest score.`),
        h("p", {}, `Tickets per person is fixed at ${a.per_person}, the value that did best in these tests. The Bayesian part's sampler checks: largest R-hat ${state.data.model.cutoff_checks.max_r_hat} (want close to 1), ${state.data.model.cutoff_checks.divergences} divergences (want few).`),
        state.data.model.fallback_used ? h("p", { class: "notice strong" }, "This run used the fallback cutoff, not the Bayesian model.") : null)));

  lineChart(errorChart, {
    x: slots.map(monthName),
    series: [
      { name: "Combo", color: "var(--series-1)", values: series("line_mae_combo") },
      { name: "Lookup table", color: "var(--series-2)", dash: "6 4", values: series("line_mae_lookup") },
    ],
    yMax: 8, yTicks: [0, 2, 4, 6, 8], height: 220, labelEvery: 2, markers: true, ySuffix: "",
    tipRows: (i) => (byMonth[slots[i]]
      ? [`${num(byMonth[slots[i]].line_mae_combo, 2)} Combo`, `${num(byMonth[slots[i]].line_mae_lookup, 2)} Lookup table`, chartTitles(i)]
      : [chartTitles(i)]),
  });
  lineChart(coverChart, {
    x: slots.map(monthName),
    series: [
      { name: "Combo", color: "var(--series-1)", values: series("line_cov_combo").map((v) => (v === null ? null : v * 100)) },
      { name: "Lookup table", color: "var(--series-2)", dash: "6 4", values: series("line_cov_lookup").map((v) => (v === null ? null : v * 100)) },
    ],
    yMax: 100, yTicks: [0, 25, 50, 80, 100], refLine: { y: 80, label: "Goal: 80%" }, ySuffix: "%", height: 220, labelEvery: 2, markers: true,
    tipRows: (i) => (byMonth[slots[i]]
      ? [`${pct(byMonth[slots[i]].line_cov_combo)} Combo`, `${pct(byMonth[slots[i]].line_cov_lookup)} Lookup table`, chartTitles(i)]
      : [chartTitles(i)]),
  });
}

/* ---------- chart: thin lines, recessive axes, crosshair + tooltip, redrawn to fit its container ---------- */
const SVG = "http://www.w3.org/2000/svg";
function s(tag, attrs, text) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}
const charts = [];
function lineChart(holder, cfg) {
  charts.push({ holder, cfg });
  drawChart(holder, cfg);
}
function drawChart(holder, cfg) {
  if (!holder.isConnected) return;
  const width = Math.max(240, holder.clientWidth || 320);
  const height = cfg.height || 200;
  const m = { top: 14, right: 12, bottom: 24, left: 40 };
  const w = width - m.left - m.right, ht = height - m.top - m.bottom;
  const n = cfg.x.length;
  const xPos = (i) => m.left + (n === 1 ? 0 : (i / (n - 1)) * w);
  const yPos = (v) => m.top + ht - (v / cfg.yMax) * ht;
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img", "aria-label": cfg.series.map((x) => x.name).join(" and ") });
  for (const t of cfg.yTicks) {
    svg.append(s("line", { x1: m.left, x2: width - m.right, y1: yPos(t), y2: yPos(t), stroke: "var(--line)", "stroke-width": 1, opacity: 0.55 }));
    svg.append(s("text", { x: m.left - 6, y: yPos(t) + 4, "text-anchor": "end" }, `${t}${cfg.ySuffix || ""}`));
  }
  const step = Math.max(cfg.labelEvery || 1, Math.ceil(n / Math.max(3, Math.floor(w / 62))));
  for (let i = 0; i < n; i += step) {
    const anchor = i === 0 ? "start" : "middle";
    svg.append(s("text", { x: xPos(i), y: height - 6, "text-anchor": anchor }, cfg.x[i]));
  }
  if (cfg.refLine) {
    svg.append(s("line", { x1: m.left, x2: width - m.right, y1: yPos(cfg.refLine.y), y2: yPos(cfg.refLine.y), stroke: "var(--ink-3)", "stroke-width": 1, "stroke-dasharray": "2 3" }));
  }
  for (const ser of cfg.series) {
    let d = "", pen = false;
    ser.values.forEach((v, i) => {
      if (v === null || v === undefined) { pen = false; return; }
      d += `${pen ? "L" : "M"}${xPos(i).toFixed(1)} ${yPos(v).toFixed(1)}`;
      pen = true;
    });
    svg.append(s("path", { d, fill: "none", stroke: ser.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": ser.dash || "none" }));
    if (cfg.markers) {
      ser.values.forEach((v, i) => {
        if (v === null || v === undefined) return;
        svg.append(s("circle", { cx: xPos(i), cy: yPos(v), r: 4, fill: ser.color, stroke: "var(--card)", "stroke-width": 2 }));
      });
    }
  }
  for (const mk of cfg.marks || []) {
    const v = cfg.series[0].values[mk.i];
    svg.append(s("circle", { cx: xPos(mk.i), cy: yPos(v), r: 5, fill: "#fff", stroke: "var(--card)", "stroke-width": 2 }));
    const right = xPos(mk.i) > width * 0.55;
    svg.append(s("text", { class: "value-label", x: xPos(mk.i) + (right ? -9 : 9), y: yPos(v) + (v > 80 ? 18 : -9), "text-anchor": right ? "end" : "start" }, mk.label));
  }
  const cross = s("line", { y1: m.top, y2: m.top + ht, stroke: "var(--ink-2)", "stroke-width": 1, visibility: "hidden" });
  svg.append(cross);
  const hit = s("rect", { x: m.left - 8, y: 0, width: w + 16, height, fill: "transparent", tabindex: 0, "aria-label": "Move along the chart to read values" });
  let current = 0;
  const show = (i, cx, cy) => {
    current = i;
    cross.setAttribute("x1", xPos(i)); cross.setAttribute("x2", xPos(i)); cross.setAttribute("visibility", "visible");
    tooltip.replaceChildren(h("strong", {}, cfg.x[i]), ...cfg.tipRows(i).map((t) => h("div", { class: "tip-row" }, t)));
    tooltip.hidden = false;
    const r = tooltip.getBoundingClientRect();
    tooltip.style.left = `${Math.min(window.innerWidth - r.width - 8, Math.max(8, cx + 12))}px`;
    tooltip.style.top = `${Math.max(8, cy - r.height - 10)}px`;
  };
  const hide = () => { cross.setAttribute("visibility", "hidden"); tooltip.hidden = true; };
  hit.addEventListener("pointermove", (ev) => {
    const box = svg.getBoundingClientRect();
    const scale = width / box.width;
    const px = (ev.clientX - box.left) * scale;
    const i = Math.max(0, Math.min(n - 1, Math.round(((px - m.left) / w) * (n - 1))));
    show(i, ev.clientX, ev.clientY);
  });
  hit.addEventListener("pointerleave", hide);
  hit.addEventListener("blur", hide);
  hit.addEventListener("focus", () => {
    const box = svg.getBoundingClientRect();
    show(current, box.left + xPos(current), box.top + m.top);
  });
  hit.addEventListener("keydown", (ev) => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    ev.preventDefault();
    current = Math.max(0, Math.min(n - 1, current + (ev.key === "ArrowRight" ? 1 : -1)));
    const box = svg.getBoundingClientRect();
    show(current, box.left + xPos(current), box.top + m.top);
  });
  svg.append(hit);
  holder.replaceChildren(svg);
}
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => charts.forEach((c) => drawChart(c.holder, c.cfg)), 120);
});

/* ---------- modals: screens only, nothing is connected ---------- */
function openModal(title, ...body) {
  modal.replaceChildren(
    h("div", { class: "modal-head" }, h("h2", { id: "modal-title" }, title),
      h("button", { type: "button", class: "close", "aria-label": "Close", onclick: () => modal.close() }, "×")),
    h("div", { class: "modal-body" }, ...body));
  modal.showModal();
}
modal.addEventListener("click", (ev) => { if (ev.target === modal) modal.close(); });

function field(labelText, control, opts = {}) {
  const id = `f-${labelText.replace(/\W+/g, "-").toLowerCase()}`;
  control.id = id;
  return h("div", { class: "field" },
    h("label", { for: id }, labelText, opts.required ? h("span", { class: "req" }, " *") : null),
    control, opts.help ? h("span", { class: "help" }, opts.help) : null);
}
function radios(name, labelText, options, required) {
  return h("fieldset", { class: "field" },
    h("legend", {}, labelText, required ? h("span", { class: "req" }, " *") : null),
    h("div", { class: "radios" }, options.map((o) => h("label", {}, h("input", { type: "radio", name, value: o, required }), o))));
}
function allShowNames() {
  const names = new Set();
  for (const list of Object.values(state.data.days)) for (const e of list) names.add(e.name);
  return [...names].sort((a, b) => a.localeCompare(b));
}
function openReport() {
  const today = localToday();
  const result = h("div", { role: "status" });
  const form = h("form", {
    class: "modal-body", style: "padding:0", novalidate: false,
    onsubmit: (ev) => {
      ev.preventDefault();
      result.replaceChildren(h("p", { class: "result" }, "Not connected yet: nothing was sent or saved. This form can't take reports until it has a database and an email service."));
    },
  },
    field("Date you went to the box office", h("input", { type: "date", name: "date", max: today, required: true }), { required: true, help: "Today or earlier." }),
    h("div", { class: "two" },
      field("Show", h("select", { name: "show", required: true }, h("option", { value: "" }, "Choose a show"), allShowNames().map((n) => h("option", {}, n))), { required: true }),
      field("Performance you were trying for", h("select", { name: "perf" }, h("option", {}, "Matinee"), h("option", {}, "Evening"), h("option", {}, "Not sure")))),
    h("div", { class: "two" },
      field("Time you arrived", h("input", { type: "time", name: "arrived", required: true }), { required: true }),
      field("People in line ahead of you", h("input", { type: "number", name: "ahead", min: 0, inputmode: "numeric" }))),
    field("Rush tickets available", h("input", { type: "number", name: "available", min: 0, inputmode: "numeric" }), { help: "If you know, or if they said." }),
    radios("got", "Did you get tickets?", ["Yes", "No", "Only full price"], true),
    h("div", { class: "two" },
      field("How many tickets you bought", h("input", { type: "number", name: "bought", min: 0, inputmode: "numeric" })),
      field("Price paid", h("input", { type: "number", name: "paid", min: 0, step: "0.01", inputmode: "decimal" }))),
    radios("sro", "Was standing room offered?", ["Yes", "No", "Don't know"], false),
    field("Time rush sold out", h("input", { type: "time", name: "soldout" }), { help: "If you know." }),
    field("Notes", h("textarea", { name: "notes", rows: 2, placeholder: "e.g. understudy on, told to come back at 5" })),
    field("Photo of your ticket", h("input", { type: "file", name: "photo", accept: "image/*" }), { help: "Optional but encouraged. Cover the barcode." }),
    h("button", { type: "submit", class: "primary" }, "Send report"),
    result);
  openModal("Report rush availability",
    h("span", { class: "not-connected" }, "Not connected yet"),
    h("p", { class: "notice strong" }, "⚠️ Only fill this out AFTER you've been to the box office. This is for reporting what actually happened, not for asking about availability."),
    h("p", { class: "muted" }, "This screen is a preview. Sending doesn't work yet, and nothing you enter leaves this page."),
    form);
}
function openRefresh() {
  const result = h("div", { role: "status" });
  const pin = h("input", { type: "password", inputmode: "numeric", autocomplete: "off", name: "pin", required: true });
  const form = h("form", {
    class: "modal-body", style: "padding:0",
    onsubmit: (ev) => {
      ev.preventDefault();
      pin.value = "";
      result.replaceChildren(h("p", { class: "result" }, "Not connected yet: the PIN wasn't checked and nothing was refreshed. You're seeing the saved predictions."));
    },
  },
    field("PIN", pin, { help: "Shared with family and friends." }),
    h("button", { type: "submit", class: "primary" }, "Refresh ticket data"),
    result);
  openModal("Refresh",
    h("span", { class: "not-connected" }, "Not connected yet"),
    h("p", {}, "When it's connected, Refresh will re-check today's TKTS board and Ticketmaster for all shows in about 10–15 seconds."),
    h("ul", { class: "reasons muted" },
      h("li", {}, "Only 2 PIN tries, then this device is blocked until midnight ET."),
      h("li", {}, "If anyone refreshed in the last 30 minutes, you get that result."),
      h("li", {}, "Refreshes left today: ", h("span", { class: "not-available" }, "not available yet"), ".")),
    form);
}
document.getElementById("open-report").addEventListener("click", () => { if (state.data) openReport(); });
document.getElementById("open-refresh").addEventListener("click", () => { if (state.data) openRefresh(); });

/* ---------- routing ---------- */
function setNav(which) {
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === which) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
}
function route() {
  if (!state.data) return;
  charts.length = 0;
  tooltip.hidden = true;
  const parts = location.hash.replace(/^#\/?/, "").split("/");
  if (parts[0] === "accuracy") {
    setNav("accuracy");
    renderAccuracy();
  } else if (parts[0] === "show" && parts[1] && parts[2]) {
    setNav("home");
    renderDetails(parts[1], decodeURIComponent(parts[2]));
  } else {
    setNav("home");
    renderHome(parts[0] === "day" ? parts[1] : null);
  }
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", route);

function renderFooter() {
  const d = state.data;
  footer.replaceChildren(
    h("p", {}, `${d.model.name}: ${d.model.line} for the line, ${d.model.cutoff} for the tickets. Made ${d.generated_at}. Reports through ${dayName(d.data_through.reports, { month: "short", day: "numeric" })}, grosses through ${dayName(d.data_through.grosses_week, { month: "short", day: "numeric" })}, schedule from Ticketmaster ${dayName(d.data_through.schedule, { month: "short", day: "numeric" })}.`),
    h("p", {}, `Placeholder settings, not final: GO at ${pct(d.placeholders.go_at_or_above)} and up, Maybe at ${pct(d.placeholders.maybe_at_or_above)} and up, based on the chance if you arrive at 9:00 AM. Arrival times aim for a ${pct(d.placeholders.target_chance)} chance.`));
}

fetch("data/predictions.json", { cache: "no-store" })
  .then((r) => { if (!r.ok) throw new Error(`status ${r.status}`); return r.json(); })
  .then((data) => { state.data = data; renderFooter(); route(); })
  .catch((err) => {
    app.replaceChildren(h("p", { class: "empty" }, `Couldn't load the predictions file (${err.message}). Start the site with a local server, not by opening the file directly.`));
  });

/* Broadway Rush site. Reads only data/predictions.json. Never computes or invents a prediction. */
"use strict";

const state = {
  data: null, picksOnly: false, paint: null, filtersOpen: null,
  sort: { key: "chance", reversed: false },
  weekSort: { key: "arrival", reversed: false }, // This week view: latest arrival first (SPEC 2.2b)
  filters: { rush: new Set(), type: new Set(), days: new Set(), runtime: new Set() },
};
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
  return `${new Date(y, mo - 1, 1).toLocaleDateString("en-US", { month: "short" })} '${String(y).slice(2)}`;
}

/* Picks live only in this browser. If storage is blocked, picks last until the page reloads. */
let picks = new Set();
try { picks = new Set(JSON.parse(localStorage.getItem("rush-picks") || "[]")); } catch { /* fine */ }
function savePicks() {
  try { localStorage.setItem("rush-picks", JSON.stringify([...picks])); } catch { /* fine */ }
}

function setApp(...nodes) {
  app.replaceChildren(...nodes.flat().filter((n) => n !== null && n !== undefined && n !== false));
}

/* ---------- pieces ---------- */
const RUSH_OPTIONS = ["In person", "Online", "Student", "Lottery", "Standing room"];
const TYPE_OPTIONS = ["Play", "Musical"];
const DAY_OPTIONS = ["M", "T", "W", "Th", "F", "S", "Su"];
const RUNTIME_OPTIONS = [
  { key: "under90", label: "Under 90 min", test: (m) => m < 90 },
  { key: "90to120", label: "90 min–2 hrs", test: (m) => m >= 90 && m <= 120 },
  { key: "120to150", label: "2–2.5 hrs", test: (m) => m > 120 && m <= 150 },
  { key: "over150", label: "Over 2.5 hrs", test: (m) => m > 150 },
];
const minutesOf = (t) => { const [a, b] = t.split(":").map(Number); return a * 60 + b; };
// "Better" comes first by default: highest chance, latest arrival, lowest prices, shortest runtime. Unknowns always go last.
const SORTS = [
  { key: "chance", label: "Best chance", needsDate: true, value: (e) => e.chance_9am, bigFirst: true },
  { key: "arrival", label: "Latest arrival", needsDate: true, value: (e) => (e.arrival ? minutesOf(e.arrival) : null), bigFirst: true },
  { key: "price", label: "Rush price", value: (e) => e.price, bigFirst: false },
  { key: "typical", label: "Typical ticket price", value: (e) => e.typical_ticket, bigFirst: false },
  { key: "runtime", label: "Runtime", needsFacts: true, value: (e) => e.runtime_minutes, bigFirst: false },
];

/* Box offices open at 10 AM most days and at noon on Sundays (SPEC 2.2b). A time on a day that opens at any other
   hour gets an asterisk, because it runs later (or earlier) than the other days' times. */
const NORMAL_OPEN = "10:00";
const dayIndex = (d) => (parseDay(d).getDay() + 6) % 7; // Monday 0 ... Sunday 6, matching DAY_KEYS
const opensUnusual = (e) => !!e.open_time && e.open_time !== NORMAL_OPEN;
function openMark(e) {
  return opensUnusual(e) ? h("span", { class: "open-mark", title: `Box office opens at ${time12(e.open_time)} this day` }, "*") : null;
}
function markedTime(e, t) {
  return [time12(t), openMark(e)];
}
function openNote(pairs) {
  const marked = pairs.filter(([, e]) => opensUnusual(e));
  if (!marked.length) return null;
  const sundayNoon = marked.filter(([d, e]) => dayIndex(d) === 6 && e.open_time === "12:00").length;
  const parts = [];
  if (sundayNoon) parts.push("Box office opens at noon on Sundays (10:00 AM other days), so Sunday times run about 2 hours later.");
  if (sundayNoon < marked.length) parts.push(`${sundayNoon ? "Other marked days" : "Marked days"} open at a different time: see the show page.`);
  return h("p", { class: "open-note" }, h("span", { class: "open-mark" }, "*"), " ", parts.join(" "));
}

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
    if (e.group === 3) return null; // no rush price to show
    return h("div", { class: "price" }, h("small", {}, "price not listed"));
  }
  return h("div", { class: "price" }, money(e.price), e.price_note ? h("small", {}, e.price_note) : null);
}
function badges(e) {
  const list = [...(e.badges || [])];
  if (e.schedule_known === false) list.push("Schedule not confirmed");
  if (!list.length) return null;
  return h("div", { class: "badges" }, list.map((b) => h("span", { class: `badge${b === "Low confidence" ? " low" : ""}` }, b)));
}
function rushLabels(e) {
  if (!e.rush_labels || !e.rush_labels.length) return null;
  return h("div", { class: "badges" }, e.rush_labels.map((l) => h("span", { class: `rush-label${l.includes("reported") ? " reported" : ""}` }, l)));
}
function seatsLine(e) {
  if (e.seats_sold_pct === null || e.seats_sold_pct === undefined) return "% seats sold: not available yet";
  const age = (parseDay(localToday()) - parseDay(e.seats_sold_week)) / 86400000;
  if (age <= 14) return `${e.seats_sold_pct}% seats sold last week`;
  return `${e.seats_sold_pct}% seats sold, week ending ${dayName(e.seats_sold_week, { month: "short", day: "numeric" })}`;
}
function runtimeText(e) {
  return e.runtime_text || null;
}
function typicalText(e) {
  if (e.typical_ticket === null || e.typical_ticket === undefined) return "Typical ticket price not available";
  return `Typical ticket ${money(e.typical_ticket)}`;
}
function factsLine(e, anyMode) {
  const parts = [e.show_type || "Play or musical not available", typicalText(e)];
  if (state.data.has_show_facts) {
    parts.splice(1, 0, runtimeText(e) || "Runtime not available");
    if (anyMode) parts.push(e.days ? `Plays ${e.days.join(" ")}` : "Days not available");
  }
  return h("div", { class: "facts-line" }, parts.join(" · "));
}
function pickBox(e) {
  const box = h("input", {
    type: "checkbox", checked: picks.has(e.show_id),
    onchange: (ev) => {
      if (ev.target.checked) picks.add(e.show_id); else picks.delete(e.show_id);
      savePicks();
      if (state.paint) state.paint();
    },
  });
  return h("label", { class: "pick" }, box, "Interested");
}
function policyLine(e) {
  const p = e.policy || {};
  if (p.general) return `In-person rush: ${p.general.time}.`;
  if (p.standing_room) return `Standing room: ${p.standing_room.time}. ${p.standing_room.how}.`;
  if (e.rush_source === "reports") return "Not on Playbill's current rush list, but recent reports describe an in-person line.";
  return "In-person policy not listed.";
}
function otherOffers(e) {
  const p = e.policy || {};
  const parts = [];
  if (p.digital) parts.push(`Online rush${p.digital.price ? ` ${money(p.digital.price)}` : ""}`);
  if (p.lottery) parts.push(`Lottery${p.lottery.price ? ` ${money(p.lottery.price)}` : ""}`);
  if (p.student) parts.push("Student");
  if (parts.length) return `No in-person rush. ${parts.join(" · ")}.`;
  if (p.other && p.other.length) return "No in-person rush. Other deals in the details.";
  return "No in-person rush, lottery or online rush listed.";
}
function tileHead(e, href) {
  return h("div", { class: "tile-top" },
    h("div", { class: "tile-name" },
      h("a", { class: "tile-link", href }, e.name),
      h("span", { class: "theater" }, e.theater)),
    priceBlock(e));
}
function tile(day, e, anyMode, from = "") {
  const head = tileHead(e, `#/show/${day}/${encodeURIComponent(e.show_id)}${from}`);
  if (anyMode) {
    return h("article", { class: "tile" }, head, rushLabels(e),
      h("div", { class: "seats" }, seatsLine(e)), factsLine(e, true),
      h("div", { class: "check-back" }, "Check back within 7 days of your date."),
      pickBox(e));
  }
  if (e.group === 1) {
    return h("article", { class: "tile" }, head, rushLabels(e), worthBar(e),
      h("div", { class: "stats" },
        h("span", { class: "chance" }, pct(e.chance_9am), " ", h("small", {}, "chance at 9:00 AM")),
        h("span", { class: "arrival" }, "Get there by ", markedTime(e, e.arrival))),
      h("div", { class: "seats" }, seatsLine(e)), factsLine(e, false),
      badges(e), pickBox(e));
  }
  if (e.group === 2) {
    return h("article", { class: "tile" }, head, rushLabels(e),
      h("div", { class: "simple-line" }, h("b", {}, "Limited data, probably easy.")),
      h("div", { class: "simple-line" }, policyLine(e)),
      h("div", { class: "seats" }, seatsLine(e)), factsLine(e, false),
      badges(e), pickBox(e));
  }
  return h("article", { class: "tile" }, head, rushLabels(e),
    h("div", { class: "simple-line" }, otherOffers(e)),
    h("div", { class: "seats" }, seatsLine(e)), factsLine(e, false),
    badges(e), pickBox(e));
}

/* ---------- This week view (SPEC 2.2b): which of the next 7 days is best, per show ---------- */
const shortTime = (t) => time12(t).replace(/ [AP]M$/, "");
function nowMinutes() {
  const n = new Date();
  return n.getHours() * 60 + n.getMinutes();
}
// Today counts until that show's box office opens, then greys out.
const isPastToday = (date, e) => date === localToday() && nowMinutes() >= minutesOf(e.open_time || NORMAL_OPEN);
const hasNumber = (e) => e.group === 1 && !!e.arrival && e.chance_9am !== null && e.chance_9am !== undefined;
function joinOr(words) {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} or ${words[words.length - 1]}`;
}
// One item per show, built from every day it plays in the 7 days. The show's facts come from its first day in its best group.
function weekShows(dates) {
  const byShow = new Map();
  for (const date of dates) {
    for (const e of state.data.days[date] || []) {
      if (!byShow.has(e.show_id)) byShow.set(e.show_id, []);
      byShow.get(e.show_id).push({ date, e });
    }
  }
  return [...byShow.values()].map((weekDays) => {
    const group = Math.min(...weekDays.map((x) => x.e.group));
    const first = weekDays.find((x) => x.e.group === group);
    return { ...first.e, group, firstDate: first.date, weekDays, best: null };
  });
}
// Best day = the latest arrival time among the days that count. Days with the same time are tied (placeholder, SPEC 9 Q28).
function weekBest(item, allowed) {
  const usable = item.weekDays.filter(({ date, e }) => allowed(date) && hasNumber(e) && !isPastToday(date, e));
  if (!usable.length) return null;
  const minutes = Math.max(...usable.map((x) => minutesOf(x.e.arrival)));
  const top = usable.filter((x) => minutesOf(x.e.arrival) === minutes);
  top.sort((a, b) => b.e.chance_9am - a.e.chance_9am || a.date.localeCompare(b.date));
  const chances = top.map((x) => x.e.chance_9am);
  return {
    top, minutes, date: top[0].date, entry: top[0].e,
    chance: Math.max(...chances), chanceLo: Math.min(...chances),
    every: usable.length > 1 && top.length === usable.length,
  };
}
const weekDayName = (d) => (d === localToday() ? "Today" : DAY_SHORT[dayIndex(d)]);
function weekRow(item, dates, allowed) {
  const bestDates = new Set((item.best ? item.best.top : []).map((x) => x.date));
  const cell = (d, cls, label, value, tip) => h("span", { class: `week-cell ${cls}`, title: tip, role: "listitem", "aria-label": `${label}: ${tip}` },
    h("span", { class: "week-cell-day" }, label), h("span", { class: "week-cell-val" }, value));
  return h("div", { class: "week-row", role: "list", "aria-label": "Get there by, each day this week" },
    dates.map((d) => {
      const label = weekDayName(d);
      const x = item.weekDays.find((w) => w.date === d);
      if (!x) return cell(d, "dark", label, "Dark", "not playing");
      if (!allowed(d)) return cell(d, "off", label, "–", "not one of your days");
      if (!hasNumber(x.e)) return cell(d, "off", label, "–", "no prediction this day");
      if (isPastToday(d, x.e)) return cell(d, "off", label, "–", "the box office has already opened");
      const e = x.e;
      const tip = `get there by ${time12(e.arrival)}, ${pct(e.chance_9am)} chance at 9:00 AM, ${e.verdict}${opensUnusual(e) ? `. Box office opens ${time12(e.open_time)}` : ""}${bestDates.has(d) ? ". Best day" : ""}`;
      return h("a", {
        class: `week-cell tone-${e.verdict.split(" ")[0]}${bestDates.has(d) ? " best" : ""}`, role: "listitem",
        href: `#/show/${d}/${encodeURIComponent(item.show_id)}/week`, title: tip, "aria-label": `${dayName(d, { weekday: "long", month: "short", day: "numeric" })}: ${tip}`,
      }, h("span", { class: "week-cell-day" }, label), h("span", { class: "week-cell-val" }, shortTime(e.arrival), openMark(e)));
    }));
}
function weekTile(item, dates, allowed) {
  const b = item.best;
  const href = `#/show/${b ? b.date : item.firstDate}/${encodeURIComponent(item.show_id)}/week`;
  if (!b) {
    return h("article", { class: "tile" }, tileHead(item, href), rushLabels(item),
      h("div", { class: "simple-line" }, "No prediction left on your days this week."),
      weekRow(item, dates, allowed), h("div", { class: "seats" }, seatsLine(item)), factsLine(item, false), badges(item), pickBox(item));
  }
  const tied = [...b.top].sort((p, q) => p.date.localeCompare(q.date));
  const when = b.every
    ? (state.filters.days.size ? "Any of your days" : "Any day it plays")
    : tied.length === 1 ? dayName(tied[0].date, { weekday: "short", month: "short", day: "numeric" })
      : joinOr(tied.map((x) => weekDayName(x.date)));
  const chanceText = pct(b.chance) === pct(b.chanceLo) ? pct(b.chance) : `${pct(b.chanceLo)}–${pct(b.chance)}`;
  const anyMarked = b.top.find((x) => opensUnusual(x.e));
  return h("article", { class: "tile" }, tileHead(item, href), rushLabels(item),
    h("div", { class: "best-day" },
      h("span", { class: "best-label" }, b.every ? "Every day about the same" : (b.top.length > 1 ? "Best days" : "Best day")),
      h("span", { class: "best-when" }, when)),
    worthBar(b.entry),
    h("div", { class: "stats" },
      h("span", { class: "chance" }, chanceText, " ", h("small", {}, "chance at 9:00 AM")),
      h("span", { class: "arrival" }, "Get there by ", time12(b.entry.arrival), anyMarked ? openMark(anyMarked.e) : null)),
    weekRow(item, dates, allowed),
    h("div", { class: "seats" }, seatsLine(item)), factsLine(item, false), badges(item), pickBox(item));
}
// Shows without a number in the week view: the day view's tile, plus the days they play this week.
function weekOtherTile(item) {
  const t = tile(item.firstDate, item, false, "/week");
  const playing = item.weekDays.map((x) => weekDayName(x.date));
  t.insertBefore(h("div", { class: "simple-line" }, `Playing this week: ${playing.join(", ")}.`), t.querySelector(".seats"));
  return t;
}
function weekStrip(items, dates, allowed) {
  const cells = dates.map((d) => {
    let shows = 0, go = 0, marked = null, open = 0;
    for (const it of items) {
      const x = it.weekDays.find((w) => w.date === d);
      if (!x || !hasNumber(x.e)) continue;
      if (isPastToday(d, x.e)) { open += 1; continue; }
      shows += 1;
      if (x.e.verdict === "GO") go += 1;
      if (!marked && opensUnusual(x.e)) marked = x.e;
    }
    return { d, shows, go, marked, off: !allowed(d), past: !shows && open > 0 };
  });
  const bestGo = Math.max(0, ...cells.filter((c) => !c.off && c.shows).map((c) => c.go));
  return h("div", { class: "week-strip", role: "list", "aria-label": "How many shows are GO each day" },
    cells.map((c) => {
      const isBest = bestGo > 0 && !c.off && c.shows && c.go === bestGo;
      const value = c.off || c.past || !c.shows ? "–" : String(c.go);
      const sub = c.off ? "not your day" : c.past ? "already open" : c.shows ? `of ${c.shows} GO` : "no numbers";
      const tip = c.off ? "not one of your days" : c.past ? "box offices have already opened" : c.shows
        ? `${c.go} of ${c.shows} shows with a prediction are GO${isBest ? ". Best day" : ""}` : "no shows with a prediction";
      return h("a", {
        class: `strip-day${isBest ? " best" : ""}${c.off || c.past ? " off" : ""}`, href: `#/day/${c.d}`, role: "listitem",
        title: tip, "aria-label": `${dayName(c.d, { weekday: "long", month: "short", day: "numeric" })}: ${tip}`,
      },
        h("b", {}, DAY_SHORT[dayIndex(c.d)], c.marked ? openMark(c.marked) : null),
        h("span", { class: "strip-date" }, c.d === localToday() ? "Today" : dayName(c.d, { month: "short", day: "numeric" })),
        h("span", { class: "strip-num" }, value),
        h("small", {}, sub));
    }));
}

/* ---------- filters and sorting: everything runs in the browser from the predictions file ---------- */
const anyFilterOn = () => Object.values(state.filters).some((f) => f.size);
function matchesFilters(e, anyMode) {
  const f = state.filters;
  if (f.rush.size && !(e.rush_labels || []).some((l) => f.rush.has(l.startsWith("In person") ? "In person" : l))) return false;
  if (f.type.size && !(e.show_type && f.type.has(e.show_type))) return false;
  if (anyMode && f.days.size && !(e.days && e.days.some((d) => f.days.has(d)))) return false;
  if (f.runtime.size) {
    if (e.runtime_minutes === null || e.runtime_minutes === undefined) return false;
    if (!RUNTIME_OPTIONS.some((o) => f.runtime.has(o.key) && o.test(e.runtime_minutes))) return false;
  }
  return true;
}
function hiddenForUnknown(entries, anyMode) {
  const f = state.filters;
  const notes = [];
  const add = (n, what) => { if (n) notes.push(`${n} ${n === 1 ? "show" : "shows"} hidden: ${what} not known`); };
  if (f.type.size) add(entries.filter((e) => !e.show_type).length, "play or musical");
  if (anyMode && f.days.size) add(entries.filter((e) => !e.days).length, "days showing");
  if (f.runtime.size) add(entries.filter((e) => e.runtime_minutes === null || e.runtime_minutes === undefined).length, "runtime");
  return notes;
}
function activeSort(anyMode, weekMode) {
  const current = weekMode ? state.weekSort : state.sort;
  const wanted = SORTS.find((x) => x.key === current.key);
  if (anyMode && wanted.needsDate) return { spec: SORTS.find((x) => x.key === "price"), reversed: false };
  // In the week view, Best chance and Latest arrival use each show's best day.
  if (weekMode && wanted.key === "chance") return { spec: { ...wanted, value: (e) => (e.best ? e.best.chance : null) }, reversed: current.reversed };
  if (weekMode && wanted.key === "arrival") return { spec: { ...wanted, value: (e) => (e.best ? e.best.minutes : null) }, reversed: current.reversed };
  return { spec: wanted, reversed: current.reversed };
}
function sortEntries(list, spec, reversed) {
  const known = [], unknown = [];
  for (const e of list) (spec.value(e) === null || spec.value(e) === undefined ? unknown : known).push(e);
  const sign = (spec.bigFirst ? -1 : 1) * (reversed ? -1 : 1);
  known.sort((a, b) => sign * (spec.value(a) - spec.value(b)) || a.name.localeCompare(b.name));
  unknown.sort((a, b) => a.name.localeCompare(b.name));
  return [...known, ...unknown];
}
function chipRow(name, options, set, opts = {}) {
  const row = h("div", { class: "control-row", role: "group", "aria-label": name },
    h("span", { class: "control-name" }, name),
    options.map((o) => {
      const key = o.key || o;
      const label = o.label || o;
      return h("button", {
        type: "button", class: "chip", "aria-pressed": set.has(key) ? "true" : "false", disabled: !!opts.disabled, "data-filter": name, "data-value": key,
        onclick: (ev) => {
          if (set.has(key)) set.delete(key); else set.add(key);
          ev.currentTarget.setAttribute("aria-pressed", set.has(key) ? "true" : "false");
          state.paint();
        },
      }, label);
    }),
    opts.note ? h("span", { class: "control-note" }, opts.note) : null);
  return row;
}

/* ---------- home ---------- */
function allShows() {
  const seen = new Map();
  for (const d of Object.keys(state.data.days).sort()) {
    for (const e of state.data.days[d]) if (!seen.has(e.show_id)) seen.set(e.show_id, e);
  }
  return [...seen.values()];
}
function renderHome(selected) {
  const data = state.data;
  const all = Object.keys(data.days).sort();
  const today = localToday();
  const upcoming = all.filter((d) => d >= today);
  const stale = upcoming.length === 0;
  const dates = (stale ? all : upcoming).slice(0, 7);
  if (!dates.length) {
    setApp(h("p", { class: "empty" }, "No predictions in the file yet."));
    return;
  }
  const anyMode = selected === "any";
  const weekMode = selected === "week";
  const day = anyMode ? "any" : weekMode ? "week" : (selected && dates.includes(selected) ? selected : dates[0]);
  const entries = anyMode ? allShows() : weekMode ? weekShows(dates) : data.days[day];
  // Week view: Days showing means "days I can go", so only those days are compared.
  const allowed = (d) => !state.filters.days.size || state.filters.days.has(DAY_KEYS[dayIndex(d)]);

  const picker = h("div", { class: "day-picker", role: "group", "aria-label": "Pick a day" },
    dates.map((d) => h("button", {
      type: "button", class: "day-chip", "aria-pressed": d === day ? "true" : "false",
      onclick: () => { location.hash = `#/day/${d}`; },
    }, h("b", {}, d === today ? "Today" : dayName(d, { weekday: "short" })), h("span", {}, dayName(d, { month: "short", day: "numeric" })))),
    h("button", {
      type: "button", class: "day-chip", "aria-pressed": weekMode ? "true" : "false",
      onclick: () => { location.hash = "#/week"; },
    }, h("b", {}, "This week"), h("span", {}, "Best day")),
    h("button", {
      type: "button", class: "day-chip", "aria-pressed": anyMode ? "true" : "false",
      onclick: () => { location.hash = "#/any"; },
    }, h("b", {}, "Any day"), h("span", {}, "Plan ahead")));

  const sortRow = h("div", { class: "control-row", role: "group", "aria-label": "Sort" },
    h("span", { class: "control-name" }, "Sort"),
    SORTS.filter((x) => !x.needsFacts || data.has_show_facts).map((x) => {
      const off = anyMode && x.needsDate;
      return h("button", {
        type: "button", class: "chip", disabled: off, "data-sort": x.key,
        title: off ? "Not available in Any day: predictions stop at 7 days" : null,
        onclick: () => {
          const current = activeSort(anyMode, weekMode);
          const next = current.spec.key === x.key ? { key: x.key, reversed: !current.reversed } : { key: x.key, reversed: false };
          if (weekMode) state.weekSort = next; else state.sort = next;
          state.paint();
        },
      }, x.label);
    }));

  const filterRows = [
    chipRow("Rush type", RUSH_OPTIONS, state.filters.rush),
    chipRow("Play or musical", TYPE_OPTIONS, state.filters.type),
  ];
  if (data.has_show_facts) {
    filterRows.push(chipRow("Days showing", DAY_OPTIONS, state.filters.days, anyMode ? {}
      : weekMode ? { note: "Days you can go: only these are compared." }
        : { disabled: true, note: "Pick This week or Any day to use this: a date already decides." }));
    filterRows.push(chipRow("Runtime", RUNTIME_OPTIONS, state.filters.runtime));
  }
  if (state.filtersOpen === null) state.filtersOpen = window.matchMedia("(min-width: 700px)").matches;
  const filterSummary = h("summary", {}, "Filters");
  const filterBox = h("details", { class: "filters", open: state.filtersOpen, ontoggle: (ev) => { state.filtersOpen = ev.target.open; } },
    filterSummary, h("div", { class: "filter-body" }, filterRows));

  const picksToggle = h("label", { class: "toggle" },
    h("input", { type: "checkbox", checked: state.picksOnly, onchange: (ev) => { state.picksOnly = ev.target.checked; state.paint(); } }),
    h("span", { id: "pick-count" }, ""));
  const resultLine = h("div", { class: "result-line", role: "status" });
  const results = h("div", {});
  const stripHolder = h("div", { class: "strip-holder" });

  state.paint = () => {
    const visible = entries.filter((e) => matchesFilters(e, anyMode) && (!state.picksOnly || picks.has(e.show_id))
      && (!weekMode || e.weekDays.some((x) => allowed(x.date))));
    if (weekMode) for (const e of entries) e.best = e.group === 1 ? weekBest(e, allowed) : null;
    const { spec, reversed } = activeSort(anyMode, weekMode);
    document.getElementById("pick-count").textContent = `Only my picks (${picks.size})`;
    sortRow.querySelectorAll("[data-sort]").forEach((b) => {
      const on = b.dataset.sort === spec.key;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      const name = SORTS.find((x) => x.key === b.dataset.sort).label;
      b.textContent = on ? `${name} ${reversed ? "↑" : "↓"}` : name;
    });
    const active = Object.values(state.filters).reduce((n, f) => n + f.size, 0);
    filterSummary.textContent = active ? `Filters (${active} on)` : "Filters";
    const notes = hiddenForUnknown(entries, anyMode);
    resultLine.replaceChildren(
      h("b", {}, `${visible.length} of ${entries.length} shows`),
      ...notes.map((n) => h("span", {}, n)),
      ...(anyFilterOn() ? [h("button", {
        type: "button", class: "clear-all",
        onclick: () => {
          Object.values(state.filters).forEach((f) => f.clear());
          filterBox.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
          state.paint();
        },
      }, "Clear all")] : []));

    const tileFor = (e) => (weekMode ? (e.group === 1 ? weekTile(e, dates, allowed) : weekOtherTile(e)) : tile(day, e, anyMode));
    const grid = (list) => h("div", { class: weekMode ? "tiles week-tiles" : "tiles" }, list.map(tileFor));
    const sections = [];
    if (weekMode) stripHolder.replaceChildren(h("h2", { class: "strip-title" }, "Shows that are GO, by day"), weekStrip(visible, dates, allowed));
    if (!visible.length) {
      sections.push(h("p", { class: "empty" }, state.picksOnly && !anyFilterOn()
        ? "None of your picks are here. Turn off \"Only my picks\" to see every show."
        : "No shows match. Try turning off a filter."));
    } else if (!anyMode && (spec.key === "chance" || (weekMode && spec.key === "arrival"))) {
      // The default view keeps the three show groups (SPEC 8). Shows without a number stay at the bottom.
      const groups = [1, 2, 3].map((g) => visible.filter((e) => e.group === g));
      if (groups[0].length) sections.push(h("section", {}, h("h2", { class: "group-title" }, "Full predictions"), grid(sortEntries(groups[0], spec, reversed))));
      if (groups[1].length) {
        sections.push(h("section", {}, h("h2", { class: "group-title" }, "At the box office, not enough reports"),
          h("p", { class: "group-note" }, "Too few reports for a number. Quiet shows like these tend to sell fewer seats, so a line is probably short."),
          grid(groups[1])));
      }
      if (groups[2].length) {
        sections.push(h("section", {}, h("h2", { class: "group-title" }, "No in-person rush line"),
          h("p", { class: "group-note" }, "Lottery and online rush only, so there's no line to predict. Few reports here doesn't mean low demand."),
          grid(groups[2])));
      }
    } else {
      sections.push(h("section", {}, grid(sortEntries(visible, spec, reversed))));
    }
    results.replaceChildren(...sections);
  };

  const pairs = weekMode
    ? entries.flatMap((it) => it.weekDays.filter((x) => hasNumber(x.e)).map((x) => [x.date, x.e]))
    : anyMode ? [] : entries.filter(hasNumber).map((e) => [day, e]);
  setApp(
    h("h1", {}, anyMode ? "What's playing when you can go?" : weekMode ? "Which day should you go?" : "Is rush worth it this morning?"),
    h("p", { class: "lede" }, anyMode
      ? "Planning further ahead: show facts only, with no chance or arrival time."
      : weekMode
        ? "Each show's best day this week: the latest you can get there and still probably get a ticket. Tap a day to see all its shows."
        : "Pick a day. Shows are ranked by your chance of a ticket if you arrive at 9:00 AM."),
    stale ? h("p", { class: "notice" }, "These predictions are out of date: every day in the file has passed.") : null,
    picker,
    weekMode ? stripHolder : null,
    openNote(pairs),
    anyMode ? h("p", { class: "notice" }, "Predictions stop 7 days out, so these tiles don't have any. Schedules change and a show could close before your date, so confirm before you go.") : null,
    h("div", { class: "controls" }, sortRow, filterBox,
      h("div", { class: "control-row" }, picksToggle), resultLine),
    results);
  state.paint();
}

/* ---------- details ---------- */
function ticketsPanel(e) {
  const levels = e.tickets.levels;
  const sentence = h("p", { class: "statement" });
  const inPersonPrice = e.price_note === "online" || e.price_note === "standing room" ? null : money(e.price);
  function paint(level) {
    const [lo, hi] = levels[String(level)];
    const mid = (lo + hi) / 2;
    const half = (hi - lo) / 2;
    const fmt = (x) => (Number.isInteger(x) ? String(x) : x.toFixed(1));
    sentence.replaceChildren(
      "We're ", h("b", {}, `${level}%`), " confident there will be ",
      h("b", {}, `${fmt(mid)} ± ${fmt(half)}`), " rush tickets",
      ...(inPersonPrice ? [" at ", h("b", {}, inPersonPrice), e.price_note ? ` (${e.price_note})` : ""] : [" (in-person price not listed)"]), ".",
      h("span", { class: "muted", style: "display:block;font-size:.88rem;margin-top:2px" }, `That's ${lo} to ${hi} tickets.`));
  }
  paint(80);
  const acc = state.data.accuracy;
  const ticketCaution = acc && acc.tickets_combo.mae > acc.tickets_lookup.mae
    ? h("p", { class: "notice" }, `Treat the ticket count as a rough guess. In tests it missed stated counts by ${num(acc.tickets_combo.mae, 1)} tickets on average, and a simple per-show lookup missed by ${num(acc.tickets_lookup.mae, 1)}. Most reports only say "at least", so the range runs wide.`)
    : null;
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
  return h("section", { class: "panel" }, sentence, ticketCaution,
    h("p", { class: "statement" }, "Get there by ", h("b", {}, time12(e.arrival)), " for the best chance of getting one."),
    e.arrival_reaches_target ? h("p", { class: "muted" }, `That's the latest time that still reaches the ${pct(state.data.placeholders.target_chance)} target (a placeholder).`)
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
    row("Digital lottery", p.lottery), row("Student", p.student), ...(p.other || []).map((x) => row(x.name, x))].filter(Boolean);
  return h("section", { class: "panel" }, h("h2", {}, "Rush policy"),
    rows.length ? rows : h("p", { class: "not-available" }, "No policy listed."),
    e.rush_source === "reports" ? h("p", { class: "muted" }, "This show isn't on Playbill's current in-person rush list, but recent Reddit reports describe one. Check at the box office.") : null,
    h("p", { class: "muted" }, `From Playbill's list of ${dayName(state.data.data_through.policies, { month: "short", day: "numeric", year: "numeric" })}.`));
}

function factsPanel(e) {
  const na = h("span", { class: "not-available" }, "not available");
  const item = (label, value) => [h("dt", {}, label), h("dd", {}, value || na.cloneNode(true))];
  const weeks = e.typical_ticket_weeks && e.typical_ticket_weeks < 4 ? ` (only ${e.typical_ticket_weeks} ${e.typical_ticket_weeks === 1 ? "week" : "weeks"} so far)` : "";
  return h("section", { class: "panel" }, h("h2", {}, "About this show"),
    h("dl", { class: "fact-list" },
      item("Play or musical", e.show_type),
      state.data.has_show_facts ? item("Runtime", e.runtime_detail || runtimeText(e)) : null,
      state.data.has_show_facts ? item("Days showing", e.days ? e.days.join(" ") : null) : null,
      item("Typical ticket price", e.typical_ticket !== null && e.typical_ticket !== undefined ? `${money(e.typical_ticket)}${weeks}` : null),
      item("Seats sold", e.seats_sold_pct !== null && e.seats_sold_pct !== undefined ? seatsLine(e) : null)),
    h("p", { class: "muted", style: "margin-top:8px" }, "Typical ticket price is the average paid over recent weeks, so it includes rush and discounted tickets."),
    e.facts_review ? h("p", { class: "notice" }, "We're not sure about the runtime or days for this show. Check before you plan around them.") : null,
    e.facts_source ? h("p", { class: "muted" }, `Runtime and days: ${e.facts_source}.`) : null);
}

function renderDetails(day, id, fromWeek) {
  const anyMode = day === "any";
  const entries = anyMode ? allShows() : (state.data.days[day] || []);
  const e = entries.find((x) => x.show_id === id);
  const backHref = anyMode ? "#/any" : fromWeek ? "#/week" : `#/day/${day}`;
  if (!e) {
    setApp(h("a", { class: "back", href: "#/" }, "← Back to shows"), h("p", { class: "empty" }, "That show isn't on the schedule for this day."));
    return;
  }
  const when = anyMode ? "Any day" : dayName(day, { weekday: "long", month: "long", day: "numeric" });
  const head = h("div", { class: "detail-head" },
    h("div", { style: "min-width:0" }, h("h1", {}, e.name),
      h("p", { class: "muted", style: "margin:2px 0 0" }, `${e.theater} · ${when}`),
      anyMode ? null : h("p", { class: "muted", style: "margin:0" }, e.schedule_known === false
        ? "Schedule not confirmed: this show isn't on Ticketmaster. Check before you go."
        : `Performances: ${e.performances.map(time12).join(", ") || NOT_AVAILABLE}`),
      rushLabels(e)),
    priceBlock(e));
  const back = h("a", { class: "back", href: backHref }, "← Back to shows");

  if (anyMode) {
    setApp(back, head, h("p", { class: "notice" }, "Check back within 7 days of your date for a prediction. Schedules change, so confirm before you go."),
      h("div", { class: "detail-grid", style: "margin-top:12px" },
        h("div", { class: "col" }, factsPanel(e), policyPanel(e)), h("div", { class: "col" }, savingsPanel(e), digitalPanel(e))));
    return;
  }
  if (e.group === 1) {
    const why = h("section", { class: "panel" }, h("h2", {}, "Why this prediction"),
      h("h3", {}, "The line"),
      e.drivers.line.length ? h("ul", { class: "reasons" }, e.drivers.line.map((t) => h("li", {}, t))) : h("p", { class: "muted" }, "Nothing stands out from an average day."),
      h("h3", {}, "The tickets"),
      e.drivers.tickets.length ? h("ul", { class: "reasons" }, e.drivers.tickets.map((t) => h("li", {}, t))) : h("p", { class: "muted" }, "Nothing stands out from a typical show."),
      h("p", { class: "muted" }, "Compared with an average day across shows. Built from ", String(e.data.line_points), " line reports and ", String(e.data.cutoff_days), " days with ticket information for this show."),
      h("p", { class: "muted" }, "One prediction per day: most reports don't say matinee or evening."),
      h("p", { class: "muted" }, "Want the full numbers? See ", h("a", { href: "#/nerd-stats" }, "Nerd stats"), "."));
    setApp(back, head, h("div", { class: "detail-grid" },
      h("div", { class: "col" }, ticketsPanel(e), chancePanel(e), linePanel(e)),
      h("div", { class: "col" }, busiestPanel(e, day), savingsPanel(e), why, factsPanel(e), digitalPanel(e), policyPanel(e))));
    return;
  }
  const note = e.group === 2
    ? h("section", { class: "panel" }, h("h2", {}, "Limited data, probably easy"),
      h("p", {}, "Too few reports for a prediction, so there's no number here."),
      h("p", {}, seatsLine(e), "."),
      h("p", { class: "muted" }, `${e.reports_per_week} reports a week and ${e.line_reports} line reports. A full prediction needs 2 reports a week or 35 line reports.`))
    : h("section", { class: "panel" }, h("h2", {}, "No in-person rush line"),
      h("p", {}, otherOffers(e)),
      h("p", {}, seatsLine(e), "."),
      h("p", { class: "muted" }, "No line to predict. Few reports here doesn't mean low demand."));
  setApp(back, head, h("div", { class: "detail-grid" },
    h("div", { class: "col" }, note, e.group === 2 ? busiestPanel(e, day) : null, factsPanel(e), policyPanel(e)), h("div", { class: "col" }, savingsPanel(e), digitalPanel(e))));
}

/* ---------- plain charts on the show page ---------- */
const DAY_KEYS = ["M", "T", "W", "Th", "F", "S", "Su"];
const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const people = (v) => String(Math.round(v));
const median = (values) => {
  const x = [...values].sort((p, q) => p - q);
  const mid = Math.floor(x.length / 2);
  return x.length % 2 ? x[mid] : (x[mid - 1] + x[mid]) / 2;
};
function niceTicks(max) {
  const step = max <= 8 ? 2 : max <= 20 ? 5 : max <= 40 ? 10 : 20;
  const top = Math.max(step, Math.ceil(max / step) * step);
  const ticks = [];
  for (let t = 0; t <= top; t += step) ticks.push(t);
  return { top, ticks };
}
function showTip(title, rows, cx, cy) {
  tooltip.replaceChildren(h("strong", {}, title), ...rows.map((t) => h("div", { class: "tip-row" }, t)));
  tooltip.hidden = false;
  const r = tooltip.getBoundingClientRect();
  tooltip.style.left = `${Math.min(window.innerWidth - r.width - 8, Math.max(8, cx + 12))}px`;
  tooltip.style.top = `${Math.max(8, cy - r.height - 10)}px`;
}
function withTip(el, title, rows) {
  const move = (ev) => showTip(title, rows, ev.clientX, ev.clientY);
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerdown", move);
  el.addEventListener("pointerleave", () => { tooltip.hidden = true; });
  return el;
}
function legendOf(items) {
  return h("div", { class: "legend" }, items.map((x) => h("span", {},
    x.dot ? h("i", { class: `dot ${x.dot}` }) : h("i", { style: `border-color:${x.color}${x.dash ? `;border-top-style:${x.dash}` : ""}` }), x.name)));
}
function numbersTable(heads, rows) {
  return h("details", { class: "numbers" }, h("summary", {}, "See the numbers"),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, heads.map((x) => h("th", {}, x)))),
      h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c) => h("td", {}, c))))))));
}
function barRows(rows, opts = {}) {
  const max = opts.max ?? Math.max(...rows.map((r) => r.value), 1);
  const wrap = h("div", { class: "bars" });
  if (opts.ref !== undefined) wrap.style.setProperty("--ref", `${(opts.ref / max) * 100}%`);
  for (const r of rows) {
    const row = h("div", { class: `bar-row tone-${r.tone || "a"}` },
      h("div", { class: `bar-label${r.showName ? " show-name" : ""}` }, r.label, r.note ? h("small", {}, r.note) : null),
      h("div", { class: `bar-track${opts.ref !== undefined ? " has-ref" : ""}` }, h("i", { style: `width:${r.value > 0 ? Math.max(1, (r.value / max) * 100) : 0}%` })),
      h("div", { class: "bar-value" }, r.text));
    wrap.append(r.tip ? withTip(row, r.tipTitle || r.label, r.tip) : row);
  }
  return wrap;
}

function linePanel(e) {
  const all = e.chance_by_time;
  const iArrival = all.findIndex((p) => p.time === e.arrival);
  const start = Math.max(0, iArrival < 0 ? all.length - 16 : Math.min(all.length - 16, iArrival));
  const curve = all.slice(start);
  const at = iArrival >= 0 ? all[iArrival] : null;
  const { top, ticks } = niceTicks(Math.max(...curve.map((p) => p.line_hi)));
  const holder = h("div", { class: "chart" });
  lineChart(holder, {
    x: curve.map((p) => time12(p.time)),
    series: [{ name: "People in line", color: "var(--series-1)", values: curve.map((p) => p.line) }],
    band: { lo: curve.map((p) => p.line_lo), hi: curve.map((p) => p.line_hi), color: "var(--series-1)" },
    yMax: top, yTicks: ticks, height: 220, labelEvery: 4, yTitle: "People in line",
    marks: at ? [{ i: iArrival - start, label: `${time12(e.arrival)}: about ${people(at.line)}` }] : [],
    tipRows: (i) => [`About ${people(curve[i].line)} people`, `Likely ${people(curve[i].line_lo)} to ${people(curve[i].line_hi)}`],
  });
  return h("section", { class: "panel" }, h("h2", {}, "How the line builds"),
    at ? h("p", {}, `If you get there by ${time12(e.arrival)}, expect about ${people(at.line)} people ahead of you (likely ${people(at.line_lo)} to ${people(at.line_hi)}).`) : null,
    holder,
    h("p", { class: "muted", style: "margin-top:6px" }, `The shaded band is where we expect the line about 8 times in 10. Box office opens ${time12(e.open_time)}.`));
}

function busiestPanel(e, day) {
  const ch = state.data.charts;
  const cells = ch && ch.show_days[e.show_id];
  if (!cells) return null;
  const shown = cells.map((x, i) => ({ ...x, i, dark: Boolean(e.days && !e.days.includes(DAY_KEYS[i])) }));
  const known = shown.filter((x) => x.typical !== null && !x.dark);
  if (known.length < 3) return null;
  const picked = (parseDay(day).getDay() + 6) % 7;
  const top = Math.max(...known.map((x) => x.typical), 1);
  const busiest = known.reduce((a, b) => (b.typical > a.typical ? b : a));
  const bars = shown.map((x) => {
    const has = x.typical !== null && !x.dark;
    const tip = x.dark ? "Not playing" : (has ? `About ${people(x.typical)} people, from ${x.days} past days` : `Too few past reports (${x.days} days)`);
    return withTip(h("div", { class: `day-bar${x.i === picked ? " picked" : ""}` },
      h("span", { class: "day-val" }, has ? people(x.typical) : "–"),
      h("span", { class: "day-track" }, h("i", { style: `height:${has ? Math.max(4, (x.typical / top) * 100) : 0}%` })),
      h("span", { class: "day-name" }, DAY_SHORT[x.i])), DAY_LONG[x.i], [tip]);
  });
  return h("section", { class: "panel" }, h("h2", {}, "Which days are busiest"),
    h("p", {}, `${DAY_LONG[busiest.i]} is usually the longest, at about ${people(busiest.typical)} people.`),
    h("div", { class: "day-bars", role: "img", "aria-label": shown.map((x) => `${DAY_LONG[x.i]}: ${x.typical !== null && !x.dark ? people(x.typical) : "no number"}`).join(", ") }, bars),
    h("p", { class: "muted", style: "margin-top:6px" }, `Typical line in the last ${ch.near_opening_hours} hours before the box office opens, from past reports. Gold is the day you picked. A dash means it's not playing or there are too few reports.`));
}

function savingsPanel(e) {
  if (!e.price || !e.typical_ticket) return null;
  const save = e.typical_ticket - e.price;
  return h("section", { class: "panel" }, h("h2", {}, "What you'd save"),
    h("p", { class: "statement" }, save > 0 ? ["About ", h("b", {}, money(save)), " less than a typical ticket."] : "Rush isn't cheaper than a typical ticket right now."),
    barRows([
      { label: "Rush", note: e.price_note, value: e.price, text: money(e.price), tone: "gold" },
      { label: "Typical ticket", value: e.typical_ticket, text: money(e.typical_ticket), tone: "gray" },
    ]),
    h("p", { class: "muted", style: "margin-top:6px" }, "Typical ticket is the average paid over recent weeks, so it already includes rush and discounts."));
}

/* ---------- Nerd stats: the full numbers, organized by question ---------- */
function bestClass(a, b, smallerIsBetter = true) {
  if (a === null || b === null || a === undefined || b === undefined || a === b) return [null, null];
  const aWins = smallerIsBetter ? a < b : a > b;
  return aWins ? ["best", null] : [null, "best"];
}
const NS_SECTIONS = [
  ["ns-summary", "Short version"], ["ns-lines", "How lines behave"], ["ns-data", "The data"],
  ["ns-model", "The model"], ["ns-tests", "How good is it?"], ["ns-truth", "Model vs. ground truth"],
];
function nsSection(id, title, intro, ...panels) {
  return h("section", { id, class: "ns-section" }, h("h2", {}, title), intro ? h("p", { class: "lede" }, intro) : null,
    h("div", { class: "accuracy-grid" }, panels));
}
function nsPanel(title, takeaway, ...body) {
  return h("section", { class: "panel" }, h("h3", {}, title), takeaway ? h("p", {}, takeaway) : null, ...body);
}

function growthPanel(ch) {
  const g = ch.line_growth;
  const labels = g.bands.map((b) => (b.from >= 1 ? `${b.from}h` : `${b.from * 60}m`));
  const span = (b) => `${b.from} to ${b.to} hours before opening`;
  const vals = (key) => g[key].map((x) => x.average);
  const { top, ticks } = niceTicks(Math.max(...vals("weekday"), ...vals("weekend")));
  const holder = h("div", { class: "chart" });
  lineChart(holder, {
    x: labels, height: 250, labelEvery: 2, markers: true, yMax: top, yTicks: ticks,
    yTitle: "Average people in line", xTitle: "Time before the box office opens",
    series: [
      { name: "Weekends", color: "var(--series-1)", values: vals("weekend") },
      { name: "Weekdays", color: "var(--series-2)", dash: "6 4", values: vals("weekday") },
    ],
    tipRows: (i) => [span(g.bands[i]), `Weekends: ${num(g.weekend[i].average, 1)} (${g.weekend[i].reports} reports)`, `Weekdays: ${num(g.weekday[i].average, 1)} (${g.weekday[i].reports} reports)`],
  });
  const near = g.bands.findIndex((b) => b.to === 2);
  const last = g.bands.length - 1;
  return nsPanel("How fast does the line grow?",
    `Weekdays go from about ${people(g.weekday[near].average)} people 2 hours before opening to about ${people(g.weekday[last].average)} in the last half hour. Weekends go from about ${people(g.weekend[near].average)} to about ${people(g.weekend[last].average)}.`,
    legendOf([{ name: "Weekends", color: "var(--series-1)" }, { name: "Weekdays", color: "var(--series-2)", dash: "dashed" }]),
    holder,
    h("p", { class: "muted", style: "margin-top:6px" }, "Each day counts once, however many people posted. This is what people reported, so it describes people who post on Reddit."),
    numbersTable(["Before opening", "Weekends", "Reports", "Weekdays", "Reports"],
      g.bands.map((b, i) => [`${b.from} to ${b.to} hrs`, num(g.weekend[i].average, 1), String(g.weekend[i].reports), num(g.weekday[i].average, 1), String(g.weekday[i].reports)])));
}

function heatPanel(ch, entries) {
  const edges = [5, 10, 15, 20];
  const heat = (v) => 1 + edges.filter((x) => v >= x).length;
  const rows = [];
  const left = [];
  for (const e of entries.filter((x) => x.group === 1)) {
    const cells = (ch.show_days[e.show_id] || []).map((x, i) => ({ ...x, i, dark: Boolean(e.days && !e.days.includes(DAY_KEYS[i])) }));
    const known = cells.filter((x) => x.typical !== null && !x.dark);
    if (known.length < 3) { left.push(e.name); continue; }
    rows.push({ e, cells, known, mean: known.reduce((a, x) => a + x.typical, 0) / known.length });
  }
  rows.sort((a, b) => b.mean - a.mean);
  const flat = rows.flatMap((r) => r.known.map((x) => ({ name: r.e.name, ...x })));
  const hi = flat.reduce((a, b) => (b.typical > a.typical ? b : a));
  const lo = flat.reduce((a, b) => (b.typical < a.typical ? b : a));
  const table = h("div", { class: "table-wrap" }, h("table", { class: "heat" },
    h("thead", {}, h("tr", {}, h("th", {}, "Show"), DAY_KEYS.map((d) => h("th", {}, d)))),
    h("tbody", {}, rows.map((r) => h("tr", {},
      h("th", { scope: "row", class: "show-name" }, r.e.name),
      r.cells.map((x) => {
        const has = x.typical !== null && !x.dark;
        const tip = x.dark ? "Not playing" : (has ? `Typically ${people(x.typical)} people, from ${x.days} past days` : `Too few past reports (${x.days} days)`);
        return withTip(h("td", { class: has ? `heat-${heat(x.typical)}` : "heat-0" }, has ? people(x.typical) : "–"), `${r.e.name}, ${DAY_LONG[x.i]}`, [tip]);
      }))))));
  const key = h("div", { class: "heat-key" }, ["Under 5", "5–9", "10–14", "15–19", "20+"].map((t, i) => h("span", {}, h("i", { class: `heat-${i + 1}` }), t)));
  return nsPanel("Which shows and days are busiest?",
    `Longest: ${hi.name} on ${DAY_LONG[hi.i]}, about ${people(hi.typical)} people. Shortest: ${lo.name} on ${DAY_LONG[lo.i]}, about ${people(lo.typical)}.`,
    key, table,
    h("p", { class: "muted", style: "margin-top:8px" }, `Typical people in line in the last ${ch.near_opening_hours} hours before opening. A dash means it's not playing now or has fewer than ${ch.min_days_per_cell} past days of reports.${left.length ? ` Too few reports to list: ${left.join(", ")}.` : ""}`));
}

function savingsChart(entries) {
  const rows = entries.filter((e) => e.group !== 3 && e.price && e.typical_ticket)
    .map((e) => ({ e, save: e.typical_ticket - e.price })).sort((a, b) => b.save - a.save);
  if (!rows.length) return null;
  const max = Math.ceil(Math.max(...rows.map((r) => r.e.typical_ticket)) / 50) * 50;
  const at = (v) => `${(v / max) * 100}%`;
  const axis = [];
  for (let t = 0; t <= max; t += 100) axis.push(h("span", { style: `left:${at(t)}` }, `$${t}`));
  const list = h("div", { class: "dumbbells" },
    h("div", { class: "dumb-row dumb-head" }, h("div", {}), h("div", { class: "dumb-axis" }, axis), h("div", { class: "dumb-save" }, "Save")),
    rows.map(({ e, save }) => withTip(h("div", { class: "dumb-row" },
      h("div", { class: "bar-label show-name" }, e.name),
      h("div", { class: "dumb-track" },
        h("span", { class: "dumb-link", style: `left:${at(Math.min(e.price, e.typical_ticket))};width:${at(Math.abs(save))}` }),
        h("span", { class: "dumb-dot rush", style: `left:${at(e.price)}` }),
        h("span", { class: "dumb-dot typical", style: `left:${at(e.typical_ticket)}` })),
      h("div", { class: "dumb-save" }, money(save))), e.name, [`Rush ${money(e.price)}${e.price_note ? ` (${e.price_note})` : ""}`, `Typical ticket ${money(e.typical_ticket)}`, `Saves ${money(save)}`])));
  return nsPanel("How much does rush save?",
    `Across ${rows.length} shows, rush typically costs ${money(median(rows.map((r) => r.e.price)))} against ${money(median(rows.map((r) => r.e.typical_ticket)))} for a typical ticket, about ${money(median(rows.map((r) => r.save)))} less.`,
    legendOf([{ name: "Rush price", dot: "rush" }, { name: "Typical ticket", dot: "typical" }]),
    list,
    h("p", { class: "muted", style: "margin-top:8px" }, "Shows with in-person rush and both prices known. Typical ticket is the average paid over recent weeks, so it already includes rush and discounts. The gap to a regular seat is usually bigger."),
    numbersTable(["Show", "Rush", "Typical ticket", "Saves"], rows.map(({ e, save }) => [e.name, money(e.price), money(e.typical_ticket), money(save)])));
}

function funnelPanel(f) {
  const steps = [
    ["Rush reports after the AI check", f.all_observations],
    ["About in-person general rush", f.in_person_general_rush],
    ["Tied to a Broadway show", f.mapped_to_a_broadway_show],
    ["Confident enough to use", f.not_low_confidence],
    ["Clear date, June 2024 or later", f.stated_valid_date_from_june_2024],
    ["Date close to when it was posted", f.date_within_2_days_before_to_14_days_after_the_comment],
    ["Date inside the show's run", f.date_inside_the_shows_run],
    ["Gives both a time and a line count", f.line_points_with_a_time_and_number],
    ["Before the box office opened", f.line_points_before_opening],
    ["After removing duplicates", f.line_points_after_dropping_duplicates],
  ];
  const rows = steps.map(([label, n], i) => ({
    label, value: n, text: n.toLocaleString(), tone: i === steps.length - 1 ? "gold" : "a",
    note: i ? `${(steps[i - 1][1] - n).toLocaleString()} removed` : null,
  }));
  return nsPanel("From Reddit comments to usable reports",
    `We scanned ${f.comments_scanned.toLocaleString()} Reddit comments and forum posts. A first AI pass and a second one that checked its work left ${f.all_observations.toLocaleString()} rush reports, and ${f.line_points_after_dropping_duplicates.toLocaleString()} passed every check to become line reports.`,
    barRows(rows),
    h("p", { class: "muted", style: "margin-top:8px" }, `The model also uses ${f.cutoff_show_days.toLocaleString()} show-days with ticket information (${f.cutoff_stated_count} stated counts, the rest only "at least" or "at most") and ${f.outcomes_arrived_before_opening_known_result} attempts with a known result. Reports run from ${dayName(f.first_date, { month: "short", year: "numeric" })} to ${dayName(f.last_date, { month: "short", year: "numeric" })}.`));
}

function reportsPanel(ch, entries) {
  const list = entries.filter((e) => e.group !== 3).sort((a, b) => b.line_reports - a.line_reports);
  const full = list.filter((e) => e.group === 1).length;
  const rule = ch.full_prediction_rule;
  return nsPanel("How many reports does each show have?",
    `${full} of ${list.length} shows with in-person rush get a full prediction. That takes ${rule.line_reports} line reports or ${rule.reports_per_week} reports a week.`,
    legendOf([{ name: "Full prediction", dot: "bar-a" }, { name: "Not enough reports", dot: "bar-gray" }, { name: `${rule.line_reports} line reports`, color: "var(--ink-2)", dash: "dotted" }]),
    barRows(list.map((e) => ({
      label: e.name, showName: true, value: e.line_reports, text: String(e.line_reports), tone: e.group === 1 ? "a" : "gray",
      tip: [`${e.line_reports} line reports`, `${e.reports_per_week} reports a week`, e.group === 1 ? "Full prediction" : "Not enough reports"],
    })), { ref: rule.line_reports }),
    h("p", { class: "muted", style: "margin-top:8px" }, "In the tests, shows with 10 to 34 earlier line reports lost to the lookup table, and shows with 35 or more beat it. That's where the rule comes from."));
}

function driversPanel(ch) {
  const rows = ch.drivers;
  return nsPanel("What moves the line most?",
    `${rows[0].name} matters most: it typically moves the prediction by ×${rows[0].factor.toFixed(2)}. Next come ${rows[1].name.toLowerCase()} (×${rows[1].factor.toFixed(2)}) and ${rows[2].name.toLowerCase()} (×${rows[2].factor.toFixed(2)}).`,
    barRows(rows.map((r) => ({ label: r.name, value: Math.log(r.factor), text: `×${r.factor.toFixed(2)}`, tip: [`Typically moves the prediction by ×${r.factor.toFixed(2)}`] }))),
    h("p", { class: "muted", style: "margin-top:8px" }, "Average push across every report in the line model, up or down. Things that rarely happen, like holidays, look small here even when they matter a lot on the day."));
}

function methodPanel(a) {
  const m = state.data.model;
  return nsPanel("How it's built", null,
    h("ul", { class: "reasons" },
      h("li", {}, h("b", {}, "The line: "), `${m.line}, predicting people in line from the time you arrive, the show, the day and recent demand. The line can only grow toward opening, because the model is built that way. Spread comes from a negative binomial fit (${m.line_spread}).`),
      h("li", {}, h("b", {}, "The tickets: "), `${m.cutoff}, because most reports only say "at least" or "at most" so many tickets. Shows share information, so thin shows lean on the rest.`),
      h("li", {}, h("b", {}, "The chance: "), `every 15 minutes, the share of ticket scenarios where your place in line still gets a ticket. Each person ahead counts as ${a.per_person} ${a.per_person === 1 ? "ticket" : "tickets"}, the best of the values tried.`),
      h("li", {}, h("b", {}, "No peeking: "), "inputs are only what's known a week ahead, grosses are at least 9 days old, and each test month trains only on earlier months."),
      h("li", {}, h("b", {}, "Sampler checks: "), `${m.fit.replace("faster fit: ", "")}. Largest R-hat ${m.cutoff_checks.max_r_hat} (want close to 1), ${m.cutoff_checks.divergences} divergences (want few).`)),
    m.fallback_used ? h("p", { class: "notice strong" }, "This run used the fallback cutoff, not the Bayesian model.") : null);
}

function predictedPanel(ch) {
  const p = ch.predicted_vs_real;
  if (!p) return null;
  const { top, ticks } = niceTicks(Math.max(...p.bands.flatMap((b) => [b.combo.real, b.lookup.real, b.to].filter((v) => v !== null))));
  const holder = h("div", { class: "chart" });
  lineChart(holder, {
    x: p.bands.map((b) => `${b.from}–${b.to}`), height: 260, labelEvery: 2, markers: true, yMax: top, yTicks: ticks,
    yTitle: "Real line (median people)", xTitle: "Predicted people in line",
    series: [
      { name: "Model", color: "var(--series-1)", values: p.bands.map((b) => b.combo.real) },
      { name: "Lookup table", color: "var(--series-2)", dash: "6 4", values: p.bands.map((b) => b.lookup.real) },
      { name: "Perfect", color: "var(--ink-3)", dash: "2 4", values: p.bands.map((b) => (b.from + b.to) / 2), noMarkers: true },
    ],
    tipRows: (i) => {
      const b = p.bands[i];
      return [`Model: real line ${b.combo.real ?? "too few"} (${b.combo.reports} reports)`, `Lookup: real line ${b.lookup.real ?? "too few"} (${b.lookup.reports} reports)`];
    },
  });
  const lastBoth = [...p.bands].reverse().find((b) => b.combo.real !== null && b.lookup.real !== null);
  return nsPanel("When we predict a line, how long is it really?",
    `Closer to the dotted line is better. When the model predicts ${lastBoth.from}–${lastBoth.to} people, the real line is about ${people(lastBoth.combo.real)}. When the lookup table predicts the same, it's about ${people(lastBoth.lookup.real)}. Correlation with the real line: ${p.correlation.combo} for the model, ${p.correlation.lookup} for the lookup table.`,
    legendOf([{ name: "Model", color: "var(--series-1)" }, { name: "Lookup table", color: "var(--series-2)", dash: "dashed" }, { name: "Perfect", color: "var(--ink-3)", dash: "dotted" }]),
    holder,
    h("p", { class: "muted", style: "margin-top:6px" }, `${p.reports.toLocaleString()} line reports from the test months. Predictions of ${p.bands[p.bands.length - 1].to} or more aren't drawn (${p.above_top.combo} for the model, ${p.above_top.lookup} for the lookup table). Bands with under 10 reports are left out.`),
    numbersTable(["Predicted", "Model: real", "Reports", "Lookup: real", "Reports"],
      p.bands.map((b) => [`${b.from}–${b.to}`, b.combo.real ?? "–", String(b.combo.reports), b.lookup.real ?? "–", String(b.lookup.reports)])));
}

function calibrationPanel(a) {
  const all = a.calibration_combo;
  const bins = all.filter((b) => b.attempts >= 5);
  const label = (b) => `${Math.round(b.from * 100)}–${Math.round(b.to * 100)}%`;
  const biggest = bins.reduce((x, y) => (y.attempts > x.attempts ? y : x));
  const worst = bins.reduce((x, y) => (y.share_got - y.mean_chance < x.share_got - x.mean_chance ? y : x));
  const overconfident = worst.mean_chance - worst.share_got > 0.05;
  const holder = h("div", { class: "chart" });
  lineChart(holder, {
    x: bins.map(label), height: 250, markers: true, yMax: 100, yTicks: [0, 25, 50, 75, 100], ySuffix: "%",
    yTitle: "Got a ticket", xTitle: "What we said",
    series: [
      { name: "What happened", color: "var(--series-1)", values: bins.map((b) => b.share_got * 100) },
      { name: "If we were perfect", color: "var(--ink-3)", dash: "2 4", values: bins.map((b) => b.mean_chance * 100), noMarkers: true },
    ],
    tipRows: (i) => [`We said ${pct(bins[i].mean_chance)} on average`, `${pct(bins[i].share_got)} got a ticket`, `${bins[i].attempts} attempts`],
  });
  return nsPanel("When we say a chance, does it come true?",
    `When we said about ${pct(biggest.mean_chance)}, ${pct(biggest.share_got)} of people got a ticket (${biggest.attempts} attempts).${overconfident ? ` The weak spot: when we said about ${pct(worst.mean_chance)}, only ${pct(worst.share_got)} did (${worst.attempts} attempts).` : ""} Above the dotted line means more people got tickets than we said.`,
    legendOf([{ name: "What happened", color: "var(--series-1)" }, { name: "If we were perfect", color: "var(--ink-3)", dash: "dotted" }]),
    holder,
    h("p", { class: "muted", style: "margin-top:6px" }, "People mostly post their wins, so the real share who got tickets is probably lower than this. Bands with under 5 attempts are in the table but not drawn."),
    numbersTable(["We said", "On average", "Got a ticket", "Attempts"], all.map((b) => [label(b), pct(b.mean_chance), pct(b.share_got), String(b.attempts)])));
}

/* ---------- Model vs. ground truth: every test result next to what really happened ---------- */
function scatterChart(holder, cfg) {
  const full = { ...cfg, draw: drawScatter };
  charts.push({ holder, cfg: full });
  requestAnimationFrame(() => drawScatter(holder, full));
  return full;
}
/* Same offsets every time, so dots don't jump around when the page redraws */
const nudge = (i, salt) => (((i + 1) * (salt ? 0.7548776662 : 0.5698402910)) % 1) - 0.5;
function drawScatter(holder, cfg) {
  if (!holder.isConnected) return;
  const width = Math.max(240, holder.clientWidth || 320);
  const m = { top: cfg.yTitle ? 30 : 14, right: 14, bottom: 42, left: cfg.yLabels ? 92 : 40 };
  const height = cfg.height || Math.min(430, Math.round((width - m.left - m.right) * 0.86) + m.top + m.bottom);
  const w = width - m.left - m.right, ht = height - m.top - m.bottom;
  const xPos = (v) => m.left + (v / cfg.xMax) * w;
  const yPos = (v) => m.top + ht - (v / cfg.yMax) * ht;
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img", "aria-label": cfg.label });
  for (const t of cfg.xTicks) {
    svg.append(s("line", { x1: xPos(t), x2: xPos(t), y1: m.top, y2: m.top + ht, stroke: "var(--line)", "stroke-width": 1, opacity: 0.4 }));
    svg.append(s("text", { x: xPos(t), y: height - 24, "text-anchor": "middle" }, `${t}${cfg.xSuffix || ""}`));
  }
  if (cfg.yLabels) {
    for (const row of cfg.yLabels) svg.append(s("text", { x: m.left - 8, y: yPos(row.y) + 4, "text-anchor": "end", class: "value-label" }, row.label));
  } else {
    for (const t of cfg.yTicks) {
      svg.append(s("line", { x1: m.left, x2: width - m.right, y1: yPos(t), y2: yPos(t), stroke: "var(--line)", "stroke-width": 1, opacity: 0.4 }));
      svg.append(s("text", { x: m.left - 6, y: yPos(t) + 4, "text-anchor": "end" }, String(t)));
    }
  }
  if (cfg.yTitle) svg.append(s("text", { x: 0, y: 12, class: "axis-title" }, cfg.yTitle));
  svg.append(s("text", { x: m.left + w / 2, y: height - 4, "text-anchor": "middle", class: "axis-title" }, cfg.xTitle));
  if (cfg.identity) {
    const end = Math.min(cfg.xMax, cfg.yMax);
    svg.append(s("line", { x1: xPos(0), y1: yPos(0), x2: xPos(end), y2: yPos(end), stroke: "var(--ink-2)", "stroke-width": 1.5, "stroke-dasharray": "2 4" }));
  }
  const spots = cfg.points.map((p) => ({ p, cx: xPos(p.x), cy: yPos(p.y) }));
  for (const d of spots) svg.append(s("circle", { class: "dot", cx: d.cx.toFixed(1), cy: d.cy.toFixed(1), r: cfg.radius || 2.4, fill: cfg.color, "fill-opacity": cfg.opacity || 0.5 }));
  const ring = s("circle", { r: (cfg.radius || 2.4) + 4, fill: "none", stroke: "var(--ink)", "stroke-width": 2, visibility: "hidden" });
  svg.append(ring);
  const hit = s("rect", { x: m.left - 8, y: 0, width: w + 22, height, fill: "transparent" });
  const hide = () => { ring.setAttribute("visibility", "hidden"); tooltip.hidden = true; };
  const seek = (ev) => {
    const box = svg.getBoundingClientRect();
    const scale = width / box.width;
    const px = (ev.clientX - box.left) * scale, py = (ev.clientY - box.top) * scale;
    let best = null, bestGap = 26 * 26;
    for (const d of spots) {
      const gap = (d.cx - px) ** 2 + (d.cy - py) ** 2;
      if (gap < bestGap) { best = d; bestGap = gap; }
    }
    if (!best) { hide(); return; }
    ring.setAttribute("cx", best.cx); ring.setAttribute("cy", best.cy); ring.setAttribute("visibility", "visible");
    showTip(best.p.title, best.p.rows, ev.clientX, ev.clientY);
  };
  hit.addEventListener("pointermove", seek);
  hit.addEventListener("pointerdown", seek);
  hit.addEventListener("pointerleave", hide);
  svg.append(hit);
  holder.replaceChildren(svg);
}
function methodToggle(onChange) {
  const buttons = [["combo", "Model"], ["lookup", "Lookup table"]].map(([key, name], i) => h("button", {
    type: "button", class: "chip", "aria-pressed": i === 0 ? "true" : "false",
    onclick: (ev) => {
      for (const b of buttons) b.setAttribute("aria-pressed", "false");
      ev.currentTarget.setAttribute("aria-pressed", "true");
      onChange(key);
    },
  }, name));
  return h("div", { class: "control-row method-toggle", role: "group", "aria-label": "Which predictions to show" }, buttons);
}
const METHOD_COLOR = { combo: "var(--gold)", lookup: "var(--series-2-light)" };
const METHOD_NAME = { combo: "Model", lookup: "Lookup table" };
function beforeOpening(hours) {
  const mins = Math.round(hours * 60);
  const hh = Math.floor(mins / 60), mm = mins % 60;
  return `${hh ? `${hh}h ` : ""}${mm || !hh ? `${mm}m` : ""}`.trim();
}
const shortDate = (d) => dayName(d, { month: "short", day: "numeric", year: "numeric" });
const OUTCOME_NAMES = { got_rush: "Got rush", sro_only: "Only standing room left", sold_out_before_me: "Sold out first", full_price_only: "Only full price left" };
const trimNum = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

function truthLinePanel(r) {
  const top = 60;
  const rows = r.line.rows;
  const over = rows.filter((x) => x[3] > top).length;
  const holder = h("div", { class: "chart" });
  const points = (key) => rows.map((x, i) => ({ x, i })).filter(({ x }) => x[3] <= top && x[key === "combo" ? 4 : 7] <= top).map(({ x, i }) => {
    const said = x[key === "combo" ? 4 : 7];
    return {
      x: Math.min(top, Math.max(0, said + nudge(i, 0) * 0.7)), y: Math.min(top, Math.max(0, x[3] + nudge(i, 1) * 0.7)),
      title: r.shows[x[0]],
      rows: [`${shortDate(x[1])}, ${beforeOpening(x[2])} before opening`, `${METHOD_NAME[key]} said ${trimNum(said)} people`, `Real line: ${x[3]}`],
    };
  });
  const cfg = scatterChart(holder, {
    label: "Predicted line against the real line for every test report", points: points("combo"), color: METHOD_COLOR.combo, opacity: 0.45,
    xMax: top, yMax: top, xTicks: [0, 20, 40, 60], yTicks: [0, 20, 40, 60], identity: true,
    xTitle: "Predicted people in line", yTitle: "Real people in line",
  });
  const toggle = methodToggle((key) => { cfg.points = points(key); cfg.color = METHOD_COLOR[key]; drawScatter(holder, cfg); });
  const t = r.line.summary;
  return nsPanel("The line: every test report",
    `The model was within 3 people ${pct(t.within3.combo)} of the time, and the lookup table ${pct(t.within3.lookup)}. Within 5 people: ${pct(t.within5.combo)} vs. ${pct(t.within5.lookup)}. Switch between them to compare.`,
    toggle, holder,
    h("p", { class: "muted", style: "margin-top:6px" }, `${rows.length.toLocaleString()} reports. A dot on the dotted line is a perfect prediction; above it, the real line was longer than predicted. Dots are nudged slightly so they don't hide each other.${over ? ` ${over} report${over === 1 ? "" : "s"} over ${top} people ${over === 1 ? "isn't" : "aren't"} drawn.` : ""}`));
}

function truthTicketsPanel(r) {
  const rows = r.tickets.rows;
  const { top, ticks } = niceTicks(Math.max(...rows.flatMap((x) => [x[2], x[3], x[6]])));
  const holder = h("div", { class: "chart" });
  const points = (key) => rows.map((x) => {
    const said = x[key === "combo" ? 3 : 6];
    return {
      x: said, y: x[2], title: r.shows[x[0]],
      rows: [shortDate(x[1]), `${METHOD_NAME[key]} said ${trimNum(said)} tickets`, key === "combo" ? `80% range: ${trimNum(x[4])} to ${trimNum(x[5])}` : null, `Stated: ${trimNum(x[2])}`].filter(Boolean),
    };
  });
  const cfg = scatterChart(holder, {
    label: "Predicted tickets against stated ticket counts", points: points("combo"), color: METHOD_COLOR.combo, opacity: 0.8, radius: 4,
    xMax: top, yMax: top, xTicks: ticks, yTicks: ticks, identity: true,
    xTitle: "Predicted rush tickets", yTitle: "Tickets people said there were",
  });
  const toggle = methodToggle((key) => { cfg.points = points(key); cfg.color = METHOD_COLOR[key]; drawScatter(holder, cfg); });
  const f = r.tickets.at_least;
  return nsPanel("The tickets: every stated count",
    `On the ${rows.length} days someone stated a count, the model's middle estimate was ${trimNum(median(rows.map((x) => x[3])))} against a stated ${trimNum(median(rows.map((x) => x[2])))}, so it looks too high. But on the ${f.days} days people only said "at least" so many, it cleared that minimum ${pct(f.combo)} of the time, and the lookup table ${pct(f.lookup)}.`,
    toggle, holder,
    h("p", { class: "muted", style: "margin-top:6px" }, "People may mention an exact count more often when it's small, so neither view is the whole story. Dots right of the dotted line mean we predicted more tickets than people said."));
}

function truthAttemptsPanel(r) {
  const rows = r.attempts.rows;
  const holder = h("div", { class: "chart" });
  const points = (key) => rows.map((x, i) => {
    const got = x[3] === "got_rush";
    const chance = x[key === "combo" ? 4 : 5];
    return {
      x: chance * 100, y: (got ? 1.2 : 0.4) + nudge(i, 1) * 0.6, title: r.shows[x[0]],
      rows: [`${shortDate(x[1])}, arrived ${beforeOpening(x[2])} before opening`, `${METHOD_NAME[key]} said ${pct(chance)}`, OUTCOME_NAMES[x[3]] || x[3]],
    };
  });
  const cfg = scatterChart(holder, {
    label: "Chance given to each attempt, split by whether the person got a ticket", points: points("combo"), color: METHOD_COLOR.combo, opacity: 0.7, radius: 3.5,
    xMax: 100, yMax: 1.6, xTicks: [0, 25, 50, 75, 100], xSuffix: "%", yTicks: [], height: 220,
    yLabels: [{ y: 1.2, label: "Got a ticket" }, { y: 0.4, label: "Missed" }], xTitle: "Chance we gave them",
  });
  const toggle = methodToggle((key) => { cfg.points = points(key); cfg.color = METHOD_COLOR[key]; drawScatter(holder, cfg); });
  const got = rows.filter((x) => x[3] === "got_rush");
  const missed = rows.filter((x) => x[3] !== "got_rush");
  const avg = (list, k) => list.reduce((a, x) => a + x[k], 0) / list.length;
  const kinds = Object.entries(OUTCOME_NAMES).filter(([k]) => k !== "got_rush")
    .map(([k, name]) => [missed.filter((x) => x[3] === k).length, name.toLowerCase()]).filter(([n]) => n);
  const panel = nsPanel("Got a ticket or not: every attempt",
    `The model gave people who got a ticket an average chance of ${pct(avg(got, 4))}, and people who missed ${pct(avg(missed, 4))}. The bigger the gap between the two rows, the better. Of the ${missed.length} misses: ${kinds.map(([n, name]) => `${n} ${name}`).join(", ")}.`,
    toggle, holder,
    h("p", { class: "muted", style: "margin-top:6px" }, `${rows.length} attempts where the person said what happened. Losses are under-reported, so real misses are probably more common than this.`));
  panel.classList.add("wide");
  return panel;
}

function modelCell(value, lo, hi) {
  return [trimNum(value), h("small", {}, `${trimNum(lo)}–${trimNum(hi)}`)];
}
function truthBrowser(r) {
  const view = { set: "line", show: "", month: "", sort: "miss", limit: 25 };
  const body = h("div", {});
  const sets = {
    line: {
      name: "Line reports", rows: r.line.rows,
      heads: ["Show", "Model", "Lookup", "Real", "Miss"],
      when: (x) => `${shortDate(x[1])} · ${beforeOpening(x[2])} before opening`,
      miss: (x) => Math.abs(x[4] - x[3]),
      cells: (x) => [modelCell(x[4], x[5], x[6]), trimNum(x[7]), String(x[3]), trimNum(Math.abs(x[4] - x[3]))],
    },
    tickets: {
      name: "Stated ticket counts", rows: r.tickets.rows,
      heads: ["Show", "Model", "Lookup", "Stated", "Miss"],
      when: (x) => shortDate(x[1]),
      miss: (x) => Math.abs(x[3] - x[2]),
      cells: (x) => [modelCell(x[3], x[4], x[5]), trimNum(x[6]), trimNum(x[2]), trimNum(Math.abs(x[3] - x[2]))],
    },
    attempts: {
      name: "Attempts", rows: r.attempts.rows,
      heads: ["Show", "Model", "Lookup", "What happened"],
      when: (x) => `${shortDate(x[1])} · arrived ${beforeOpening(x[2])} before opening`,
      miss: (x) => Math.abs((x[3] === "got_rush" ? 1 : 0) - x[4]),
      cells: (x) => [pct(x[4]), pct(x[5]), OUTCOME_NAMES[x[3]] || x[3]],
    },
  };
  const months = [...new Set(r.line.rows.map((x) => x[1].slice(0, 7)))].sort();
  const paint = () => {
    const set = sets[view.set];
    const usedShows = [...new Set(set.rows.map((x) => x[0]))].sort((a, b) => r.shows[a].localeCompare(r.shows[b]));
    if (view.show !== "" && !usedShows.includes(Number(view.show))) view.show = "";
    const list = set.rows.filter((x) => (view.show === "" || x[0] === Number(view.show)) && (view.month === "" || x[1].startsWith(view.month)));
    const sorted = [...list].sort((a, b) => (view.sort === "miss" ? set.miss(b) - set.miss(a) : b[1].localeCompare(a[1])));
    const shown = sorted.slice(0, view.limit);
    const choose = (label, value, options, onchange) => h("label", { class: "ns-select" }, label,
      h("select", { onchange: (ev) => { onchange(ev.target.value); view.limit = 25; paint(); } },
        options.map(([v, text]) => { const o = h("option", { value: v }, text); o.selected = String(v) === String(value); return o; })));
    body.replaceChildren(
      h("div", { class: "control-row" }, Object.entries(sets).map(([k, x]) => h("button", {
        type: "button", class: "chip", "aria-pressed": view.set === k ? "true" : "false",
        onclick: () => { view.set = k; view.limit = 25; paint(); },
      }, `${x.name} (${x.rows.length.toLocaleString()})`))),
      h("div", { class: "control-row browse-filters" },
        choose("Show", view.show, [["", "All shows"], ...usedShows.map((i) => [i, r.shows[i]])], (v) => { view.show = v; }),
        choose("Month", view.month, [["", "All test months"], ...months.map((m) => [m, monthName(m)])], (v) => { view.month = v; }),
        choose("Sort", view.sort, [["miss", view.set === "attempts" ? "Biggest surprise first" : "Biggest miss first"], ["date", "Newest first"]], (v) => { view.sort = v; })),
      h("p", { class: "muted browse-count" }, list.length ? `Showing ${shown.length} of ${list.length.toLocaleString()}` : "No results match these filters."),
      list.length ? h("div", { class: "table-wrap" }, h("table", { class: "browse" },
        h("thead", {}, h("tr", {}, set.heads.map((x) => h("th", {}, x)))),
        h("tbody", {}, shown.map((x) => h("tr", {},
          h("td", {}, h("span", { class: "show-name" }, r.shows[x[0]]), h("small", {}, set.when(x))), set.cells(x).map((c) => h("td", {}, c))))))) : null,
      shown.length < list.length ? h("button", { type: "button", class: "link-button browse-more", onclick: () => { view.limit += 25; paint(); } }, `Show ${Math.min(25, list.length - shown.length)} more`) : null);
  };
  paint();
  return h("section", { class: "panel wide" }, h("h3", {}, "Look up any test result"),
    h("p", {}, "Every prediction next to what was really reported. Pick a show or month, or start with the biggest misses."),
    h("p", { class: "muted" }, "The small numbers under the model's prediction are its 80% range. Miss is how far the model was from what was reported. A big miss can mean the model was wrong or the report was: these come from Reddit comments and aren't verified."), body);
}

function truthSection(ch) {
  const r = ch.test_results;
  if (!r) return null;
  return nsSection("ns-truth", "Model vs. ground truth",
    `Every result from the test months, each predicted using only earlier days. Ground truth here means what people reported on Reddit, pulled from comments by AI and tested against human-reviewed labels. It isn't verified, and wins get posted more than losses.`,
    truthLinePanel(r), truthTicketsPanel(r), truthAttemptsPanel(r), truthBrowser(r));
}

function renderNerdStats() {
  const a = state.data.accuracy;
  const ch = state.data.charts;
  if (!a || !ch) {
    setApp(h("h1", {}, "Nerd stats"),
      h("p", { class: "empty" }, "Not available yet: the test on past months hasn't finished, and this page shows only real test results."));
    return;
  }
  const entries = allShows();
  const lc = a.line_combo, ll = a.line_lookup, tc = a.tickets_combo, tl = a.tickets_lookup;
  const cc = a.chance_combo, cl = a.chance_lookup, cb = a.chance_base_rate;
  const dev = a.months;
  const covGap = (x) => (x === null ? null : Math.abs(x - 0.8));
  const row = (label, combo, lookup, fmt, smaller = true, always = null) => {
    const [x, y] = bestClass(combo, lookup, smaller);
    return h("tr", {}, h("td", {}, label), h("td", { class: x }, fmt(combo)), h("td", { class: y }, fmt(lookup)), h("td", {}, always ?? "–"));
  };
  const plainRow = (label, combo, lookup, fmt) => h("tr", {}, h("td", {}, label), h("td", {}, fmt(combo)), h("td", {}, fmt(lookup)), h("td", {}, "–"));
  const covRow = (label, c, l) => {
    const [x, y] = bestClass(covGap(c), covGap(l));
    return h("tr", {}, h("td", {}, label), h("td", { class: x }, pct(c, 1)), h("td", { class: y }, pct(l, 1)), h("td", {}, "–"));
  };
  const table = h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Measure"), h("th", {}, state.data.model.name), h("th", {}, "Per-show lookup table"), h("th", {}, "Always say yes"))),
    h("tbody", {},
      row(`Line error, people (${lc.points} reports)`, lc.mae, ll.mae, (v) => num(v, 2)),
      covRow("80% line range held", lc.coverage80, ll.coverage80),
      plainRow("Width of that range, people", lc.width80, ll.width80, (v) => num(v, 1)),
      row("Arrival-time error, minutes", lc.arrival_error_min, ll.arrival_error_min, (v) => num(v, 0)),
      row(`Ticket error, tickets (${tc.days} stated counts)`, tc.mae, tl.mae, (v) => num(v, 2)),
      covRow("80% ticket range held", tc.coverage80, tl.coverage80),
      plainRow("Width of that range, tickets", tc.width80, tl.width80, (v) => num(v, 1)),
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
  const legend = () => legendOf([{ name: "Model", color: "var(--series-1)" }, { name: "Lookup table", color: "var(--series-2)", dash: "dashed" }]);

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
  const jump = h("nav", { class: "ns-nav", "aria-label": "Sections of this page" }, NS_SECTIONS.map(([id, name]) => h("button", {
    type: "button", class: "chip", onclick: () => document.getElementById(id).scrollIntoView({ block: "start" }),
  }, name)));

  setApp(
    h("h1", {}, "Nerd stats"),
    h("p", { class: "lede" }, `The numbers behind the predictions. Test results come from ${dev.length} past months, each predicted using only earlier days. None of this has been checked on real trips yet.`),
    jump,
    nsSection("ns-summary", "The short version",
      `Better than the simple lookup table on: ${beats.join(", ") || "none of the main measures"}. Not better on: ${loses.join(", ") || "none of them"}.`,
      h("section", { class: "panel wide" }, h("div", { class: "stat-row" },
        h("div", { class: "stat" }, h("b", {}, `${num(lc.mae, 2)} people`), h("span", {}, `average line error (lookup table: ${num(ll.mae, 2)})`)),
        h("div", { class: "stat" }, h("b", {}, pct(lc.coverage80, 1)), h("span", {}, "of real lines inside the 80% range (goal: 80%)")),
        h("div", { class: "stat" }, h("b", {}, pct(cc.accuracy_at_50, 1)), h("span", {}, `yes/no right (always saying yes: ${pct(a.always_yes_accuracy, 1)})`)),
        h("div", { class: "stat" }, h("b", {}, `${cc.misses_caught_at_50} of ${cc.misses}`), h("span", {}, "misses caught at 50%"))))),
    nsSection("ns-lines", "How rush lines behave", "From real Reddit reports, before any model.",
      growthPanel(ch), heatPanel(ch, entries), savingsChart(entries)),
    nsSection("ns-data", "Where the data comes from", null,
      funnelPanel(a.funnel), reportsPanel(ch, entries)),
    nsSection("ns-model", "What the model looks at", null,
      driversPanel(ch), methodPanel(a)),
    nsSection("ns-tests", "How good is it?", `Test months: ${dev.map(monthName).join(", ")}. ${a.locked.map(monthName).join(", ")} are locked and unscored here, so they can give the final model an honest score.`,
      nsPanel("Does it beat the simple lookup table?", null, table,
        h("p", { class: "muted", style: "margin-top:8px" }, "Gold marks the better of the model and the lookup table. For ranges, better means closer to the 80% it promises; width isn't marked, because a narrow range that doesn't hold isn't better. Ticket and outcome rows rest on few reports, so small gaps may be luck.")),
      predictedPanel(ch), calibrationPanel(a),
      nsPanel("The always-yes problem", `People mostly post their wins. Across ${a.funnel.outcomes_arrived_before_opening_known_result} attempts with a known result, ${pct(a.always_yes_all_attempts, 1)} got a ticket (${pct(a.always_yes_spec, 1)} of ${a.funnel.attempts_wider_count.toLocaleString()} on a wider count that includes reports without a stated date). On the ${cc.attempts} attempts in these tests, always saying yes is right ${pct(a.always_yes_accuracy, 1)} of the time.`,
        h("p", { class: "muted" }, "Treat this as a rough check: losses are under-reported, so no score here is the true rate."),
        h("h4", {}, "Did the verdicts work out?"),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Verdict (placeholder)"), h("th", {}, "Attempts"), h("th", {}, "Got a ticket"), h("th", {}, "Share"))),
          h("tbody", {}, vr("GO"), vr("Maybe"), vr("Stay home")))),
        h("p", { class: "muted", style: "margin-top:8px" }, `Scored on the chance at the time each person really arrived, with GO at ${pct(state.data.placeholders.go_at_or_above)} and up and Maybe at ${pct(state.data.placeholders.maybe_at_or_above)} and up.`)),
      nsPanel("Line error by test month", null,
        h("p", { class: "muted" }, "Average miss on the number of people in line. Lower is better. Gaps are the locked months."), legend(), errorChart),
      nsPanel("Did the 80% line range hold?", null,
        h("p", { class: "muted" }, "Share of real counts inside the range. The goal is 80%, not 100%. Gaps are the locked months."), legend(), coverChart),
      nsPanel("Real trips", null,
        live ? null : h("p", { class: "not-available" }, "Not available yet: no predictions have been checked against real rush days or verified reports."))),
    truthSection(ch));

  const biggestMiss = Math.max(...a.windows.flatMap((w) => [w.line_mae_combo, w.line_mae_lookup]));
  const errorTop = Math.ceil(biggestMiss / 2) * 2;
  lineChart(errorChart, {
    x: slots.map(monthName),
    series: [
      { name: "Model", color: "var(--series-1)", values: series("line_mae_combo") },
      { name: "Lookup table", color: "var(--series-2)", dash: "6 4", values: series("line_mae_lookup") },
    ],
    yMax: errorTop, yTicks: [0, errorTop / 4, errorTop / 2, (3 * errorTop) / 4, errorTop], height: 220, labelEvery: 2, markers: true, ySuffix: "",
    tipRows: (i) => (byMonth[slots[i]]
      ? [`${num(byMonth[slots[i]].line_mae_combo, 2)} Model`, `${num(byMonth[slots[i]].line_mae_lookup, 2)} Lookup table`, chartTitles(i)]
      : [chartTitles(i)]),
  });
  lineChart(coverChart, {
    x: slots.map(monthName),
    series: [
      { name: "Model", color: "var(--series-1)", values: series("line_cov_combo").map((v) => (v === null ? null : v * 100)) },
      { name: "Lookup table", color: "var(--series-2)", dash: "6 4", values: series("line_cov_lookup").map((v) => (v === null ? null : v * 100)) },
    ],
    yMax: 100, yTicks: [0, 25, 50, 80, 100], refLine: { y: 80, label: "Goal: 80%" }, ySuffix: "%", height: 220, labelEvery: 2, markers: true,
    tipRows: (i) => (byMonth[slots[i]]
      ? [`${pct(byMonth[slots[i]].line_cov_combo)} Model`, `${pct(byMonth[slots[i]].line_cov_lookup)} Lookup table`, chartTitles(i)]
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
  requestAnimationFrame(() => drawChart(holder, cfg));
}
function drawChart(holder, cfg) {
  if (!holder.isConnected) return;
  const width = Math.max(240, holder.clientWidth || 320);
  const height = cfg.height || 200;
  const m = { top: cfg.yTitle ? 30 : 14, right: 12, bottom: cfg.xTitle ? 42 : 24, left: 40 };
  const w = width - m.left - m.right, ht = height - m.top - m.bottom;
  const n = cfg.x.length;
  const xPos = (i) => m.left + (n === 1 ? 0 : (i / (n - 1)) * w);
  const yPos = (v) => m.top + ht - (v / cfg.yMax) * ht;
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img", "aria-label": cfg.series.map((x) => x.name).join(" and ") });
  for (const t of cfg.yTicks) {
    svg.append(s("line", { x1: m.left, x2: width - m.right, y1: yPos(t), y2: yPos(t), stroke: "var(--line)", "stroke-width": 1, opacity: 0.55 }));
    svg.append(s("text", { x: m.left - 6, y: yPos(t) + 4, "text-anchor": "end" }, `${t}${cfg.ySuffix || ""}`));
  }
  const step = Math.max(cfg.labelEvery || 1, Math.ceil(n / Math.max(3, Math.floor(w / 84))));
  for (let i = 0; i < n; i += step) {
    const anchor = i === 0 ? "start" : (i === n - 1 ? "end" : "middle");
    svg.append(s("text", { x: xPos(i), y: height - (cfg.xTitle ? 24 : 6), "text-anchor": anchor }, cfg.x[i]));
  }
  if (cfg.yTitle) svg.append(s("text", { x: 0, y: 12, class: "axis-title" }, cfg.yTitle));
  if (cfg.xTitle) svg.append(s("text", { x: m.left + w / 2, y: height - 4, "text-anchor": "middle", class: "axis-title" }, cfg.xTitle));
  if (cfg.band) {
    const up = cfg.band.hi.map((v, i) => `${i ? "L" : "M"}${xPos(i).toFixed(1)} ${yPos(v).toFixed(1)}`).join("");
    const down = cfg.band.lo.map((v, i) => `L${xPos(i).toFixed(1)} ${yPos(v).toFixed(1)}`).reverse().join("");
    svg.append(s("path", { d: `${up}${down}Z`, fill: cfg.band.color, opacity: 0.22, stroke: "none" }));
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
    if (cfg.markers && !ser.noMarkers) {
      ser.values.forEach((v, i) => {
        if (v === null || v === undefined) return;
        svg.append(s("circle", { cx: xPos(i), cy: yPos(v), r: 4, fill: ser.color, stroke: "var(--card)", "stroke-width": 2 }));
      });
    }
  }
  for (const mk of cfg.marks || []) {
    const v = cfg.series[0].values[mk.i];
    svg.append(s("circle", { cx: xPos(mk.i), cy: yPos(v), r: 5, fill: "var(--ink)", stroke: "var(--card)", "stroke-width": 2 }));
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
  resizeTimer = setTimeout(() => charts.forEach((c) => (c.cfg.draw || drawChart)(c.holder, c.cfg)), 120);
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
  if (parts[0] === "nerd-stats" || parts[0] === "accuracy") {
    setNav("nerd-stats");
    renderNerdStats();
  } else if (parts[0] === "show" && parts[1] && parts[2]) {
    setNav("home");
    renderDetails(parts[1], decodeURIComponent(parts[2]), parts[3] === "week");
  } else {
    setNav("home");
    renderHome(parts[0] === "any" || parts[0] === "week" ? parts[0] : (parts[0] === "day" ? parts[1] : null));
  }
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", route);

function renderFooter() {
  const d = state.data;
  footer.replaceChildren(
    h("p", {}, `${d.model.name}: ${d.model.line} for the line, ${d.model.cutoff} for the tickets. Made ${d.generated_at}. Reports through ${dayName(d.data_through.reports, { month: "short", day: "numeric" })}, grosses through ${dayName(d.data_through.grosses_week, { month: "short", day: "numeric" })}, schedule from Ticketmaster ${dayName(d.data_through.schedule, { month: "short", day: "numeric" })}.`),
    h("p", {}, `Placeholder settings, not final: GO at ${pct(d.placeholders.go_at_or_above)} and up, Maybe at ${pct(d.placeholders.maybe_at_or_above)} and up, based on the chance if you arrive at 9:00 AM. The arrival target is ${pct(d.placeholders.target_chance)}.`));
}

fetch("data/predictions.json", { cache: "no-store" })
  .then((r) => { if (!r.ok) throw new Error(`status ${r.status}`); return r.json(); })
  .then((data) => { state.data = data; renderFooter(); route(); })
  .catch((err) => {
    setApp(h("p", { class: "empty" }, `Couldn't load the predictions file (${err.message}). Start the site with a local server, not by opening the file directly.`));
  });

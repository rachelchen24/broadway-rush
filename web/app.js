/* Broadway Rush site. Reads only data/predictions.json. Never computes or invents a prediction. */
"use strict";

const state = {
  data: null, picksOnly: false, paint: null, filtersOpen: null,
  view: (() => { try { return localStorage.getItem("br-view") === "carousel" ? "carousel" : "grid"; } catch { return "grid"; } })(),
  sort: { key: "chance", reversed: false },
  weekSort: { key: "arrival", reversed: false }, // This week view: latest arrival first (SPEC 2.2b)
  filters: { rush: new Set(), type: new Set(), days: new Set(), runtime: new Set(), showtime: new Set(), star: new Set() }, // star: N13 c
};
const app = document.getElementById("app");
const footer = document.getElementById("footer");
const modal = document.getElementById("modal");
const tooltip = document.getElementById("tooltip");
const NOT_AVAILABLE = "Not available yet";
/* N13 (SPEC 2.8, Rachel's UI round 2026-11-23): one switch per lettered piece. To undo a piece, set it to false:
   its CSS only applies under body.n13-<letter> and its JS (the "N13 <letter>" sections near the end) only runs when on. */
const N13 = { a: true, b: true, c: true, d: true, e: true, f: true, g: true };
for (const [k, on] of Object.entries(N13)) if (on) document.body.classList.add(`n13-${k}`);
/* N14 (SPEC 2.8, Rachel's UI round 2, 2026-11-23): same idea. Set a piece to false to undo it; its CSS only applies
   under body.n14-<letter> and its JS ("N14 <letter>" sections near the end) only runs when on. Where N14 replaces an
   N13 piece, the N13 code stays in place and N14 takes over through these switches. */
const N14 = { a: true, b: true, c: true, d: true, e: true, f: true, g: true };
for (const [k, on] of Object.entries(N14)) if (on) document.body.classList.add(`n14-${k}`);

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
/* ---------- Links out (SPEC 2.8 N2, N4). The site only links: it never enters a lottery or fetches these pages. ---------- */
// Google Maps directions to the theater. Maps fills in the viewer's location itself; the site never asks for it.
function mapsHref(e) {
  if (!e.theater) return null;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${e.address || e.theater}, New York, NY`)}`;
}
function theaterLink(e, cls = "theater") {
  const href = mapsHref(e);
  if (!href) return null;
  return h("a", {
    class: `${cls} theater-link`, href, target: "_blank", rel: "noopener",
    title: `Directions to ${e.theater} in Google Maps (opens a new tab)`,
  }, e.theater);
}
// Playbill's "where" and "how" text is messy: a bare domain, a full address, or a sentence with an address in it.
// Take the first web address, add https:// when it's missing, and link only a plain web address. Never guess one.
const URL_RE = /((?:https?:\/\/)?(?:[a-z0-9-]+\.)+(?:com|org|net|nyc|co|us|io|info|show|theater|theatre)(?:\/[^\s,;"'()<>]*)?)/i;
function cleanUrl(text) {
  if (!text) return null;
  const m = String(text).match(URL_RE);
  if (!m) return null;
  let u = m[1].replace(/[.,;:!?]+$/, "");
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  try {
    const p = new URL(u);
    return p.protocol === "https:" || p.protocol === "http:" ? p.href : null;
  } catch { return null; }
}
// The app named in the policy text ("Available through the TodayTix app", "download the Hamilton App"). Never invented.
function appName(x) {
  const m = `${x.how || ""} ${x.where || ""} ${x.time || ""}`.match(/\bthe\s+([A-Z][A-Za-z0-9]+)\s+[Aa]pp\b/);
  return m ? m[1] : null;
}
// Order (SPEC 2.8 N4): where, then how. A hand-saved address from the show facts file is the last resort.
function offerLink(x, saved) {
  if (!x) return null;
  const url = cleanUrl(x.where) || cleanUrl(x.how) || (saved ? cleanUrl(saved) : null);
  const app = appName(x);
  if (!url && !app) return null;
  return { url, app, site: url ? siteName(url) : null };
}
function siteName(url) {
  const host = new URL(url).hostname.replace(/^www\./, "").toLowerCase();
  if (host.endsWith("todaytix.com")) return "TodayTix";
  if (host.endsWith("luckyseat.com")) return "Lucky Seat";
  if (host === "lottery.broadwaydirect.com") return "Broadway Direct";
  if (host === "rush.telecharge.com") return "Telecharge";
  return host;
}
const lotteryLink = (e) => offerLink((e.policy || {}).lottery, e.lottery_url);
const digitalLink = (e) => offerLink((e.policy || {}).digital);
// "Open TodayTix ↗ or in the TodayTix app". An app with no address gets the mention alone.
function linkLine(link, verb) {
  if (!link) return null;
  const parts = [];
  if (link.url) parts.push(h("a", { class: "out-link", href: link.url, target: "_blank", rel: "noopener" }, `${verb} on ${link.site}`, " ↗"));
  if (link.app) parts.push(link.url ? ` or in the ${link.app} app` : `In the ${link.app} app`);
  return h("p", { class: "link-line" }, parts);
}
function rushLabels(e) {
  if (!e.rush_labels || !e.rush_labels.length) return null;
  const links = { Lottery: lotteryLink(e), Online: digitalLink(e) };
  return h("div", { class: "badges" }, e.rush_labels.map((l) => {
    const cls = `rush-label${l.includes("reported") ? " reported" : ""}`;
    const link = links[l];
    if (link && link.url) {
      const what = l === "Lottery" ? "Enter the lottery" : "Online rush";
      return h("a", {
        class: `${cls} rush-link`, href: link.url, target: "_blank", rel: "noopener",
        title: `${what} on ${link.site}${link.app ? `, or in the ${link.app} app` : ""} (opens a new tab)`,
      }, l, " ↗");
    }
    return h("span", { class: cls }, l);
  }));
}

/* ---------- High-profile stars (SPEC 2.2a, 2.8 N5). Shown only once Rachel has reviewed registry/stars.csv:
   until then the predictions file has no `stars` and none of this appears. ---------- */
const LEAVING_SOON_DAYS = 14;
const dayDiff = (a, b) => Math.round((parseDay(b) - parseDay(a)) / 86400000);
// Stars in the show on that day (any day mode and the week view use today).
function starsOn(e, day) {
  const d = !day || day === "any" || day === "week" ? localToday() : day;
  return (e.stars || []).filter((x) => (!x.joined || x.joined <= d) && (!x.last_performance || x.last_performance >= d));
}
// "Key appeals" on the show page (Rachel's name, 2026-11-11): each star with role, when they joined and their final
// performance once announced, highlighted in the last 14 days; plus an announced closing date. Nothing to say, no section.
function keyAppealsPanel(e, day) {
  const d = !day || day === "any" ? localToday() : day;
  const list = starsOn(e, day);
  const closing = e.closing_date && e.closing_date >= d ? e.closing_date : null;
  if (!list.length && !closing) return null;
  return h("section", { class: "panel" }, h("h2", {}, "Key appeals"),
    list.map((x) => {
      const soon = x.last_performance && dayDiff(d, x.last_performance) <= LEAVING_SOON_DAYS;
      return h("div", { class: `appeal${soon ? " soon" : ""}` },
        h("h3", {}, "★ ", x.name, x.role ? h("span", { class: "appeal-role" }, ` as ${x.role}`) : null),
        h("p", { class: "muted" }, [
          x.joined ? `In the show since ${dayName(x.joined, { month: "long", year: "numeric" })}` : null,
          x.last_performance ? `Final performance ${dayName(x.last_performance, { month: "long", day: "numeric" })}` : "No final performance announced",
        ].filter(Boolean).join(" · ")),
        soon ? h("p", { class: "appeal-soon" }, "Leaving soon: expect bigger crowds in the last weeks.") : null);
    }),
    closing ? h("p", {}, `The show closes ${dayName(closing, { month: "long", day: "numeric", year: "numeric" })}.`) : null);
}

/* ---------- Special deals (SPEC 2.8 N10): flagged on the site, never in the model ---------- */
// Standing deals come from Playbill's policy list (policy.other). Dated deals come from registry/special_deals.csv
// through the predictions file (special_deals, with start and end dates).
function dealsFor(e, day) {
  const list = ((e.policy || {}).other || []).map((x) => ({ ...x, standing: true, link: offerLink(x) }));
  for (const x of e.special_deals || []) {
    if (day && day !== "any" && day !== "week" && ((x.start && day < x.start) || (x.end && day > x.end))) continue;
    list.push({ name: x.name, how: x.detail, price: x.price, start: x.start, end: x.end, today: true,
      link: x.url ? { url: cleanUrl(x.url), site: cleanUrl(x.url) ? siteName(cleanUrl(x.url)) : null } : null });
  }
  return list;
}
function dealBadge(e, day) {
  const deals = dealsFor(e, day);
  if (!deals.length) return null;
  const dated = deals.filter((x) => x.today);
  const text = dated.length ? `Special deal today: ${dated.map((x) => x.name).join(", ")}` : `Special deal${deals.length > 1 ? "s" : ""}: ${deals.map((x) => x.name).join(", ")}`;
  return h("div", { class: "badges" }, h("span", { class: "badge deal", title: "This show has an extra offer. Details on the show page." }, "🏷 ", text));
}
function dealsPanel(e, day) {
  const deals = dealsFor(e, day);
  if (!deals.length) return null;
  const range = (x) => (x.start || x.end ? `${x.start ? dayName(x.start, { month: "short", day: "numeric" }) : ""}–${x.end ? dayName(x.end, { month: "short", day: "numeric" }) : ""}` : null);
  return h("section", { class: "panel" }, h("h2", {}, "Special deals"),
    deals.map((x) => h("div", { class: "deal-row" },
      h("h3", {}, x.name, x.price ? ` · ${money(x.price)}` : ""),
      h("p", { class: "muted" }, [x.how, x.time, x.where && !cleanUrl(x.where) ? x.where : null, x.limit, range(x)].filter(Boolean).join(" · ")),
      x.link && x.link.url ? linkLine(x.link, "Get it") : null)),
    h("p", { class: "muted" }, "Deals don't change the prediction. A deal day may be busier or cheaper than the numbers here."));
}

/* ---------- Two-show days (SPEC 2.8 N8) ---------- */
// A performance starting before 5 PM is a matinee. One prediction covers the whole day's rush (SPEC 5.2).
const MATINEE_BEFORE = 17 * 60;
const perfsOf = (e) => e.performances || [];
const isMatinee = (t) => minutesOf(t) < MATINEE_BEFORE;
const twoShows = (e) => perfsOf(e).length >= 2;
const hasShowtime = (e, which) => perfsOf(e).some((t) => (which === "matinee" ? isMatinee(t) : !isMatinee(t)));
const hourText = (t) => time12(t).replace(":00 ", " ").replace(" AM", " am").replace(" PM", " pm");
function twoShowLine(e) {
  return twoShows(e) ? h("div", { class: "two-show" }, `2 shows today: ${perfsOf(e).map(hourText).join(" & ")}`) : null;
}
function showtimeLine(e, which) {
  const times = perfsOf(e).filter((t) => (which === "matinee" ? isMatinee(t) : !isMatinee(t)));
  return times.length ? h("div", { class: "two-show" }, `${which === "matinee" ? "Matinee" : "Evening"}: ${times.map(hourText).join(" & ")}`) : null;
}
// How rush is sold on a 2-show day, from registry/show_facts.csv (two_show_rush). Unknown is said, never guessed.
function twoShowRushText(e) {
  const how = e.two_show_rush || "unknown";
  if (how === "both at opening") return "Rush for both performances goes on sale when the box office opens.";
  if (how === "separately") return `Rush for each performance is sold separately${e.two_show_rush_note ? `: ${e.two_show_rush_note}` : "."}`;
  return "We don't know yet whether rush for the later performance is sold at opening or later in the day. Ask at the box office.";
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
function factsLine(e, anyMode) {
  // No typical ticket price on tiles (Rachel 2026-11-12): it read like a discount site. It stays on the show page.
  const parts = [e.show_type || "Play or musical not available"];
  if (state.data.has_show_facts) {
    parts.splice(1, 0, runtimeText(e) || "Runtime not available");
    if (anyMode) parts.push(e.days ? `Plays ${e.days.join(" ")}` : "Days not available");
  }
  return h("div", { class: "facts-line" }, parts.join(" · "));
}
// Favorite star (Rachel 2026-11-12, replaced the "Interested" checkbox). Same browser-only list as before, so old picks carry over.
function pickBox(e) {
  const on = picks.has(e.show_id);
  return h("button", {
    type: "button", class: "fav", "aria-pressed": String(on),
    "aria-label": `${on ? "Remove" : "Add"} ${e.name || e.show_id} ${on ? "from" : "to"} favorites`, title: on ? "Favorited" : "Favorite",
    onclick: () => {
      if (picks.has(e.show_id)) picks.delete(e.show_id); else picks.add(e.show_id);
      savePicks();
      if (state.paint) state.paint();
    },
  }, on ? "★" : "☆");
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
// The show's own picture from Ticketmaster (Rachel 2026-11-19), linked, never stored; hidden if it fails to load.
function tileImage(e) {
  if (N14.c) return n14Img(e, "tile-img"); // N14 c: same shape everywhere, stage drawing when there's no photo
  if (!e.image) return null;
  return h("img", { class: "tile-img", src: e.image, alt: "", loading: "lazy", decoding: "async", onerror: (ev) => ev.target.remove() });
}
function tileHead(e, href) {
  return [tileImage(e), h("div", { class: "tile-top" },
    h("div", { class: "tile-name" },
      h("a", { class: "tile-link", href }, e.name),
      theaterLink(e) || h("span", { class: "theater" }, e.theater)),
    priceBlock(e))];
}
// showtime: "matinee" or "evening" inside a Matinee or Evening section or filter, so the tile names that performance.
function tile(day, e, anyMode, from = "", showtime = null) {
  const head = tileHead(e, `#/show/${day}/${encodeURIComponent(e.show_id)}${from}`);
  if (anyMode) {
    return h("article", { class: "tile" }, head, rushLabels(e),
      h("div", { class: "seats" }, seatsLine(e)), factsLine(e, true),
      h("div", { class: "check-back" }, "Check back within 7 days of your date."),
      dealBadge(e, day), pickBox(e));
  }
  const perfLine = showtime ? (twoShows(e) ? [showtimeLine(e, showtime), twoShowLine(e)] : showtimeLine(e, showtime)) : twoShowLine(e);
  if (e.group === 1) {
    return h("article", { class: "tile" }, head, rushLabels(e), perfLine, worthBar(e),
      h("div", { class: "stats" },
        h("span", { class: "chance" }, pct(e.chance_9am), " ", h("small", {}, "chance at 9:00 AM")),
        h("span", { class: "arrival" }, "Get there by ", markedTime(e, e.arrival))),
      h("div", { class: "seats" }, seatsLine(e)), factsLine(e, false),
      badges(e), dealBadge(e, day), pickBox(e));
  }
  if (e.group === 2) {
    return h("article", { class: "tile" }, head, rushLabels(e), perfLine,
      h("div", { class: "simple-line" }, h("b", {}, "Limited data, probably easy.")),
      h("div", { class: "simple-line" }, policyLine(e)),
      h("div", { class: "seats" }, seatsLine(e)), factsLine(e, false),
      badges(e), dealBadge(e, day), pickBox(e));
  }
  return h("article", { class: "tile" }, head, rushLabels(e), perfLine,
    h("div", { class: "simple-line" }, otherOffers(e)),
    h("div", { class: "seats" }, seatsLine(e)), factsLine(e, false),
    badges(e), dealBadge(e, day), pickBox(e));
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
      const tip = `get there by ${time12(e.arrival)}, ${pct(e.chance_9am)} chance at 9:00 AM, ${e.verdict}${opensUnusual(e) ? `. Box office opens ${time12(e.open_time)}` : ""}${twoShows(e) ? `. 2 shows: ${perfsOf(e).map(hourText).join(" & ")}` : ""}${bestDates.has(d) ? ". Best day" : ""}`;
      return h("a", {
        class: `week-cell tone-${e.verdict.split(" ")[0]}${bestDates.has(d) ? " best" : ""}`, role: "listitem",
        href: `#/show/${d}/${encodeURIComponent(item.show_id)}/week`, title: tip, "aria-label": `${dayName(d, { weekday: "long", month: "short", day: "numeric" })}: ${tip}`,
      }, h("span", { class: "week-cell-day" }, label, twoShows(e) ? h("sup", { class: "two-mark", title: "2 shows this day" }, "2") : null),
      h("span", { class: "week-cell-val" }, shortTime(e.arrival), openMark(e)));
    }));
}
function weekTile(item, dates, allowed) {
  const b = item.best;
  const href = `#/show/${b ? b.date : item.firstDate}/${encodeURIComponent(item.show_id)}/week`;
  if (!b) {
    return h("article", { class: "tile" }, tileHead(item, href), rushLabels(item),
      h("div", { class: "simple-line" }, "No prediction left on your days this week."),
      weekRow(item, dates, allowed), weekTwoShowLine(item, allowed), h("div", { class: "seats" }, seatsLine(item)), factsLine(item, false), badges(item), dealBadge(item, "week"), pickBox(item));
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
    weekRow(item, dates, allowed), weekTwoShowLine(item, allowed),
    h("div", { class: "seats" }, seatsLine(item)), factsLine(item, false), badges(item), dealBadge(item, "week"), pickBox(item));
}
// "2 shows: Wed & Sat (2 pm & 8 pm)" in the This week view (SPEC 2.8 N8)
function weekTwoShowLine(item, allowed) {
  const twos = item.weekDays.filter((x) => twoShows(x.e) && allowed(x.date));
  if (!twos.length) return null;
  const times = [...new Set(twos.map((x) => perfsOf(x.e).map(hourText).join(" & ")))];
  return h("div", { class: "two-show" }, `2 shows: ${joinOr(twos.map((x) => weekDayName(x.date))).replace(" or ", " & ")}`,
    times.length === 1 ? ` (${times[0]})` : "");
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
    let shows = 0, go = 0, marked = null, open = 0, twice = 0;
    for (const it of items) {
      const x = it.weekDays.find((w) => w.date === d);
      if (x && twoShows(x.e)) twice += 1;
      if (!x || !hasNumber(x.e)) continue;
      if (isPastToday(d, x.e)) { open += 1; continue; }
      shows += 1;
      if (x.e.verdict === "GO") go += 1;
      if (!marked && opensUnusual(x.e)) marked = x.e;
    }
    return { d, shows, go, marked, twice, off: !allowed(d), past: !shows && open > 0 };
  });
  const bestGo = Math.max(0, ...cells.filter((c) => !c.off && c.shows).map((c) => c.go));
  return h("div", { class: "week-strip", role: "list", "aria-label": "How many shows are GO each day" },
    cells.map((c) => {
      const isBest = bestGo > 0 && !c.off && c.shows && c.go === bestGo;
      const value = c.off || c.past || !c.shows ? "–" : String(c.go);
      const sub = c.off ? "not your day" : c.past ? "already open" : c.shows ? `of ${c.shows} GO` : "no numbers";
      const tip = c.off ? "not one of your days" : c.past ? "box offices have already opened" : c.shows
        ? `${c.go} of ${c.shows} shows with a prediction are GO${c.twice ? `. ${c.twice} play twice` : ""}${isBest ? ". Best day" : ""}` : "no shows with a prediction";
      return h("a", {
        class: `strip-day${isBest ? " best" : ""}${c.off || c.past ? " off" : ""}`, href: `#/day/${c.d}`, role: "listitem",
        title: tip, "aria-label": `${dayName(c.d, { weekday: "long", month: "short", day: "numeric" })}: ${tip}`,
      },
        h("b", {}, DAY_SHORT[dayIndex(c.d)], c.marked ? openMark(c.marked) : null),
        h("span", { class: "strip-date" }, c.d === localToday() ? "Today" : dayName(c.d, { month: "short", day: "numeric" })),
        h("span", { class: "strip-num" }, value),
        h("small", {}, sub),
        c.twice && !c.off ? h("small", { class: "strip-two", title: `${c.twice} of these shows play twice this day` }, `${c.twice} twice`) : null);
    }));
}

/* ---------- filters and sorting: everything runs in the browser from the predictions file ---------- */
const anyFilterOn = () => Object.values(state.filters).some((f) => f.size);
function matchesFilters(e, anyMode, weekMode = false, allowed = () => true) {
  const f = state.filters;
  // Show time (Rachel 2026-11-12): one picked = has that showtime; both = plays matinee AND evening; neither = all.
  // In the This week view it's enough on one of your days.
  if (!anyMode && f.showtime.size) {
    const ok = (x) => [...f.showtime].every((w) => hasShowtime(x, w));
    if (!(weekMode ? e.weekDays.some((x) => allowed(x.date) && ok(x.e)) : ok(e))) return false;
  }
  if (f.rush.size && !(e.rush_labels || []).some((l) => f.rush.has(l.startsWith("In person") ? "In person" : l))) return false;
  if (f.type.size && !(e.show_type && f.type.has(e.show_type))) return false;
  // Days showing works on every view (Rachel 2026-11-12). This week uses it to pick which days count (allowed).
  if (!weekMode && f.days.size && !(e.days && e.days.some((d) => f.days.has(d)))) return false;
  if (f.runtime.size) {
    if (e.runtime_minutes === null || e.runtime_minutes === undefined) return false;
    if (!RUNTIME_OPTIONS.some((o) => f.runtime.has(o.key) && o.test(e.runtime_minutes))) return false;
  }
  return true;
}
function hiddenForUnknown(entries, anyMode, weekMode = false) {
  const f = state.filters;
  const notes = [];
  const add = (n, what) => { if (n) notes.push(`${n} ${n === 1 ? "show" : "shows"} hidden: ${what} not known`); };
  if (f.type.size) add(entries.filter((e) => !e.show_type).length, "play or musical");
  if (!weekMode && f.days.size) add(entries.filter((e) => !e.days).length, "days showing");
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
const NO_DATA_MAX_REPORTS = 6;
const noData = (e) => e.group !== 3 && (e.line_reports ?? 0) <= NO_DATA_MAX_REPORTS;
const noDataLine = (list) => (list.length
  ? h("p", { class: "muted no-data" }, `No data for: ${list.map((e) => e.name).sort((a, b) => a.localeCompare(b)).join(", ")}.`) : null);
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
  // Shows with in-person rush but 0-6 line reports get no tile, only a name in the "No data for" line (Rachel 2026-11-12).
  const allEntries = anyMode ? allShows() : weekMode ? weekShows(dates) : data.days[day];
  const noDataShows = allEntries.filter(noData);
  const entries = allEntries.filter((e) => !noData(e));
  // Week view: Days showing means "days I can go", so only those days are compared.
  const allowed = (d) => !state.filters.days.size || state.filters.days.has(DAY_KEYS[dayIndex(d)]);

  const picker = N13.b ? n13CalendarStrip(dates, day, today, weekMode, anyMode) : h("div", { class: "day-picker", role: "group", "aria-label": "Pick a day" },
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

  const viewRow = h("div", { class: "control-row", role: "group", "aria-label": "View" },
    h("span", { class: "control-name" }, "View"),
    [["grid", "Grid"], ["carousel", "Carousel"]].map(([key, label]) => h("button", {
      type: "button", class: "chip", "data-view": key, "aria-pressed": String(state.view === key),
      onclick: () => {
        state.view = key;
        try { localStorage.setItem("br-view", key); } catch { /* private window: keep it for this visit only */ }
        viewRow.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === key)));
        state.paint();
      },
    }, label)));

  const filterRows = [
    chipRow("Rush type", RUSH_OPTIONS, state.filters.rush),
    chipRow("Play or musical", TYPE_OPTIONS, state.filters.type),
  ];
  if (data.has_show_facts) {
    filterRows.push(chipRow("Days showing", DAY_OPTIONS, state.filters.days));
    filterRows.push(chipRow("Runtime", RUNTIME_OPTIONS, state.filters.runtime));
  }
  // Show time (SPEC 2.8 N8, changed 2026-11-12): no 2-show-day filter; Any day has no performance times, so no row there.
  if (!anyMode) filterRows.push(chipRow("Show time", [{ key: "matinee", label: "Matinee" }, { key: "evening", label: "Evening" }], state.filters.showtime));
  else state.filters.showtime.clear();
  if (N13.c && data.has_stars) filterRows.push(chipRow("Star in the cast", [{ key: "on", label: "★ Star in the cast" }], state.filters.star));
  if (state.filtersOpen === null) state.filtersOpen = window.matchMedia("(min-width: 700px)").matches;
  const filterSummary = h("summary", {}, "Filters");
  const filterBox = h("details", { class: "filters", open: state.filtersOpen, ontoggle: (ev) => { state.filtersOpen = ev.target.open; } },
    filterSummary, h("div", { class: "filter-body" }, filterRows));

  const picksToggle = h("button", {
    type: "button", class: "chip fav-filter", id: "pick-count", "aria-pressed": String(state.picksOnly),
    onclick: (ev) => { state.picksOnly = !state.picksOnly; ev.currentTarget.setAttribute("aria-pressed", String(state.picksOnly)); state.paint(); },
  }, "");
  const favRow = h("div", { class: "control-row n14-favrow" }, picksToggle);
  const resultLine = h("div", { class: "result-line", role: "status" });
  const results = h("div", {});
  const stripHolder = h("div", { class: "strip-holder" });

  state.paint = () => {
    const visible = entries.filter((e) => matchesFilters(e, anyMode, weekMode, allowed) && (!state.picksOnly || picks.has(e.show_id))
      && (!weekMode || e.weekDays.some((x) => allowed(x.date))) && n13StarOk(e, day, weekMode, allowed));
    if (weekMode) for (const e of entries) e.best = e.group === 1 ? weekBest(e, allowed) : null;
    const { spec, reversed } = activeSort(anyMode, weekMode);
    document.getElementById("pick-count").textContent = `★ Show favorites (${picks.size})`;
    sortRow.querySelectorAll("[data-sort]").forEach((b) => {
      const on = b.dataset.sort === spec.key;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      const name = SORTS.find((x) => x.key === b.dataset.sort).label;
      b.textContent = on ? `${name} ${reversed ? "↑" : "↓"}` : name;
    });
    const active = Object.values(state.filters).reduce((n, f) => n + f.size, 0);
    filterSummary.textContent = active ? `Filters (${active} on)` : "Filters";
    const notes = hiddenForUnknown(entries, anyMode, weekMode);
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

    const tileFor = (e, showtime) => (weekMode ? (e.group === 1 ? weekTile(e, dates, allowed) : weekOtherTile(e)) : tile(day, e, anyMode, "", showtime));
    // Grid or carousel (Rachel 2026-11-19: both views). The carousel is one swipeable row per group, with arrows.
    const grid = (list, showtime) => {
      const cls = `tiles${weekMode ? " week-tiles" : ""}${state.view === "carousel" ? " carousel-track" : ""}`;
      const track = h("div", { class: cls }, list.map((e) => tileFor(e, showtime)));
      if (state.view !== "carousel") return track;
      if (N13.d) return n13Coverflow([...track.children], list); // N13 d: 3D coverflow instead of the flat row
      const step = (dir) => () => track.scrollBy({ left: dir * track.clientWidth * 0.9, behavior: "smooth" });
      return h("div", { class: "carousel" },
        h("button", { type: "button", class: "carousel-arrow prev", "aria-label": "Previous shows", onclick: step(-1) }, "‹"),
        track,
        h("button", { type: "button", class: "carousel-arrow next", "aria-label": "Next shows", onclick: step(1) }, "›"));
    };
    // The three show groups (SPEC 8), with h2 titles, or h3 inside a Matinee or Evening section (SPEC 2.8 N8)
    const grouped = (list, showtime, tag) => {
      const out = [];
      if (!(!anyMode && (spec.key === "chance" || (weekMode && spec.key === "arrival")))) {
        out.push(h("section", {}, grid(sortEntries(list, spec, reversed), showtime)));
        return out;
      }
      // The default view keeps the three show groups. Shows without a number stay at the bottom.
      const groups = [1, 2, 3].map((g) => list.filter((e) => e.group === g));
      if (groups[0].length) out.push(h("section", {}, h(tag, { class: "group-title" }, "Full predictions"), grid(sortEntries(groups[0], spec, reversed), showtime)));
      if (groups[1].length) {
        out.push(h("section", {}, h(tag, { class: "group-title" }, "At the box office, not enough reports"),
          h("p", { class: "group-note" }, "Too few reports for a number. Quiet shows like these tend to sell fewer seats, so a line is probably short."),
          grid(groups[1], showtime)));
      }
      if (groups[2].length) {
        out.push(h("section", {}, h(tag, { class: "group-title" }, "No in-person rush line"),
          h("p", { class: "group-note" }, "Lottery and online rush only, so there's no line to predict. Few reports here doesn't mean low demand."),
          grid(groups[2], showtime)));
      }
      return out;
    };
    const sections = [];
    if (weekMode) stripHolder.replaceChildren(h("h2", { class: "strip-title" }, "Shows that are GO, by day"), weekStrip(visible, dates, allowed));
    const picked = [...state.filters.showtime];
    const dayView = !anyMode && !weekMode;
    if (!visible.length) {
      sections.push(h("p", { class: "empty" }, state.picksOnly && !anyFilterOn()
        ? "None of your favorites are here. Tap the ☆ on a show to favorite it, or turn off \"Show favorites\" to see every show."
        : "No shows match. Try turning off a filter."));
    } else if (dayView && picked.length === 1) {
      sections.push(...grouped(visible, picked[0], "h2"));
    } else {
      sections.push(...grouped(visible, null, "h2"));
    }
    results.replaceChildren(...sections, noDataLine(noDataShows) || "");
  };

  const pairs = weekMode
    ? entries.flatMap((it) => it.weekDays.filter((x) => hasNumber(x.e)).map((x) => [x.date, x.e]))
    : anyMode ? [] : entries.filter(hasNumber).map((e) => [day, e]);
  setApp(
    h("h1", { class: "sentence page-q" }, anyMode ? "What's playing when you can go?" : weekMode ? "Which day should you go?" : "Is rush worth it this morning?"),
    h("p", { class: "lede page-q" }, anyMode
      ? "Planning further ahead: show facts only, with no chance or arrival time."
      : weekMode
        ? "Each show's best day this week: the latest you can get there and still probably get a ticket. Tap a day to see all its shows."
        : "Pick a day. Shows are ranked by your chance of a ticket if you arrive at 9:00 AM."),
    stale ? h("p", { class: "notice" }, "These predictions are out of date: every day in the file has passed.") : null,
    picker,
    weekMode ? stripHolder : null,
    openNote(pairs),
    anyMode ? h("p", { class: "notice" }, "Predictions stop 7 days out, so these tiles don't have any. Schedules change and a show could close before your date, so confirm before you go.") : null,
    // N14 b: Show favorites sits on the Sort and View row instead of under Filters
    h("div", { class: "controls" }, N13.c ? h("div", { class: "n13-sortview" }, sortRow, viewRow, N14.b ? favRow : null) : [sortRow, viewRow, N14.b ? favRow : null], filterBox,
      N14.b ? null : favRow, resultLine),
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
    if (e.tickets.source === "lookup") {
      sentence.replaceChildren(
        "About ", h("b", {}, String(e.tickets.median)), " rush tickets",
        ...(inPersonPrice ? [" at ", h("b", {}, inPersonPrice), e.price_note ? ` (${e.price_note})` : ""] : [" (in-person price not listed)"]), ".",
        h("span", { class: "muted", style: "display:block;font-size:.88rem;margin-top:2px" }, `${level}% of stated counts fell between ${lo} and ${hi}.`));
      return;
    }
    sentence.replaceChildren(
      "We're ", h("b", {}, `${level}%`), " confident there will be ",
      h("b", {}, `${fmt(mid)} ± ${fmt(half)}`), " rush tickets",
      ...(inPersonPrice ? [" at ", h("b", {}, inPersonPrice), e.price_note ? ` (${e.price_note})` : ""] : [" (in-person price not listed)"]), ".",
      h("span", { class: "muted", style: "display:block;font-size:.88rem;margin-top:2px" }, `That's ${lo} to ${hi} tickets.`));
  }
  paint(80);
  const acc = state.data.accuracy;
  const ticketCaution = e.tickets.source === "lookup"
    ? h("p", { class: "notice" }, `${e.tickets.own_show ? `This number comes from the ${e.tickets.stated_days} days someone said how many rush tickets this show had` : "This show has too few stated counts, so this number comes from every show's stated counts"}. In tests that simple lookup was closer than the model (${acc ? `${num(acc.tickets_lookup.mae, 1)} vs ${num(acc.tickets_combo.mae, 1)} tickets off` : "on stated counts"}). People mostly post counts when they're small, so treat it as a rough guess.`)
    : acc && acc.tickets_combo.mae > acc.tickets_lookup.mae
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
    linkLine(digitalLink(e), "Open"),
    h("p", {}, "Be in the app a few minutes early: it opens right on time."),
    h("p", { class: "muted" }, "Combo idea: do a morning digital rush for one show, then walk to another show's box office."));
}

function policyPanel(e) {
  const p = e.policy || {};
  const row = (name, x, link, verb) => x ? h("div", {},
    h("h3", {}, name, x.price ? ` · ${money(x.price)}` : ""),
    h("p", { class: "muted" }, [x.time, link && link.url && cleanUrl(x.where) ? null : x.where, x.limit].filter(Boolean).join(" · ")),
    link ? linkLine(link, verb) : null) : null;
  const rows = [row("In-person rush", p.general), row("Standing room", p.standing_room), row("Digital rush", p.digital, digitalLink(e), "Open"),
    row("Digital lottery", p.lottery, lotteryLink(e), "Enter the lottery"), row("Student", p.student),
    ...(p.other || []).map((x) => row(x.name, x, offerLink(x), "Get it"))].filter(Boolean);
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
      h("p", { class: "muted", style: "margin:2px 0 0" }, theaterLink(e, "head-theater") || e.theater, ` · ${when}`),
      anyMode ? null : h("p", { class: "muted", style: "margin:0" }, e.schedule_known === false
        ? "Schedule not confirmed: this show isn't on Ticketmaster. Check before you go."
        : twoShows(e)
          ? `2 shows today: ${perfsOf(e).map((t) => `${time12(t)} (${isMatinee(t) ? "matinee" : "evening"})`).join(" and ")}`
          : `Performances: ${e.performances.map(time12).join(", ") || NOT_AVAILABLE}`),
      !anyMode && twoShows(e) ? h("p", { class: "two-show-note" },
        "The prediction covers the whole day's rush, since reports rarely say which performance. ", twoShowRushText(e)) : null,
      rushLabels(e), dealBadge(e, day)),
    priceBlock(e));
  const back = h("a", { class: "back", href: backHref }, "← Back to shows");

  if (N14.d && (anyMode || e.group === 1)) { n14ShowPage(e, day, back, head); return; } // N14 d
  if (N13.g && (anyMode || e.group === 1)) { n13ShowDashboard(e, day, back, head); return; } // N13 g
  if (anyMode) {
    setApp(back, head, h("p", { class: "notice" }, "Check back within 7 days of your date for a prediction. Schedules change, so confirm before you go."),
      h("div", { class: "detail-grid", style: "margin-top:12px" },
        h("div", { class: "col" }, factsPanel(e), policyPanel(e)), h("div", { class: "col" }, keyAppealsPanel(e, day), dealsPanel(e, day), savingsPanel(e), digitalPanel(e))));
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
      h("div", { class: "col" }, keyAppealsPanel(e, day), dealsPanel(e, day), busiestPanel(e, day), savingsPanel(e), why, factsPanel(e), digitalPanel(e), policyPanel(e))));
    return;
  }
  const note = e.group === 2
    ? h("section", { class: "panel" }, h("h2", {}, "Limited data, probably easy"),
      h("p", {}, "Too few reports for a prediction, so there's no number here."),
      h("p", {}, seatsLine(e), "."),
      h("p", { class: "muted" }, `${e.reports_per_week} reports a week and ${e.line_reports} line reports. A full prediction needs 2 reports a week or 35 line reports.`))
    : h("section", { class: "panel" }, h("h2", {}, "No in-person rush line"),
      h("p", {}, otherOffers(e)),
      linkLine(lotteryLink(e), "Enter the lottery"), linkLine(digitalLink(e), "Open"),
      h("p", {}, seatsLine(e), "."),
      h("p", { class: "muted" }, "No line to predict. Few reports here doesn't mean low demand."));
  if (N14.d) { n14ShowPage(e, day, back, head, note); return; } // N14 d
  if (N13.g) { n13ShowDashboard(e, day, back, head, note); return; } // N13 g
  setApp(back, head, h("div", { class: "detail-grid" },
    h("div", { class: "col" }, note, e.group === 2 ? busiestPanel(e, day) : null, factsPanel(e), policyPanel(e)), h("div", { class: "col" }, keyAppealsPanel(e, day), dealsPanel(e, day), savingsPanel(e), digitalPanel(e))));
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
  if (N14.d) return null; // N14 d: no "what you'd save" anywhere on the site
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
  ["ns-lines", "How lines behave"], ["ns-summary", "Short version"], ["ns-data", "The data"],
  ["ns-model", "The model"], ["ns-tests", "How good is it?"], ["ns-truth", "Model vs. ground truth"],
];
const KPI_ICONS = {
  people: "M16 19v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 17.5V19M10 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6M20 19v-1.5a3.5 3.5 0 0 0-2.6-3.4M15 5.1a3 3 0 0 1 0 5.8",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8M12 12h.01",
  check: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M8 12.5l2.5 2.5L16 9.5",
  alert: "M12 3l9.5 17h-19zM12 10v4M12 17h.01",
};
function kpi(tone, icon, title, big, unit, foot) {
  const svg = s("svg", { viewBox: "0 0 24 24", width: "30", height: "30", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
  svg.append(s("path", { d: KPI_ICONS[icon] }));
  return h("div", { class: `kpi ${tone}` },
    h("p", { class: "kpi-title" }, title),
    h("div", { class: "kpi-main" }, svg, h("b", {}, big)),
    h("div", { class: "kpi-foot" }, h("span", {}, unit), h("span", {}, foot)));
}
function nsSection(id, title, intro, ...panels) {
  return h("section", { id, class: "ns-section" }, h("h2", {}, title), intro ? h("p", { class: "lede" }, intro) : null,
    h("div", { class: "accuracy-grid" }, panels));
}
// Each chart is a closed FAQ-style question (Rachel 2026-11-12: don't bombard the viewer). Charts drawn while closed
// have no width, so they're redrawn when opened.
function nsPanel(title, takeaway, ...body) {
  return h("details", { class: "panel faq", ontoggle: (ev) => { if (ev.target.open) redrawIn(ev.target); } },
    h("summary", {}, h("h3", {}, title)),
    h("div", { class: "faq-body" }, takeaway ? h("p", {}, takeaway) : null, ...body));
}
// "Which shows and days are busiest?" starts open at the top (Rachel 2026-11-12).
function openPanel(panel) { panel.open = true; requestAnimationFrame(() => redrawIn(panel)); return panel; }
function redrawIn(el) {
  charts.filter((c) => el.contains(c.holder)).forEach((c) => (c.cfg.draw || drawChart)(c.holder, c.cfg));
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
        const cell = h("td", { class: has ? `heat-${heat(x.typical)}` : "heat-0" }, has ? people(x.typical) : "–");
        if (N14.f) return n14HeatCell(cell, `${r.e.name}, ${DAY_LONG[x.i]}`, tip, has ? heat(x.typical) : 0); // N14 f
        return withTip(cell, `${r.e.name}, ${DAY_LONG[x.i]}`, [tip]);
      }))))));
  const key = h("div", { class: "heat-key" }, ["Under 5", "5–9", "10–14", "15–19", "20+"].map((t, i) => h("span", {}, h("i", { class: `heat-${i + 1}` }), t)));
  return nsPanel("Which shows and days are busiest?",
    `Longest: ${hi.name} on ${DAY_LONG[hi.i]}, about ${people(hi.typical)} people. Shortest: ${lo.name} on ${DAY_LONG[lo.i]}, about ${people(lo.typical)}.`,
    key, N14.f ? n14HeatInfo(table) : null, table,
    h("p", { class: "muted", style: "margin-top:8px" }, `Typical people in line in the last ${ch.near_opening_hours} hours before opening. A dash means it's not playing now or has fewer than ${ch.min_days_per_cell} past days of reports.${left.length ? ` Too few reports to list: ${left.join(", ")}.` : ""}`));
}

// What the AI reading cost (Rachel 2026-11-17). From data/interim/llm_spend.csv via site_extras.ai_spend(); every
// call is logged by the code that made it. All other data sources are free.
function spendPanel(s) {
  if (!s) return null;
  const usd = (x) => `$${x.toFixed(2)}`;
  return nsPanel("What did it cost?",
    `${usd(s.total_usd)} in all, for ${s.calls.toLocaleString()} AI calls (Claude Haiku), against a ${usd(s.cap_usd)} cap I set at the start. Every other data source is free.`,
    h("table", { class: "spend" },
      h("tbody", {}, ...s.items.map((x) => h("tr", {}, h("td", {}, x.label), h("td", { class: "num" }, usd(x.usd)))),
        h("tr", { class: "total" }, h("td", {}, "Total"), h("td", { class: "num" }, usd(s.total_usd))))),
    h("p", { class: "muted" }, `Through ${dayName(s.through, { month: "short", day: "numeric", year: "numeric" })}. Most of it went to turning Reddit comments into reports and then checking each one a second time.`));
}

function funnelPanel(f) {
  const steps = [
    ["Reports pulled out", f.all_observations, null],
    ["In-person general rush", f.in_person_general_rush, "lottery, digital, standing room, student"],
    ["Matched to a Broadway show", f.mapped_to_a_broadway_show, "off-Broadway, tours, show unclear"],
    ["AI was confident", f.not_low_confidence, "low confidence"],
    ["Date checks out", f.date_inside_the_shows_run, "no date, wrong year, outside the run"],
    ["Line counts for the model", f.line_points_after_dropping_duplicates, "no time or count, after opening, duplicates"],
  ];
  const max = steps[0][1];
  const funnel = h("div", { class: "funnel", role: "list" }, steps.map(([label, n, why], i) => h("div", { class: `funnel-row${i === steps.length - 1 ? " final" : ""}`, role: "listitem" },
    h("div", { class: "funnel-label" }, label),
    h("div", { class: "funnel-track" }, h("div", { class: "funnel-bar", style: `width:${(n / max) * 100}%` }, h("span", {}, n.toLocaleString()))),
    h("div", { class: "funnel-cut" }, why ? [h("b", {}, `−${(steps[i - 1][1] - n).toLocaleString()}`), ` ${why}`] : `from ${f.comments_scanned.toLocaleString()} comments scanned`))));
  return nsPanel("From Reddit comments to usable reports",
    `We scanned ${f.comments_scanned.toLocaleString()} Reddit comments and forum posts. An AI pulled out ${f.all_observations.toLocaleString()} rush reports, and ${f.line_points_after_dropping_duplicates.toLocaleString()} passed every check to become line reports.`,
    funnel,
    h("p", { class: "muted", style: "margin-top:8px" }, `The model also uses ${f.cutoff_show_days.toLocaleString()} show-days with ticket information (${f.cutoff_stated_count} stated counts, the rest only "at least" or "at most") and ${f.outcomes_arrived_before_opening_known_result} attempts with a known result. Reports run from ${dayName(f.first_date, { month: "short", year: "numeric" })} to ${dayName(f.last_date, { month: "short", year: "numeric" })}.`));
}

function reportsPanel(ch, entries) {
  const list = entries.filter((e) => e.group !== 3 && !noData(e)).sort((a, b) => b.line_reports - a.line_reports);
  const none = entries.filter(noData);
  const full = list.filter((e) => e.group === 1).length;
  const rule = ch.full_prediction_rule;
  return nsPanel("How many reports does each show have?",
    `${full} of ${list.length} shows with in-person rush get a full prediction. That takes ${rule.line_reports} line reports or ${rule.reports_per_week} reports a week.`,
    legendOf([{ name: "Full prediction", dot: "bar-a" }, { name: "Not enough reports", dot: "bar-gray" }, { name: `${rule.line_reports} line reports`, color: "var(--ink-2)", dash: "dotted" }]),
    barRows(list.map((e) => ({
      label: e.name, showName: true, value: e.line_reports, text: String(e.line_reports), tone: e.group === 1 ? "a" : "gray",
      tip: [`${e.line_reports} line reports`, `${e.reports_per_week} reports a week`, e.group === 1 ? "Full prediction" : "Not enough reports"],
    })), { ref: rule.line_reports }),
    h("p", { class: "muted", style: "margin-top:8px" }, "In the tests, shows with 10 to 34 earlier line reports lost to the lookup table, and shows with 35 or more beat it. That's where the rule comes from."),
    noDataLine(none));
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
      h("li", {}, h("b", {}, "The tickets: "), `${m.cutoff}, because most reports only say "at least" or "at most" so many tickets. Shows share information, so thin shows lean on the rest. "Sold out at 10:30" plus a line count shortly before it counts as an "at most".`),
      m.tickets_shown ? h("li", {}, h("b", {}, "The ticket number you see: "), `the ${m.tickets_shown}. The model's ticket estimates still drive the chance.`) : null,
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
  return nsPanel("Look up any test result", null,
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
    setApp(h("h1", { class: "sentence" }, "Nerd stats"),
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

  const f = state.data.final_score;
  const finalPanel = f ? nsPanel("The final score: 3 locked months", `${f.months.map(monthName).join(", ")} were kept out of every test and choice, then scored once on the final model.`,
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Measure"), h("th", {}, state.data.model.name), h("th", {}, "Per-show lookup table"), h("th", {}, "Always say yes"))),
      h("tbody", {},
        row(`Line error, people (${f.line_combo.points} reports)`, f.line_combo.mae, f.line_lookup.mae, (v) => num(v, 2)),
        covRow("80% line range held", f.line_combo.coverage80, f.line_lookup.coverage80),
        row(`Ticket error, tickets (${f.tickets_combo.days} stated counts)`, f.tickets_combo.mae, f.tickets_lookup.mae, (v) => num(v, 2)),
        row(`"Got one at #N": 80% range reached N (${f.bounds_combo.lower_days} days)`, f.bounds_combo.lower_agree, f.bounds_lookup.lower_agree, (v) => pct(v, 0), false),
        row(`Yes/no right, at 50% (${f.chance_combo.attempts} attempts)`, f.chance_combo.accuracy_at_50, f.chance_lookup.accuracy_at_50, (v) => pct(v, 1), false, pct(f.always_yes_accuracy, 1)),
        row("Chance error (Brier, smaller is better)", f.chance_combo.brier, f.chance_lookup.brier, (v) => num(v, 3), true, `${num(f.chance_base_rate.brier, 3)} (flat rate)`)))),
    h("p", { class: "muted", style: "margin-top:8px" }, `The line model beat the lookup table in all ${f.windows.length} locked months, and its error stayed close to the test months (${num(f.line_combo.mae, 2)} vs ${num(lc.mae, 2)}), so the choices made on the test months weren't luck. The lookup is still closer on stated ticket counts, so the site shows its ticket number.`)) : null;

  const slots = [];
  const start = new Date(2025, 10, 1);
  for (let i = 0; i < 12; i++) {
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
    slots.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  }
  const byMonth = Object.fromEntries([...a.windows, ...(f ? f.windows.map((w) => ({ ...w, locked: true })) : [])].map((w) => [w.month, w]));
  const series = (key) => slots.map((m) => (byMonth[m] ? byMonth[m][key] : null));
  const chartTitles = (i) => (byMonth[slots[i]] ? `${byMonth[slots[i]].points} line reports${byMonth[slots[i]].locked ? " · locked month, scored once" : ""}` : "Locked for the final score");
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
    h("h1", { class: "sentence" }, "Nerd stats"),
    h("p", { class: "lede" }, `The numbers behind the predictions. Test results come from ${dev.length} past months, each predicted using only earlier days${f ? `, plus one final score on ${f.months.length} locked months` : ""}. None of this has been checked on real trips yet.`),
    jump,
    nsSection("ns-lines", "How rush lines behave", "From real Reddit reports, before any model.",
      openPanel(heatPanel(ch, entries)), growthPanel(ch)),
    nsSection("ns-summary", "The short version",
      `Better than the simple lookup table on: ${beats.join(", ") || "none of the main measures"}. Not better on: ${loses.join(", ") || "none of them"}.`,
      // Gradient number cards (Rachel 2026-11-19: the Gradient Able template's stat cards, in a SIX-cover palette)
      h("div", { class: "ns-kpis" },
        kpi("k1", "people", "Line error", `${num(lc.mae, 2)}`, "people off, on average", `Lookup table: ${num(ll.mae, 2)}`),
        kpi("k2", "target", "Inside the 80% range", pct(lc.coverage80, 1), "of real lines", "Goal: 80%"),
        kpi("k3", "check", "Yes/no right", pct(cc.accuracy_at_50, 1), "at 50%", `Always saying yes: ${pct(a.always_yes_accuracy, 1)}`),
        kpi("k4", "alert", "Misses caught", `${cc.misses_caught_at_50} of ${cc.misses}`, "at 50%", "Times it warned before a loss"))),
    nsSection("ns-data", "Where the data comes from", null,
      funnelPanel(a.funnel), reportsPanel(ch, entries), spendPanel(state.data.ai_spend)),
    nsSection("ns-model", "What the model looks at", null,
      driversPanel(ch), methodPanel(a)),
    nsSection("ns-tests", "How good is it?", f ? `Test months: ${dev.map(monthName).join(", ")}. ${a.locked.map(monthName).join(", ")} stayed locked until the final score below.` : `Test months: ${dev.map(monthName).join(", ")}. ${a.locked.map(monthName).join(", ")} are locked and unscored here, so they can give the final model an honest score.`,
      finalPanel ? openPanel(finalPanel) : null,
      nsPanel(f ? "Does it beat the simple lookup table? (9 test months)" : "Does it beat the simple lookup table?", null, table,
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
        h("p", { class: "muted" }, `Average miss on the number of people in line. Lower is better. ${f ? "Dec, Apr and Aug are the locked months, scored once at the end." : "Gaps are the locked months."}`), legend(), errorChart),
      nsPanel("Did the 80% line range hold?", null,
        h("p", { class: "muted" }, `Share of real counts inside the range. The goal is 80%, not 100%. ${f ? "Dec, Apr and Aug are the locked months, scored once at the end." : "Gaps are the locked months."}`), legend(), coverChart),
      nsPanel("Real trips", null,
        live ? null : h("p", { class: "not-available" }, "Not available yet: no predictions have been checked against real rush days or verified reports."))),
    truthSection(ch));

  const biggestMiss = Math.max(...Object.values(byMonth).flatMap((w) => [w.line_mae_combo, w.line_mae_lookup]));
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

/* ========== N13 a: big centered title with stars around it (SPEC 2.8 N13 a) ========== */
const N13_SPARKLE = "M12 0C13 8 16 11 24 12C16 13 13 16 12 24C11 16 8 13 0 12C8 11 11 8 12 0Z";
const N13_STAR = "M12 1.5l3.1 6.6 7.2.9-5.3 5 1.4 7.1L12 17.6l-6.4 3.5L7 14l-5.3-5 7.2-.9z";
function n13StarCluster(side) {
  const box = h("span", { class: `n13-stars ${side}`, "aria-hidden": "true" });
  [["n13-s1", N13_SPARKLE], ["n13-s2", N13_STAR], ["n13-s3", N13_SPARKLE], ["n13-s4", N13_STAR]].forEach(([cls, d]) => {
    const svg = s("svg", { viewBox: "0 0 24 24", class: cls });
    svg.append(s("path", { d }));
    box.append(svg);
  });
  return box;
}
if (N13.a && !N14.a) { // N14 a replaces the side stars with the marquee sign
  const brand = document.querySelector(".site-header .brand");
  const wrap = h("div", { class: "n13-title" });
  brand.before(wrap);
  wrap.append(n13StarCluster("left"), brand, n13StarCluster("right"));
}
/* ========== end N13 a ========== */

/* ========== N13 b: calendar-icon day strip filling the full width (SPEC 2.8 N13 b) ==========
   Same days and links as the old day picker; each box looks like a calendar date (month band, big number, weekday). */
function n13CalendarStrip(dates, day, today, weekMode, anyMode) {
  const box = (pressed, band, big, small, href, label) => h("button", {
    type: "button", class: "n13-cal-day", "aria-pressed": pressed ? "true" : "false", "aria-label": label,
    onclick: () => { location.hash = href; },
  }, h("span", { class: "n13-cal-band" }, band), h("span", { class: "n13-cal-num" }, big), h("span", { class: "n13-cal-wd" }, small));
  return h("div", { class: "n13-cal", role: "group", "aria-label": "Pick a day" },
    dates.map((d) => box(d === day, dayName(d, { month: "short" }), String(parseDay(d).getDate()),
      d === today ? "Today" : dayName(d, { weekday: "short" }), `#/day/${d}`, dayName(d, { weekday: "long", month: "long", day: "numeric" }))),
    box(weekMode, "Week", "7", "Best day", "#/week", "This week: each show's best day"),
    box(anyMode, "Any day", "∞", "Plan ahead", "#/any", "Any day: plan ahead"));
}
/* ========== end N13 b ========== */

/* ========== N13 c: Sort + View side by side, filter groups in a grid, Nerd stats colors, "Star in the cast" filter ==========
   The filter keeps shows with a high-profile star performing that day: the same starsOn check as the tile's star label
   and Key appeals (the 20,000-views rule from N5). In This week, a star on any of your days counts; Any day uses today. */
function n13StarOk(e, day, weekMode, allowed) {
  if (!N13.c || !state.filters.star.size) return true;
  if (weekMode) return e.weekDays.some((x) => allowed(x.date) && starsOn(x.e, x.date).length > 0);
  return starsOn(e, day).length > 0;
}
/* ========== end N13 c ========== */

/* ========== N13 g: the show page as a dashboard (SPEC 2.8 N13 g) ==========
   Same panels as before, arranged in rows: big number cards, About table beside the picture + Key appeals, charts in
   pairs, a full-width rush policy, a compact "why", and a Nerd stats button that opens Nerd stats on this show. */
KPI_ICONS.clock = "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 7v5l3.5 2";
KPI_ICONS.ticket = "M3 7h18v3a2 2 0 0 0 0 4v3H3v-3a2 2 0 0 0 0-4zM14 7v10";
function n13NerdButton(e) {
  return h("a", { class: "n13-nerd-btn", href: `#/nerd-stats/${encodeURIComponent(e.show_id)}` },
    "Nerd stats for this show ", h("span", { "aria-hidden": "true" }, "→"));
}
function n13Row(cls, ...items) {
  const list = items.flat().filter(Boolean);
  return list.length ? h("div", { class: `n13-row ${cls} n${list.length}` }, list) : null;
}
function n13AboutTable(e) {
  const na = () => h("span", { class: "not-available" }, "not available");
  const weeks = e.typical_ticket_weeks && e.typical_ticket_weeks < 4 ? ` (only ${e.typical_ticket_weeks} ${e.typical_ticket_weeks === 1 ? "week" : "weeks"} so far)` : "";
  const rows = [
    ["Play or musical", e.show_type],
    state.data.has_show_facts ? ["Runtime", e.runtime_detail || runtimeText(e)] : null,
    state.data.has_show_facts ? ["Days showing", e.days ? e.days.join(" ") : null] : null,
    ["Typical ticket", e.typical_ticket !== null && e.typical_ticket !== undefined ? `${money(e.typical_ticket)}${weeks}` : null],
    ["Seats sold", e.seats_sold_pct !== null && e.seats_sold_pct !== undefined ? seatsLine(e) : null],
  ].filter(Boolean);
  return h("section", { class: "panel n13-about" }, h("h2", {}, "About this show"),
    h("table", { class: "n13-about-table" }, h("tbody", {}, rows.map(([k, v]) => h("tr", {}, h("th", { scope: "row" }, k), h("td", {}, v || na()))))),
    h("p", { class: "muted n13-small" }, "Typical ticket: the average paid over recent weeks, including rush and discounts."),
    e.facts_review ? h("p", { class: "notice" }, "We're not sure about the runtime or days for this show. Check before you plan around them.") : null,
    e.facts_source ? h("p", { class: "muted n13-small" }, `Runtime and days: ${e.facts_source}.`) : null);
}
function n13Why(e) {
  const list = (xs, empty) => (xs.length ? h("ul", { class: "reasons" }, xs.map((t) => h("li", {}, t))) : h("p", { class: "muted" }, empty));
  return h("section", { class: "panel n13-why" }, h("h2", {}, "Why this prediction"),
    h("div", { class: "n13-why-cols" },
      h("div", {}, h("h3", {}, "The line"), list(e.drivers.line, "Nothing stands out from an average day.")),
      h("div", {}, h("h3", {}, "The tickets"), list(e.drivers.tickets, "Nothing stands out from a typical show."))),
    h("p", { class: "muted n13-small" }, `Compared with an average day across shows. Built from ${e.data.line_points} line reports and ${e.data.cutoff_days} days with ticket information for this show. One prediction per day: most reports don't say matinee or evening.`),
    n13NerdButton(e));
}
function n13Kpis(e) {
  const t = e.tickets && e.tickets.levels && e.tickets.levels["80"];
  const l = e.line_at_9am;
  return h("div", { class: "ns-kpis n13-kpis" },
    kpi("k1", "check", "Chance at 9:00 AM", pct(e.chance_9am), e.verdict, `Opens ${time12(e.open_time || NORMAL_OPEN)}`),
    kpi("k2", "clock", "Get there by", time12(e.arrival), "for the best shot", `${pct(state.data.placeholders.target_chance)} target`),
    e.tickets ? kpi("k3", "ticket", "Rush tickets", `~${e.tickets.median}`, "about", t ? `80%: ${t[0]} to ${t[1]}` : "") : null,
    l ? kpi("k4", "people", "Line at 9:00 AM", `~${Math.round(l.median)}`, "people ahead", `Likely ${Math.round(l.lo)} to ${Math.round(l.hi)}`) : null);
}
function n13ShowDashboard(e, day, back, head, note = null) {
  const anyMode = day === "any";
  // Header: the Nerd stats button sits under the price, top right
  head.classList.add("n13-head");
  const price = head.children.length > 1 ? head.lastElementChild : null;
  head.append(h("div", { class: "n13-head-right" }, price, n13NerdButton(e)));
  const pic = e.image ? h("figure", { class: "n13-pic" },
    h("img", { src: e.image, alt: `${e.name} artwork`, loading: "lazy", decoding: "async", onerror: (ev) => ev.target.closest("figure").remove() })) : null;
  const appeals = keyAppealsPanel(e, day);
  const side = pic || appeals ? h("div", { class: "n13-stack" }, pic, appeals) : null;
  const policy = policyPanel(e);
  policy.classList.add("n13-policy");
  const rows = anyMode
    ? [h("p", { class: "notice" }, "Check back within 7 days of your date for a prediction. Schedules change, so confirm before you go."),
      n13Row("about-side", n13AboutTable(e), side), n13Row("extras", dealsPanel(e, day), savingsPanel(e), digitalPanel(e)), policy]
    : e.group === 1
      ? [n13Kpis(e), n13Row("about-side", n13AboutTable(e), side), n13Row("pair", ticketsPanel(e), chancePanel(e)),
        n13Row("pair", linePanel(e), busiestPanel(e, day)), n13Row("extras", dealsPanel(e, day), savingsPanel(e), digitalPanel(e)), policy, n13Why(e)]
      : [n13Row("pair", note, e.group === 2 ? busiestPanel(e, day) : null), n13Row("about-side", n13AboutTable(e), side),
        n13Row("extras", dealsPanel(e, day), savingsPanel(e), digitalPanel(e)), policy];
  setApp(back, head, h("div", { class: "n13-dash" }, rows));
}
// #/nerd-stats/<show_id>: open the "Look up any test result" panel filtered to that show
function n13FocusShow(id) {
  const e = allShows().find((x) => x.show_id === id);
  const sel = document.querySelector(".browse-filters select");
  if (!e || !sel) return;
  const panel = sel.closest("details");
  if (panel) panel.open = true;
  const opt = [...sel.options].find((o) => o.textContent === e.name);
  if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event("change")); }
  (panel || sel).scrollIntoView({ block: "start" });
}
/* ========== end N13 g ========== */

/* ========== N13 e: Nerd stats as a dashboard grid (SPEC 2.8 N13 e) ==========
   Each section becomes a 12-column grid: charts side by side (half width), wide tables across the full width, small
   panels a third. Panels open so several charts show at once (except the long results browser). A panel left alone at
   the end of a row stretches to fill it, so there's never an empty half. Under 860px it's one column again. */
const N13_WIDE = ["Which shows and days are busiest?", "The final score", "Does it beat the simple lookup table", "Look up any test result"];
const N13_THIRD = ["What did it cost?"];
const N13_CLOSED = ["Look up any test result"];
function n13NerdDashboard() {
  for (const grid of document.querySelectorAll(".ns-section .accuracy-grid")) {
    const items = [...grid.children];
    const spans = items.map((el) => {
      const title = (el.querySelector(":scope > summary h3") || {}).textContent || "";
      if (!el.matches("details.panel")) return 12; // number cards and other blocks
      if (!N13_CLOSED.some((t) => title.startsWith(t)) && !el.open) openPanel(el);
      if (N13_WIDE.some((t) => title.startsWith(t))) return 12;
      return N13_THIRD.some((t) => title.startsWith(t)) ? 4 : 6;
    });
    // Pack into rows of 12; the last item on a short row takes the rest of it
    let used = 0;
    spans.forEach((span, i) => {
      if (used + span > 12) used = 0;
      const next = spans[i + 1];
      if (next === undefined || used + span + next > 12) spans[i] = 12 - used;
      used = (used + spans[i]) % 12;
    });
    items.forEach((el, i) => el.style.setProperty("--span", spans[i]));
  }
}
/* ========== end N13 e ========== */

/* ========== N13 d: 3D coverflow carousel (SPEC 2.8 N13 d; docs/reference/glassy-coverflow-carousel.md) ==========
   Rebuilt in plain JS from the reference's geometry: the center tile full size and flat, two on each side stepping
   back, shrinking 8% each, tilting up to 42° and darkening. Drag/swipe, ← → (Home/End), or the ‹ › buttons rotate it;
   it wraps around. Clicking a side tile brings it to the center; clicking the center tile opens the show page.
   Keeps the page's sort order. No autoplay. Reduced motion keeps the 3D layout without the animation. */
function n13Coverflow(cards, list) {
  const n = cards.length;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let index = 0, drag = 0, cardW = 300, step = 234;
  const lastD = new Array(n).fill(null);
  // Side tiles are inert (not tabbable, links off); a click on one rotates it to the center (see the stage click below)
  const slots = cards.map((card) => h("div", { class: "cf-card" }, card));
  const deck = h("div", { class: "cf-deck" }, slots);
  const stage = h("div", {
    class: "cf-stage", tabindex: "0", role: "region", "aria-roledescription": "carousel", "aria-label": "Shows: use the left and right arrow keys",
  }, h("div", { class: "cf-floor", "aria-hidden": "true" }), deck);
  const title = h("p", { class: "cf-title" });
  const sub = h("p", { class: "cf-sub" });
  const count = h("span", { class: "cf-count" });
  const live = h("p", { class: "cf-live", "aria-live": "polite" });
  const btn = (dir, label, text) => h("button", { type: "button", class: "cf-btn", "aria-label": label, onclick: () => go(index + dir) }, text);
  const dock = h("div", { class: "cf-dock" }, count, h("span", { class: "cf-sep", "aria-hidden": "true" }), btn(-1, "Previous show", "‹"), btn(1, "Next show", "›"));
  const wrap = h("div", { class: "cf" }, stage,
    h("div", { class: "cf-info" }, title, sub, dock, h("p", { class: "cf-hint" }, "Drag to explore or ← → to browse")), live);

  // Shortest signed distance from the center, so it wraps around both ways
  const dist = (i) => {
    let d = i - index;
    if (d > n / 2) d -= n;
    if (d < -n / 2) d += n;
    return d;
  };
  function layout(animate = true) {
    slots.forEach((slot, i) => {
      const d = dist(i);
      const off = d + drag / step;
      const a = Math.min(Math.abs(off), 3);
      const hidden = Math.abs(d) > 2;
      // No animation while dragging, under reduced motion, or when a tile wraps to the other side (it would fly across)
      const jump = lastD[i] !== null && Math.abs(d - lastD[i]) > 1.5;
      slot.style.transition = !animate || reduce || jump || drag ? "none" : "";
      slot.style.width = `${cardW}px`;
      slot.style.transform = `translate3d(${off * step}px, 0, ${-a * 130}px) rotateY(${-Math.max(-42, Math.min(42, off * 30))}deg) scale(${1 - a * 0.08})`;
      slot.style.zIndex = String(10 - Math.round(Math.abs(off)));
      slot.style.opacity = hidden ? "0" : "1";
      slot.style.setProperty("--dim", String(Math.min(Math.abs(off), 2) * 0.19));
      slot.classList.toggle("is-center", d === 0);
      slot.style.pointerEvents = hidden ? "none" : "";
      cards[i].inert = d !== 0;
      lastD[i] = d;
    });
    const e = list[index];
    title.textContent = e.name;
    sub.textContent = [e.theater, e.chance_9am !== undefined && e.chance_9am !== null ? `${pct(e.chance_9am)} chance at 9:00 AM` : null].filter(Boolean).join(" · ");
    count.textContent = `${String(index + 1).padStart(2, "0")} / ${String(n).padStart(2, "0")}`;
    live.textContent = `${e.name}. ${index + 1} of ${n}.`;
  }
  function go(i) { index = ((i % n) + n) % n; drag = 0; layout(); }
  function size() {
    if (!stage.isConnected) return;
    const w = stage.clientWidth;
    cardW = Math.min(420, Math.round(w * (w < 500 ? 0.84 : 0.72))); // wider on phones so long names fit
    step = cardW * 0.78;
    stage.style.perspective = `${window.innerWidth >= 1600 ? 1250 : window.innerWidth < 600 ? 900 : 1100}px`;
    layout(false);
    const tallest = Math.max(...slots.map((x) => x.firstChild.offsetHeight));
    stage.style.height = `${tallest + 28}px`;
  }
  // Drag / swipe: horizontal after 8px sideways, cancelled if mostly vertical (12px) so the page still scrolls
  let start = null, horizontal = false, suppressUntil = 0;
  stage.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0) return;
    start = { x: ev.clientX, y: ev.clientY, t: performance.now(), id: ev.pointerId };
    horizontal = false;
  });
  stage.addEventListener("pointermove", (ev) => {
    if (!start || ev.pointerId !== start.id) return;
    const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
    if (!horizontal) {
      if (Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx)) { start = null; return; }
      if (Math.abs(dx) < 8) return;
      horizontal = true;
      try { stage.setPointerCapture(ev.pointerId); } catch { /* pointer already gone */ }
    }
    drag = dx;
    layout(false);
  });
  const end = (ev) => {
    if (!start || ev.pointerId !== start.id) return;
    const dx = ev.clientX - start.x;
    const speed = Math.abs(dx) / Math.max(1, performance.now() - start.t);
    if (horizontal) {
      suppressUntil = performance.now() + 300;
      const far = Math.abs(dx) > Math.min(55, cardW * 0.18) || (Math.abs(dx) > 14 && speed > 0.35);
      drag = 0;
      if (far) go(index + (dx < 0 ? 1 : -1)); else layout();
    }
    start = null;
    horizontal = false;
  };
  stage.addEventListener("pointerup", end);
  stage.addEventListener("pointercancel", end);
  stage.addEventListener("click", (ev) => { if (performance.now() < suppressUntil) { ev.preventDefault(); ev.stopPropagation(); } }, true);
  // Inert side tiles let clicks fall through to the deck, so find the visible side tile under the pointer
  stage.addEventListener("click", (ev) => {
    if (slots[index].contains(ev.target)) return;
    const hit = slots.map((slot, i) => ({ i, r: slot.getBoundingClientRect(), z: Number(slot.style.zIndex), on: slot.style.opacity === "1" }))
      .filter((x) => x.on && x.i !== index && ev.clientX >= x.r.left && ev.clientX <= x.r.right && ev.clientY >= x.r.top && ev.clientY <= x.r.bottom)
      .sort((x, y) => y.z - x.z)[0];
    if (hit) go(hit.i);
  });
  stage.addEventListener("keydown", (ev) => {
    const to = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: n - 1 }[ev.key];
    if (to === undefined) return;
    ev.preventDefault();
    go(to);
  });
  const ro = new ResizeObserver(() => { if (!stage.isConnected) { ro.disconnect(); return; } size(); });
  ro.observe(stage);
  requestAnimationFrame(size);
  // Pictures load after the first layout, so tiles grow: resize once each one lands
  stage.querySelectorAll("img").forEach((img) => img.addEventListener("load", () => size(), { once: true }));
  return wrap;
}
/* ========== end N13 d ========== */

/* ========== N14 d: show page, the predictions first (SPEC 2.8 N14 d) ==========
   Top: the ticket estimate with its range and your chance, next to how the line builds (the arrival time to beat).
   Limited-data shows have no model numbers, so their top is the "probably easy" note next to the busiest-days chart.
   Below: everything else in two columns that balance themselves and end at the same height (no blank holes).
   Gold panel headings, no colored side lines, no savings, and the page sits in the middle 2/3 on wide screens. */
function n14ShowImage(e) {
  if (N14.c) return n14Picture(e, "n14-show-pic"); // N14 c: one shape everywhere, placeholder when there's no photo
  if (!e.image) return null;
  return h("figure", { class: "n14-show-pic" },
    h("img", { src: e.image, alt: `${e.name} artwork`, decoding: "async", onerror: (ev) => ev.target.closest("figure").remove() }));
}
function n14Columns(panels) {
  const list = panels.filter(Boolean);
  const a = h("div", { class: "n14-col" }, list);
  const b = h("div", { class: "n14-col" });
  const box = h("div", { class: "n14-cols" }, a, b);
  // After the first paint, measure at half width and try every split that keeps the reading order (2^n, n <= ~8).
  // Most even split wins; if even the best leaves more than ~100px uneven, keep one full-width column (no holes).
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (!box.isConnected || box.clientWidth < 760 || list.length < 2) return;
    box.classList.add("measuring");
    const heights = list.map((x) => x.offsetHeight + 14);
    box.classList.remove("measuring");
    let best = null;
    for (let mask = 1; mask < (1 << list.length) - 1; mask++) {
      let ha = 0, hb = 0;
      heights.forEach((v, i) => { if (mask & (1 << i)) hb += v; else ha += v; });
      if (!best || Math.abs(ha - hb) < best.diff) best = { mask, diff: Math.abs(ha - hb) };
    }
    if (best.diff > 100) { box.classList.add("single"); return; }
    list.forEach((x, i) => (best.mask & (1 << i) ? b : a).append(x));
    box.classList.add("dealt");
  }));
  return box;
}
function n14ShowPage(e, day, back, head, note = null) {
  const anyMode = day === "any";
  head.classList.add("n14-head");
  const price = head.children.length > 1 ? head.lastElementChild : null;
  head.prepend(n14ShowImage(e) || "");
  head.append(h("div", { class: "n14-head-right" }, price, n13NerdButton(e)));
  const policy = policyPanel(e);
  policy.classList.add("n14-policy");
  let top = null;
  let rest = [];
  if (anyMode) {
    top = h("p", { class: "notice" }, "Check back within 7 days of your date for a prediction. Schedules change, so confirm before you go.");
    rest = [n13AboutTable(e), keyAppealsPanel(e, day), dealsPanel(e, day), digitalPanel(e)];
  } else if (e.group === 1) {
    const predict = ticketsPanel(e);
    predict.classList.add("n14-predict");
    predict.prepend(h("h2", {}, "Rush tickets and your chance"));
    const line = linePanel(e);
    line.classList.add("n14-line");
    top = h("div", { class: "n14-top" }, predict, line);
    rest = [chancePanel(e), busiestPanel(e, day), n13Why(e), n13AboutTable(e), keyAppealsPanel(e, day), dealsPanel(e, day), digitalPanel(e)];
  } else {
    const busy = e.group === 2 ? busiestPanel(e, day) : null;
    if (note) note.classList.add("n14-predict");
    top = h("div", { class: `n14-top${busy ? "" : " single"}` }, note, busy);
    rest = [n13AboutTable(e), keyAppealsPanel(e, day), dealsPanel(e, day), digitalPanel(e)];
  }
  setApp(back, h("div", { class: "n14-page" }, head, top, n14Columns(rest), policy));
}
/* ========== end N14 d ========== */

/* ========== N14 a: the title inside a gold Broadway marquee sign (SPEC 2.8 N14 a) ==========
   Light bulbs all around the frame, placed to fit its size. They chase slowly and softly (three groups taking turns);
   under reduced motion they stay lit. */
if (N14.a) {
  const brand = document.querySelector(".site-header .brand");
  const sign = h("div", { class: "n14-marquee" });
  const bulbs = h("span", { class: "n14-bulbs", "aria-hidden": "true" });
  brand.before(sign);
  sign.append(bulbs, brand);
  let last = "";
  const place = () => {
    const w = sign.clientWidth, ht = sign.clientHeight;
    if (!w || `${w}x${ht}` === last) return;
    last = `${w}x${ht}`;
    const inset = 11, gap = w < 500 ? 22 : 27;
    const nx = Math.max(2, Math.round((w - 2 * inset) / gap)), ny = Math.max(2, Math.round((ht - 2 * inset) / gap));
    const pts = [];
    // Clockwise from the top-left corner, so neighbors chase in order
    for (let i = 0; i < nx; i++) pts.push([inset + (i * (w - 2 * inset)) / nx, inset]);
    for (let j = 0; j < ny; j++) pts.push([w - inset, inset + (j * (ht - 2 * inset)) / ny]);
    for (let i = nx; i > 0; i--) pts.push([inset + (i * (w - 2 * inset)) / nx, ht - inset]);
    for (let j = ny; j > 0; j--) pts.push([inset, inset + (j * (ht - 2 * inset)) / ny]);
    bulbs.replaceChildren(...pts.map(([x, y], k) => h("i", { class: `n14-bulb b${k % 3}`, style: `left:${x.toFixed(1)}px;top:${y.toFixed(1)}px` })));
  };
  new ResizeObserver(place).observe(sign);
  if (document.fonts) document.fonts.ready.then(place);
}
/* ========== end N14 a ========== */

/* ========== N14 c: one image shape everywhere + a stage drawing for shows without a photo (SPEC 2.8 N14 c) ==========
   Tiles, carousel cards and the show page all use 16:9, cropped to fill. web/img/stage.svg is our own drawing
   (curtains, spotlight, three performers), so it's free to use; it also stands in when a Ticketmaster photo fails. */
const N14_STAGE = "img/stage.svg";
function n14Img(e, cls, alt = "") {
  return h("img", {
    class: `${cls} n14-img${e.image ? "" : " n14-stage"}`.trim(), src: e.image || N14_STAGE, alt, loading: "lazy", decoding: "async",
    title: e.image ? null : "No photo for this show yet",
    onerror: (ev) => { if (!ev.target.src.endsWith(N14_STAGE)) { ev.target.src = N14_STAGE; ev.target.classList.add("n14-stage"); } },
  });
}
function n14Picture(e, cls) {
  return h("figure", { class: cls }, n14Img(e, "", e.image ? `${e.name} artwork` : "A theater stage: no photo for this show yet"));
}
/* ========== end N14 c ========== */

/* ========== N14 f: the busiest-shows grid: pink info line instead of a box over the numbers (SPEC 2.8 N14 f) ==========
   Hover, tap or tab to a cell: it turns light pink (tinted by its level, so you can still tell how busy it was) and its
   details show in a pink line above the grid. */
const N14_LEVELS = ["no data", "under 5", "5–9", "10–14", "15–19", "20+"];
function n14HeatCell(cell, title, tip, level) {
  cell.tabIndex = 0;
  cell.dataset.title = title;
  cell.dataset.tip = `${tip}${level ? ` · level ${N14_LEVELS[level]}` : ""}`;
  return cell;
}
function n14HeatInfo(table) {
  const empty = "Hover or tap a day to see how busy it is.";
  const info = h("p", { class: "n14-heat-info", "aria-live": "polite" }, empty);
  const show = (ev) => {
    const td = ev.target.closest("td[data-title]");
    if (!td) return;
    table.querySelectorAll(".n14-hot").forEach((x) => x.classList.remove("n14-hot"));
    td.classList.add("n14-hot");
    info.replaceChildren(h("b", {}, td.dataset.title), ": ", td.dataset.tip);
  };
  table.addEventListener("pointerover", show);
  table.addEventListener("focusin", show);
  table.addEventListener("pointerleave", () => {
    info.textContent = empty;
    table.querySelectorAll(".n14-hot").forEach((x) => x.classList.remove("n14-hot"));
  });
  return info;
}
/* ========== end N14 f ========== */

/* ========== N14 e: Refresh as an icon in the top-right corner; bigger Nerd stats jump buttons (SPEC 2.8 N14 e) ==========
   Only Rachel uses Refresh, so it's a quiet circular-arrow icon that says "Refresh" on hover or focus. Same button, same
   click handler (openRefresh), just moved and redrawn. */
if (N14.e) {
  const btn = document.getElementById("open-refresh");
  const svg = s("svg", { viewBox: "0 0 24 24", width: "20", height: "20", fill: "none", stroke: "currentColor", "stroke-width": "2.2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
  svg.append(s("path", { d: "M20 11a8 8 0 1 0-2.3 5.7" }), s("path", { d: "M20 4v7h-7" }));
  btn.replaceChildren(svg, h("span", { class: "n14-refresh-label" }, "Refresh"));
  btn.setAttribute("aria-label", "Refresh");
  btn.classList.add("n14-refresh");
  document.querySelector(".site-header").append(btn);
}
/* ========== end N14 e ========== */

/* ========== N14 g: Nerd stats as a real, clickable dashboard (SPEC 2.8 N14 g) ==========
   Sections reordered so the strongest results come first; panels paired side by side (12-column grid, sizes below);
   gold question headings; and things to click: the headline cards jump to their charts, the line-growth chart has
   series toggles beside it, funnel steps explain what was dropped and why, a show in "reports per show" opens a card
   with its page and its test results, and show names in the busiest grid open the show. */
const N14_ORDER = ["ns-summary", "ns-tests", "ns-lines", "ns-truth", "ns-model", "ns-data"];
// [title starts with, columns out of 12]. Panels keep this order inside their section.
const N14_LAYOUT = {
  "ns-tests": [["The final score", 6], ["Does it beat", 6], ["Line error by test month", 6], ["Did the 80% line range hold?", 6],
    ["When we predict a line", 6], ["When we say a chance", 6], ["The always-yes problem", 7], ["Real trips", 5]],
  "ns-lines": [["Which shows and days are busiest?", 6], ["How fast does the line grow?", 6]],
  "ns-truth": [["The line: every test report", 6], ["The tickets: every stated count", 6], ["Got a ticket or not", 12], ["Look up any test result", 12]],
  "ns-model": [["What moves the line most?", 6], ["How it's built", 6]],
  "ns-data": [["From Reddit comments", 5], ["How many reports does each show have?", 4], ["What did it cost?", 3]],
};
const N14_KPI_TARGETS = { k1: "Line error by test month", k2: "Did the 80% line range hold?", k3: "When we say a chance", k4: "The always-yes problem" };
const n14Title = (el) => ((el.querySelector(":scope > summary h3") || {}).textContent || "");
function n14FindPanel(start) {
  return [...document.querySelectorAll(".ns-section details.panel")].find((x) => n14Title(x).startsWith(start));
}
function n14Jump(start) {
  const panel = n14FindPanel(start);
  if (!panel) return;
  if (!panel.open) openPanel(panel);
  panel.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  panel.classList.remove("n14-flash");
  requestAnimationFrame(() => panel.classList.add("n14-flash"));
}
function n14NerdDashboard() {
  const main = app;
  const nav = main.querySelector(".ns-nav");
  // 1. Sections: strongest results first; the jump buttons follow the same order
  const sections = N14_ORDER.map((id) => document.getElementById(id)).filter(Boolean);
  const all = [...main.querySelectorAll(":scope > .ns-section")];
  const marker = document.createComment("n14 sections");
  if (all.length) all[all.length - 1].after(marker);
  sections.forEach((sec) => main.insertBefore(sec, marker));
  marker.remove();
  if (nav) {
    const buttons = [...nav.children];
    const byId = new Map(NS_SECTIONS.map(([id], i) => [id, buttons[i]]));
    N14_ORDER.forEach((id) => byId.get(id) && nav.append(byId.get(id)));
  }
  // 2. Each section: order and size the panels, open them, fill any short row
  for (const sec of sections) {
    const grid = sec.querySelector(".accuracy-grid");
    if (!grid) continue;
    const layout = N14_LAYOUT[sec.id] || [];
    const items = [...grid.children];
    const rank = (el) => { const i = layout.findIndex(([t]) => n14Title(el).startsWith(t)); return i < 0 ? 99 : i; };
    items.sort((x, y) => rank(x) - rank(y)).forEach((el) => grid.append(el));
    const spans = items.map((el) => {
      if (!el.matches("details.panel")) return 12;
      const title = n14Title(el);
      if (!title.startsWith("Look up any test result") && !el.open) openPanel(el);
      const hit = layout.find(([t]) => title.startsWith(t));
      return hit ? hit[1] : 6;
    });
    let used = 0;
    spans.forEach((span, i) => {
      if (used + span > 12) used = 0;
      const next = spans[i + 1];
      if (next === undefined || used + span + next > 12) spans[i] = 12 - used;
      used = (used + spans[i]) % 12;
    });
    items.forEach((el, i) => el.style.setProperty("--span", spans[i]));
    grid.classList.add("n14-grid");
  }
  // 3. Things to click
  document.querySelectorAll(".ns-kpis .kpi").forEach((card) => {
    const tone = [...card.classList].find((c) => /^k\d$/.test(c));
    const target = N14_KPI_TARGETS[tone];
    if (!target) return;
    card.classList.add("n14-click");
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.title = "Show the chart behind this number";
    card.addEventListener("click", () => n14Jump(target));
    card.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); n14Jump(target); } });
  });
  n14GrowthToggles();
  n14FunnelInfo();
  n14ReportsCard();
  n14HeatLinks();
}
// Line growth: legend becomes on/off toggles beside the chart
function n14GrowthToggles() {
  const panel = n14FindPanel("How fast does the line grow?");
  const entry = panel && charts.find((c) => panel.contains(c.holder));
  if (!entry) return;
  const body = panel.querySelector(".faq-body");
  const all = entry.cfg.series.slice();
  const on = new Set(all.map((x) => x.name));
  const legend = body.querySelector(".legend");
  const toggles = h("div", { class: "n14-toggles", role: "group", "aria-label": "Lines to show" },
    h("span", { class: "n14-side-label" }, "Show"),
    all.map((ser) => h("button", {
      type: "button", class: "n14-toggle", "aria-pressed": "true", style: `--c:${ser.color}`,
      onclick: (ev) => {
        if (on.has(ser.name) && on.size === 1) return; // keep at least one line
        if (on.has(ser.name)) on.delete(ser.name); else on.add(ser.name);
        ev.currentTarget.setAttribute("aria-pressed", String(on.has(ser.name)));
        entry.cfg.series = all.filter((x) => on.has(x.name));
        drawChart(entry.holder, entry.cfg);
      },
    }, h("i", { class: ser.dash ? "dashed" : "" }), ser.name)));
  const takeaway = body.firstElementChild && body.firstElementChild.tagName === "P" ? body.firstElementChild : null;
  const side = h("div", { class: "n14-side" }, toggles, takeaway);
  if (legend) legend.remove();
  const chartBox = h("div", { class: "n14-chartbox" });
  entry.holder.before(chartBox);
  chartBox.append(entry.holder);
  body.prepend(h("div", { class: "n14-split" }, chartBox, side));
  requestAnimationFrame(() => drawChart(entry.holder, entry.cfg));
}
// Cleaning funnel: hover, tap or tab to a step to see what it kept, what it dropped and why
function n14FunnelInfo() {
  const rows = [...document.querySelectorAll(".funnel .funnel-row")];
  if (!rows.length) return;
  const empty = "Hover or tap a step to see what it dropped and why.";
  const info = h("p", { class: "n14-info", "aria-live": "polite" }, empty);
  rows[rows.length - 1].parentElement.after(info);
  const nums = rows.map((r) => Number((r.querySelector(".funnel-bar span") || {}).textContent.replace(/,/g, "")));
  rows.forEach((r, i) => {
    r.tabIndex = 0;
    const label = r.querySelector(".funnel-label").textContent;
    const cut = r.querySelector(".funnel-cut").textContent.replace(/^−[\d,]+\s*/, "");
    const text = i === 0
      ? `${nums[0].toLocaleString()} reports pulled out ${cut}: the AI read every comment and kept anything about a rush line, ticket count or outcome.`
      : `${nums[i - 1].toLocaleString()} → ${nums[i].toLocaleString()}: kept ${pct(nums[i] / nums[i - 1])}, dropped ${(nums[i - 1] - nums[i]).toLocaleString()} (${cut}).`;
    const show = () => {
      rows.forEach((x) => x.classList.toggle("n14-hot", x === r));
      info.replaceChildren(h("b", {}, label), ": ", text);
    };
    r.addEventListener("pointerenter", show);
    r.addEventListener("focus", show);
  });
  info.parentElement.addEventListener("pointerleave", () => { rows.forEach((x) => x.classList.remove("n14-hot")); info.textContent = empty; });
}
// Reports per show: click a show to see its numbers, its page and its test results
function n14ReportsCard() {
  const panel = n14FindPanel("How many reports does each show have?");
  if (!panel) return;
  const shows = allShows();
  const dayFor = (id) => Object.keys(state.data.days).sort().find((d) => state.data.days[d].some((x) => x.show_id === id));
  const card = h("div", { class: "n14-info n14-card", "aria-live": "polite" }, "Click a show to see its numbers.");
  panel.querySelector(".bars").after(card);
  panel.querySelectorAll(".bar-row").forEach((row) => {
    const name = row.querySelector(".bar-label").textContent;
    const e = shows.find((x) => x.name === name);
    if (!e) return;
    row.classList.add("n14-click");
    row.tabIndex = 0;
    const open = () => {
      panel.querySelectorAll(".bar-row.n14-hot").forEach((x) => x.classList.remove("n14-hot"));
      row.classList.add("n14-hot");
      const day = dayFor(e.show_id);
      card.replaceChildren(
        h("b", {}, e.name), h("br"),
        `${e.line_reports} line reports · ${e.reports_per_week} reports a week · ${e.group === 1 ? "full prediction" : "not enough reports for a prediction yet"}`,
        h("span", { class: "n14-card-links" },
          day ? h("a", { href: `#/show/${day}/${encodeURIComponent(e.show_id)}` }, "Open its show page →") : null,
          e.group === 1 ? h("a", { href: `#/nerd-stats/${encodeURIComponent(e.show_id)}` }, "See its test results →") : null));
    };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } });
  });
}
// Busiest grid: show names open the show page
function n14HeatLinks() {
  const shows = allShows();
  const dayFor = (id) => Object.keys(state.data.days).sort().find((d) => state.data.days[d].some((x) => x.show_id === id));
  document.querySelectorAll(".heat tbody th.show-name").forEach((th) => {
    const e = shows.find((x) => x.name === th.textContent);
    const day = e && dayFor(e.show_id);
    if (day) th.replaceChildren(h("a", { class: "n14-show-link", href: `#/show/${day}/${encodeURIComponent(e.show_id)}` }, e.name));
  });
}
/* ========== end N14 g ========== */

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
  app.classList.toggle("n14-narrow", N14.d && parts[0] === "show"); // N14 d: show page in the middle 2/3
  if (parts[0] === "nerd-stats" || parts[0] === "accuracy") {
    setNav("nerd-stats");
    renderNerdStats();
    if (N13.e && !N14.g) n13NerdDashboard(); // N13 e (N14 g takes over when on)
    if (N14.g) n14NerdDashboard(); // N14 g
    if (N13.g && parts[1]) setTimeout(() => n13FocusShow(decodeURIComponent(parts[1])), 60); // N13 g
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
    h("p", {}, `Placeholder settings, not final: GO at ${pct(d.placeholders.go_at_or_above)} and up, Maybe at ${pct(d.placeholders.maybe_at_or_above)} and up, based on the chance if you arrive at 9:00 AM. The arrival target is ${pct(d.placeholders.target_chance)}.`),
    // Credits. The Times Square Alliance shared its counts on the condition that they're credited and the raw counts
    // never appear on the site (2026-11-17); Wikipedia and Open-Meteo ask for credit too.
    h("p", { class: "credits" }, "Pedestrian counts: Times Square Alliance. Rush reports: r/Broadway on Reddit. Rush policies, casts and schedules: Playbill. Casting news: BroadwayWorld. Performances and show images: Ticketmaster. TKTS board: TDF. Midtown subway riders: MTA (data.ny.gov). Page views: Wikipedia. Weather: Open-Meteo.com."));
}

fetch("data/predictions.json", { cache: "no-store" })
  .then((r) => { if (!r.ok) throw new Error(`status ${r.status}`); return r.json(); })
  .then((data) => { state.data = data; renderFooter(); route(); })
  .catch((err) => {
    setApp(h("p", { class: "empty" }, `Couldn't load the predictions file (${err.message}). Start the site with a local server, not by opening the file directly.`));
  });

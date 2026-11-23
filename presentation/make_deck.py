"""Builds presentation/broadway-rush-slides.pptx (preliminary, 2026-11-23). Re-run after the charts change.

    .venv\\Scripts\\python presentation\\make_visuals.py
    .venv\\Scripts\\python presentation\\make_deck.py

Plain python-pptx: 16:9, the website's purple and gold, Arial Black headlines, Segoe UI body. Every text box is
editable in PowerPoint afterwards.
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
VIS = HERE / "visuals"
OUT = HERE / "broadway-rush-slides.pptx"

BG, CARD = RGBColor(0x3B, 0x28, 0x62), RGBColor(0x51, 0x3B, 0x7D)
INK, INK2, GOLD, PINK, TEAL = (RGBColor(0xF7, 0xF1, 0xFF), RGBColor(0xD6, 0xC9, 0xEC), RGBColor(0xF0, 0xB8, 0x29),
                               RGBColor(0xFF, 0x4F, 0xB3), RGBColor(0x2F, 0x9F, 0xC0))
HEAD, BODY = "Arial Black", "Segoe UI"
W, H = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]


def slide():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    return s


def text(s, x, y, w, h, runs, size=18, color=INK, font=BODY, align=PP_ALIGN.LEFT, space=6):
    """runs: a string, or a list of paragraphs; each paragraph a string or a list of (text, bold, color) parts."""
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    paras = [runs] if isinstance(runs, str) else runs
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        para.space_after = Pt(space)
        for part in ([(p, False, color)] if isinstance(p, str) else p):
            t, bold, c = (part + (color,))[:3] if len(part) == 2 else part
            r = para.add_run()
            r.text = t
            r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
            r.font.color.rgb = c
    return tb


def title(s, head, kicker=None):
    if kicker:
        text(s, Inches(.6), Inches(.35), Inches(12), Inches(.4), kicker.upper(), size=13, color=PINK, font=BODY)
    text(s, Inches(.6), Inches(.65), Inches(12.2), Inches(1), head.upper(), size=30, color=INK, font=HEAD)
    bar = s.shapes.add_shape(1, Inches(.62), Inches(1.5), Inches(.9), Emu(45000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = GOLD
    bar.line.fill.background()


def picture(s, name, x, y, w=None, h=None):
    p = VIS / name
    if p.exists():
        return s.shapes.add_picture(str(p), x, y, width=w, height=h)
    text(s, x, y, w or Inches(5), Inches(.5), f"[missing: {name}]", size=14, color=PINK)


def bullets(s, x, y, w, h, items, size=18):
    paras = []
    for it in items:
        if isinstance(it, tuple):  # (bold lead, rest)
            paras.append([("• ", False, GOLD), (it[0], True, INK), (it[1], False, INK2)])
        else:
            paras.append([("• ", False, GOLD), (it, False, INK2)])
    return text(s, x, y, w, h, paras, size=size, space=10)


def stat(s, x, y, big, small, color=GOLD):
    box = s.shapes.add_shape(1, x, y, Inches(2.9), Inches(1.35))
    box.fill.solid()
    box.fill.fore_color.rgb = CARD
    box.line.fill.background()
    text(s, x + Inches(.2), y + Inches(.1), Inches(2.6), Inches(.7), big, size=30, color=color, font=HEAD)
    text(s, x + Inches(.2), y + Inches(.78), Inches(2.6), Inches(.6), small, size=12.5, color=INK2)


# 1. Title
s = slide()
text(s, Inches(.6), Inches(1.6), Inches(6.8), Inches(1.2), "BROADWAY RUSH", size=40, color=GOLD, font=HEAD)
text(s, Inches(.6), Inches(2.75), Inches(6.4), Inches(1.6),
     "Predicting Broadway rush-ticket lines from 153,378 Reddit comments", size=24, color=INK)
text(s, Inches(.6), Inches(4.4), Inches(6.4), Inches(1),
     [[("Rachel Chen", True, INK)], "NYU Center for Data Science · Project Expo 2026"], size=16, color=INK2)
picture(s, "site_shows.png", Inches(7.4), Inches(.9), w=Inches(5.4))

# 2. The problem
s = slide()
title(s, "Is rush worth the early alarm?", "The problem")
bullets(s, Inches(.6), Inches(1.9), Inches(7.2), Inches(5), [
    ("Rush tickets: ", "$40–50 seats some shows sell when the box office opens, first come, first served."),
    ("The gamble: ", "lines can start hours early and tickets can run out after a handful of people. "
                     "You can't tell in advance."),
    ("The question: ", "for any day this week, how long will each line be, how many tickets will there be, "
                       "and what's my chance if I arrive at 9:00?"),
    ("The catch: ", "no dataset of rush lines exists. Ticketing sites don't keep history, "
                    "so I had to build the data first."),
], size=19)
stat(s, Inches(8.5), Inches(2.0), "$40–50", "typical rush ticket price")
stat(s, Inches(8.5), Inches(3.6), "0", "public datasets of rush lines before this project", color=PINK)
stat(s, Inches(8.5), Inches(5.2), "108", "shows with rush reports, Jun 2024 – Nov 2026", color=TEAL)

# 3. Data
s = slide()
title(s, "Building the dataset", "Data collection and cleaning")
bullets(s, Inches(.6), Inches(1.9), Inches(5.4), Inches(5.3), [
    ("Reddit r/Broadway: ", "153,378 comments via the Arctic Shift archive, the only record of real lines."),
    ("Box office: ", "weekly grosses (capacity %, average price), 127 weeks; two sources agree within 0.02%."),
    ("Context: ", "rush policies and schedules (Playbill), performances (Ticketmaster API), "
                  "TKTS discount boards (GitHub Actions job), casting news, subway riders, Times Square foot traffic."),
    ("No peeking: ", "every input uses only what was known 7 days before the date."),
], size=16)
picture(s, "0_cleaning_funnel.png", Inches(6.3), Inches(1.85), w=Inches(6.6))

# 4. LLM extraction
s = slide()
title(s, "Teaching an LLM to read rush reports", "Extraction and validation")
bullets(s, Inches(.6), Inches(1.9), Inches(7.4), Inches(5.3), [
    ("Claude Haiku via the Batch API: ", "each comment plus its parent becomes typed observations: line counts, "
                                         "arrival times, spot in line, outcome, stated ticket counts. About $3 in total."),
    ("Answer key: ", "human-reviewed labels with a held-out set, scored on report detection, observation "
                     "precision/recall and per-field accuracy."),
    ("Error analysis over score-chasing: ", "the main failure was copying numbers from the parent comment. "
                                            "One prompt fix took precision from 67% to 80%."),
    ("Second-pass checker: ", "a re-read step that flags and fixes doubtful observations; "
                              "precision rose to 82–93% on the two test sets."),
], size=17)
stat(s, Inches(8.7), Inches(2.0), "94%", "of held-out comments correctly called report / no report")
stat(s, Inches(8.7), Inches(3.6), "77% / 87%", "observation precision / recall, held-out set", color=TEAL)
stat(s, Inches(8.7), Inches(5.2), "15,044", "clean rush reports after checks and de-duplication", color=PINK)

# 5. How lines behave
s = slide()
title(s, "What the data shows", "Exploration")
picture(s, "1_line_growth.png", Inches(.6), Inches(1.8), w=Inches(8.6))
bullets(s, Inches(9.4), Inches(2.0), Inches(3.6), Inches(5), [
    "Lines build slowly, then fast in the last 2 hours.",
    "The middle half of mornings spans about 8 to 21 people at opening: same show, very different days.",
    "For most shows, Saturday and Sunday lines run longest.",
], size=16)

# 6. Model
s = slide()
title(s, "Two models, one answer", "Model design")
for i, (head, body, color) in enumerate([
        ("LINE LENGTH", "LightGBM gradient-boosted trees predict people in line at each hour before opening, with an "
                        "80% range. Line counts are plentiful (6,714 points), so trees can learn day-of-week and "
                        "show patterns.", GOLD),
        ("TICKETS RELEASED", "A hierarchical Bayesian negative-binomial model (NumPyro, NUTS) learns from exact "
                             "counts plus censored clues: \"got one at #N\" means at least N; \"sold out before me at "
                             "#N\" means fewer than N. Shows share information, so thin shows borrow strength.", TEAL),
        ("YOUR CHANCE", "Combine the two: simulate the line at your arrival time and the day's ticket supply, and "
                        "count the share of scenarios where your spot still gets a ticket.", PINK)]):
    x = Inches(.6 + i * 4.2)
    box = s.shapes.add_shape(1, x, Inches(2.0), Inches(3.9), Inches(3.9))
    box.fill.solid()
    box.fill.fore_color.rgb = CARD
    box.line.color.rgb = color
    text(s, x + Inches(.25), Inches(2.2), Inches(3.4), Inches(.6), head, size=18, color=color, font=HEAD)
    text(s, x + Inches(.25), Inches(2.95), Inches(3.4), Inches(3.6), body, size=17, color=INK2)

# 7. Evaluation
s = slide()
title(s, "How do I know it works?", "Evaluation")
picture(s, "2_line_error_by_month.png", Inches(.6), Inches(1.8), w=Inches(8.6))
bullets(s, Inches(9.4), Inches(1.9), Inches(3.6), Inches(5.4), [
    ("Rolling backtest: ", "each test month is predicted by a model trained only on earlier months."),
    ("Baseline: ", "a per-show lookup table. The model has to beat it to earn its complexity."),
    ("Fair comparisons: ", "every model is scored on the identical test reports."),
    ("Locked months: ", "3 months stayed untouched until the end, then were scored once: 4.60 vs 5.67 people. "
                        "No drop from the test months (4.53), so the choices weren't luck."),
], size=15)

# 8. Feature testing
s = slide()
title(s, "Testing 37 inputs, keeping 14", "Feature selection")
picture(s, "3_what_mattered.png", Inches(.6), Inches(1.75), h=Inches(5.5))
bullets(s, Inches(9.2), Inches(1.9), Inches(3.8), Inches(5.4), [
    "Each input group removed in turn, model retrained, error compared month by month.",
    ("Keep rule: ", "removing it must hurt by more than month-to-month noise."),
    ("Surprise: ", "star casting, TKTS and Times Square traffic didn't help. "
                   "Too many inputs for this much data adds noise."),
    ("Lean set: ", "line error 4.65 → 4.52 people on identical test reports."),
], size=15)

# 9. Tickets
s = slide()
title(s, "The honest part: tickets", "Results")
picture(s, "4_tickets_two_tests.png", Inches(.6), Inches(1.8), w=Inches(8.6))
bullets(s, Inches(9.4), Inches(1.9), Inches(3.6), Inches(5.4), [
    ("Reporting bias: ", "people post counts mostly when they're small, so that test rewards guessing low."),
    ("Sold-out clues: ", "\"sold out by 10:30\" plus a line count shortly before became an \"at most\" clue: "
                         "ticket error down 11%, better in 7 of 8 months."),
    ("What the site shows: ", "the lookup's ticket number (closer on stated counts); the model drives your chance."),
], size=15)

# 10. Website
s = slide()
title(s, "The product", "Website")
picture(s, "site_shows.png", Inches(.6), Inches(1.8), h=Inches(4.75))
picture(s, "site_nerdstats.png", Inches(7.2), Inches(1.8), h=Inches(4.75))
text(s, Inches(.6), Inches(6.7), Inches(12.2), Inches(.6),
     "Shows ranked by your chance of a ticket · 7-day view · filters · show pages · \"Nerd stats\" with every test result",
     size=15, color=INK2)

# 11. Lessons
s = slide()
title(s, "What I learned", "Takeaways")
bullets(s, Inches(.6), Inches(1.9), Inches(12), Inches(5.3), [
    ("Data you need often doesn't exist. ", "Building it (scraping, LLM extraction, validation) was most of the work."),
    ("Measure the LLM like any model: ", "answer key, held-out set, read the errors."),
    ("A simple baseline keeps you honest. ", "It still wins one ticket test, so the site uses it there."),
    ("Lock some data away. ", "One untouched final score shows whether your choices were luck."),
    ("More features ≠ better. ", "Removing six input groups improved the model."),
    ("Know your test's bias. ", "Who posts, and when, shapes what \"accuracy\" means."),
], size=20)

# 12. Thanks
s = slide()
text(s, Inches(.6), Inches(2.2), Inches(12), Inches(1.2), "THANK YOU", size=54, color=GOLD, font=HEAD, align=PP_ALIGN.CENTER)
text(s, Inches(.6), Inches(3.6), Inches(12), Inches(1.5),
     ["Code: github.com/rachelchen24/broadway-rush", "Live site: [add Vercel link]"],
     size=20, color=INK2, align=PP_ALIGN.CENTER)
text(s, Inches(.6), Inches(6.4), Inches(12), Inches(.8),
     "Data: r/Broadway (Reddit), Playbill, Ticketmaster, TDF, BroadwayWorld, MTA, Wikimedia. "
     "Pedestrian counts: Times Square Alliance.", size=12, color=INK2, align=PP_ALIGN.CENTER)

prs.save(OUT)
print("wrote", OUT, len(prs.slides), "slides")

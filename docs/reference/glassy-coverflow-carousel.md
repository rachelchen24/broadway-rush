# Reference: 21st.dev "Glassy Coverflow Carousel" (Rachel's pick, 2026-11-23)

Kept for SPEC §2.8 N13 d. This is the React component Rachel liked on 21st.dev. **Our site is plain HTML/CSS/JS (`web/`), not React, Tailwind or TypeScript, so don't install it.** Rebuild the same motion in vanilla JS in `web/app.js` and `web/styles.css`. The code comment says its geometry was "adapted from educalvolpz/coverflow-carousel on 21st"; check that component's license before copying code word for word. Reusing the numbers and the idea is fine.

## What to take from it

**Geometry** (per card, `offset` = distance from the center card, including any drag in progress):
- Stage: `perspective: 1100px` (1250px at 1600px+ wide, 900px under 600px), `transform-style: preserve-3d`, cards absolutely positioned and centered.
- Card width: `min(420px, 72% of stage width)`. Spacing between cards: `step = cardWidth * 0.78`.
- `transform: translate3d(offset * step px, 0, -min(|offset|, 3) * 130 px) rotateY(-clamp(offset * 30, -42, 42) deg) scale(1 - min(|offset|, 3) * 0.08)`.
- Shows 2 cards on each side. One extra hidden slot on each end recycles cards at the wraparound so they don't fly across the deck. `z-index: 10 - |d|`.
- Side cards get a dark overlay: opacity `min(|offset|, 2) * 0.19`.
- Transition: `transform .7s cubic-bezier(.22,1,.36,1), opacity .5s ease`. No transition while dragging.
- A soft blurred oval "floor" shadow under the stage.

**Input**
- Drag or swipe: becomes horizontal after 8px of sideways movement, and cancels if the move is mostly vertical (more than 12px), so the page still scrolls. It moves to the next card if dragged past `min(55px, 18% of card)`, or a quick flick (over 14px at more than 0.35 px/ms). Clicks are ignored for 300ms after a drag.
- Keyboard: ← → move, Home/End jump to the first or last card. Only the center card is tabbable.
- Clicking a side card brings it to the center. Clicking the center card opens it. **For us that opens the show page**, not a preview dialog.
- It wraps around endlessly.

**Bottom area**
- Under the stage: the center card's title (large) and subtitle (small, muted).
- A pill-shaped "dock": position counter `03 / 12` | ‹ (pause/play) ›. Autoplay is off by default and pauses on hover, focus, drag, a hidden tab or reduced motion. Our call: probably leave autoplay out.
- Hint line: "Drag to explore or ← → to browse".
- Screen-reader live region: "Title. 3 of 12."

**Reduced motion:** keep the 3D layout, turn off the animated transitions and autoplay.

## What NOT to take
- The light `Canvas` default colors: map its color roles to our dark purple tokens plus the Nerd stats gradients (N13 f).
- The brand logo header, YouTube trailer embed, "browser bar" dots, Inter/Outfit fonts (we use Montserrat Black + Poppins), lucide-react icons (use text chevrons or inline SVG), and the prompt's "fill with Unsplash images" step (we have real Ticketmaster show images).
- Its fixed `height: 100svh` shell: ours sits inside the home page, one coverflow per group (as the current carousel is one row per group), sized to fit the tile.

## Original prompt (as Rachel pasted it, code summarized)
The prompt asks to copy `glassy-coverflow-carousel.tsx` into `/components/ui` of a shadcn + Tailwind + TypeScript project, install `lucide-react`, and render the demo (five action films, `layout="poster"`, `initialIndex={2}`). Its props: `items` (id, title, subtitle, image, accent, description, href, trailerUrl), `initialIndex`, `layout` ("website" 16:10 or "poster" 2:3), `interval` (≥2500ms), `autoPlay`, `label`, `brand`, `onSelect`. Full source: Rachel's message in the 2026-11-23 spec chat. Ask her to paste it again if the exact code is needed.

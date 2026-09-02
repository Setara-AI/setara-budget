# Claude Design prompt — QC Studio (just the tools that exist today)

**Scope:** This brief covers ONLY the five quality-control tools that are working right now —
not the full screenplay→stringout pipeline (that lives in `claude-design-prompt.md`). Use this to
get a beautiful, real front end for the current studio, then wire it to the FastAPI endpoints.

**How to use this:** Paste everything below the line into Claude Design for a cohesive first pass.
Then refine screen-by-screen in chat (e.g. "make the Consistency before/after a draggable slider,"
"show the Nano Banana refusal error state"). If it's too much at once, feed it in this order:
(1) *Aesthetic direction* + *App shell*, (2) the *Shared component language*, (3) the two **check &
fix** tools (Consistency, Animation) — they're the most complex and define the rest. Tune the accent
color and density with Claude Design's sliders. When you love it, use **developer handoff → Claude
Code** (with your `frontend-design` skill + `CLAUDE.md`) to build it against the FastAPI endpoints.
Working name below is **"QC Studio"** — swap for whatever you like.

---

Design a professional, cinematic web application called **QC Studio** — an automated quality-control
bench for AI-generated film stills. A filmmaker drops in a generated frame (and sometimes a reference
frame) and the app tells them, with a clear verdict, whether the image is good enough to use — and for
two of the tools, automatically **re-renders it until it passes**. The user is a **director, DIT, or
post supervisor, not an engineer** — it should feel like a premium film-production instrument they'd
trust on a real project, never a generic AI SaaS dashboard or a developer console.

There are **five tools**, in two families:

- **Check only** (a verdict, no image change): **Cinematic**, **Clearance**, **Character**.
- **Check & fix** (a verdict, then automatic re-rendering until it passes): **Consistency**, **Animation**.

Make that two-family distinction legible in the UI — "check & fix" tools carry a small "fixes images"
marker and show an *attempts* history; "check only" tools never imply they'll alter the frame.

## Aesthetic direction

Anchor the look on **Krea**: dark, premium, generation-first — deep charcoal surfaces, minimal chrome,
lots of breathing room, and the **image under test treated as the hero of the screen**. Borrow the
**calm review/approval clarity of Frame.io** for the verdict and status language.

- **Color:** a near-black, slightly warm charcoal base (not pure #000), subtle elevation — thin 1px
  borders, soft shadows, a faint glass blur on overlays/inspectors. Commit to **one** confident accent:
  a warm cinematic **amber/gold** for primary actions and the "passed/approved" signal. Use a calm
  **green** for pass, a **muted red/amber** for fail/flag, never alarmist. Let most of the color come
  from the **stills themselves**, not decorative gradients.
- **Typography:** distinctive, not generic. A **characterful display face** for titles/verdicts paired
  with a **clean technical sans** for body and a **monospace** for scores, confidence values, seeds and
  thresholds. Avoid the default "AI" look (no Inter/Roboto/Arial).
- **Density & motion:** pro-tool information density, calm and spacious. Motion only at high-impact
  moments: a result resolving from "analyzing" into a verdict, a satisfying **"lock"/"passed"**
  animation, and a smooth cross-fade between *original → fixed* attempts.
- **Avoid:** purple-on-white gradients, stock card grids, cluttered enterprise chrome, emoji, anything
  that reads as a generic template.

## App shell

A **left rail** lists the five tools, grouped under two headers — **Check** (Cinematic · Clearance ·
Character) and **Check & Fix** (Consistency · Animation). Each tool opens a focused **workspace**.

- **Persistent top bar:** the QC Studio wordmark, and a **Gemini API key** control (entered once,
  shared across the four Gemini-powered tools; show a subtle "connected" dot). **Character runs fully
  locally and needs no key** — reflect that on its screen. The two Check-&-Fix tools use the paid Nano
  Banana Pro model — show a small **"paid · billing required"** marker on those two.
- **Workspace layout (shared across all five):** a calm two-region layout — **inputs on the left**
  (uploads + a few controls + the primary action button), **results on the right** (the hero verdict).
  This is the one consistent skeleton; the result region differs per tool (below).

## Shared component language (make these especially crisp — they repeat everywhere)

1. **Verdict banner** — the headline result at the top of every result region. Three visual states:
   **PASS** (green/amber, calm), **FAIL / NEEDS REVIEW** (muted red), and **FIXED** (amber "lock"
   treatment, for the check-&-fix tools after a successful re-render). Includes a one-line plain-English
   summary and a **confidence** read (0–100, mono).
2. **Score meter** — a small ring or bar showing "X of N traits/aspects passed (NN%)" against the
   active **threshold** marker, so you can see how close to the bar it landed.
3. **Criteria checklist** — replaces the current plain markdown tables. A list of rows, each = one
   trait/aspect/category with a **pass/fail/flag pill**, its human name, and a one-sentence note.
   **Critical / must-pass** items are visually elevated (a small "must-pass" tag) and, when failing,
   surface to the top. This single component skins all five tools' detailed results.
4. **Threshold / strictness control** — a slider with a labelled value and a tooltip explaining the
   trade-off ("higher = stricter"). Lives in the inputs column.
5. **Upload dropzone** — premium drag/drop for a single image; a multi-file variant for Character's
   1–5 reference photos. Show thumbnails once added.
6. **Attempts strip** (check-&-fix tools only) — a horizontal filmstrip of every render attempt
   ("Original → Fix 1 → Fix 2 …"), each thumbnail captioned with its score; selecting one shows it in
   the hero. Pair with a **before/after compare** (slider or toggle) of original vs current best.
7. **QC badge** — a tiny status chip (pass/fail/flag + tool icon) for each tool; designed to also live
   on a thumbnail later, so it reads at small sizes. (This is the seed of the badge cluster the full
   pipeline product will reuse.)

## The five screens (populate with realistic film content — a moody two-scene piece such as a
rain-soaked hospital waiting room or a small sci-fi cabin — never lorem ipsum, never fake brand logos)

### 1. Cinematic — *Check only*
"Does this look like a real, cinematic film still — not flat, not AI-looking?" High bar.
- **Inputs:** one image; a **"Bar"** strictness slider (fraction of traits that must pass; default high,
  ~0.85); Check button.
- **Result:** Verdict banner — **CINEMATIC & REAL** vs **NOT CINEMATIC / NOT REAL** — with a score meter
  ("X/8 traits, confidence NN/100"). Below, the criteria checklist of **8 traits**, with **shallow depth
  of field** and **photorealism** shown as the two **must-pass** traits (a fail on either fails the whole
  image regardless of the rest). Each trait has a one-line "why."

### 2. Clearance — *Check only*
A rights/likeness screening aid. "Could anything here need legal clearance?"
- **Inputs:** one image; a **Sensitivity** slider (min confidence to flag; lower = more flags, default
  ~50); Screen button.
- **Result:** Verdict banner — **NEEDS RIGHTS REVIEW** vs **NO FLAGS (above sensitivity)**. Criteria
  checklist over **4 categories**: **celebrity / public-figure likeness, copyrighted character,
  brand logo, recognizable IP** — each with a **flag / clear** pill, a **confidence** value, and a note.
  Design a distinct **"flagged but below sensitivity (low-confidence)"** sub-state. A persistent italic
  **disclaimer**: "Screening aid only — not legal clearance." Keep the tone neutral/advisory, not alarmist.

### 3. Character — *Check only · runs locally, no API key*
"Does this specific actor's face appear in this still?" Local face recognition.
- **Inputs:** a **multi-upload** for **1–5 reference photos** of the actor (clear faces); one image to
  check; a **Match threshold** slider (higher = stricter, default ~0.40); Check button. **No API key**
  control on this screen — call out that it's fully local.
- **Result:** Verdict banner — **CHARACTER IS IN THE SHOT** vs **NOT FOUND**. The hero is the checked
  image with **detected-face bounding boxes drawn on it — green = match, red = other face — each labelled
  with a similarity score**. Below, a small table of faces sorted by similarity (similarity value +
  match yes/no). Design the **"no faces detected"** and **"no face found in the reference photos"** states.

### 4. Consistency — *Check & fix* (paid · Nano Banana Pro)
Continuity vs a reference frame, then a targeted re-render of only what drifted.
- **Inputs:** a **Reference** image (canonical look of the scene) + the **image to fix**; a **Strictness**
  slider (fraction of aspects that must match, default ~0.70); a **Max regenerations** slider (1–3);
  "Check & fix continuity" button.
- **Result:** Verdict banner — **CONSISTENT** / **FIXED after N re-renders** / **STILL INCONSISTENT**.
  Score meter + the criteria checklist over **5 aspects**: **set/location** and **wardrobe** as the two
  **must-pass** aspects, plus **props, lighting, color grade**. Show the **Attempts strip** (Original →
  Fix 1 → …) with each attempt's "X/5 aspects" score, and a **before/after compare** against the
  reference. Make clear in copy what the fix preserves: it **locks the people's faces, pose, and the
  framing** and only repaints the drifted aspects.

### 5. Animation — *Check & fix* (paid · Nano Banana Pro)
Match an image to a reference **style**, then fix its **framing** — a two-phase loop with a final check.
- **Inputs:** a **Style reference** image (target look) + the **image to fix** (also defines correct
  framing); a **Strictness** slider (default ~0.70); a **Max regenerations per loop** slider (1–3);
  "Check & fix (style, then framing)" button.
- **Result:** Verdict banner — **BOTH STYLE & FRAMING PASS** vs **NOT FULLY (raise retries / lower
  strictness)**. Show the loop as **two phases**: **Phase 1 Style** (dimensions: render*, lines, shading,
  color, design, aesthetic) then **Phase 2 Framing** (dimensions: shot*, placement*, scale, crop), with
  a final reconcile check (* = must-match). Use the **Attempts strip**, captioned by phase
  ("Style: fix 1 → OK", "Framing: fix 1 → OK", "Final check → OK"), and a per-phase criteria checklist.

## States to nail throughout (this is what makes it feel real, not a demo)

- **Analyzing / running** — and a heavier, reassuring **long-running paid** state for the two
  check-&-fix tools (re-rendering can take a while and costs money per image).
- **Pass · Fail · Needs-review · Flagged-but-low-confidence · Fixed** (the verdict-banner variants).
- **Errors** — design a friendly error card, including the real one where **Nano Banana Pro refuses to
  edit photos of identifiable real people** (identity/deepfake limits), and "the model returned no image."
- **Empty / missing inputs** — no image yet, missing reference, missing 1–5 reference photos,
  **missing API key** (for the four Gemini tools; never shown on Character).

## Build/handoff notes (so the design maps cleanly to code)

Built in **React + TypeScript + Tailwind + shadcn/ui**, dark theme, as a **reusable component system**
with design tokens (CSS variables for color, spacing, radius, typography). Favor shadcn-compatible
primitives (cards, tabs, dialogs, tooltips, badges, sheets, tables, sliders, progress, command palette).
Keep interactive controls clearly identifiable (they'll get `data-testid`s). Each tool maps to one
FastAPI endpoint — **`/cinematic`, `/clearance`, `/character`, `/continuity`, `/animation`** — taking
image(s) + a threshold and returning a structured verdict (per-trait/aspect/category booleans + notes +
confidence; the two fix tools also return the attempt images and their scores). The highest-value
reusable components — make these especially crisp: the **verdict banner**, the **criteria checklist**,
the **score meter**, the **attempts strip + before/after compare**, and the **QC badge**.

# Claude Design prompt — script-to-image-stringout studio (Krea-referenced)

**How to use this:** Paste everything below the line into Claude Design for a cohesive first pass.
Then refine screen-by-screen in the chat (e.g. "make the timeline editor full-screen," "show the
failed-shot retry state"). If it's too much at once, feed it in this order: (1) the *Aesthetic
direction* + *The spine*, (2) the *Timeline editor*, (3) the *Visual clarification* screen — those
three define the whole system. Tune the accent color and density with Claude Design's sliders. When
you love it, use **developer handoff → Claude Code** (with your `frontend-design` skill + `CLAUDE.md`)
to build it against your FastAPI endpoints. Swap the working name "Throughline" for whatever you like.

---

Design a professional, cinematic web application called **Throughline** — a script-to-image studio for
filmmakers. It takes a screenplay and walks it through an AI production pipeline that ends in an
**image stringout**: accurate cinematic still frames for every shot, laid out on an editorial
timeline. The user is a **director or filmmaker, not an engineer** — it should feel like a premium
film-production tool they'd trust on a real project, never a generic AI SaaS dashboard or a developer
console.

Two systems are combined here: a **generation pipeline** (screenplay → enriched screenplay →
continuity → shotlist → still images) and a **quality-control layer** that automatically checks every
generated still and refines it until it passes. Both must be visible in the design.

This is the first milestone (stills on a timeline, not video yet), so video and audio stages appear in
the pipeline but as elegant, clearly-disabled "coming soon" states.

## Aesthetic direction

Anchor the look on **Krea**: dark, premium, fluid, generation-first — deep charcoal surfaces, minimal
chrome, lots of breathing room, and the actual generated imagery treated as the hero of the screen.
Blend in the **editorial precision of DaVinci Resolve** for the timeline, and the **calm review/approval
clarity of Frame.io** for status and review gates.

- **Color:** a near-black, slightly warm charcoal base (not pure #000), with subtle elevation — thin
  1px borders, soft shadows, a faint glass blur on overlays and inspectors. Commit to **one** confident
  accent: a warm cinematic **amber/gold** (film, projector light) used sparingly for primary actions,
  active states, and the "approved/locked" signal. Let most of the color come from the **generated
  stills themselves**, not decorative gradients.
- **Typography:** distinctive, not generic. Pair a **characterful display face** for titles and scene
  headings (editorial/cinematic feel) with a **clean technical sans** for body and a **monospace** for
  timecode, seeds, IDs, and prompt text. Do NOT use Inter/Roboto/Arial or the default "AI" look.
- **Density & motion:** pro-tool information density, but calm and spacious — never cramped. Use motion
  only at high-impact moments: a staggered reveal on load, smooth transitions when a pipeline stage
  changes status, and a satisfying "lock" animation when something is approved.
- **Avoid:** purple gradients on white, stock card grids, cluttered enterprise chrome, emoji, anything
  that reads as a generic template.

## The spine: the production pipeline

The whole app is organized around a **pipeline of stages in fixed order**, always visible (a left rail
or top stepper):

`Parse → Clarify → Rewrite → Continuity → Bible → Characters → Shotlist → Generate & QC Stills → Stringout`
— then a greyed future cluster: `Video · Audio`.

Each stage shows a **status chip**: *waiting · running · needs review · approved · failed · complete*.
Stages with a review gate get a clear "Review & edit" or "Auto-accept & continue" affordance.

A persistent **project header** across the top: project title, mode badge (*Generate Stringout* /
*Build Manually*), an overall progress meter, and a small **"Real vs Mocked"** indicator showing which
providers are live (e.g. "Nano Banana Pro: live" vs "mocked").

## Screens (one shared component language; populate with realistic film content — a moody two-scene
piece like a rain-soaked hospital-waiting-room drama or a small sci-fi scene, never lorem ipsum)

1. **Mode select / landing** — a confident cinematic entry. Two large choices: **Generate Image
   Stringout** (full auto) and **Build Manually** (scene-by-scene). A drop zone for the screenplay
   (.fountain/.fdx/.pdf/.txt) plus optional uploads (director notes, look-book images, character refs,
   storyboard PDF, prop/location refs). Toggles: "Ask me visual questions first," "Let AI decide missing
   details," "Use Nano Banana Pro for stills."

2. **Script understanding review** — after parse: a clean breakdown with tabs/columns for **Scenes,
   Characters, Locations, Props, Story/arc**. Editable lists; scene cards show INT/EXT · location ·
   time-of-day; inline correction.

3. **Visual clarification questions** (the signature screen) — questions grouped by **Global style,
   Characters, Wardrobe, Locations, Props, Scenes, Continuity, Camera/Lens, Tone/Lighting**. Each
   question card: the question, a one-line **"why this matters for generation,"** suggested-answer chips,
   a reference-image upload, and per-question actions *Answer · Skip · Let AI decide · Apply globally /
   to this scene only*. An answered/unanswered progress meter and a prominent **"Let AI decide all
   unanswered."**

4. **Visual decisions review** — a ledger of every decision with a **source tag** (*user · AI default ·
   inferred from script · reference*), editable before approval.

5. **Enriched screenplay** — **side-by-side original vs enriched**, screenplay-formatted, with the added
   visual detail **highlighted and color-coded by source**. Approve / edit / regenerate.

6. **Production Bible** — editable, versioned: camera/lens (default *ARRI Alexa 65 · Panavision Ultra
   Panatar II anamorphic · 2.39:1*), global style, tone vocabulary, atmosphere rules,
   character/prop/location/continuity rules.

7. **Character sheets / casting board** — a board of character cards, each with a generated **reference
   sheet** (angles/expressions), status *draft · needs review · locked*, upload-your-own, regenerate,
   and a clear **Lock identity** action. Locked = the canonical face used in every shot.

8. **Continuity board** — tags beyond characters: wardrobe, props, locations, set details, vehicles,
   lighting/weather motifs, symbols, object-state changes. Each tag: canonical description, reference
   thumbnail, first appearance, scene list, **lock** toggle. Make the gate visible: *stills can't
   generate until continuity-critical items are locked.*

9. **Shotlist editor** — per scene, an editable list of shots: shot type, description, assigned
   characters (small locked-identity avatars), continuity-tag chips, still duration, status; add /
   delete / reorder / edit; show which source action/dialogue line each shot came from.

10. **Generate & QC Stills** — whole-film and per-scene progress; a grid of shots filling in as stills
    generate. **This is where the two systems meet:** each generated still is automatically run through
    the quality checks and shows three status badges —
    **Cinematic** (looks like a real film still, not flat/AI), **Continuity** (matches the locked
    character/wardrobe/set/prop/lighting/color references), and **Clearance** (no celebrity-likeness or
    IP flags). Pass = check, fail = warning. Each shot has **Check & refine** (re-render until it passes),
    and failed generations get *retry · edit prompt · change provider · use placeholder*.

11. **Image stringout timeline editor (the centerpiece)** — a DaVinci-Resolve-style editor:
    - **Program viewer** top-center (selected still, large).
    - **Scene navigator strip** above the ruler.
    - **Timeline** along the bottom: a ruler with **timecode and scene markers**, tracks **V1/V2/V3
      stacking up from a centerline**, still-image clips back-to-back on V1 (each clip a thumbnail);
      clips movable/trimmable and movable across tracks; locked/revised badges on clips, plus the small
      **QC badges** (cinematic/continuity/clearance) on each clip.
    - **Left panel:** scene/shot list.
    - **Right inspector:** for the selected clip — the still, the **image prompt** in mono with its
      composable sections visible, model (*Nano Banana Pro*), seed, **source screenplay lines + enriched
      lines**, characters, continuity tags, scene, duration, **QC results** (the three checks with their
      reasons), **version history** (revert to prior stills), and **lock / regenerate / check & refine**
      controls. Regenerate always creates a **new version** (never overwrites).

12. **Export panel** — a tidy list of exportable artifacts (stringout manifest JSON, original + enriched
    screenplay, visual decisions, continuity tags, Bible JSON, shotlist CSV, prompt-package ZIP,
    still-image ZIP), each with format and a download action; MP4/video marked as a future TODO.

13. **States to nail throughout** — design the **review gate**, **running/progress**,
    **failed-with-retry**, **QC pass vs flag**, **locked**, and **mocked-provider** states explicitly;
    these are what make it feel like a real production tool rather than a demo.

## Build/handoff notes (so the design maps cleanly to code)

Built in **React + TypeScript + Tailwind + shadcn/ui**, dark theme. Design it as a **reusable component
system** with consistent design tokens (CSS variables for color, spacing, radius, typography). Favor
shadcn-compatible primitives (cards, tabs, dialogs, tooltips, badges, sheets, tables, sliders, progress,
command palette). Keep interactive controls clearly identifiable (they'll get `data-testid`s). The
highest-value reusable components — make these especially crisp: the **stage stepper**, the **clarification
question card**, the **character card**, the **shot row**, the **QC badge cluster**, and the **timeline
clip + inspector**.

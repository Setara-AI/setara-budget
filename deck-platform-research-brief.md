# Film Pitch Deck Platform — Research & Product Brief

*Auto-generated, imagery-first pitch decks for film/TV, powered by Higgsfield Cinema Soul.*
*Research date: 2026-08-07*

---

## 1. What goes into a professional pitch deck

**Format norms:** 10–20 slides, 16:9 landscape (1920×1080), exported as PDF, a "7–10 minute read." Deck + lookbook packages commonly run ~12 deck slides + 8–15 lookbook pages. Imagery dominates: roughly 60–80% image-forward overall, near-100% in the lookbook stretch — exactly the "images at the forefront, text explains" shape you described.

**Standard sections, in typical order** (synthesized from the Sundance Collab official guidelines, Celtx, We Make Movies, LA Film School):

| # | Section | Notes |
|---|---------|-------|
| 1 | **Cover** | Title, tagline, names, one striking hero image (+ LLC if soliciting money) |
| 2 | **Logline** | 1–2 sentences: genre, protagonist, conflict, stakes |
| 3 | **Synopsis** | 1–3 paragraphs; features must pitch the *whole* story incl. ending |
| 4 | **Tone / genre / comps** | Comps from the **last 2–5 years**, budget-appropriate (Sundance's explicit guidance) |
| 5 | **Themes** | The "why now" resonance; often merged into director's statement |
| 6 | **Characters / casting** | Attached cast headshots+credits, or a *realistic* wish list — Sundance warns a $10M actor on a $2M budget undermines credibility |
| 7 | **World / setting** | Landscape imagery of the story's world |
| 8 | **Visual style / lookbook** | 2–8 pages, the most image-heavy stretch: cinematography, palette, lighting, framing |
| 9 | **Director's statement** | Personal, specific "why me / why now" |
| 10 | **Team bios** | Headshots, credits, links |
| 11 | **Budget** | A range is acceptable ("$1.5M–$4M") |
| 12 | **Financing plan** | Raised to date, sources, ask; for investors: recoupment waterfall, 18–36-month return norms |
| 13 | **Schedule** | Production → post → festival/delivery targets |
| 14 | **Audience / market** | What financiers weigh most |
| 15 | **Contact / CTA** | End with a call to action (read the script, take a meeting) |

**Variants by audience** (should be a generator setting — "who is this deck for?"):
- **Investors:** heavy on budget/financing/recoupment/comps-with-revenue; "emphasize the opportunity, not the risk."
- **Studios/streamers:** creative vision + slate fit; financials mostly drop out.
- **Talent attachment:** character-forward lookbook — the role and the vision.
- **Grants:** mission alignment + impact plan + fiscal sponsor.
- **TV series:** adds pilot synopsis, season arc, episode grid, future-season outlines.
- **Documentary:** participants + access story + filming approach + impact plan, often a WIP trailer link.

**Famous reference decks:** Stranger Things' "Montauk" bible (portrait, styled as a vintage paperback — tone understood before a word of plot); A Quiet Place lookbook (opens on tagline, tone via reference stills); The Mountain (disciplined two-color theory); Hunter's Creed (market-first for a built-in audience).

**AI imagery attitudes are split (important):** practitioner threads (Stage 32, 2024–25) range from "AI in pitch materials is frowned on / reads cheap" to producers responding well to fully AI-illustrated decks. The consensus midpoint: **story-specific, polished, photoreal frames beat stock imagery; obvious AI artifacts read as amateur.** This is precisely the argument for Soul-class quality + a QC gate over Midjourney screenshots.

---

## 2. User inputs (the intake form)

Tiered so a writer with only a script can still get a deck, while a packaged producer can feed everything:

**Tier 1 — minimum viable (everything else derivable):**
- Screenplay (PDF/FDX/Fountain) — *or* logline + treatment/outline for early-stage
- Deck audience (investor / streamer / talent / grant) and project type (feature / series / doc)
- Contact info

**Tier 2 — strongly recommended (we scaffold defaults, user confirms):**
- Logline & synopsis if they have preferred versions (else we draft from script)
- Comps (else we suggest recent, budget-appropriate ones for approval)
- Budget number or range; financing raised to date
- Cast attachments or wish list (real headshots uploaded — see likeness rule below)
- Team bios + headshots + credits
- Director's statement or bullet answers to "why you / why now" prompts

**Tier 3 — optional look controls:**
- Reference images / reference films for tone (feeds the look board)
- Tone words, period/setting overrides, palette preferences
- For TV: episode ideas / pilot outline; for docs: participants + access story + trailer link
- Sizzle/tone-reel link, press, letters of interest

**We derive:** structure per audience, section copy, comps formatting, the entire visual system (look board → every image), layout, schedule template, audience/market slide, episode grid scaffolding.

---

## 3. Generation pipeline (script → deck)

Nearly every stage is a pattern already proven in montage-studio:

1. **Ingest** — screenplay parse (unpdf; note the Node-20 ArrayBuffer.transfer polyfill gotcha).
2. **Understand (Claude)** — logline, synopsis, tone words, genre, period, main characters only (no extras), 8–12 key visual moments, suggested comps. Same shape as the storyboard "script brain."
3. **Look definition** — generate a **character-free 2×2 look board** (Cinema Soul, always 2K) from tone words + user style refs. This is the global reference for every subsequent image — the proven fix for one-character-bleeds-everywhere and inconsistent grade.
4. **Section imagery** — cover key art, world plates, per-character portraits, moment stills — each rendered with the look board as reference (the reference-matched-cinematic-prompter skill codifies the prompt technique). Character consistency via Soul ID / cast-closeup-as-reference (the PITCH_CAST_CLOSEUPS pattern) or Nano Banana character swap onto character-free plates.
5. **QC gate** — Gemini cinematic checker + pure `compute_*` decision function; regenerate failures from the *original* references (loop hygiene), degrade gracefully on QC outages.
6. **Copy** — deck-grade text per section, audience-variant aware.
7. **Layout & export** — image-forward 16:9 templates (full-bleed stills, text overlays), PDF export + shareable web deck; a "Montauk mode" stylized template is a fun differentiator later.

---

## 4. Higgsfield Cinema Soul — integration paths

### Facts that shape everything
- **Higgsfield has a first-party REST API**: `platform.higgsfield.ai`, key auth (`Authorization: Key key:secret`), Soul = `higgsfield-ai/soul/standard`. Also resold via aggregators (fal, WaveSpeedAI, eachlabs) — useful fallback + pricing comps (~**$0.009/image at 1K** via third-party APIs; Soul ≈ 0.25 credits on consumer plans).
- **BUT: Cinema Soul (`soul_cinematic`) specifically is NOT on the public APIs** (verified 2026-08). Aggregators expose only regular Soul (text-to-image / image-to-image) + VFX; our Cinema Soul access to date has been through the account-authed MCP (consumer product, not multi-tenant). Public-user imagery therefore runs on **Soul-standard API + reference conditioning**: Cinema Soul (via our account) generates the *look masters* — either per-deck look boards or a curated library of pre-made "look packs" — and API Soul image-to-image (explicitly built for reference-driven restyling with character consistency) renders the volume, locked to those masters with the reference-matched prompting technique. Cinema Soul = internal look factory; Soul API = public render engine. Parallel track: pursue Higgsfield Enterprise to get `soul_cinematic` exposed on our key (they license models out — e.g. Soul Cinema shipped inside Kolbo — and are pushing MCP/CLI/Skills ecosystem plays), and watch aggregators for it appearing. **Do not** scale a farm of consumer accounts driven by MCP/CLI automation for public users — that is exactly the "reselling service access" the ToS prohibits.
- **ToS:** you may NOT resell/white-label *access to the Higgsfield service*, but **outputs are commercially usable with no separate license — explicitly including client deliverables and products incorporating AI visuals.** Selling *decks* (our product) with Soul-generated images inside is the sanctioned shape; there's an Enterprise offering for exactly this. Their broad content-license grants drew criticism in 2025–26 — worth a legal read before deep coupling.
- Higgsfield scale (2026): 15M+ users, ~$1.3B valuation reportedly re-raising at $5B — a stable-enough vendor, but keep an abstraction layer.

### Internal phases (us using it)
- **Phase 0 — agent-driven "deck factory" (this week, zero build):** Claude + the Higgsfield MCP produce complete decks on request — script in, PDF out — using the exact pipeline above by hand. Validates the format, templates, and image recipes before writing product code. Could even be a paid concierge service immediately.
- **Phase 1 — internal tool:** standalone sibling app (own port/repo, per the never-cross-contaminate rule) that reuses montage-studio's proven services: script brain, Cinema Soul step, QC gate, cost ledger, job journal. Server calls Soul autonomously via the REST API (no MCP dependency).
- **Phase 2 — productize** that same app: auth, credits, templates gallery, web-deck sharing.

### Public-release options for the imagery engine
1. **Our key, metered credits (recommended):** we hold the platform API key server-side, sell prepaid deck credits at 2–5× raw cost (the standard pattern on fal/Replicate-built products). Neutralize vendor names in the cost ledger (established white-label rule) — the user buys "Cinematic engine" images, not "Higgsfield."
2. **Engine abstraction:** "Cinematic" = Soul via platform API, fallback = aggregator (fal/WaveSpeed) or Nano Banana Pro — same neutral standard/cinematic naming already used for the video engine. Protects against ToS shifts, outages, and moderation differences.
3. **BYO-key tier:** power users paste their own Higgsfield key — zero image-cost risk for us, but high friction; offer as a pro option, not the default.
4. **Enterprise partnership:** Higgsfield actively courts ecosystem plays; an official integration could unlock better pricing/rate limits and marketing.

### Operational must-haves (lessons already paid for)
- **Moderation defense:** provider filters reject prompts *and reference images* silently — even AI-generated character sheets. Ship the proven 4-layer pattern: preflight screen → canary submit (cap burn at 1 image) → persisted last-error banner → persistent logs.
- **Queue-and-poll, don't fan out:** API concurrency starts low (fal starts at 2); a 20-image deck needs a job queue with progress UI, not parallel blasts.
- **Real-person likeness rule:** never *generate* wishlist actors' likenesses (deepfake restrictions + legal exposure). Cast pages use uploaded real headshots; AI imagery covers world, tone, moments, and *original* characters ("type" casting language only).
- Always 2K quality on Soul; per-user cost ledger from day one; self-healing progress locks.

---

## 5. Market & positioning

**The whitespace is real.** LTX Studio and Storyboarder.ai own "script → storyboard → deck" at *previz/storyboard* aesthetic quality; Gamma/Beautiful.ai/Decktopus own generic decks with no script understanding and no consistent visual world (Tome died — horizontal AI decks are commoditized). **Nobody delivers investor-grade lookbook decks with photoreal, tonally-matched, internally consistent imagery.** The defensible triad: script understanding + one graded visual world governing every frame + film-industry deck grammar (audience variants, comps discipline, finance slides).

**Price anchor:** human deck designers charge **$500–$5,000** (film lookbooks typically $800–$3,000, 20–30 hours). COGS for a ~25-image deck at aggregator rates is on the order of **$1–3** including QC calls and retries. A $29–$99/deck price (or $30–50/mo subscription with deck credits) undercuts humans by 10–50× at software margins.

**Demand proxies:** Sundance alone gets 14–17K submissions/yr; FilmFreeway has 3M registered filmmakers across 15K+ festivals; screenwriting contests add tens of thousands of projects annually — low hundreds of thousands of pitchable projects/year, each currently paying a designer or burning DIY hours.

**Monetization sketch** (mirrors the trailer app's free-concept/paid-stills split):
- **Free:** script analysis + text-only deck preview + watermarked low-res look board — the hook.
- **Paid per deck or subscription:** full 2K imagery, all templates, PDF + web deck, revision passes.
- **Upsells:** extra look-board directions, motion cover (Seedance clip), talent/investor variant re-renders of the same deck, print-res export.

## 6. Top risks
1. **AI stigma with gatekeepers** — mitigated by Soul-class photorealism, the QC gate, and framing pages as "visual references," plus always letting users swap in real photos.
2. **Higgsfield ToS / platform risk** — sanctioned path is selling decks not access, but get a legal read; keep the engine abstraction.
3. **Moderation rejections burning money** — solved pattern, must ship day one.
4. **Consistency across 20+ images** — the look-board + Soul ID + character-swap stack is the core technical moat *and* the core technical risk; Phase 0 validates it cheaply.
5. **Likeness/IP in user inputs** — clearance-style screening (the Clearance checker pattern) on generated imagery before export.

---

*Sources: Sundance Collab pitch-deck guidelines (PDF), Celtx, We Make Movies, LA Film School, Storydoc, Stage 32 AI-imagery thread, Higgsfield ToS + help center + Enterprise pages, Sacra Higgsfield report, fal.ai/Replicate pricing docs, Slidebean/VIP Graphics deck-pricing surveys, LTX Studio & Storyboarder.ai product pages, FilmFreeway/Sundance submission stats.*

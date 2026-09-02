# Pasted script - AI production estimate

## $194,046

**Set aside $194,046** to deliver 2 AI shots (10s of screen time) across 2 scenes from a 0.2-page script.

- **$820,962 per script page** · $19,405 per delivered second
- **83% over** the traditional bid of $106,250 ($87,796 over)
- Model spend is only **0.02%** of the bid - $32.72. The rest is people and time.
- **6 people over 6 weeks** (3 AI seats), scheduled by deadline.

## The stack

| Line | Amount | Share of bid |
| --- | --- | --- |
| Generation (models) | $32.72 | 0.02% |
| Labor | $136,800 | 70% |
| Tooling, storage, review | $3,780 | 1.9% |
| **Direct cost** | **$140,613** |  |
| Contingency (15%) | $21,092 |  |
| **Cost to deliver** | **$161,705** |  |
| Margin (20%) | $32,341 |  |
| **BID** | **$194,046** |  |

## Generation spend

| Line | Quantity | Unit | Total | Price |
| --- | --- | --- | --- | --- |
| Reference library | 117 images | $0.1340 | $15.68 | published |
| Shot reference plates | 3 images | $0.1340 | $0.40 | published |
| Video generation | 16 seconds | $1.0400 | $16.64 | **projected** |
| **Subtotal** |  |  | **$32.72** |  |

- _Reference library_: 2 characters x 3 angles, 2 locations x 2, 3 props x 1, 5 options each, x1.80 for 2 approval round(s)

- _Shot reference plates_: 2 shots, plates per shot by complexity, including revision attempts

- _Video generation_: 2 shots at 1920x1080, 10s delivered, 16s billed after revisions and the 4s minimum take

## The same script at every model tier

| Model | Res | $/sec | Billed | Video | Generation subtotal | Price |
| --- | --- | --- | --- | --- | --- | --- |
| seedance-2.5-480p | 864x496 | $0.2149 | 16s | $3.44 | $19.61 | published |
| seedance-2.5-720p-ref | 1280x720 | $0.2765 | 16s | $4.42 | $20.62 | published |
| seedance-2.0-720p | 1280x720 | $0.3024 | 16s | $4.84 | $20.93 | published |
| seedance-2.5-720p | 1280x720 | $0.4622 | 16s | $7.40 | $23.65 | published |
| seedance-2.0-1080p | 1920x1080 | $0.6804 | 16s | $10.89 | $26.99 | published |
| seedance-2.5-1080p ← | 1920x1080 | $1.0400 | 16s | $16.64 | $32.72 | **projected** |
| seedance-2.0-4k | 3840x2160 | $1.5552 | 16s | $24.88 | $40.96 | published |

_Generation subtotal only - labor and tooling are unchanged by the tier._

## Crew

| Role | Kind | Count | Rate | Weeks | Cost |
| --- | --- | --- | --- | --- | --- |
| AI Supervisor / Lead | AI | 1 | $6,000/wk | 6 | $36,000 |
| AI Producer / Coordinator | craft | 1 | $4,000/wk | 6 | $24,000 |
| Generation Artist | AI | 1 | $3,500/wk | 6 | $21,000 |
| Reference / Asset Artist | AI | 1 | $3,000/wk | 6 | $18,000 |
| Continuity Supervisor | craft | 1 | $2,800/wk | 6 | $16,800 |
| Editor / Assembly | craft | 1 | $3,500/wk | 6 | $21,000 |
| **Total** |  | **6** |  | **36 person-weeks** | **$136,800** |

### Load per role

| Role | Unit | Required | Capacity | Utilisation |  |
| --- | --- | --- | --- | --- | --- |
| Generation Artist | shot_attempts | 3 | 240 | 1.3% | ok |
| Reference / Asset Artist | images | 120 | 900 | 13% | ok |
| Continuity Supervisor | images | 120 | 1,500 | 8.0% | ok |
| Editor / Assembly | scenes | 2 | 60 | 3.3% | ok |

## Scenes

| # | Scene | Time | Pages | Tier | Score | Cast | Props | Shots | Attempts | Billed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | INT WAREHOUSE | NIGHT | 1/8 | simple | 1 | 1 | 2 | 1 | 1.6x | 8s |
| 2 | EXT DOCKS | DAY | 1/8 | simple | 1 | 1 | 1 | 1 | 1.6x | 8s |

### Why each scene scored what it did

- **1. WAREHOUSE** (simple, 1): +1 night / low-light continuity
- **2. DOCKS** (simple, 1): +1 exterior world-building

## Assumptions

**These are the numbers to argue with.** Everything above is derived from them.

### Generation
- Revision model: `attempts = 1 + rounds x hit_rate`, hit rate **60%** of shots per round; rounds by tier: simple 1, moderate 2, complex 3, hero 4
- Shots per page by tier: simple 5, moderate 7, complex 9, hero 12
- Seconds per shot by tier: simple 5s, moderate 5s, complex 5s, hero 5s
- Reference library: **5 options** per asset, 3 angles per character, 2 plates per location, 1 per prop, 2 approval round(s) at 40% hit rate

### Money
- Contingency **15%**, margin **20%**
- Traditional baseline: **3 pages/shoot day** at **$85,000/day**, post at 25% → 1.0 shoot days
- Weekly crew rates are PLACEHOLDERS - replace them with your own before quoting.

### Script reading
- Props are detected from the screenwriting convention that a prop is CAPITALISED on first appearance. Review the list; the parser is deliberate but literal.
- Page count follows 55 lines to a page; one page is treated as one minute.

## Price sources

| Line | Source | Kind |
| --- | --- | --- |
| Reference library | <https://ai.google.dev/gemini-api/docs/pricing> | published |
| Video generation | <https://fal.ai/models/bytedance/seedance-2.5/text-to-video> | published |

_Prices read 2026-08-26. The default video tier (`seedance-2.5-1080p`) is PROJECTED: PROJECTED. fal does not currently offer 2.5 above 720p - this applies 2.5's published token rate ($0.0214/1k) to 1920x1080. Treat it as a planning figure, not a quote._
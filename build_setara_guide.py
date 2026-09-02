# -*- coding: utf-8 -*-
"""Builds the Setara complete guide PDF — a detailed, step-by-step walkthrough of the whole tool."""
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, ListFlowable, ListItem, HRFlowable, KeepTogether, NextPageTemplate,
)
from reportlab.lib.styles import ParagraphStyle

# ---- Brand palette ---------------------------------------------------------
GREEN   = colors.HexColor("#2f5e3f")   # forest green primary
INK     = colors.HexColor("#171717")   # near-black
BODY    = colors.HexColor("#2b2b2b")
MUTED   = colors.HexColor("#6b6b66")
PAPER   = colors.HexColor("#f5f4f0")   # warm paper
TINT    = colors.HexColor("#eef1ec")   # callout tint (greenish paper)
RULE    = colors.HexColor("#d8d6cf")
ACCENT  = colors.HexColor("#3a7a52")

OUT = "/Users/matthewwarter/Desktop/Setara — Complete Guide.pdf"

# ---- Styles ----------------------------------------------------------------
SANS = "Helvetica"; SANSB = "Helvetica-Bold"; SERIF = "Times-Roman"; SERIFI = "Times-Italic"

st_title   = ParagraphStyle("title", fontName=SANSB, fontSize=34, leading=38, textColor=INK, spaceAfter=6)
st_sub     = ParagraphStyle("sub", fontName=SERIFI, fontSize=14, leading=19, textColor=MUTED, spaceAfter=4)
st_cover_meta = ParagraphStyle("covermeta", fontName=SANS, fontSize=10, leading=15, textColor=MUTED)
st_h1      = ParagraphStyle("h1", fontName=SANSB, fontSize=20, leading=24, textColor=GREEN, spaceBefore=8, spaceAfter=8)
st_h1num   = ParagraphStyle("h1num", fontName=SANSB, fontSize=11, leading=12, textColor=ACCENT, spaceAfter=2)
st_h2      = ParagraphStyle("h2", fontName=SANSB, fontSize=13.5, leading=17, textColor=INK, spaceBefore=12, spaceAfter=4)
st_h3      = ParagraphStyle("h3", fontName=SANSB, fontSize=11, leading=14, textColor=ACCENT, spaceBefore=8, spaceAfter=2)
st_body    = ParagraphStyle("body", fontName=SERIF, fontSize=10.5, leading=15.5, textColor=BODY, spaceAfter=7, alignment=TA_LEFT)
st_bullet  = ParagraphStyle("bullet", fontName=SERIF, fontSize=10.5, leading=15, textColor=BODY)
st_lead    = ParagraphStyle("lead", fontName=SERIF, fontSize=11.5, leading=17, textColor=BODY, spaceAfter=9)
st_callh   = ParagraphStyle("callh", fontName=SANSB, fontSize=9.5, leading=12, textColor=GREEN, spaceAfter=3)
st_callb   = ParagraphStyle("callb", fontName=SERIF, fontSize=9.7, leading=13.5, textColor=BODY)
st_toc     = ParagraphStyle("toc", fontName=SANS, fontSize=10.5, leading=18, textColor=BODY)
st_tocnum  = ParagraphStyle("tocnum", fontName=SANSB, fontSize=10.5, leading=18, textColor=GREEN)
st_step    = ParagraphStyle("step", fontName=SERIF, fontSize=10.5, leading=15, textColor=BODY)
st_kv      = ParagraphStyle("kv", fontName=SERIF, fontSize=10, leading=14, textColor=BODY)

# ---- Flowable helpers ------------------------------------------------------
def h1(num, text):
    return KeepTogether([Spacer(1, 6), Paragraph("STAGE / SECTION " + num if False else num, st_h1num),
                         Paragraph(text, st_h1),
                         HRFlowable(width="100%", thickness=1.4, color=GREEN, spaceAfter=8)])

def h2(text): return Paragraph(text, st_h2)
def h3(text): return Paragraph(text, st_h3)
def body(text): return Paragraph(text, st_body)
def lead(text): return Paragraph(text, st_lead)

def bullets(items, style=st_bullet):
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=14, value="•") for t in items],
        bulletType="bullet", bulletColor=GREEN, bulletFontSize=8, leftIndent=10, spaceAfter=8,
    )

def steps(items):
    return ListFlowable(
        [ListItem(Paragraph(t, st_step), leftIndent=18) for t in items],
        bulletType="1", bulletColor=GREEN, bulletFontName=SANSB, bulletFontSize=10, leftIndent=14, spaceAfter=9,
    )

def callout(title, text):
    inner = [Paragraph(title.upper(), st_callh), Paragraph(text, st_callb)]
    t = Table([[inner]], colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TINT),
        ("BOX", (0, 0), (-1, -1), 0.75, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
    ]))
    return KeepTogether([Spacer(1, 2), t, Spacer(1, 8)])

def kvtable(rows):
    data = [[Paragraph("<b>%s</b>" % k, st_kv), Paragraph(v, st_kv)] for k, v in rows]
    t = Table(data, colWidths=[1.55 * inch, 4.95 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    return KeepTogether([Spacer(1, 1), t, Spacer(1, 8)])

# ---- Page furniture --------------------------------------------------------
def on_page(canvas, doc):
    canvas.saveState()
    w, h = LETTER
    # footer rule + text
    canvas.setStrokeColor(RULE); canvas.setLineWidth(0.5)
    canvas.line(0.9 * inch, 0.72 * inch, w - 0.9 * inch, 0.72 * inch)
    canvas.setFont(SANS, 8); canvas.setFillColor(MUTED)
    canvas.drawString(0.9 * inch, 0.55 * inch, "Setara — Complete Guide")
    canvas.drawRightString(w - 0.9 * inch, 0.55 * inch, "Page %d" % doc.page)
    canvas.setFillColor(GREEN)
    canvas.drawCentredString(w / 2.0, 0.55 * inch, "S E T A R A")
    canvas.restoreState()

def on_cover(canvas, doc):
    canvas.saveState()
    w, h = LETTER
    canvas.setFillColor(PAPER); canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setFillColor(GREEN); canvas.rect(0, h - 0.5 * inch, w, 0.5 * inch, fill=1, stroke=0)
    canvas.rect(0, 0, w, 0.35 * inch, fill=1, stroke=0)
    canvas.restoreState()

doc = BaseDocTemplate(
    OUT, pagesize=LETTER,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch, topMargin=0.95 * inch, bottomMargin=0.95 * inch,
    title="Setara — Complete Guide", author="Setara", subject="How the tool works, step by step",
)
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
cover_frame = Frame(doc.leftMargin, 1.0 * inch, doc.width, 8.5 * inch, id="cover")
doc.addPageTemplates([
    PageTemplate(id="cover", frames=[cover_frame], onPage=on_cover),
    PageTemplate(id="body", frames=[frame], onPage=on_page),
])

S = []  # story

# ============================ COVER =========================================
S += [Spacer(1, 1.7 * inch)]
S += [Paragraph("Setara", st_title)]
S += [Paragraph("The Complete Guide", ParagraphStyle("ct", fontName=SANSB, fontSize=22, leading=24, textColor=GREEN, spaceAfter=10))]
S += [HRFlowable(width="38%", thickness=2, color=GREEN, spaceAfter=14, hAlign="LEFT")]
S += [Paragraph("How the tool works, and every single step of the process — from a one-line idea to a finished, exportable film.", st_sub)]
S += [Spacer(1, 2.3 * inch)]
S += [Paragraph("An AI film studio. Three generators. One pipeline.<br/>Microdrama &nbsp;·&nbsp; Pitch &nbsp;·&nbsp; Animation", st_cover_meta)]
S += [NextPageTemplate("body")]
S += [PageBreak()]

# ============================ CONTENTS ======================================
S += [Paragraph("Contents", st_h1), HRFlowable(width="100%", thickness=1.4, color=GREEN, spaceAfter=10)]
toc = [
    ("1", "What Setara Is"),
    ("2", "The Big Picture — One Pipeline, End to End"),
    ("3", "The Home Screen — Choosing a Generator"),
    ("4", "Starting a Project — Inputs &amp; Settings"),
    ("5", "Stage 1 · Continuity — The Creative Brief"),
    ("6", "Stage 2 · Generate Script — Script, Shotlist &amp; Look Guide"),
    ("7", "Stage 3 · Character Sheets — Cast, Locations &amp; Props"),
    ("8", "Stage 4 · Videos — Rendering the Clips"),
    ("9", "Stage 5 · Assemble — The Timeline Editor"),
    ("10", "Tara — Your In-Studio Creative Agent"),
    ("11", "Export — Fifteen Deliverables"),
    ("12", "Spend — Where the Money Goes"),
    ("13", "Under the Hood — Models, QC Loops &amp; Hygiene"),
    ("14", "Tips, Pitfalls &amp; Best Practices"),
    ("15", "Glossary"),
]
for n, t in toc:
    row = Table([[Paragraph(n, st_tocnum), Paragraph(t, st_toc)]], colWidths=[0.4 * inch, 6.1 * inch])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    S += [row]
S += [PageBreak()]

# ============================ 1. WHAT SETARA IS =============================
S += [h1("1", "What Setara Is")]
S += [lead("Setara is an AI film studio. You give it a story — anything from a single sentence to a full screenplay — and it walks that story, beat by beat, all the way to a finished short film you can play and download. Everything in between — the script, the cast, the locations, the look, the shots, the voiceover, the music, and the final edit — is generated, quality-checked, and assembled inside one continuous pipeline.")]
S += [body("The guiding idea is that a film is not a single button press. It is a sequence of dependent decisions: the look depends on the script, the shots depend on the look, the edit depends on the shots. Setara makes each of those decisions an explicit, reviewable <b>stage</b>, so you can shape the film at any point rather than accept whatever a one-shot generator hands back.")]
S += [h2("Three kinds of film")]
S += [body("Setara ships three <b>generators</b>, each tuned for a different format and audience. They share the same pipeline but differ in shape, length, and visual treatment:")]
S += [bullets([
    "<b>Root — the Microdrama Generator.</b> A vertical (9:16) short, grown from a single synopsis. Built for fast, serialized, scroll-native storytelling; episodes can continue from a cliffhanger.",
    "<b>Branch — the Pitch Generator.</b> A cinematic 16:9 cut, adapted from a story, script, or beat sheet. Built to sell an idea — a trailer-grade stringout with photoreal stills and a narrated spine.",
    "<b>Bloom — the Animation Generator.</b> One animated world held in a single, consistent style (for example, 3D Pixar-style or hand-painted 2D). Built so every frame reads as the same animated production.",
])]
S += [callout("In one line", "Story in → reviewable stages (brief, script, look, cast, shots, edit) → finished MP4 out, with every intermediate asset exportable.")]

# ============================ 2. BIG PICTURE ================================
S += [h1("2", "The Big Picture — One Pipeline, End to End")]
S += [body("Once a project exists, the left-hand <b>stage rail</b> is your map of the whole process. Each entry is a stage you can open, review, and act on. The pipeline runs top to bottom, and later stages depend on earlier ones:")]
S += [kvtable([
    ("Continuity", "The creative brief — the intent of the film, set first so everything downstream is built from it."),
    ("Generate Script", "The script and the shotlist, plus a compact Look Guide that locks the visual world."),
    ("Character Sheets", "Reference sheets for the cast, plus location plates and prop sheets — the visual vocabulary."),
    ("Videos", "Per-scene clips, rendered from the shots and tagged to the cast, with voiceover and music."),
    ("Assemble", "A real timeline editor where the clips, voiceover, and score become one cut you render to MP4."),
    ("Export", "Fifteen downloadable deliverables — documents, media bundles, an edit XML, and the full film."),
    ("Spend", "An itemized ledger of every billed API call, so cost is always visible."),
])]
S += [body("Alongside the rail, a creative agent named <b>Tara</b> is always open on the right. You can ask her, in plain language, to change a character's look, refine a shot, or re-roll an image — she performs the real change using the same safe services the buttons do.")]
S += [callout("You are always in the loop", "Nothing is a black box. Every stage shows what it produced, lets you regenerate just one piece, and never silently re-renders work you have already approved or locked.")]

# ============================ 3. HOME SCREEN ===============================
S += [h1("3", "The Home Screen — Choosing a Generator")]
S += [body("Setara opens on a full-screen chooser: three edge-to-edge panels — <b>Root</b>, <b>Branch</b>, and <b>Bloom</b> — each a doorway into one of the generators. The top bar carries the three primary controls and your balance:")]
S += [bullets([
    "<b>New</b> — return to the generator chooser to start a fresh project.",
    "<b>Library</b> — your gallery of every project, shown as 16:9 thumbnails (the rendered film, or a placeholder) with the title, clip count, date, and status. A sort filter lets you view All, Microdramas, Pitches, or Animations. Hovering a tile reveals a delete control.",
    "<b>Spend</b> — the cost dashboard across all work.",
    "<b>Balance badge</b> — your live provider credit, so you always know what you have to spend.",
])]
S += [body("Click a generator panel to open its intake form. From there you describe the film and press Generate; Setara writes the script and the look, saves the project to your Library, and drops you into the editor.")]

# ============================ 4. STARTING A PROJECT ========================
S += [h1("4", "Starting a Project — Inputs &amp; Settings")]
S += [body("Each generator's intake is tuned to how that kind of film begins, but all three share a settings row and an optional-information panel.")]
S += [h2("4.1 · The settings row (all generators)")]
S += [kvtable([
    ("Image model", "Nano Banana Pro or GPT Image 2 — both render at high quality; the choice is used by every Generate and Regenerate. Persisted on the project."),
    ("Aspect ratio", "9:16, 16:9, 1:1 and more. Microdrama defaults to 9:16; Pitch and Animation default to 16:9. This drives every still and the final render."),
    ("Resolution", "480p / 720p / 1080p — read by the video renderer at generation time."),
])]
S += [h2("4.2 · Microdrama (Root)")]
S += [steps([
    "Write your <b>synopsis</b> — a few sentences: who it is about, the feeling, where it is going.",
    "Optionally press <b>Suggest 4 concepts</b> to have Setara propose loglines; pick one to fill the box.",
    "Set the number of <b>clips</b> (each ~15 seconds, five cuts) and an optional <b>tone</b>.",
    "Press <b>Generate montage</b>. Setara writes a three-act montage, builds the look guide, and opens the editor.",
])]
S += [h2("4.3 · Pitch (Branch)")]
S += [steps([
    "Paste your <b>story, script, or beat sheet</b> — prose, a treatment, or a fountain/PDF you upload (Setara digests PDFs and screenplays into a beat sheet for you).",
    "Optionally use <b>Suggest concepts</b> to generate loglines that write the full script when picked.",
    "Set the target <b>length in minutes</b> and an optional <b>tone</b>.",
    "Press <b>Generate pitch</b> to adapt the story into a timed cinematic shotlist.",
])]
S += [h2("4.4 · Animation (Bloom)")]
S += [steps([
    "Enter your <b>idea, premise, or story</b> (typed or uploaded).",
    "Describe the <b>animation style</b> — one look for the whole film (e.g. “hand-painted 2D, gouache texture, soft cel shading, warm muted palette, inked outlines”), and optionally upload a <b>style frame</b> to anchor it.",
    "Set <b>length</b> and <b>tone</b>, then press <b>Generate animation</b>.",
])]
S += [h2("4.5 · Optional additional information (all generators)")]
S += [bullets([
    "<b>Add references</b> — attach reference images (a real place, a face, a look) that anchor the generated visuals.",
    "<b>Ask a questionnaire</b> — answer a few short creative questions (audience, feeling, lead, turn, ending) that fold into the brief as explicit creative direction.",
])]
S += [callout("Stills are paid; concepts are not", "Writing the script, brief, and loglines is cheap text generation. Rendering images and clips bills your image/video providers (~$0.13 per still at 2K, and video by Seedance's token rate). You can preview and shape the writing before spending on visuals.")]

# ============================ 5. CONTINUITY ================================
S += [h1("5", "Stage 1 · Continuity — The Creative Brief")]
S += [lead("Continuity is where the film's intent is set, and it is deliberately first. Everything downstream — the script, the look, the casting — is built from this brief, so a few minutes here shapes the entire film.")]
S += [h2("What you do here")]
S += [steps([
    "Drop any <b>reference images</b> at the top — a look, a place, or a face to anchor the world.",
    "Answer the <b>brief questions</b>: the logline (the story in a sentence), the audience, the one feeling to leave them with, whose story it is, the turn (the moment everything changes), how it ends, and the tone &amp; look.",
    "Or press <b>Auto-Generate</b> to have Setara draft the whole brief from your source story — then tweak anything.",
    "<b>Save the brief</b>, then continue to Generate Script. The brief is folded into the script source as a creative-direction block, so the script is written <i>from</i> it.",
])]
S += [callout("Why a brief at all?", "A one-shot generator answers the prompt it was given. A brief makes the film's intent explicit and persistent, so every later regeneration — a new script draft, a re-rolled shot — still serves the same story.")]

# ============================ 6. GENERATE SCRIPT ==========================
S += [h1("6", "Stage 2 · Generate Script — Script, Shotlist &amp; Look Guide")]
S += [body("This stage holds the written film. At the top sit the <b>title</b> and <b>logline</b>; below them, a compact <b>Look Guide</b> and the <b>shotlist</b>.")]
S += [h2("6.1 · The shotlist")]
S += [body("The script is presented as a shotlist: the film is broken into <b>beats</b> (roughly 15-second scenes), and each beat into the individual <b>shots</b> (cuts) inside it. Every shot is paired with the exact <b>voiceover</b> line that plays over it — or marked silent — so you can read precisely what is seen and heard, moment by moment.")]
S += [h2("6.2 · The Look Guide")]
S += [body("Folded into this tab is the <b>Look Guide</b> — a compact, expandable card that locks the film's visual world: its genre, palette, lighting, camera/format, sound, location treatment, character wardrobe, and recurring motifs. For Animation projects it also holds the <b>style guide</b> control — a 2&times;2 model sheet that pins the single animation style every later image is matched to. The Look Guide is auto-derived when the project is created and can be regenerated.")]
S += [h2("6.3 · Regenerate")]
S += [body("For Pitch and Animation projects you can <b>Regenerate the script</b> from its source at any time — paste or edit the story, and Setara rewrites the shotlist fresh using the latest creative direction, then refreshes the voiceover and score on the next render.")]
S += [callout("Skill-checked, automatically", "The voiceover writer is held to a story-to-video craft skill: each draft is scored against the skill's own diagnostic checklists and regenerated up to N times, keeping the best. This quality loop runs automatically in the backend during generation — there is no button to press.")]

# ============================ 7. CHARACTER SHEETS =========================
S += [h1("7", "Stage 3 · Character Sheets — Cast, Locations &amp; Props")]
S += [lead("Before any shot is rendered, Setara builds the film's visual vocabulary: a reference sheet for every character, a plate for every location, and a sheet for every key prop. These references are then reused on every clip so people, places, and objects stay consistent across the whole film.")]
S += [h2("7.1 · Two ways to make a character")]
S += [body("Each character can be created either way, per character:")]
S += [bullets([
    "<b>Create it in the tool.</b> Press Generate and Setara renders a standard reference sheet from the character's description — a clean turnaround in the project's style.",
    "<b>Upload a photo.</b> Open the character and choose <b>Upload photo</b>; the system converts your image into our standard character sheet, matching the face, hair, build, and wardrobe — rendered photoreal for live-action projects, or fully in the established animation style for animation projects.",
])]
S += [h2("7.2 · The three sections")]
S += [bullets([
    "<b>Cast</b> — one card per character, image with the name underneath. Click a card to open it large.",
    "<b>Locations</b> — a plate per unique setting. If you uploaded a location photo it becomes the anchor for every setting. Click in to view large.",
    "<b>Props</b> — a sheet per key prop. A continuity matrix at the bottom shows who and what recurs across every scene.",
])]
S += [h2("7.3 · The detail view (click any image)")]
S += [body("Clicking a card opens a full lightbox: the image large on the left, actions on the right. From there you can:")]
S += [bullets([
    "<b>Refine</b> — describe a tweak and re-render just that image, keeping everything else identical.",
    "<b>Regenerate</b> — a fresh take from scratch.",
    "<b>Upload photo</b> — convert an uploaded photo into the sheet (cast).",
    "<b>Lock</b> — freeze a sheet so it is never re-rendered when you re-run a step.",
    "<b>View prompt</b> — read the exact generation prompt behind the image.",
])]
S += [h2("7.4 · Generate missing, never clobber")]
S += [body("The top <b>Generate missing</b> button renders only the characters, props, and locations that do not yet have an image — everything you have already made (locked or not) is kept and never re-rendered. You can also switch the <b>image model</b> here; the choice is used by the next Generate or Regenerate.")]
S += [callout("Consistency is the whole point", "Because clips reference these sheets, locking a character you are happy with guarantees their face carries identically into every shot — and, for series, into future episodes.")]

# ============================ 8. VIDEOS ===================================
S += [h1("8", "Stage 4 · Videos — Rendering the Clips")]
S += [body("With the script and the references in place, Setara renders the film as a sequence of per-scene <b>clips</b>. Each clip is generated from its shot description and tagged to the characters present, so the cast's reference sheets keep faces consistent. The render is the expensive, paid step — it bills the video provider (Seedance) by its real token rate, which is resolution-aware.")]
S += [h2("8.1 · The full auto-generate")]
S += [body("From the project header, <b>Auto-generate</b> runs the entire montage pipeline in one go — character sheets &rarr; clips &rarr; voiceover &rarr; music &rarr; final cut — reporting the same live, per-item progress you would see running each stage by hand. A prominent progress banner shows the current phase and lets you <b>Stop</b> at any time to halt spend (clips already submitted to the provider may still land, but nothing new starts).")]
S += [h2("8.2 · What gets produced")]
S += [bullets([
    "<b>Video clips</b> — one per scene, on the project's aspect ratio and resolution.",
    "<b>Voiceover</b> — the narration recorded per beat (ElevenLabs), fitted to the footage.",
    "<b>Music</b> — a score sized to the timeline and mixed under the dialogue.",
    "<b>Final cut</b> — the clips, voiceover, and music baked into one MP4.",
])]
S += [callout("Stop means stop", "Setara is careful with money. Generations claim a single-operation lock, a Stop cancels every queued and running job, and recovery sweeps reclaim any paid render that a crash left orphaned — so you are not billed twice for the same clip.")]

# ============================ 9. ASSEMBLE =================================
S += [h1("9", "Stage 5 · Assemble — The Timeline Editor")]
S += [lead("Assemble is a real, functional non-linear editor. The rendered clips, voiceover, and music are laid out on a timeline you can rearrange, trim, cut, QC, and repair — then render to a single MP4.")]
S += [h2("9.1 · The program monitor")]
S += [body("The large viewer plays whatever sits under the playhead, kept in sync with the transport. It fills the frame edge-to-edge so you watch the picture, not black bars. The full, uncropped frame is always available by clicking a clip into its lightbox.")]
S += [h2("9.2 · Tracks &amp; the scene strip")]
S += [bullets([
    "<b>V1</b> — the video program (the cut that becomes the MP4).",
    "<b>A1</b> — voiceover / detached clip audio.",
    "<b>A2</b> — the music score.",
    "<b>Scene strip</b> — colored bars above the ruler mark each scene by number; hover a bar for its full setting.",
])]
S += [h2("9.3 · The transport &amp; toolbar")]
S += [bullets([
    "<b>Play / loop / mute</b>, a compact <b>timecode</b> (minutes:seconds.milliseconds), and <b>zoom</b> controls.",
    "<b>Render MP4</b> — stitch the timeline into one downloadable film.",
    "<b>Detach audio</b> — split every clip's audio onto the A1 track to edit it.",
    "<b>Reset order</b> — put clips back in scene order and drop duplicates, keeping your cuts.",
    "<b>Cut &amp; QC</b> — re-cut every segment and run physics QC; expendable broken B-roll is removed, the rest flagged.",
    "<b>Repair flagged</b> — auto-fix flagged shots: fix the frame, re-animate, re-QC, and swap it in.",
    "<b>Regenerate score / voiceover</b> — re-make the music or re-record the narration to the current timeline, then re-render.",
])]
S += [body("You can drag clips between slots and tracks, trim their edges, delete a selected clip, and scrub by dragging the ruler. The program monitor and the rendered MP4 show the same clip at every instant, so what you cut is what you get.")]

# ============================ 10. TARA ===================================
S += [h1("10", "Tara — Your In-Studio Creative Agent")]
S += [body("Tara is the always-open assistant on the right of the editor. You talk to her in plain language and she makes <b>real changes to the project's content</b> — she never touches code, settings, or infrastructure, only your creative assets.")]
S += [h2("What she can do")]
S += [bullets([
    "<b>Change a character's look</b> — “give her red hair”, “make him older and weathered”, “put her in a navy coat”.",
    "<b>Refine a specific shot</b> — adjust framing, lighting, or what is in a scene's still.",
    "<b>Re-roll an image</b> — a fresh take of a character sheet, prop sheet, or location plate.",
])]
S += [body("She routes your request to the right tool, runs the real service, and the editor refetches so the result appears. A change takes a little time to render; she tells you it is on its way.")]
S += [callout("She keeps the prior context", "Crucially, Tara preserves what already exists. A change edits the current image rather than re-rolling blind, and the established art style is always kept — so on an animation project, “make her blond” returns the character blond and still fully in the Pixar style, never live-action.")]

# ============================ 11. EXPORT =================================
S += [h1("11", "Export — Fifteen Deliverables")]
S += [body("The Export tab turns the project into downloadable files, grouped by kind. Every file is named to a convention: <b>PROJECTNAME_(thing)_V1.ext</b> (for example, <i>Without_the_Apron_Shotlist_V1.csv</i>). Items that have not been generated yet are disabled until they are ready.")]
S += [h3("Deliverables")]
S += [bullets([
    "<b>Everything</b> — one ZIP with every document, the edit XML, and all media, cleanly foldered.",
    "<b>Full Edit (MP4)</b> — the finished, rendered film.",
])]
S += [h3("Script &amp; documents (PDF / CSV)")]
S += [bullets([
    "<b>Script</b>, <b>Enriched Script</b> (with per-shot visuals), <b>Voiceover Script</b>, <b>Continuity &amp; Look</b>, and <b>Questionnaire</b> — all as PDFs.",
    "<b>Shotlist</b> — an editable CSV of every shot paired with its voiceover.",
])]
S += [h3("Media (ZIP)")]
S += [bullets([
    "<b>Images</b> (character sheets, plates, props, stills), <b>Videos</b> (every clip), <b>Voiceover</b> (the narration audio), and <b>Music</b> (the score).",
])]
S += [h3("Editorial &amp; data")]
S += [bullets([
    "<b>Edit XML</b> — an editorial timeline (FCP7 XML) with the clips laid out on V1/A1/A2 and real file paths, ready to import into Premiere, Resolve, or Final Cut.",
    "<b>Prompts</b> — a ZIP of every generation prompt.",
    "<b>Spend</b> — the full cost ledger as a CSV.",
])]

# ============================ 12. SPEND ==================================
S += [h1("12", "Spend — Where the Money Goes")]
S += [body("The Spend tab is an itemized, live ledger of every billed call this project makes, so cost spikes — QC retries, regenerated sheets, extra writer attempts — are visible at a glance. The headline number is the measured spend (your provider balance before vs. after a run — actual money), and the table breaks it down per call.")]
S += [bullets([
    "Each row shows the <b>time</b>, the <b>API</b> (Video, Image, Voiceover, Music, LLM, QC), the <b>outcome</b> (used, QC retry, recovered, failed), the <b>model</b>, the <b>units</b>, and the estimated <b>cost</b>.",
    "Summary cards total spend per API. A “wasted” figure flags spend that produced nothing.",
    "The header <b>balance panel</b> shows each provider's live balance and which one you are spending through; you can switch the spend provider there.",
])]
S += [callout("Outcomes, decoded", "<b>used</b> = in the project · <b>QC retry</b> = a rejected attempt (quality spend) · <b>failed/orphaned</b> = paid, produced nothing · <b>recovered</b> = rescued after a crash.")]

# ============================ 13. UNDER THE HOOD =========================
S += [h1("13", "Under the Hood — Models, QC Loops &amp; Hygiene")]
S += [body("Setara orchestrates several specialist models, each doing what it is best at, behind the stages you have seen.")]
S += [kvtable([
    ("Writing", "An LLM writes the brief, script, shotlist, and voiceover, and powers Tara's routing."),
    ("Images", "Nano Banana Pro or GPT Image 2 render character sheets, location plates, prop sheets, and stills."),
    ("Video", "Seedance renders the per-scene clips from the shots and reference frames."),
    ("Voice", "ElevenLabs records the narration per beat, fitted to the footage."),
    ("Music", "A score is generated, sized to the timeline, and mixed under the dialogue."),
    ("Vision QC", "A vision model scores every generated frame against strict criteria before it is accepted."),
])]
S += [h2("13.1 · The QC loops")]
S += [body("Generation is not fire-and-forget. Each image is run through a <b>quality-control loop</b>: it is rendered, scored by a checker, and regenerated up to N times, keeping the best result. The checker is matched to the project: a <b>photorealism</b> checker for microdrama and pitch (shallow depth of field, natural light, plausible staging), and an inverse <b>animation-style</b> checker for animation (the new frame must match the established medium, line, shading, and palette).")]
S += [h2("13.2 · Loop hygiene")]
S += [body("A key discipline: regeneration always re-renders from the <b>original</b> reference each retry, never stacking on the previous attempt — stacking degrades the image. Refines feed the existing image back in as a reference so an edit keeps the look and likeness rather than drifting.")]
S += [callout("Why it can refuse", "Editing photos of real, identifiable people can be declined by the image models for identity/deepfake reasons, and face-swap is blocked. Fixes are most reliable on AI-generated or non-identifiable subjects — which is exactly what the reference sheets are.")]

# ============================ 14. BEST PRACTICES =========================
S += [h1("14", "Tips, Pitfalls &amp; Best Practices")]
S += [bullets([
    "<b>Spend the brief.</b> A few minutes in Continuity (or one Auto-Generate, then tweaks) pays off across every later stage, because the script and look are built from it.",
    "<b>Shape the writing before the visuals.</b> Read and regenerate the shotlist while it is still free text generation; only then render stills and clips.",
    "<b>Lock what you love.</b> Locking a character sheet or scene guarantees it survives re-runs and carries identically into every shot.",
    "<b>Regenerate one thing, not everything.</b> Use the per-image Regenerate / Refine (or ask Tara) instead of re-running a whole stage, to keep cost and consistency under control.",
    "<b>Use Stop the moment something looks wrong.</b> It cancels queued and running jobs immediately; recovery reclaims anything already paid for.",
    "<b>For animation, lock the style first.</b> Generate the 2&times;2 style guide before the cast so every later image is matched to one consistent look.",
    "<b>Mind the model caveats.</b> Real, identifiable people can be refused; the local face-recognition models (where used) are licensed for non-commercial use.",
])]

# ============================ 15. GLOSSARY ===============================
S += [h1("15", "Glossary")]
S += [kvtable([
    ("Generator", "One of the three project types: Root (Microdrama), Branch (Pitch), Bloom (Animation)."),
    ("Stage", "A reviewable step in the pipeline, shown in the left rail."),
    ("Brief", "The creative-direction document set in Continuity; folded into the script source."),
    ("Beat", "A ~15-second scene; each beat contains several shots (cuts)."),
    ("Shot / cut", "One image or clip inside a beat, paired with the voiceover line over it."),
    ("Reference sheet", "A character / prop / location image reused on every clip for consistency."),
    ("Look Guide", "The compact visual bible — genre, palette, lighting, camera, motifs."),
    ("Style guide", "Animation only: a 2x2 model sheet that locks the single animation style."),
    ("QC loop", "Render → score → regenerate up to N times, keeping the best."),
    ("Lock", "Freeze an asset so a re-run never re-renders it."),
    ("Tara", "The in-studio agent that makes real content changes from plain-language requests."),
    ("Stringout", "An assembled sequence of stills/clips — the film before final polish."),
])]
S += [Spacer(1, 14)]
S += [HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=8)]
S += [Paragraph("Setara — story in, film out. Every stage reviewable; every asset exportable.", ParagraphStyle("end", fontName=SERIFI, fontSize=10.5, leading=15, textColor=MUTED, alignment=TA_CENTER))]

# ---- Build -----------------------------------------------------------------
def _start_body(canvas, doc2):
    pass

doc.build(S)
print("WROTE", OUT)

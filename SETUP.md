# Setup — Studio

A small local web app with six tabs that check (and sometimes fix) AI-generated film
frames: **Trailer**, **Animation**, **Character**, **Cinematic**, **Consistency**,
**Clearance**. Most tabs use Google's Gemini; the Character tab runs entirely on your
own machine.

## 1. Get a Gemini API key (~2 minutes)

1. Go to https://aistudio.google.com
2. Sign in with a Google account.
3. Click **Get API key** (left sidebar), then **Create API key**.
4. Let it create a new project, then **copy** the key and keep it somewhere safe.

No credit card is required for the checking tabs (Cinematic, Clearance, and the
checks inside the other tabs). The tabs that **generate or fix images** — Trailer,
Animation, Consistency — use Nano Banana Pro, which is paid (~$0.13 per 2K image)
and needs **billing enabled** on that Google project.

## 2. Install Python 3.10 or newer

Download it from https://www.python.org/downloads if you don't have it. Check with:

    python3 --version

## 3. Install the dependencies

In a terminal, from this folder:

    pip3 install -r requirements.txt

Only if you want the **Character** tab (local face recognition), also run:

    pip3 install -r requirements_face.txt

That tab downloads ~300 MB of face models the first time you use it.

## 4. Run it

    python3 studio_app.py

A local web address (like http://127.0.0.1:7860) will appear — open it in your
browser. To run a single tool on its own:

    python3 -m studio cinematic

(Any of: `trailer`, `animation`, `character`, `cinematic`, `continuity`, `clearance`.)

## 5. Use it

Paste your API key into the box at the top — every tab shares it. Then pick a tab,
drop in your image(s), and press the button. Each tool explains itself at the top of
its tab.

If you'd rather not paste the key each time, set it in your environment before
launching and the box fills itself in:

    export GEMINI_API_KEY="your-key-here"

## Tuning what "correct" means

Each tool's standards live at the top of its module in `studio/tools/`, as a list of
`Criterion` entries:

- **the criteria list** (`TRAITS`, `ASPECTS`, `STYLE_DIMENSIONS`, `CATEGORIES`…) —
  add, remove, or reword them; set `critical=True` for ones that must pass for an
  overall pass.
- **`PASS_THRESHOLD`** — what fraction of the criteria must pass (0.85 = 85%). Every
  tab has a live slider for this too.

After editing, re-run the checks:

    python3 -m unittest discover -s tests -t .

## Cost

Checks run on Gemini Flash and are inexpensive (roughly 1.5 cents each). Image
generation is the part that costs real money — around $0.13 per 2K image, and a
fix loop may spend a few of those, so the retry sliders cap what any one run can burn.

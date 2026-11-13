---
name: hooklab
description: Ingest a short-form video URL (TikTok, Instagram, YouTube), an image URL/local file, or raw text into HookLab for hook analysis — or, if there's nothing to ingest, explain what HookLab is and which command to use. Use whenever the user pastes a content URL, asks to analyse/ingest/score a hook/reel/short/piece of copy, or asks what HookLab can do / how to use it / seems unsure which HookLab command they need.
---

# /hooklab — ingest content, or explain HookLab if there's nothing to ingest

This skill has two modes. Work out which one applies from what follows `/hooklab` before doing anything.

## Step 0: decide the mode

- **Ingest mode** — the argument is a URL, a local file path, or a block of text/copy to analyse. Go to "Ingest mode" below.
- **Guide mode** — there's no content to ingest: the user is asking what HookLab does, how to use it, which command they need, or something similarly explanatory ("show me the guide", "what can hooklab do", "how does this work"). Go to "Guide mode" below.

If it's ambiguous, default to guide mode rather than guessing at a source to ingest.

---

## Ingest mode

**Chat-native.** `ingest.py` only fetches (Apify) and saves (SQLite). **You (the agent) do the analysis yourself** — the hook typing, checklist scoring, demographic/niche classification, retention tactics, replication templates, and asset extraction. No external model API is involved: everything downstream of getting the transcript and thumbnail is you.

**Working directory for all commands:** the repository root (run everything from the folder containing this repo).
**Shell:** PowerShell examples below; `APIFY_TOKEN` must be set in the shell you run from (it's the only env var HookLab needs).

### Step 1: fetch

Run:
```powershell
python ingest.py --fetch-only "<source>"
```
This prints **one JSON object on the last line of stdout** (Apify's own client library logs run progress to stderr, so stdout stays clean — if you want to be extra safe, redirect stderr away: `python ingest.py --fetch-only "<source>" 2>$null`). Parse that JSON. It has a `content_type` field telling you what you're dealing with:

| `content_type` | What you get in the JSON | What to do |
|---|---|---|
| `video` | `transcript`, `thumbnail_path` (local file or null), `kpi` (views/likes/comments/shares), `title`, `platform` | Go to "Analysing video" below |
| `local_video` | `transcript` is empty (no spoken-word transcription); analyse from the extracted frame and any on-screen text | Go to "Analysing video" below |
| `image_url` / `image_file` | `local_image_path` | Go to "Analysing image" below |
| `text` / `text_file` | `text` | Go to "Analysing text" below |
| `ambiguous` | `message` | Ask the user directly: "Is this a video, image, or text?" Then rerun step 1 with `--type video` / `--type image_url` / `--type text` appended. |

If a personal note was given, pass it through: `python ingest.py --fetch-only "<source>" --note "<note>"`. If marking as the user's own content, that flag doesn't affect fetch, carry it through to the save step instead (see Step 3).

### Step 2: analyse it yourself

Read any local image (`thumbnail_path` or `local_image_path`) by opening the image file before judging it — don't score a video or image on transcript/text alone if a thumbnail exists.

Produce a JSON object named `result` with **exactly** these fields (field names matter, they map straight to database columns):

**Analysing video** (`content_type` is `video` or `local_video`):
```
hook_type            one of: curiosity gap, outcome reveal, problem/agitation, controversy, relatability, authority claim
dominant_layer        one of: visual, text_overlay, audio
dominant_emotion       single dominant emotion the hook activates
target_demographic     one of: kids, teens, young adults, adults, middle-aged, seniors
niche                  one of: tech, lifestyle, fitness, finance, food, travel, fashion, education, entertainment, gaming, beauty, motivation, drone, business, humour, other
visual_explanation     what is shown on screen
pacing_explanation     how fast/slow it feels and how that affects attention
colour_explanation     specific colour/contrast choices
text_explanation       any on-screen text/captions visible
audio_explanation      what is said/heard per the transcript
overall_explanation    two sentences: why the hook works or doesn't, and the psychological mechanism
weakness               one sentence, the single weakest element
replication_template   one paragraph: the structure a creator could follow to replicate this in any niche
retention_tactics      array of up to 5 strings naming devices that sustain attention past the hook, [] if too short to assess
checklist: {
  outcome_before_how, text_in_first_2s, audio_suspense, human_face_or_reaction,
  two_layers_aligned, pattern_interrupt, no_intro_before_value   — all booleans
}
```
Mark each `true` only when its observable condition is met, otherwise `false`. Judge the hook (roughly the first 3 seconds), not the whole video:
- `outcome_before_how`: the first frame or spoken line shows or states the finished result / peak payoff before any explanation.
- `text_in_first_2s`: legible on-screen text is present within the first 2 seconds.
- `audio_suspense`: the audio opens mid-sentence or mid-action to create suspense, not a clean intro.
- `human_face_or_reaction`: a human face with eyes visible (no sunglasses) appears within roughly the first second, or a clear emotional reaction is shown.
- `two_layers_aligned`: at least two of {spoken hook, visual action, on-screen headline} state the same specific subject (all three aligned is ideal); misaligned layers fail.
- `pattern_interrupt`: the first second contains visual movement (camera pan, fast cut, or a subject entering/moving) or an otherwise unexpected visual.
- `no_intro_before_value`: does not open with a greeting ("hey guys", "welcome back") or preamble; the value or subject lands immediately.

**Analysing image** (`content_type` is `image_url` or `image_file`):
```
layout_pattern         plain English compositional structure
colour_palette         array of up to 5 dominant colours as hex codes
text_style             font weight/colour/placement/size, or "none"
emotional_tone         1-3 words
visual_hook_type       one of: curiosity gap, outcome reveal, pattern interrupt, social proof, contrast, authority, relatability
scroll_stop_reason     one sentence on exactly what stops a scroll and why
target_demographic     one of: kids, teens, young adults, adults, middle-aged, seniors
niche                  same list as video
checklist: {
  clear_focal_point, text_readable_at_glance, contrast_directs,
  recognisable_aesthetic, creates_question   — all booleans
}
```
Mark each `true` only when its condition is met:
- `clear_focal_point`: one element the eye lands on first, not a cluttered or competing composition.
- `text_readable_at_glance`: any text is legible without zooming (large enough, high contrast).
- `contrast_directs`: colour or contrast deliberately steers the eye to the focal point (e.g. a bright, high-key subject against a muted background).
- `recognisable_aesthetic`: the layout reads as a specific, identifiable style or platform format, not generic.
- `creates_question`: raises a question or desire the frame does not fully resolve.

**Analysing text** (`content_type` is `text` or `text_file`):
```
hook_type              same list as video
emotional_trigger      the specific emotion targeted
offer_structure        structure of any offer/value prop, or "none"
headline_technique     the specific copywriting technique used
strength               one sentence on what stops attention
weakness               one sentence, or "none"
rewrite_suggestion     one concrete improvement, or "none"
target_demographic     one of: kids, teens, young adults, adults, middle-aged, seniors
niche                  same list as video
retention_tactics      array of up to 5 strings, [] if a single standalone line
checklist: {
  claim_without_qualifying, specific_person, information_gap,
  under_10_words, concrete_language   — all booleans
}
```
Mark each `true` only when its condition is met:
- `claim_without_qualifying`: the first sentence states a claim outright, with no hedging ("might", "I think", "sort of", "kind of").
- `specific_person`: names or clearly addresses a specific audience or situation (e.g. "if you're a solo founder under 10k MRR"), not "everyone".
- `information_gap`: opens a loop the reader has to keep reading to close.
- `under_10_words`: the opening statement is under 10 words.
- `concrete_language`: uses concrete specifics, ideally a non-rounded number ("$4,213", "19 days"), rather than abstract phrasing.

### Step 3: extract reusable assets

From your own analysis above, extract 2-6 distinct reusable creative assets as an `assets` array. Each item:
```
asset_type          one of: layout_pattern, text_style, colour_palette, hook_template, audio_pattern, emotional_trigger
asset_description    plain English description of this specific asset
reuse_instruction     concrete, actionable instruction to recreate it in a new video/post — name tools, timings, font choices, colour codes, structural patterns, or verbal techniques
```
Only extract what's genuinely supported by your analysis, don't invent assets that aren't there.

### Step 4: save it

Build one JSON object combining everything and pipe it into `--save-result`:
```json
{
  "content_type": "<from step 1>",
  "source": "<the original source>",
  "platform": "<from step 1, or null>",
  "note": "<personal note or null>",
  "is_own": false,
  "thumbnail_path": "<from step 1, video/local_video only>",
  "kpi": "<from step 1, video only, omit entirely for local_video>",
  "title": "<from step 1, video/local_video only>",
  "result": { ...your step 2 object... },
  "assets": [ ...your step 3 array... ]
}
```
Write this to a temp file (e.g. `_ingest_payload.json` in the working directory), then:
```powershell
Get-Content _ingest_payload.json -Raw | python ingest.py --save-result
```
Then delete the temp file. Report the printed terminal output back to the user concisely, don't dump it raw: summarise the checklist pass rate, the strongest asset(s), and the DB row id.

### Known gotchas

- **Local video files**: `--fetch-only` extracts a frame for analysis (needs `ffmpeg` on PATH) but produces no spoken-word transcript, so judge them on the frame and any on-screen text.
- **Fetching URLs** needs `APIFY_TOKEN` set. Text and local-file sources need no token at all.

### After ingesting

A simple ingest changes only data, not code, so there's nothing else to update afterwards unless the ingest surfaced a bug you had to fix in the pipeline itself.

---

## Guide mode

This is a reference mode, not an execution mode — answer from the summary below rather than running code, unless the user's question requires you to check current state (e.g. "how many hooks do I have ingested" → that's `db_export.py`, not this).

### What HookLab is

A suite of agent skills (Claude Code and Codex) for analysing short-form video hooks. Accepts any URL (TikTok, Instagram, YouTube), image, or text, fetched via Apify actors. Analysis, checklist scoring, demographic/niche classification, retention tactics, and asset extraction are done chat-natively by the agent, with no external model API. A Flask + HTML dashboard shows checklist analytics, a filterable content library, and an asset bank.

**Reference:** see `CLAUDE.md` and `README.md` in the repo root for entry points, the file map, and environment variables before doing any non-trivial HookLab work.

### The commands, and when to use each

| Command | Use when... |
|---|---|
| `/hooklab <url/image/text>` | You have one piece of content to analyse and score. |
| `/hooklab` (no ingestible content) | You want an explanation of what HookLab does or which command to use — this mode. |
| `/hooklab-scriptgen` | You want a new video script engineered from the existing library (chat-native, asks topic/niche/demographic/platform/length). |
| `/hooklab-dashboard` | You want to see the visual analytics dashboard in the browser. |

### Checklists (what "pass rate" means)

- **Video (7 items):** shows outcome before how, on-screen text in first 2s, audio suspense/mid-thought cut, human face/reaction, 2+ layers aligned to one mechanism, pattern interrupt in first second, avoids intro before value.
- **Image (5 items):** clear single focal point, text readable without zooming, contrast-driven colour palette, recognisable aesthetic/platform style, creates an unresolved question or desire.
- **Text/Copy (5 items):** unqualified claim in first sentence, addresses a specific person/situation, creates an information gap, opening under 10 words, concrete not abstract language.

`/hooklab-scriptgen` (via `db_export.py`) only pulls hooks passing ≥50% of their checklist into the reference library — that's the quality bar for "provenly good enough to build from."

### Typical flow

1. Ingest content as it comes in: `/hooklab <url>`.
2. Check the dashboard periodically: `/hooklab-dashboard`.
3. When ready to plan a new video: `/hooklab-scriptgen`.

### Where to look for more detail

- Entry points, environment variables, and the file map: `CLAUDE.md` and `README.md` in the repo root.
- If something about HookLab feels out of date or missing, check the code on disk rather than assuming the docs are current.

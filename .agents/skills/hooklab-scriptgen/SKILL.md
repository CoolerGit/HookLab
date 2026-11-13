---
name: hooklab-scriptgen
description: Compose one engineered short-form video script from the user's HookLab content library, chat-native (no terminal, no external API). Use when the user asks to generate/compose/write a hook script, build a video brief, or run the HookLab composer.
---

# /hooklab-scriptgen — chat-native composer

This is the HookLab script composer, run entirely in chat. It asks the brief questions directly in chat, pulls the reference library via the read-only `db_export.py` export, and **you (the agent) compose the script yourself** — this skill never calls an external model API. Thumbnails are shown inline in chat using `![[...]]`-style embeds where a local path is available, or described if only a remote thumbnail exists.

**Working directory for all commands:** the repository root (run everything from the folder containing this repo).

## Steps

### 1. Ask the brief questions in chat

Ask these one at a time or together if the user already gave some upfront:
- What is the video about? (specific topic)
- Niche
- Target demographic
- Platform — one of: `TikTok`, `Instagram Reels`, `YouTube Shorts`
- Video length — one of: `15s`, `30s`, `60s`

To suggest defaults for niche/demographic, use the `suggestions` field in `db_export.py`'s output (see step 2).

### 2. Pull the library

```powershell
python db_export.py
```
This prints one JSON object to stdout: `{ suggestions, hooks, retention_tactics, assets }`. No interactive prompts, read-only, safe to run anytime. `hooks` only includes hooks passing ≥50% of their checklist (`MIN_PASS_RATE`), already sorted by pass rate, capped at 10. Each hook includes `thumbnail_path` (a local path under `thumbnails/`, or null) — open that image file and embed it inline when you cite that hook as your source, so the user can see what they're building from.

### 3. Compose the script yourself

Do not call any external API. Reason over the JSON: pick the strongest hook for this niche/demographic from `hooks`, the retention tactics from `retention_tactics` most likely to sustain attention for this topic, and the asset patterns from `assets` that amplify the chosen mechanism. Cite exactly where each element came from (e.g. "Hook #3 — authority claim, 6/7 pass rate, Instagram").

The library is your primary source. When it is thin (few or no qualifying hooks, or none in this niche), supplement with the general principles in `hook-principles.md` (in this skill folder): a three-phase (hook / retention / CTA) cross-niche reference. Treat those as strong defaults, not laws, and always prefer the library where they conflict, it is real evidence from this account. If you lean on a principle from that doc, cite it as such (e.g. "principles doc: single-action CTA") so sourcing stays honest.

Writing style rules — apply to every word of copy:
- No em dashes. Colon, comma, or restructure instead.
- Hook line (first spoken sentence / text overlay): short and punchy, one clean sentence.
- Everything else: medium-to-long sentences with natural flow, no fragments.

Structure your answer with these fields:
```json
{
  "sourcing": {
    "hook_source": "e.g. Hook #3 — authority claim, 6/7 pass rate, Instagram",
    "hook_reason": "one sentence on why this hook structure fits the brief",
    "retention_sources": ["..."],
    "asset_sources": ["..."]
  },
  "hook": {
    "visual_direction": "exact shot or action to film",
    "text_overlay": "exact words on screen with timing cues, or none",
    "audio_voiceover": "exact words to say, or sound design description",
    "mechanic": "one sentence on the psychological mechanism and which checklist items this passes"
  },
  "retention_beats": [
    {"timestamp": "3-10s", "beat": "..."},
    {"timestamp": "10-25s", "beat": "..."}
  ],
  "cta": "closing line, one sentence",
  "why_this_build": "two sentences on why this combination is optimal"
}
```

Present this to the user as a readable chat response (sourcing breakdown, hook, retention structure, CTA, why this build) — not as raw JSON.

### 4. Persist it

Write the full object (topic, niche, target_demographic, platform, video_length, plus everything above) to `renders/script_latest.json`:

```powershell
python -c "import json,os; os.makedirs('renders', exist_ok=True); json.dump(<the object>, open('renders/script_latest.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)"
```
In practice, write `renders/script_latest.json` directly with the JSON you composed — simpler than round-tripping through `python -c`. Make sure the top-level object has `topic`, `niche`, `target_demographic`, `platform`, `video_length` alongside `sourcing`/`hook`/`retention_beats`/`cta`/`why_this_build`.

Then save it into the `generated_scripts` table so it shows up alongside terminal-composed scripts:
```powershell
python -c "import json,sqlite3; d=json.load(open('renders/script_latest.json',encoding='utf-8')); conn=sqlite3.connect('hooks.db'); conn.execute('CREATE TABLE IF NOT EXISTS generated_scripts (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, niche TEXT, target_demographic TEXT, platform TEXT, video_length TEXT, sourcing TEXT, script_full TEXT, created_at TEXT)'); conn.execute('INSERT INTO generated_scripts (topic, niche, target_demographic, platform, video_length, sourcing, script_full, created_at) VALUES (?,?,?,?,?,?,?,datetime())', (d.get('topic'), d.get('niche'), d.get('target_demographic'), d.get('platform'), d.get('video_length'), json.dumps(d.get('sourcing', {})), json.dumps(d))); conn.commit(); conn.close()"
```

## If the library is empty

If `db_export.py` returns `{"error": "hooks.db not found"}` or `hooks` is an empty list, tell the user there's nothing qualifying yet (no hook has hit the 50% checklist pass rate) and to ingest more content with `/hooklab` first. Don't fabricate sourcing.

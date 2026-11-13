---
name: hooklab-seo
description: Generate SEO-optimised title, description/caption, and tags for a short-form video, informed by the user's own HookLab library, live platform trend research, and their voice from pasted examples. Use when asked to write a title/description/caption/tags for a video, optimise a post for SEO, or figure out what to post something as.
---

# /hooklab-seo — SEO title, description, and tags generator

Chat-native, like `/hooklab-scriptgen` — no terminal script to run end to end, no external API call. **You (the agent) compose the output yourself**, reasoning over three inputs: the user's own ingested library (what's proven to work), live web research (what's working on the platform right now), and a voice sample the user pastes in for this run.

**Working directory for all commands:** the repository root (run everything from the folder containing this repo).

## Steps

### 1. Ask the brief questions in chat

Ask these upfront (skip any the user already gave you):
- **Subject** — either an existing hook ID from their library (`hooks #N`) to write SEO copy for, or a short description of a new/unreleased video if it hasn't been ingested yet.
- **Platform** — one of: `TikTok`, `Instagram Reels`, `YouTube Shorts`. SEO conventions differ enough between these that this isn't optional.
- **Voice sample** — ask them to paste 1-2 of their own past captions/titles/descriptions so the output sounds like them, not a generic copywriter. If they have none to hand or skip it, fall back to a clean, punchy, platform-appropriate tone and say so explicitly in your output rather than silently guessing at "their voice."

### 2. Pull "previous winning trends" from their own library

Run:
```powershell
python -c "
import sys
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3, json
conn = sqlite3.connect('hooks.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('''
    SELECT id, platform, content_title, niche, target_demographic,
           checklist_summary, hook_type, dominant_emotion,
           views, likes, comments, url
    FROM hooks
    WHERE checklist_summary IS NOT NULL
''').fetchall()

def pass_rate(s):
    try:
        a, b = s.split('/')
        return int(a.strip().split()[0]) / int(b.strip().split()[0])
    except Exception:
        return 0

data = [dict(r) for r in rows]
data.sort(key=lambda r: (pass_rate(r.get('checklist_summary') or ''), r.get('views') or 0), reverse=True)
print(json.dumps(data[:12], ensure_ascii=False))
"
```
This is read-only and safe to run anytime. Prefer rows matching the requested platform when picking what to reference, but fall back to the full set if there's too little data for that platform alone. Look at `content_title` (the actual caption/title used), `niche`, `hook_type`, and `views`/`likes` together to spot what topics and phrasing have actually performed for them, not just what scored well on the checklist.

If `hooks.db` doesn't exist or returns no rows, say so and skip straight to web research — don't fabricate library trends.

### 3. Live web research for platform SEO + posting time

Search the web (do this fresh each run, don't rely on training-data knowledge — platform algorithms and SEO conventions change often). Research, for the specific platform chosen:
- Current title/caption/hashtag best practices and length conventions.
- What YouTube's "Tags" field is actually worth doing now vs. relying on title/description keywords (YouTube has deprecated tags' influence over time — check current guidance rather than assuming).
- Optimal posting time/day for that platform, framed as general guidance (note explicitly that their own account's analytics, if they have access to them, will beat generic advice).

Keep this to 1-3 targeted searches — don't sprawl into a general research session.

### 4. Compose the output in their voice

Write:
- **Title** — platform-appropriate. YouTube Shorts wants a keyword-forward, clickable title; Instagram Reels and TikTok don't really have a separate "title" field, so treat this as the opening line of the caption instead and say so.
- **Description/caption** — matched to the voice sample from step 1. State clearly if no sample was given and you defaulted to a generic tone.
- **Tags/hashtags** — respect platform norms (e.g. Instagram: a handful of tightly relevant tags beats 30 generic ones; TikTok: fewer, trend-aware; YouTube: description keywords now matter more than the Tags field, per current research from step 3).
- **Platform tips** — 2-4 bullet points specific to what you found in step 3, not generic advice.
- **Optimal time to post** — from step 3's research, with the caveat that their own account analytics would be more precise.

Writing style rules:
- No em dashes. Colon, comma, or restructure instead.
- British English.
- No filler, no fluff, say what you mean.

### 5. Present it

Structure the chat response clearly under headers (Title / Description / Tags / Platform Tips / Best Time to Post), cite which hook(s) from their library informed the trend read (e.g. "Hook #5 — 5/7 pass rate, 3.4M views — informed the curiosity-gap framing"), and cite what the web research told you (with a one-line summary, not a wall of search results).

This isn't persisted to the database — it's a one-off chat output. Only save it somewhere if the user asks.

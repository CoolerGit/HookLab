---
name: hooklab-edit
description: Edit a raw clip into a finished short-form video (default 9:16 1080x1920) using HyperFrames, grounded in the clip's own transcript and optionally shaped by HookLab's saved patterns. Use when the user gives a video file and asks to edit it, package it, add graphics/captions, or turn it into a Short/Reel/TikTok.
argument-hint: "[path to video] [optional: hook id, or overrides like 16:9]"
---

# /hooklab-edit — raw clip to finished short

Orchestrates existing skills, does not reinvent them. **Read `shorts-edit/SKILL.md` and `talking-head-recut` for the full workflow and the card HTML/GSAP contract, then follow that workflow with the HookLab changes below.** Captions follow `captions-overlay` doctrine.

**Deps:** run `npx hyperframes doctor` first; fix missing ffmpeg/ffprobe/Chrome/whisper before building (same as shorts-edit).

## What changes vs. plain shorts-edit

### 1. Output default is 9:16 1080x1920, always
shorts-edit defaults output to "match the source". **Override that: default canvas is 1080x1920 regardless of source shape, resolution, or framerate.** Only change it if the user's request says otherwise (e.g. "16:9", "square"). The re-encode step already normalises any input fps/codec/container; the composition uses `object-fit: cover` + `object-position`, so no pixel-hardcoded crops, any source resolution just works.

### 2. Classify content shape before storyboarding (new Step 0)
Sample 3-5 frames across the clip + read the transcript. Decide which case, then storyboard accordingly:
- **Single talking-head, clear subject** → normal shorts-edit treatment (crop, split, face-bottom cards).
- **No-face / screen recording** (app demo, gameplay, code, slides) → skip the face-crop entirely. Full native frame, cards are the primary layer, captions still apply. Simpler, not harder.
- **Multi-speaker / no single dominant subject** → see Step 1.

### 3. Detect scene cuts (new)
Landscape/multicam sources cut between angles; one fixed crop can't follow them. Detect cuts:
```bash
ffmpeg -v error -i "<source>" -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep -o "pts_time:[0-9.]*"
```
Extract a frame per segment, judge framing per segment, and set `object-position` (or a hard `tl.set` reframe at the cut, as done for the Hormozi clip). If a segment has no clear single subject to crop to, **ask the user** what to do (full-frame fallback vs. a specific crop). Do not silently guess a crop on ambiguous multi-speaker footage.

### 4. Ground content in the real transcript
The clip's own transcript is the source of truth for card copy. If the user ran `/hooklab-scriptgen` earlier this session, or names a hook id, use that brief/`replication_template`/library patterns to inform **structure, pacing, and style** only, never to override what's actually said in the clip.

### 5. Brand + captions
Use this skill's `brand.md` (HookLab colours, Pally). Copy bundled `assets/fonts/Pally-*.woff2` into `public/fonts/` (do not re-download). Add a word-by-word caption rail per `captions-overlay` (rail-first, Pally Bold, payoff words in `--cap-hot`) unless the user says no captions.

### 6. Always snapshot before rendering
`npx hyperframes lint public` (0 errors), then `npx hyperframes snapshot public --at <t>` for every distinct segment/layout and **show the user the frames to approve before the full render.** This is the checkpoint.

## Output
`videos/<name>/output.mp4` (mux the source audio back after render — hyperframes render is video-only). Report the path. Offer tweaks; re-renders are cheap.

## Out of scope
Auto-posting to any platform. This skill only produces the finished MP4.

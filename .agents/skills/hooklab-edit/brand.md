# HookLab brand preset

Use these tokens for every `/hooklab-edit` build (overrides `shorts-edit`'s defaults).

## Colours (paste into composition `:root`)

```css
--bg: #23262b;         /* card surface */
--bg-deep: #16181c;    /* page + fullscreen card base */
--text: #f4f5f7;       /* primary text */
--accent-0: #4c8dff;   /* the one loud colour: kickers, marks, rules, dividers */
--accent-1: #7bb0ff;   /* accent tint */
--accent-3: #8b8f96;   /* neutral gray, secondary text */
--cap-hot: #ffd23f;    /* caption emphasis (payoff words) */
```

## Fonts

- Card body: **Inter** 400/600/800 (CDN, same as shorts-edit).
- Card mono / titles: **JetBrains Mono** 500/700 (CDN, same as shorts-edit).
- Captions: **Pally** 500/700 — bundled in this skill at `assets/fonts/Pally-*.woff2`. Copy into `public/fonts/`, do not re-download.

## Captions

Word-by-word rail (see `captions-overlay` doctrine): Pally Bold, white, `text-shadow` + thin dark stroke for legibility, payoff words in `--cap-hot`. Bottom overlay (~70% canvas height), not a reserved band. Rail-first; emphasis is inline colour, not behind-subject matting.

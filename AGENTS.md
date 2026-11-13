# HookLab

A suite of agent skills for analysing short-form video hooks, usable from Claude Code or Codex. The hook analysis is done chat-natively by the agent; the Python scripts are helpers the skills call, not standalone tools.

## Skills

`.claude/skills/` (Claude Code) and `.agents/skills/` (Codex) hold identical copies: `hooklab`, `hooklab-scriptgen`, `hooklab-dashboard`, `hooklab-seo`, `hooklab-edit`.

## Helper scripts

- `ingest.py` — `--fetch-only` fetches a URL via Apify (transcript, thumbnail, stats) and prints JSON; `--save-result` reads the agent's analysis JSON from stdin and writes it to `hooks.db`. It does not analyse anything itself.
- `server.py` — Flask dashboard (serves `dashboard.html` and a read-only JSON API over `hooks.db`).
- `db_export.py` — read-only JSON export of the library, consumed by `/hooklab-scriptgen`.
- `library.py` — shared helpers (DB loaders, pass-rate, pip bootstrap) used by `ingest.py`/`db_export.py`/`server.py`.

## Environment

`APIFY_TOKEN` (for fetching URLs), set as an OS-level environment variable, never hardcoded. See `.env.example`. No other API keys are required: the agent does the analysis, so there is no external model API to configure.

When editing a skill, change `.claude/skills/` and copy it to `.agents/skills/` (`cp -r .claude/skills/. .agents/skills/`). CI fails if the two differ.

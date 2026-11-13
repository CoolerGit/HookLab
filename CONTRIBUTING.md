# Contributing to HookLab

Thanks for your interest in improving HookLab.

## Getting set up

1. Fork and clone the repo.
2. `pip install -r requirements.txt`
3. Set `APIFY_TOKEN` as an environment variable (see `.env.example`). It's the only key HookLab needs.
4. Open the repo in Claude Code (`/hooklab <url>`) or Codex (`$hooklab <url>`) and use the skills.

`hooks.db` self-initialises on first run, so you do not need any seed data.

## Guidelines

- Keep changes small and focused. One concern per pull request.
- Prefer the standard library and existing helpers over new dependencies.
- HookLab runs inside Claude Code or Codex; the hook analysis is done by the agent, not an external API. Edit skills in `.claude/skills/` and mirror them to `.agents/skills/` (CI checks they match). The Python helper scripts target Python 3.10+.
- Do not commit personal data, API keys, `hooks.db`, or `thumbnails/`.

## Submitting a change

1. Create a branch.
2. Make your change and confirm the affected scripts still byte-compile (`python -m compileall .`) and run.
3. Open a pull request describing what changed and why.

## Scope

This repository is a suite of agent skills for hook analysis, plus a dashboard. Auto-posting to social platforms is intentionally not part of it.

By contributing you agree that your contributions are licensed under the [Apache-2.0](LICENSE) license.

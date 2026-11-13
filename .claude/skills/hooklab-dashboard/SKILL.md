---
name: hooklab-dashboard
description: Open the HookLab visual dashboard (Flask + dashboard.html) in the browser. Use when the user asks to open, view, launch, or check the HookLab dashboard.
---

# /hooklab-dashboard — launch the dashboard

`server.py` is a small Flask app that serves `dashboard.html` and a read-only JSON API over `hooks.db`. Running it opens `http://localhost:5000` in the default browser automatically and then blocks the terminal (`Ctrl+C` to stop) — it does not exit on its own.

**Working directory:** the repository root (run from the folder containing this repo).

## Steps

1. Check whether a server is already listening on port 5000 before starting a second one:
   ```powershell
   Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
   ```
   If something is already listening there, just tell the user it's already running at `http://localhost:5000` — don't start a duplicate.
2. Otherwise, launch it as a background process (it blocks, and it auto-opens the browser itself, so run it detached rather than foreground-and-wait):
   ```powershell
   Start-Process -FilePath python -ArgumentList "server.py" -WindowStyle Hidden
   ```
3. Confirm to the user that the dashboard is live at `http://localhost:5000` and that the browser tab should have opened automatically. If it didn't open (e.g. headless session), give them the URL to open manually. `server.py` binds `0.0.0.0`, so it's also reachable from their phone on the same Wi-Fi, but since it's launched detached (`-WindowStyle Hidden`), its own startup print of the LAN IP won't reach you. Get the LAN IP yourself and pass along `http://<that IP>:5000`:
   ```powershell
   (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp,Manual -ErrorAction SilentlyContinue | Where-Object {$_.IPAddress -notlike '169.*'}).IPAddress
   ```
4. If Flask isn't installed, `server.py` auto-installs it on first run — expected on a fresh machine, not an error.
5. If `hooks.db` doesn't exist yet, the dashboard will load with an empty-state message ("No data yet") — that's correct behaviour, not a bug. Tell the user to run `/hooklab <url>` first if they expect to see data and don't.

## Do not

- Don't run `python server.py` in the foreground without backgrounding it — it never returns, so the command will hang until timeout.

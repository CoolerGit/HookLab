import os
import sys
import time
import json
import threading
import webbrowser
import sqlite3

from library import ensure, _pass_rate

ensure("flask")
from flask import Flask, jsonify, send_from_directory, request

app = Flask(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "hooks.db")
THUMB_DIR = os.path.join(BASE_DIR, "thumbnails")


def query(sql, params=()):
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def thumb_url(path):
    if not path:
        return None
    if not os.path.exists(path):
        return None
    return "/thumbnails/" + os.path.basename(path)


BEST_OF_WEEK_CATEGORIES = [
    ("layout_pattern", "Thumbnail & Layout of Visuals"),
    ("audio_pattern",  "Audio & Background Music"),
    ("colour_palette", "Colour Palette"),
    ("hook_template",  "Hook Template"),
    ("text_style",     "Text Style"),
]


def compute_best_of_week():
    week_hooks = query("""
        SELECT * FROM hooks
        WHERE datetime(analyzed_at) >= datetime('now', '-7 days')
    """)
    for h in week_hooks:
        h["_rank"] = (_pass_rate(h.get("checklist_summary")), h.get("views") or 0)

    categories = []
    for atype, label in BEST_OF_WEEK_CATEGORIES:
        rows = query("""
            SELECT a.id, a.asset_type, a.asset_description, a.reuse_instruction,
                   h.id AS hook_id, h.hook_type, h.platform, h.url,
                   h.thumbnail_path, h.checklist_summary, h.views, h.likes, h.comments
            FROM assets a
            JOIN hooks h ON a.source_table = 'hooks' AND a.source_id = h.id
            WHERE a.asset_type = ?
              AND datetime(h.analyzed_at) >= datetime('now', '-7 days')
        """, (atype,))
        best, best_rank = None, None
        for r in rows:
            rank = (_pass_rate(r.get("checklist_summary")), r.get("views") or 0)
            if best_rank is None or rank > best_rank:
                best_rank, best = rank, r
        if best:
            best["thumbnail_url"] = thumb_url(best.get("thumbnail_path") or "")
        categories.append({"key": atype, "label": label, "asset": best})

    best_hook = max(week_hooks, key=lambda h: h["_rank"]) if week_hooks else None
    rt_asset = None
    if best_hook:
        try:
            tactics = json.loads(best_hook.get("retention_tactics") or "[]")
        except Exception:
            tactics = []
        if tactics:
            rt_asset = {
                "hook_id":            best_hook["id"],
                "hook_type":          best_hook.get("hook_type"),
                "platform":           best_hook.get("platform"),
                "url":                best_hook.get("url"),
                "thumbnail_url":      thumb_url(best_hook.get("thumbnail_path") or ""),
                "checklist_summary":  best_hook.get("checklist_summary"),
                "views":              best_hook.get("views"),
                "tactics":            tactics,
            }
    categories.append({"key": "retention_tactics", "label": "Retention Tactics", "asset": rt_asset})

    return {"week_hook_count": len(week_hooks), "categories": categories}


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "dashboard.html")


@app.route("/thumbnails/<path:filename>")
def thumbnail(filename):
    return send_from_directory(THUMB_DIR, filename)


@app.route("/fonts/<path:filename>")
def fonts(filename):
    return send_from_directory(os.path.join(BASE_DIR, "fonts"), filename)


@app.route("/renders/<path:filename>")
def renders(filename):
    renders_dir = os.path.join(BASE_DIR, "renders")
    return send_from_directory(renders_dir, filename)


@app.route("/api/hook-json/<int:hook_id>")
def hook_json(hook_id):
    rows = query("SELECT * FROM hooks WHERE id = ?", (hook_id,))
    if not rows:
        return jsonify({"error": "Hook not found"}), 404
    return jsonify(rows[0])


@app.route("/api/delete", methods=["POST"])
def delete_item():
    payload  = request.get_json(force=True, silent=True) or {}
    table    = payload.get("table")
    item_id  = payload.get("id")

    if table not in ("hooks", "ingested_content") or not isinstance(item_id, int):
        return jsonify({"error": "invalid request"}), 400
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "no database"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

        thumb_path = row["thumbnail_path"] if table == "hooks" and "thumbnail_path" in row.keys() else None

        conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        conn.execute("DELETE FROM assets WHERE source_table = ? AND source_id = ?", (table, item_id))
        conn.commit()
    finally:
        conn.close()

    if thumb_path and os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except Exception:
            pass

    return jsonify({"ok": True})


@app.route("/api/favourite", methods=["POST"])
def toggle_favourite():
    payload  = request.get_json(force=True, silent=True) or {}
    table    = payload.get("table")
    item_id  = payload.get("id")

    if table not in ("hooks", "ingested_content") or not isinstance(item_id, int):
        return jsonify({"error": "invalid request"}), 400
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "no database"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(f"SELECT is_favourite FROM {table} WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404

        new_value = 0 if row["is_favourite"] else 1
        conn.execute(f"UPDATE {table} SET is_favourite = ? WHERE id = ?", (new_value, item_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "is_favourite": new_value})


@app.route("/api/data")
def data():
    hooks    = query("SELECT * FROM hooks ORDER BY analyzed_at DESC")
    ingested = query("SELECT * FROM ingested_content ORDER BY analyzed_at DESC")
    assets   = query("SELECT * FROM assets ORDER BY id DESC")

    for h in hooks:
        h["thumbnail_url"] = thumb_url(h.get("thumbnail_path") or "")

    return jsonify({
        "hooks":         hooks,
        "ingested":      ingested,
        "assets":        assets,
        "best_of_week":  compute_best_of_week(),
    })


def _open_browser():
    time.sleep(0.9)
    webbrowser.open("http://localhost:5000")


def _lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    lan_ip = _lan_ip()
    print("\n  HookLab  ->  http://localhost:5000")
    if lan_ip:
        print(f"  On your phone (same Wi-Fi)  ->  http://{lan_ip}:5000")
    print("  Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=5000, debug=False)

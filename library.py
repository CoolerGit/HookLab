import sys
import json
import subprocess
from collections import Counter

MIN_PASS_RATE = 0.5
MAX_HOOKS     = 10
MAX_TACTICS   = 15
MAX_ASSETS    = 12


def ensure(package, import_name=None):
    import importlib
    name = import_name or package
    try:
        importlib.import_module(name)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])


def _pass_rate(summary):
    try:
        parts = (summary or "").split("/")
        return int(parts[0].strip().split()[0]) / int(parts[1].strip().split()[0])
    except Exception:
        return 0


def _rows(conn, sql, params=()):
    cur  = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load_hooks(conn):
    rows = _rows(conn, """
        SELECT id, hook_type, dominant_emotion, platform,
               target_demographic, niche,
               checklist_results, checklist_summary,
               replication_template, overall_explanation,
               weakness, visual_explanation, audio_explanation,
               retention_tactics, thumbnail_path
        FROM hooks
        WHERE checklist_summary IS NOT NULL
        ORDER BY analyzed_at DESC
    """)
    qualified = [r for r in rows if _pass_rate(r.get("checklist_summary") or "") >= MIN_PASS_RATE]
    qualified.sort(key=lambda r: _pass_rate(r.get("checklist_summary") or ""), reverse=True)
    return qualified[:MAX_HOOKS]


def load_retention_tactics(conn):
    tactics = []
    for r in _rows(conn, """
        SELECT id, hook_type, platform, niche, target_demographic,
               retention_tactics, checklist_summary
        FROM hooks
        WHERE retention_tactics IS NOT NULL AND retention_tactics != '[]'
    """):
        try:
            items = json.loads(r["retention_tactics"])
        except Exception:
            continue
        if items:
            tactics.append({
                "source":      f"Hook #{r['id']} ({r['platform'] or 'unknown'}, {r['hook_type'] or 'unknown'})",
                "niche":       r["niche"] or "",
                "demographic": r["target_demographic"] or "",
                "items":       items,
            })

    try:
        for r in _rows(conn, """
            SELECT id, content_type, hook_type, niche, target_demographic,
                   retention_tactics
            FROM ingested_content
            WHERE retention_tactics IS NOT NULL AND retention_tactics != '[]'
        """):
            try:
                items = json.loads(r["retention_tactics"])
            except Exception:
                continue
            if items:
                tactics.append({
                    "source":      f"{(r['content_type'] or 'content').title()} #{r['id']} ({r['hook_type'] or 'unknown'})",
                    "niche":       r["niche"] or "",
                    "demographic": r["target_demographic"] or "",
                    "items":       items,
                })
    except Exception:
        pass

    return tactics[:MAX_TACTICS]


def load_assets(conn):
    rows = _rows(conn, """
        SELECT a.asset_type, a.asset_description, a.reuse_instruction,
               h.id AS hook_id, h.hook_type, h.checklist_summary, h.platform
        FROM assets a
        JOIN hooks h ON a.source_table = 'hooks' AND a.source_id = h.id
        WHERE a.asset_type IN ('hook_template', 'audio_pattern', 'emotional_trigger')
          AND h.checklist_summary IS NOT NULL
        ORDER BY h.analyzed_at DESC
        LIMIT ?
    """, (MAX_ASSETS * 2,))
    return [r for r in rows if _pass_rate(r.get("checklist_summary") or "") >= MIN_PASS_RATE][:MAX_ASSETS]


def suggest_from_db(conn):
    niches, demos = [], []
    for table in ("hooks", "ingested_content"):
        try:
            for niche, demo in conn.execute(
                f"SELECT niche, target_demographic FROM {table} "
                f"WHERE niche IS NOT NULL OR target_demographic IS NOT NULL"
            ):
                if niche:
                    niches.append(niche.strip().lower())
                if demo:
                    demos.append(demo.strip().lower())
        except Exception:
            pass
    return {
        "niche":       Counter(niches).most_common(1)[0][0] if niches else None,
        "demographic": Counter(demos).most_common(1)[0][0]  if demos  else None,
    }

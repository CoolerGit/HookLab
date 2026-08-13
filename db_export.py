import sys
import os
import json
import sqlite3

from library import load_hooks, load_retention_tactics, load_assets, suggest_from_db

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.db")


def main():
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": "hooks.db not found"}))
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    out = {
        "suggestions":       suggest_from_db(conn),
        "hooks":             load_hooks(conn),
        "retention_tactics": load_retention_tactics(conn),
        "assets":            load_assets(conn),
    }
    conn.close()

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

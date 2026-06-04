"""
Helper script to clean Smart BI/Commerce migration state in SQLite when
legacy tables exist without migration records. Run via:
  venv\Scripts\python.exe tools/reset_smart_bi_state.py
Then run:
  venv\Scripts\python.exe manage.py migrate smart_bi --fake-initial
  venv\Scripts\python.exe manage.py migrate commerce --fake
  venv\Scripts\python.exe manage.py migrate
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db.sqlite3"


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Ensure django_migrations table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_migrations'")
    if not cur.fetchone():
        raise SystemExit("django_migrations table missing; database not initialized.")

    # Delete Smart BI and Commerce migration records to allow re-faking
    cur.execute("DELETE FROM django_migrations WHERE app='smart_bi'")
    cur.execute("DELETE FROM django_migrations WHERE app='commerce' AND name LIKE '0025_%'")
    cur.execute("DELETE FROM django_migrations WHERE app='commerce' AND name LIKE '0026_%'")

    # Drop problematic Smart BI tables if they exist
    for table in ["smart_bi_fraudalert"]:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cur.fetchone():
            cur.execute(f'DROP TABLE "{table}"')

    conn.commit()
    conn.close()
    print("Reset complete: removed smart_bi + commerce migration rows and dropped stray tables (if any).")


if __name__ == "__main__":
    main()

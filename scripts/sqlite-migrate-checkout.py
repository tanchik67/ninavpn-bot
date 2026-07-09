#!/usr/bin/env python3
"""
SQLite: add payments.checkout_token / checkout_email if Alembic failed.
Run on server:
  cd /opt/ninavpn-bot && ./venv/bin/python scripts/sqlite-migrate-checkout.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _db_path() -> Path:
    env = ROOT / ".env"
    url = ""
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if "ninavpn.db" in url:
        tail = url.split("ninavpn.db", 1)[-1].lstrip("/")
        if tail.startswith("///"):
            return Path(tail[2:])
        if tail.startswith("/"):
            return Path(tail)
    return ROOT / "ninavpn.db"


def main() -> int:
    db = _db_path()
    if not db.is_file():
        print(f"DB not found: {db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(payments)")}
        if "checkout_token" not in cols:
            conn.execute("ALTER TABLE payments ADD COLUMN checkout_token VARCHAR(64)")
            print("OK: +checkout_token")
        else:
            print("OK: checkout_token exists")
        if "checkout_email" not in cols:
            conn.execute("ALTER TABLE payments ADD COLUMN checkout_email VARCHAR(254)")
            print("OK: +checkout_email")
        else:
            print("OK: checkout_email exists")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_checkout_token "
            "ON payments (checkout_token)"
        )
        print("OK: index ix_payments_checkout_token")

        try:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            if row and row[0] != "003_checkout_token":
                conn.execute(
                    "UPDATE alembic_version SET version_num = '003_checkout_token'"
                )
                print("OK: alembic_version -> 003_checkout_token")
        except sqlite3.OperationalError:
            pass

        conn.commit()
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

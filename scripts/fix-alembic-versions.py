#!/usr/bin/env python3
"""Remove null bytes from alembic/versions/*.py (fixes ValueError on some VPS)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "alembic" / "versions"


def main() -> int:
    if not VERSIONS.is_dir():
        print(f"not found: {VERSIONS}", file=sys.stderr)
        return 1
    fixed = 0
    for path in sorted(VERSIONS.glob("*.py")):
        raw = path.read_bytes()
        if b"\x00" not in raw:
            continue
        path.write_bytes(raw.replace(b"\x00", b""))
        print(f"fixed null bytes: {path.name}")
        fixed += 1
    if fixed == 0:
        print("OK: no null bytes in migration files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Clean alembic/versions on server:
- remove macOS AppleDouble junk (._*.py)
- strip null bytes from real migration files
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "alembic" / "versions"


def main() -> int:
    if not VERSIONS.is_dir():
        print(f"not found: {VERSIONS}", file=sys.stderr)
        return 1

    removed = 0
    for path in sorted(VERSIONS.iterdir()):
        name = path.name
        if name.startswith("._") or name == ".DS_Store":
            path.unlink(missing_ok=True)
            print(f"removed junk: {name}")
            removed += 1

    fixed = 0
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name.startswith("._"):
            continue
        raw = path.read_bytes()
        if b"\x00" not in raw:
            continue
        path.write_bytes(raw.replace(b"\x00", b""))
        print(f"fixed null bytes: {path.name}")
        fixed += 1

    if removed == 0 and fixed == 0:
        print("OK: alembic/versions clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

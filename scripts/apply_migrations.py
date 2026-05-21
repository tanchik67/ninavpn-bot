#!/usr/bin/env python3
"""
Применить миграции Alembic с переменными из .env (как у бота).
Запуск на сервере:
  cd /opt/ninavpn-bot && ./venv/bin/python scripts/apply_migrations.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        from dotenv import dotenv_values
    except ImportError:
        print("Нужен python-dotenv.", file=sys.stderr)
        return 1

    env_file = ROOT / ".env"
    if env_file.is_file():
        for k, v in dotenv_values(env_file).items():
            if k and v is not None:
                os.environ[k] = v
    else:
        print("Предупреждение: нет файла", env_file, file=sys.stderr)

    os.chdir(ROOT)
    db_url = (os.environ.get("DATABASE_URL") or "").strip() or "sqlite+aiosqlite:///ninavpn.db"
    print("Миграции применяются к DATABASE_URL из .env (cwd = каталог бота):")
    print(" ", db_url)

    venv_py = ROOT / "venv" / "bin" / "python"
    exe = str(venv_py) if venv_py.is_file() else sys.executable
    cmd = [exe, "-m", "alembic", "upgrade", "head"]
    print("Running:", " ".join(cmd), "in", ROOT)
    return subprocess.call(cmd, cwd=ROOT, env=os.environ)


if __name__ == "__main__":
    sys.exit(main())

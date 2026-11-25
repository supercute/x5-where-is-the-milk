"""Create a consistent SQLite snapshot and prune old backups."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENTION_DAYS = 14


def database_path() -> Path:
    url = os.getenv("DATABASE_URL", "sqlite:////data/store.db")
    if not url.startswith("sqlite:///"):
        raise SystemExit("Backup supports SQLite DATABASE_URL only")
    return Path(url.removeprefix("sqlite:///"))


def create_backup(target_dir: Path) -> Path:
    source_path = database_path()
    if not source_path.is_file():
        raise SystemExit(f"Database not found: {source_path}")

    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = target_dir / f"store-{timestamp}.db"
    temporary = target.with_suffix(".db.tmp")

    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    destination = sqlite3.connect(temporary)
    try:
        source.backup(destination)
        result = destination.execute("PRAGMA quick_check;").fetchone()
        if not result or result[0] != "ok":
            raise SystemExit("Backup verification failed")
    finally:
        destination.close()
        source.close()

    for suffix in ("-wal", "-shm"):
        temporary.with_name(temporary.name + suffix).unlink(missing_ok=True)
    temporary.chmod(0o600)
    temporary.replace(target)

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    for old in target_dir.glob("store-????-??-??.db"):
        try:
            date = datetime.strptime(old.stem.removeprefix("store-"), "%Y-%m-%d")
        except ValueError:
            continue
        if date.replace(tzinfo=timezone.utc) < cutoff:
            old.unlink(missing_ok=True)
    return target


if __name__ == "__main__":
    print(create_backup(Path(sys.argv[1] if len(sys.argv) > 1 else "/backup")))

from __future__ import annotations

import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.stability.migrations import migrate


def create_backup(root: Path, notes: str = "") -> dict:
    migrate(root)

    backup_dir = root / "studio_memory" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = backup_dir / f"mind-frontier-{timestamp}.zip"
    database = root / "studio_memory" / "atlas.db"

    include_paths = [
        database,
        root / ".env.example",
        root / "requirements.txt",
        root / "docs",
    ]

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in include_paths:
            if not path.exists():
                continue
            if path.is_file():
                handle.write(path, path.relative_to(root))
            else:
                for child in path.rglob("*"):
                    if child.is_file():
                        handle.write(child, child.relative_to(root))

    with sqlite3.connect(database) as db:
        db.execute(
            """
            INSERT INTO system_backups (
                created_at,
                archive_path,
                database_size_bytes,
                notes
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                str(archive),
                database.stat().st_size if database.exists() else 0,
                notes,
            ),
        )
        db.commit()

    return {
        "ok": True,
        "archive": str(archive),
        "size_bytes": archive.stat().st_size,
    }


def prune_backups(root: Path, keep: int = 10) -> dict:
    backup_dir = root / "studio_memory" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    archives = sorted(
        backup_dir.glob("mind-frontier-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    removed = []
    for archive in archives[max(1, keep):]:
        archive.unlink(missing_ok=True)
        removed.append(str(archive))

    return {"removed": removed, "kept": min(len(archives), max(1, keep))}

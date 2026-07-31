import logging
import sqlite3
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


def backup_db() -> Path | None:
    """Hot-copy the live SQLite file to a second path on the same volume via
    sqlite3's backup API, which is WAL-safe (a plain file copy is not, since
    a concurrent writer could be mid-checkpoint)."""
    if not settings.db_path.is_file():
        return None
    backup_path = settings.myhub_data_dir / "myhub_backup.db"
    src = sqlite3.connect(settings.db_path)
    try:
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return backup_path

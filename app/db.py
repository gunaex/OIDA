from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .config import settings


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


@contextmanager
def transaction():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def migrate() -> None:
    with connect() as db:
        # Phase 1 creates the migration ledger. Apply every later migration once,
        # in filename order, so accepted migrations remain immutable.
        for path in sorted(Path("migrations").glob("*.sql")):
            if path.name != "001_phase1.sql":
                applied = db.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=?", (path.stem,)
                ).fetchone()
                if applied:
                    continue
            db.executescript(path.read_text())
            db.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,?)",
                (path.stem, now()),
            )

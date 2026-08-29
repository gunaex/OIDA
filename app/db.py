from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import re

from .config import settings


def is_postgres() -> bool:
    return getattr(settings, "database_url", "").startswith(("postgresql://", "postgres://"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    if is_postgres():
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("psycopg is required for PostgreSQL") from exc
        return PostgresConnection(psycopg.connect(settings.database_url, row_factory=dict_row))
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


def _postgres_sql(sql: str, named: bool = False) -> str:
    # Application SQL never embeds literal question marks; placeholders are portable here.
    if named:
        return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
    return sql.replace("?", "%s")


class PostgresCursor:
    def __init__(self, cursor): self.cursor = cursor
    def _row(self, row): return PortableRow(row) if row is not None else None
    def fetchone(self): return self._row(self.cursor.fetchone())
    def fetchall(self): return [self._row(x) for x in self.cursor.fetchall()]
    def __iter__(self): return (self._row(x) for x in self.cursor)


class PortableRow:
    """Matches sqlite3.Row's key and positional access behavior."""
    def __init__(self, value):
        self.value = value
        self.names = list(value.keys())
    def __getitem__(self, key):
        if isinstance(key, int): return self.value[self.names[key]]
        return self.value[key]
    def __iter__(self):
        return (self.value[name] for name in self.names)
    def __len__(self): return len(self.names)
    def keys(self): return self.names


class PostgresConnection:
    def __init__(self, connection): self.connection = connection
    def execute(self, sql, parameters=(), *extra):
        if extra: parameters = (parameters, *extra)
        cursor = self.connection.cursor()
        cursor.execute(_postgres_sql(sql, isinstance(parameters, dict)), parameters)
        return PostgresCursor(cursor)
    def executescript(self, script):
        cursor = self.connection.cursor()
        statements = [x.strip() for x in re.sub(r"^PRAGMA[^;]+;", "", script, flags=re.MULTILINE).split(";") if x.strip()]
        for statement in statements: cursor.execute(statement)
    def commit(self): self.connection.commit()
    def rollback(self): self.connection.rollback()
    def close(self): self.connection.close()
    def __enter__(self): return self
    def __exit__(self, kind, value, traceback):
        if kind: self.rollback()
        else: self.commit()
        self.close()


@contextmanager
def transaction():
    db = connect()
    try:
        db.execute("BEGIN" if is_postgres() else "BEGIN IMMEDIATE")
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
            if is_postgres():
                db.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?) ON CONFLICT(version) DO NOTHING", (path.stem, now()))
            else:
                db.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,?)", (path.stem, now()))

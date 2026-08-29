import sqlite3
from types import SimpleNamespace


def test_phase1_database_upgrades_once_to_phase2(tmp_path, monkeypatch):
    from app import db as database

    path = tmp_path / "upgrade.db"
    connection = sqlite3.connect(path)
    connection.executescript(open("migrations/001_phase1.sql").read())
    connection.execute("INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)", ("001_phase1", database.now()))
    connection.commit(); connection.close()

    monkeypatch.setattr(database, "settings", SimpleNamespace(database_path=str(path)))
    database.migrate()
    database.migrate()  # proves ALTER statements are not replayed

    connection = sqlite3.connect(path)
    project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    versions = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    connection.close()
    assert {"next_solution_number", "next_plan_number"}.issubset(project_columns)
    assert {"solution_candidates", "delivery_plans", "delivery_baselines", "ai_run_telemetry"}.issubset(tables)
    assert versions == {"001_phase1", "002_phase2_delivery_design", "003_ai_provider_telemetry"}

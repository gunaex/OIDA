from dataclasses import replace

from app.config import Settings


def test_production_configuration_fails_closed():
    unsafe = Settings(environment="pilot", database_url="sqlite:///./data/oida.db",
                      session_secret="short", bootstrap_password="change-me",
                      cookie_secure=False, allowed_origins=())
    assert set(unsafe.validate_runtime()) == {
        "POSTGRESQL_REQUIRED", "SESSION_SECRET_REQUIRED", "SECURE_BOOTSTRAP_PASSWORD_REQUIRED",
        "SECURE_COOKIE_REQUIRED", "ALLOWED_ORIGINS_REQUIRED",
    }
    safe = replace(unsafe, database_url="postgresql://host/db", session_secret="x" * 48,
                   bootstrap_password="a-secure-bootstrap-password", cookie_secure=True,
                   allowed_origins=("https://oida.example.com",))
    assert safe.validate_runtime() == []


def test_health_and_database_readiness_do_not_call_ai(client):
    health = client.get("/health")
    ready = client.get("/ready")
    assert health.status_code == ready.status_code == 200
    assert health.json()["database"] == "NOT_CHECKED"
    assert ready.json()["database"] == "READY"
    assert "ai_configured" in health.json()
    assert "version" in health.json()


def test_production_origin_guard(client, monkeypatch):
    import app.main as main
    from types import SimpleNamespace
    monkeypatch.setattr(main, "settings", SimpleNamespace(
        production=True, allowed_origins=("https://oida.example.com",),
        login_attempts_per_minute=8, cookie_secure=True,
    ))
    blocked = client.post("/api/auth/login", json={"email":"owner@example.com", "password":"change-me"})
    allowed = client.post("/api/auth/login", headers={"Origin":"https://oida.example.com"},
                          json={"email":"owner@example.com", "password":"change-me"})
    assert blocked.status_code == 403
    assert allowed.status_code == 200


def test_login_failure_rate_limit_and_audit(client):
    import app.main as main
    main._login_attempts.clear()
    responses = [client.post("/api/auth/login", json={"email":"owner@example.com", "password":"wrong"})
                 for _ in range(9)]
    assert all(x.status_code == 401 for x in responses[:8])
    assert responses[8].status_code == 429
    main._login_attempts.clear()

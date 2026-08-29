from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("OIDA_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/oida.db")
    session_secret: str = os.getenv("OIDA_SESSION_SECRET", "local-development-secret-change-me")
    cookie_secure: bool = os.getenv("OIDA_COOKIE_SECURE", "false").lower() == "true"
    bootstrap_email: str = os.getenv("OIDA_BOOTSTRAP_EMAIL", "owner@example.com")
    bootstrap_password: str = os.getenv("OIDA_BOOTSTRAP_PASSWORD", "change-me")
    bootstrap_name: str = os.getenv("OIDA_BOOTSTRAP_NAME", "Project Owner")
    ai_provider: str = os.getenv("AI_PROVIDER", "disabled")
    ai_model: str = os.getenv("AI_MODEL", "gpt-5.5")
    ai_reasoning_effort: str = os.getenv("AI_REASONING_EFFORT", "high")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    execution_freshness_seconds: int = int(os.getenv("EXECUTION_FRESHNESS_SECONDS", "900"))
    document_again_url: str = os.getenv("DOCUMENT_AGAIN_URL", "")
    document_again_api_key: str = os.getenv("DOCUMENT_AGAIN_API_KEY", "")
    document_again_account_id: str = os.getenv("DOCUMENT_AGAIN_ACCOUNT_ID", "")
    document_again_tenant_id: str = os.getenv("DOCUMENT_AGAIN_TENANT_ID", "")
    pm_again_url: str = os.getenv("PM_AGAIN_URL", "")
    pm_again_api_key: str = os.getenv("PM_AGAIN_API_KEY", "")
    integration_timeout_seconds: float = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))
    document_freshness_seconds: int = int(os.getenv("DOCUMENT_FRESHNESS_SECONDS", "900"))
    allowed_origins: tuple[str, ...] = tuple(x.strip() for x in os.getenv("OIDA_ALLOWED_ORIGINS", "").split(",") if x.strip())
    build_version: str = os.getenv("OIDA_BUILD_VERSION", "development")
    login_attempts_per_minute: int = int(os.getenv("OIDA_LOGIN_ATTEMPTS_PER_MINUTE", "8"))

    @property
    def database_path(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Phase 1 supports sqlite:/// DATABASE_URL only")
        return self.database_url[len(prefix):]

    @property
    def production(self) -> bool:
        return self.environment.lower() in {"production", "pilot"}

    def validate_runtime(self) -> list[str]:
        failures = []
        if self.production and not self.database_url.startswith(("postgresql://", "postgres://")):
            failures.append("POSTGRESQL_REQUIRED")
        if self.production and (len(self.session_secret) < 32 or self.session_secret == "local-development-secret-change-me"):
            failures.append("SESSION_SECRET_REQUIRED")
        if self.production and (len(self.bootstrap_password) < 14 or self.bootstrap_password == "change-me"):
            failures.append("SECURE_BOOTSTRAP_PASSWORD_REQUIRED")
        if self.production and not self.cookie_secure: failures.append("SECURE_COOKIE_REQUIRED")
        if self.production and not self.allowed_origins: failures.append("ALLOWED_ORIGINS_REQUIRED")
        return failures


settings = Settings()

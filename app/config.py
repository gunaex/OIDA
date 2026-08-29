from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
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

    @property
    def database_path(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Phase 1 supports sqlite:/// DATABASE_URL only")
        return self.database_url[len(prefix):]


settings = Settings()

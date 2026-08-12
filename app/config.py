from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ari:ari@localhost:5433/ari"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""

    # Day 6 — anomaly detection thresholds, all overridable via env vars.
    loop_threshold: int = 3
    cost_hard_threshold_tokens: int = 5000
    cost_zscore_threshold: float = 2.0
    cost_zscore_min_samples: int = 3


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ari:ari@localhost:5433/ari"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""


settings = Settings()

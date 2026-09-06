"""Application settings. Variable set is owned by `docs/deployment.md` §11."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"

    database_url: str
    redis_url: str

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Benchmark the `evaluation_run` job scores against (`docs/evaluation.md` §2).
    # Unset fails the job rather than silently scoring the synthetic placeholder.
    benchmark_path: str = ""

    session_secret: str
    # Operator password for the admin session (`docs/api-spec.md` §15).
    # Unset means nobody can log in, which locks the API rather than opening it.
    operator_password: str = ""
    # Fernet key for OAuth tokens at rest (`docs/data-model.md` §17).
    credential_encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]

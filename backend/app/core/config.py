from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+pysqlite:///:memory:"
    test_database_url: str = "sqlite+pysqlite:///:memory:"
    secret_key: str = "development-secret"
    upload_dir: str = ".local/uploads"
    export_dir: str = ".local/exports"

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

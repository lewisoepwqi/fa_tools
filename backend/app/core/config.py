from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+pysqlite:///:memory:"
    test_database_url: str = "sqlite+pysqlite:///:memory:"
    secret_key: str = "development-secret"
    upload_dir: str = ".local/uploads"
    export_dir: str = ".local/exports"
    # 允许的前端来源（逗号分隔）。开发默认放行 Vite dev server。
    cors_origins: list[str] = ["http://localhost:5173"]
    # base64 url-safe 32B Fernet key;非 development 缺失则启动报错。开发用固定 key。
    field_encryption_key: str = "ZmFfdG9vbHNfZGV2X2tleV8zMmJ5dGVzX2xvbmdfISE="

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

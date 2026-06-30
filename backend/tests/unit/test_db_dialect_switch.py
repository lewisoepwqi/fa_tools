"""测试：_create_test_engine 跟随 settings.test_database_url 的方言。"""
from app.core.config import get_settings


def test_test_database_url_defaults_sqlite():
    """默认 test_database_url 是 SQLite，本地无 PG 时测试跑 SQLite。"""
    assert get_settings().test_database_url.startswith("sqlite")


def test_engine_dialect_follows_settings():
    """_create_test_engine 跟随 settings.test_database_url 的方言。"""
    from tests.conftest import _create_test_engine

    engine = _create_test_engine()
    assert engine.dialect.name == "sqlite"  # 默认环境
    engine.dispose()

import pytest
from sqlalchemy import text

from app.core.config import get_settings


@pytest.mark.skipif(
    get_settings().test_database_url.startswith("postgresql"),
    reason="PRAGMA foreign_keys 是 SQLite 专属语法；PostgreSQL 原生强制外键，无需 pragma",
)
def test_foreign_keys_pragma_on(client_with_db):
    _, db = client_with_db
    result = db.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1

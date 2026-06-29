from sqlalchemy import text


def test_foreign_keys_pragma_on(client_with_db):
    _, db = client_with_db
    result = db.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1

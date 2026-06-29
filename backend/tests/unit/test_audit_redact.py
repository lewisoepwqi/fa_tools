from app.services.audit_service import redact


def test_redact_password_and_token():
    out = redact({"password_hash": "abc", "access_token": "t", "name": "甲"})
    assert out["password_hash"] == "***"
    assert out["access_token"] == "***"
    assert out["name"] == "甲"


def test_redact_account_masked():
    out = redact({"account_no_encrypted": "6222021234567890"})
    assert out["account_no_encrypted"] == "****7890"


def test_redact_nested():
    out = redact({"inner": {"password": "p", "x": 1}})
    assert out["inner"]["password"] == "***"
    assert out["inner"]["x"] == 1


def test_redact_none():
    assert redact(None) is None

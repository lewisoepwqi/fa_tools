from app.core.config import Settings


def test_security_settings_defaults():
    s = Settings()
    assert s.access_token_ttl_minutes == 480
    assert s.bootstrap_admin_email
    assert s.bootstrap_admin_password
    assert s.field_encryption_key

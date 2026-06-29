from app.core.crypto import decrypt, encrypt, mask_account


def test_encrypt_decrypt_roundtrip():
    cipher = encrypt("6222021234567890")
    assert cipher != "6222021234567890"
    assert decrypt(cipher) == "6222021234567890"


def test_encrypt_is_nondeterministic():
    assert encrypt("123456") != encrypt("123456")  # Fernet 随机 IV


def test_mask_account_keeps_last4():
    assert mask_account("6222021234567890") == "****7890"


def test_mask_account_short_value_all_masked():
    assert mask_account("12") == "****"


def test_mask_account_none():
    assert mask_account(None) is None

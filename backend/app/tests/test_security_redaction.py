import pytest

from app.security import redact_secret, telegram_bot_deeplink, valid_deeplink_payload


def test_redact_secret_does_not_return_full_secret():
    assert redact_secret("sk_test_123456789") == "sk_t...6789"
    assert redact_secret("short") == "***"
    assert redact_secret("") == ""


def test_deeplink_payload_validation():
    assert valid_deeplink_payload("v_aircraft_001")
    assert valid_deeplink_payload("ABC-123_xyz")
    assert not valid_deeplink_payload("../secret")
    assert not valid_deeplink_payload("x" * 65)


def test_telegram_bot_deeplink_validation():
    assert telegram_bot_deeplink("@StorefrontTestBot", "file-11") == "https://t.me/StorefrontTestBot?start=file-11"
    with pytest.raises(ValueError):
        telegram_bot_deeplink("bad host", "file-11")
    with pytest.raises(ValueError):
        telegram_bot_deeplink("StorefrontTestBot", "../secret")

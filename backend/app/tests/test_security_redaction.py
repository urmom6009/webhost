from app.security import redact_secret, valid_deeplink_payload


def test_redact_secret_does_not_return_full_secret():
    assert redact_secret("sk_test_123456789") == "sk_t...6789"
    assert redact_secret("short") == "***"
    assert redact_secret("") == ""


def test_deeplink_payload_validation():
    assert valid_deeplink_payload("v_aircraft_001")
    assert valid_deeplink_payload("ABC-123_xyz")
    assert not valid_deeplink_payload("../secret")
    assert not valid_deeplink_payload("x" * 65)

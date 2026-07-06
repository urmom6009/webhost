import re


DEEPLINK_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def redact_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def valid_deeplink_payload(value: str | None) -> bool:
    if value is None:
        return False
    return bool(DEEPLINK_RE.fullmatch(value))

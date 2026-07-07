import re
from urllib.parse import quote


DEEPLINK_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TELEGRAM_BOT_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


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


def telegram_bot_deeplink(username: str | None, payload: str) -> str:
    normalized = (username or "").strip().lstrip("@")
    if not TELEGRAM_BOT_USERNAME_RE.fullmatch(normalized) or not valid_deeplink_payload(payload):
        raise ValueError("invalid telegram bot link")
    return f"https://t.me/{quote(normalized)}?start={quote(payload)}"

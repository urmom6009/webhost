from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PLACEHOLDER_VALUES = {
    "",
    "replace_me",
    "changeme",
    "change_me",
    "example.com",
    "sk_test_replace_me",
    "whsec_replace_me",
}


def looks_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return normalized in PLACEHOLDER_VALUES or "replace_me" in normalized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    public_base_url: str = Field(..., alias="PUBLIC_BASE_URL")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(..., alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_bot_username: str = Field("BOT_USERNAME", alias="TELEGRAM_BOT_USERNAME")

    stripe_secret_key: str = Field(..., alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(..., alias="STRIPE_WEBHOOK_SECRET")

    database_url: str = Field(..., alias="DATABASE_URL")

    auto_migrate: bool = Field(False, alias="AUTO_MIGRATE")
    app_version: str = Field("dev", alias="APP_VERSION")

    delivery_token_ttl_minutes: int = Field(60, alias="DELIVERY_TOKEN_TTL_MINUTES")
    delivery_token_max_uses: int = Field(3, alias="DELIVERY_TOKEN_MAX_USES")
    download_storage_root: str = Field("/srv/storefront-media/products", alias="DOWNLOAD_STORAGE_ROOT")
    download_public_prefix: str = Field("/download-file", alias="DOWNLOAD_PUBLIC_PREFIX")
    download_url_secret: str = Field("storefront-download-secret", alias="DOWNLOAD_URL_SECRET")
    download_url_ttl_seconds: int = Field(1800, alias="DOWNLOAD_URL_TTL_SECONDS")
    enable_legacy_onedrive_delivery: bool = Field(True, alias="ENABLE_LEGACY_ONEDRIVE_DELIVERY")

    admin_telegram_ids: str = Field("", alias="ADMIN_TELEGRAM_IDS")
    admin_portal_token: str | None = Field(None, alias="ADMIN_PORTAL_TOKEN")
    admin_portal_session_hours: int = Field(12, alias="ADMIN_PORTAL_SESSION_HOURS")
    admin_portal_max_upload_mb: int = Field(5120, alias="ADMIN_PORTAL_MAX_UPLOAD_MB")

    @field_validator(
        "telegram_bot_token",
        "telegram_webhook_secret",
        "stripe_secret_key",
        "stripe_webhook_secret",
        "database_url",
    )
    @classmethod
    def reject_placeholder_secrets(cls, value: str, info):
        if looks_placeholder(value):
            raise ValueError(f"{info.field_name} is missing or uses a placeholder value")
        return value

    @model_validator(mode="after")
    def validate_public_url(self):
        if looks_placeholder(self.public_base_url):
            raise ValueError("PUBLIC_BASE_URL is missing or uses a placeholder value")
        if not self.public_base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("PUBLIC_BASE_URL must be HTTPS outside localhost development")
        return self

    @property
    def telegram_webhook_path(self) -> str:
        return f"/telegram/webhook/{self.telegram_webhook_secret}"

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}{self.telegram_webhook_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AccessGrant, DeliveryToken, File, Product, utcnow


@dataclass(frozen=True)
class DeliveryTarget:
    provider: str
    url: str | None = None
    storage_key: str | None = None
    display_name: str | None = None
    content_type: str | None = None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comparable(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


def safe_storage_key(storage_key: str) -> str:
    key = storage_key.strip().replace("\\", "/")
    parts = [part for part in key.split("/") if part]
    if not parts:
        raise ValueError("storage key cannot be empty")
    if key.startswith("/") or any(part in {".", ".."} for part in parts):
        raise ValueError("storage key must be a relative path without dot segments")
    return "/".join(parts)


def local_file_path(storage_key: str) -> Path:
    settings = get_settings()
    safe_key = safe_storage_key(storage_key)
    root = Path(settings.download_storage_root).resolve()
    path = (root / safe_key).resolve()
    if os.path.commonpath([str(root), str(path)]) != str(root):
        raise ValueError("storage key escapes storage root")
    return path


def sign_download_url(storage_key: str) -> str:
    settings = get_settings()
    safe_key = safe_storage_key(storage_key)
    expires = int((utcnow() + timedelta(seconds=settings.download_url_ttl_seconds)).timestamp())
    prefix = settings.download_public_prefix.rstrip("/")
    quoted_key = "/".join(quote(part, safe="") for part in safe_key.split("/"))
    uri = f"{prefix}/{quoted_key}"
    digest = hashlib.md5(f"{expires}{uri} {settings.download_url_secret}".encode("utf-8")).digest()
    sig = quote(base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="), safe="")
    return f"{uri}?expires={expires}&sig={sig}"


async def create_delivery_token(session: AsyncSession, grant: AccessGrant) -> str:
    settings = get_settings()

    raw_token = secrets.token_urlsafe(32)

    token = DeliveryToken(
        access_grant_id=grant.id,
        token_hash=hash_token(raw_token),
        expires_at=utcnow() + timedelta(minutes=settings.delivery_token_ttl_minutes),
        max_uses=settings.delivery_token_max_uses,
    )

    session.add(token)
    await session.flush()

    return raw_token


async def redeem_delivery_token(session: AsyncSession, raw_token: str) -> DeliveryTarget | None:
    if len(raw_token) < 32:
        return None

    token_hash = hash_token(raw_token)

    result = await session.execute(
        select(DeliveryToken, AccessGrant, Product)
        .join(AccessGrant, DeliveryToken.access_grant_id == AccessGrant.id)
        .join(Product, AccessGrant.product_id == Product.id)
        .where(DeliveryToken.token_hash == token_hash)
    )

    row = result.first()

    if row is None:
        return None

    token, grant, product = row
    now = utcnow()

    if grant.status != "active":
        return None

    if not product.active:
        return None

    if grant.expires_at is not None and comparable(grant.expires_at) < now:
        return None

    if comparable(token.expires_at) < now:
        return None

    if token.used_count >= token.max_uses:
        return None

    file_result = await session.execute(
        select(File)
        .where(File.product_id == product.id)
        .where(File.active.is_(True))
        .where(File.storage_provider == "local_hdd")
        .order_by(File.created_at.desc())
    )
    local_file = file_result.scalars().first()

    if local_file is not None:
        try:
            path = local_file_path(local_file.storage_key)
        except ValueError:
            return None
        if not path.is_file():
            return None
        token.used_count += 1
        await session.flush()
        return DeliveryTarget(
            provider="local_hdd",
            url=sign_download_url(local_file.storage_key),
            storage_key=local_file.storage_key,
            display_name=local_file.display_name,
            content_type=local_file.content_type,
        )

    if get_settings().enable_legacy_onedrive_delivery:
        token.used_count += 1
        await session.flush()
        return DeliveryTarget(provider="static_onedrive", url=product.onedrive_url)

    return None

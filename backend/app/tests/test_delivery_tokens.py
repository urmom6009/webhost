from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import AccessGrant, DeliveryToken, File, Order, Product, User, utcnow
from app.services.delivery import create_delivery_token, hash_token, redeem_delivery_token, safe_storage_key


async def create_owned_product(session):
    user = User(telegram_id=1001, username="buyer", first_name="Buyer")
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        description="test",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add_all([user, product])
    await session.flush()
    order = Order(
        user_id=user.id,
        product_id=product.id,
        status="paid",
        amount_cents=999,
        currency="usd",
    )
    session.add(order)
    await session.flush()
    grant = AccessGrant(user_id=user.id, product_id=product.id, order_id=order.id, status="active")
    session.add(grant)
    await session.flush()
    return user, product, order, grant


@pytest.mark.asyncio
async def test_delivery_links_are_hashed_at_rest(session):
    _, _, _, grant = await create_owned_product(session)
    raw_token = await create_delivery_token(session, grant)
    token = (
        await session.execute(select(DeliveryToken).where(DeliveryToken.token_hash == hash_token(raw_token)))
    ).scalar_one()

    assert token.token_hash != raw_token
    assert len(token.token_hash) == 64


@pytest.mark.asyncio
async def test_delivery_token_expires(session):
    _, _, _, grant = await create_owned_product(session)
    raw_token = await create_delivery_token(session, grant)
    token = (
        await session.execute(select(DeliveryToken).where(DeliveryToken.token_hash == hash_token(raw_token)))
    ).scalar_one()
    token.expires_at = utcnow() - timedelta(minutes=1)
    await session.flush()

    assert await redeem_delivery_token(session, raw_token) is None


@pytest.mark.asyncio
async def test_overused_token_fails(session):
    _, _, _, grant = await create_owned_product(session)
    raw_token = await create_delivery_token(session, grant)
    token = (
        await session.execute(select(DeliveryToken).where(DeliveryToken.token_hash == hash_token(raw_token)))
    ).scalar_one()
    token.max_uses = 1
    await session.flush()

    target = await redeem_delivery_token(session, raw_token)
    assert target is not None
    assert target.url == "https://onedrive.test/file"
    assert await redeem_delivery_token(session, raw_token) is None


@pytest.mark.asyncio
async def test_inactive_product_cannot_be_redeemed(session):
    _, product, _, grant = await create_owned_product(session)
    raw_token = await create_delivery_token(session, grant)
    product.active = False
    await session.flush()

    assert await redeem_delivery_token(session, raw_token) is None


@pytest.mark.asyncio
async def test_local_hdd_file_is_preferred(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("DOWNLOAD_PUBLIC_PREFIX", "/download-file")
    monkeypatch.setenv("DOWNLOAD_URL_SECRET", "storefront-download-secret")
    get_settings.cache_clear()

    _, product, _, grant = await create_owned_product(session)
    local_path = tmp_path / "test-product" / "test-file.zip"
    local_path.parent.mkdir()
    local_path.write_bytes(b"test file")
    session.add(
        File(
            product_id=product.id,
            storage_provider="local_hdd",
            storage_key="test-product/test-file.zip",
            display_name="test-file.zip",
            content_type="application/zip",
            size_bytes=local_path.stat().st_size,
            active=True,
        )
    )
    raw_token = await create_delivery_token(session, grant)
    await session.flush()

    target = await redeem_delivery_token(session, raw_token)

    assert target is not None
    assert target.provider == "local_hdd"
    assert target.url is not None
    assert target.url.startswith("/download-file/test-product/test-file.zip?expires=")
    assert "sig=" in target.url
    get_settings.cache_clear()


def test_safe_storage_key_rejects_path_traversal():
    with pytest.raises(ValueError):
        safe_storage_key("../secret.txt")

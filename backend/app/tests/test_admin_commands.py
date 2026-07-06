import pytest
from sqlalchemy import select

import app.admin as admin
from app.config import get_settings
from app.models import AccessGrant, AuditEvent, DeliveryToken, File, Order, Payment, Product, User
from app.services.delivery import create_delivery_token, redeem_delivery_token


class FakeTelegramUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.username = "admin" if user_id == 9001 else "buyer"
        self.first_name = "Admin" if user_id == 9001 else "Buyer"


class FakeMessage:
    def __init__(self, user_id: int = 9001, text: str | None = None):
        self.from_user = FakeTelegramUser(user_id)
        self.text = text
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


class FakeCommand:
    def __init__(self, args):
        self.args = args


async def create_paid_order(session):
    user = User(telegram_id=3003, username="buyer", first_name="Buyer")
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
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="stripe",
        provider_session_id="cs_test_123",
        provider_payment_id="pi_test_123",
        status="paid",
        amount_minor=999,
        currency="usd",
    )
    grant = AccessGrant(user_id=user.id, product_id=product.id, order_id=order.id, status="active")
    session.add_all([payment, grant])
    await session.commit()
    return user, product, order, grant


@pytest.mark.asyncio
async def test_non_admin_cannot_use_admin_commands(session):
    message = FakeMessage(user_id=3003)

    await admin.product_list(message, session)

    assert "admin access required" in message.answers[0]["text"]
    events = (await session.execute(select(AuditEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].action == "product_list"
    assert events[0].success is False


@pytest.mark.asyncio
async def test_admin_can_create_product_and_audit_event(session):
    message = FakeMessage()

    await admin.product_create(
        message,
        FakeCommand('slug="v_aircraft_001" title="aircraft video 001" price_cents=999 currency="usd" onedrive_url="https://onedrive.test/file"'),
        session,
    )

    product = (await session.execute(select(Product))).scalar_one()
    event = (await session.execute(select(AuditEvent))).scalar_one()
    assert product.slug == "v_aircraft_001"
    assert product.active is True
    assert event.action == "product_created"
    assert "product created" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_admin_can_attach_local_file(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    local_path = tmp_path / "v_aircraft_001" / "original.mp4"
    local_path.parent.mkdir()
    local_path.write_bytes(b"video")
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add(product)
    await session.commit()

    message = FakeMessage()
    await admin.file_attach(
        message,
        FakeCommand('slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4" content_type="video/mp4"'),
        session,
    )

    file = (await session.execute(select(File))).scalar_one()
    assert file.storage_provider == "local_hdd"
    assert file.storage_key == "v_aircraft_001/original.mp4"
    assert file.size_bytes == 5
    assert product.storage_provider == "local_hdd"
    assert "file attached" in message.answers[0]["text"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_can_replace_asset_metadata_and_file(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    local_path = tmp_path / "v_aircraft_001" / "replacement.mp4"
    local_path.parent.mkdir()
    local_path.write_bytes(b"replacement-video")
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add(product)
    await session.flush()
    old_file = File(
        product_id=product.id,
        storage_provider="local_hdd",
        storage_key="v_aircraft_001/old.mp4",
        active=True,
    )
    session.add(old_file)
    await session.commit()

    message = FakeMessage()
    await admin.asset_replace(
        message,
        FakeCommand(
            'slug="v_aircraft_001" title="aircraft video updated" price_cents=1299 '
            'storage_key="v_aircraft_001/replacement.mp4" display_name="Replacement.mp4" content_type="video/mp4"'
        ),
        session,
    )

    files = (await session.execute(select(File).order_by(File.created_at))).scalars().all()
    active_files = [file for file in files if file.active]
    assert product.title == "aircraft video updated"
    assert product.price_cents == 1299
    assert product.storage_provider == "local_hdd"
    assert len(active_files) == 1
    assert active_files[0].storage_key == "v_aircraft_001/replacement.mp4"
    assert active_files[0].display_name == "Replacement.mp4"
    assert "asset updated" in message.answers[0]["text"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_interactive_product_create_attaches_local_file(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    local_path = tmp_path / "test-product" / "test-file.zip"
    local_path.parent.mkdir()
    local_path.write_bytes(b"zip")

    start = FakeMessage()
    await admin.product_create(start, FakeCommand(None), session)
    assert "slug" in start.answers[0]["text"]

    for text in (
        "test_local_001",
        "Test Local File",
        "100",
        "usd",
        "description",
        "test-product/test-file.zip",
        "-",
        "application/zip",
    ):
        await admin.handle_admin_flow(FakeMessage(text=text), session)

    product = (await session.execute(select(Product))).scalar_one()
    file = (await session.execute(select(File))).scalar_one()
    assert product.slug == "test_local_001"
    assert product.storage_provider == "local_hdd"
    assert file.storage_key == "test-product/test-file.zip"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_can_disable_product_and_disabled_product_cannot_be_purchased(session):
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add(product)
    await session.commit()

    message = FakeMessage()
    await admin.product_disable(message, FakeCommand('slug="v_aircraft_001"'), session)

    assert product.active is False
    events = (await session.execute(select(AuditEvent))).scalars().all()
    assert events[0].action == "product_disabled"


@pytest.mark.asyncio
async def test_caption_generation_uses_bot_link(session):
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        preview_caption="preview text",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add(product)
    await session.commit()

    message = FakeMessage()
    await admin.caption(message, FakeCommand('slug="v_aircraft_001"'), session)

    assert "preview text" in message.answers[0]["text"]
    assert "https://t.me/StorefrontTestBot?start=v_aircraft_001" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_admin_can_resend_delivery_without_duplicate_access_grant(session):
    _, _, order, _ = await create_paid_order(session)

    message = FakeMessage()
    await admin.resend_delivery(message, FakeCommand(f'order_id="{order.id}"'), session)

    grants = (await session.execute(select(AccessGrant))).scalars().all()
    tokens = (await session.execute(select(DeliveryToken))).scalars().all()
    assert len(grants) == 1
    assert len(tokens) == 1
    assert "/dl/" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_revoked_grant_cannot_produce_valid_delivery(session):
    user, product, _, grant = await create_paid_order(session)
    raw_token = await create_delivery_token(session, grant)
    await session.commit()

    message = FakeMessage()
    await admin.revoke_access(
        message,
        FakeCommand(f'telegram_id={user.telegram_id} slug="{product.slug}"'),
        session,
    )

    assert grant.status == "revoked"
    assert await redeem_delivery_token(session, raw_token) is None
    assert "revoked grants: 1" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_debug_clear_me_removes_admin_test_buyer_entries(session):
    user = User(telegram_id=9001, username="admin", first_name="Admin")
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add_all([user, product])
    await session.flush()
    order = Order(user_id=user.id, product_id=product.id, status="paid", amount_cents=999, currency="usd")
    session.add(order)
    await session.flush()
    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="stripe",
        provider_session_id="cs_test_admin",
        status="paid",
        amount_minor=999,
        currency="usd",
    )
    grant = AccessGrant(user_id=user.id, product_id=product.id, order_id=order.id, status="active")
    session.add_all([payment, grant])
    await session.flush()
    await create_delivery_token(session, grant)
    await session.commit()

    message = FakeMessage()
    await admin.debug_clear_me(message, FakeCommand("confirm=yes"), session)

    assert (await session.execute(select(User))).scalars().all() == []
    assert (await session.execute(select(Order))).scalars().all() == []
    assert (await session.execute(select(Payment))).scalars().all() == []
    assert (await session.execute(select(AccessGrant))).scalars().all() == []
    assert (await session.execute(select(DeliveryToken))).scalars().all() == []
    assert "cleared your test buyer entries" in message.answers[0]["text"]

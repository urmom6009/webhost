import pytest
from sqlalchemy import select

import app.bot as bot_module
from app.models import AccessGrant, Order, Payment, Product, User


class FakeTelegramUser:
    id = 3003
    username = "buyer"
    first_name = "Buyer"


class FakeMessage:
    from_user = FakeTelegramUser()

    def __init__(self):
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


class FakeCallback:
    from_user = FakeTelegramUser()

    def __init__(self, data):
        self.data = data
        self.message = FakeMessage()
        self.answers = []

    async def answer(self, text=None, show_alert=None):
        self.answers.append({"text": text, "show_alert": show_alert})


class FakeCommand:
    def __init__(self, args):
        self.args = args


@pytest.mark.asyncio
async def test_start_without_payload_creates_user_and_lists_active_assets(session):
    active_product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        description="test",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    disabled_product = Product(
        slug="v_disabled_001",
        title="disabled",
        description="test",
        price_cents=1999,
        currency="usd",
        onedrive_url="https://onedrive.test/disabled",
        active=False,
    )
    session.add_all([active_product, disabled_product])
    await session.commit()

    message = FakeMessage()
    await bot_module.handle_start(message, FakeCommand(None), session)

    users = (await session.execute(select(User))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    assert len(users) == 1
    assert users[0].telegram_id == FakeTelegramUser.id
    assert orders == []
    assert "account: <b>@buyer</b>" in message.answers[0]["text"]
    assert str(users[0].id) not in message.answers[0]["text"]
    assert "choose an asset" in message.answers[0]["text"]

    keyboard = message.answers[0]["reply_markup"]
    assert len(keyboard.inline_keyboard) == 1
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "aircraft video 001 - 9.99 USD"
    assert button.callback_data == f"buy:{active_product.id}"


@pytest.mark.asyncio
async def test_product_deep_link_creates_pending_order(session, monkeypatch):
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        description="test",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add(product)
    await session.commit()

    checkout = type("Checkout", (), {"id": "cs_test_123", "url": "https://checkout.test"})()
    monkeypatch.setattr(bot_module, "create_checkout_session", lambda **kwargs: checkout)

    message = FakeMessage()
    await bot_module.handle_start(message, FakeCommand("v_aircraft_001"), session)

    orders = (await session.execute(select(Order))).scalars().all()
    payments = (await session.execute(select(Payment))).scalars().all()
    assert len(orders) == 1
    assert orders[0].status == "pending"
    assert len(payments) == 1
    assert payments[0].provider_session_id == "cs_test_123"
    assert "pay with stripe" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_buy_callback_creates_pending_order(session, monkeypatch):
    product = Product(
        slug="v_aircraft_001",
        title="aircraft video 001",
        description="test",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )
    session.add(product)
    await session.commit()

    checkout = type("Checkout", (), {"id": "cs_test_456", "url": "https://checkout.test"})()
    monkeypatch.setattr(bot_module, "create_checkout_session", lambda **kwargs: checkout)

    callback = FakeCallback(f"buy:{product.id}")
    await bot_module.handle_buy_callback(callback, session)

    users = (await session.execute(select(User))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    payments = (await session.execute(select(Payment))).scalars().all()
    assert len(users) == 1
    assert len(orders) == 1
    assert orders[0].product_id == product.id
    assert len(payments) == 1
    assert payments[0].provider_session_id == "cs_test_456"
    assert "pay with stripe" in callback.message.answers[0]["text"]
    assert callback.answers == [{"text": None, "show_alert": None}]


@pytest.mark.asyncio
async def test_invalid_product_slug_is_rejected(session):
    message = FakeMessage()
    await bot_module.handle_start(message, FakeCommand("../secret"), session)

    orders = (await session.execute(select(Order))).scalars().all()
    assert orders == []
    assert "couldn't find" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_disabled_product_cannot_be_purchased(session):
    product = Product(
        slug="v_disabled_001",
        title="disabled",
        description="test",
        price_cents=999,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=False,
    )
    session.add(product)
    await session.commit()

    message = FakeMessage()
    await bot_module.handle_start(message, FakeCommand("v_disabled_001"), session)

    orders = (await session.execute(select(Order))).scalars().all()
    assert orders == []
    assert "couldn't find" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_my_purchases_issues_fresh_delivery_link(session):
    user = User(telegram_id=FakeTelegramUser.id, username="buyer", first_name="Buyer")
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
    order = Order(user_id=user.id, product_id=product.id, status="paid", amount_cents=999, currency="usd")
    session.add(order)
    await session.flush()
    grant = AccessGrant(user_id=user.id, product_id=product.id, order_id=order.id, status="active")
    session.add(grant)
    await session.commit()

    message = FakeMessage()
    await bot_module.handle_my_purchases(message, session)

    assert "your purchases" in message.answers[0]["text"]
    assert "/dl/" in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_help_shows_customer_commands_without_internal_buyer_id(session):
    message = FakeMessage()
    await bot_module.handle_help(message, session)

    users = (await session.execute(select(User))).scalars().all()
    assert len(users) == 1
    assert "account: @buyer" in message.answers[0]["text"]
    assert "/catalog" in message.answers[0]["text"]
    assert "/my_purchases" in message.answers[0]["text"]
    assert str(users[0].id) not in message.answers[0]["text"]

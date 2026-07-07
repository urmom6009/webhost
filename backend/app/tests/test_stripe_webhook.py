import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.main as main
from app.models import AccessGrant, DeliveryToken, Order, Payment, Product, User
from app.services.stripe_service import create_checkout_session


class FakeScalarResult:
    def __init__(self, product):
        self.product = product

    def scalar_one_or_none(self):
        return self.product


class FakeSessionContext:
    def __init__(self, product):
        self.product = product

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement):
        return FakeScalarResult(self.product)


async def create_pending_stripe_order(session):
    user = User(telegram_id=2002, username="buyer", first_name="Buyer")
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
        status="pending",
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
        status="pending",
        amount_minor=999,
        currency="usd",
    )
    session.add(payment)
    await session.flush()
    return user, product, order, payment


def test_checkout_session_metadata_includes_order_id(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return type("Checkout", (), {"id": "cs_test_123", "url": "https://checkout.test"})()

    monkeypatch.setattr("stripe.checkout.Session.create", fake_create)
    user = User(id=uuid.uuid4(), telegram_id=2002)
    product = Product(slug="v_aircraft_001", title="aircraft video", price_cents=999, currency="usd", onedrive_url="x")
    product.id = uuid.uuid4()
    order = Order(id=uuid.uuid4(), user_id=user.id, product_id=product.id, amount_cents=999, currency="usd")

    create_checkout_session(order, user, product)

    assert captured["client_reference_id"] == str(order.id)
    assert captured["metadata"]["order_id"] == str(order.id)
    assert captured["metadata"]["telegram_id"] == str(user.telegram_id)
    assert captured["metadata"]["product_slug"] == product.slug


def test_stripe_webhook_invalid_signature_is_rejected(monkeypatch):
    def raise_bad_signature(*args, **kwargs):
        raise main.stripe.error.SignatureVerificationError("bad", "sig")

    monkeypatch.setattr(main.stripe.Webhook, "construct_event", raise_bad_signature)

    with TestClient(main.app) as client:
        response = client.post("/stripe/webhook", data=b"{}", headers={"stripe-signature": "bad"})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_paid_webhook_creates_one_grant_and_one_delivery_token(session):
    user, product, order, payment = await create_pending_stripe_order(session)
    checkout = {
        "id": "cs_test_123",
        "client_reference_id": str(order.id),
        "metadata": {"order_id": str(order.id)},
        "payment_status": "paid",
        "payment_intent": "pi_test_123",
        "amount_total": 999,
        "currency": "usd",
    }

    message = await main.handle_checkout_session_completed(session, checkout)

    grants = (await session.execute(select(AccessGrant))).scalars().all()
    tokens = (await session.execute(select(DeliveryToken))).scalars().all()
    assert message["chat_id"] == user.telegram_id
    assert len(grants) == 1
    assert len(tokens) == 1
    assert grants[0].order_id == order.id
    assert payment.status == "paid"


@pytest.mark.asyncio
async def test_duplicate_paid_webhook_does_not_double_fulfill(session):
    _, _, order, _ = await create_pending_stripe_order(session)
    checkout = {
        "id": "cs_test_123",
        "client_reference_id": str(order.id),
        "metadata": {"order_id": str(order.id)},
        "payment_status": "paid",
        "payment_intent": "pi_test_123",
        "amount_total": 999,
        "currency": "usd",
    }

    await main.handle_checkout_session_completed(session, checkout)
    await main.handle_checkout_session_completed(session, checkout)

    grants = (await session.execute(select(AccessGrant))).scalars().all()
    assert len(grants) == 1


@pytest.mark.asyncio
async def test_wrong_amount_does_not_grant_access(session):
    _, _, order, payment = await create_pending_stripe_order(session)
    checkout = {
        "id": "cs_test_123",
        "client_reference_id": str(order.id),
        "metadata": {"order_id": str(order.id)},
        "payment_status": "paid",
        "payment_intent": "pi_test_123",
        "amount_total": 1,
        "currency": "usd",
    }

    assert await main.handle_checkout_session_completed(session, checkout) is None
    grants = (await session.execute(select(AccessGrant))).scalars().all()
    assert grants == []
    assert payment.status == "amount_mismatch"
    assert order.status == "payment_mismatch"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_product_purchase_redirect_rejects_disabled_product(monkeypatch):
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSessionContext(None))

    with pytest.raises(HTTPException) as exc_info:
        await main.product_purchase_redirect("file-11")

    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_product_purchase_redirects_invalid_deeplink_payload(monkeypatch):
    # ensure DB session is never used for invalid deeplink payloads
    def failing_session():
        raise AssertionError("SessionLocal should not be called for invalid deeplink payload")

    monkeypatch.setattr(main, "SessionLocal", failing_session)
    monkeypatch.setattr(main, "valid_deeplink_payload", lambda payload: False)

    with pytest.raises(HTTPException as exc_info):
        await main.product_purchase_redirect("invalid-slug")

    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_product_purchase_redirect_returns_503_on_bad_bot_username(monkeypatch):
    product = Product(
        slug="file-11",
        title="File 11",
        description="test",
        price_cents=80000,
        currency="usd",
        onedrive_url="https://onedrive.test/file",
        active=True,
    )

    # valid deeplink payload and active product so we reach the telegram state
    def failing_telegram_bot_deeplink(*args, **kwargs):
        raise ValueError("bad bot name")

    monkeypatch.setattr(main, "telegram_bot_deeplink", failing_telegram_bot_deeplink)

    with pytest.raises(HTTPException) as exc_info:
        await main.product_purchase_redirect("file-11")

    assert exc_info.value.status_code == 503

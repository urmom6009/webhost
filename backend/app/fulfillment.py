import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import AccessGrant, Order, Payment, utcnow
from app.services.delivery import create_delivery_token


@dataclass
class FulfillmentResult:
    fulfilled: bool
    delivery_token: str | None
    reason: str | None = None


async def fulfill_paid_order(
    session: AsyncSession,
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    source: str,
) -> FulfillmentResult:
    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.product),
            selectinload(Order.access_grants),
        )
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        return FulfillmentResult(False, None, "order_not_found")

    payment_result = await session.execute(
        select(Payment).where(Payment.id == payment_id).where(Payment.order_id == order.id)
    )
    payment = payment_result.scalar_one_or_none()
    if payment is None:
        return FulfillmentResult(False, None, "payment_not_found")

    if payment.status == "paid" and order.fulfilled_at is not None:
        grant = next((grant for grant in order.access_grants if grant.status == "active"), None)
        if grant is None:
            return FulfillmentResult(False, None, "already_paid_without_active_grant")
        raw_token = await create_delivery_token(session, grant)
        return FulfillmentResult(True, raw_token, "already_fulfilled")

    if payment.amount_minor != order.amount_cents or payment.currency.lower() != order.currency.lower():
        payment.status = "amount_mismatch"
        order.status = "payment_mismatch"
        return FulfillmentResult(False, None, "amount_or_currency_mismatch")

    grant = next((grant for grant in order.access_grants if grant.status == "active"), None)
    if grant is None:
        grant = AccessGrant(
            user_id=order.user_id,
            product_id=order.product_id,
            order_id=order.id,
            status="active",
        )
        session.add(grant)
        await session.flush()

    payment.status = "paid"
    payment.paid_at = payment.paid_at or utcnow()
    order.status = "paid"
    order.paid_at = order.paid_at or utcnow()
    order.fulfilled_at = order.fulfilled_at or utcnow()

    raw_token = await create_delivery_token(session, grant)
    return FulfillmentResult(True, raw_token, source)


async def build_delivery_url(raw_token: str) -> str:
    settings = get_settings()
    return f"{settings.public_base_url.rstrip('/')}/dl/{raw_token}"

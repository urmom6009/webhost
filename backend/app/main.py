import uuid
from contextlib import asynccontextmanager

import stripe
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.bot import bot, configure_command_menu, dp
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.fulfillment import build_delivery_url, fulfill_paid_order
from app.models import Order, Payment, ProviderEvent
from app.portal import router as portal_router
from app.services.delivery import redeem_delivery_token
from app.services.stripe_service import configure_stripe

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    configure_stripe()
    try:
        await configure_command_menu()
    except Exception:
        pass
    yield
    await bot.session.close()


app = FastAPI(
    title="telegram storefront mvp",
    lifespan=lifespan,
)
app.include_router(portal_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
async def version() -> dict[str, str]:
    return {"version": settings.app_version}


@app.get("/ready")
async def ready() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("select 1"))
    return {"status": "ready"}


@app.post(settings.telegram_webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="invalid telegram webhook secret")

    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": bot})

    async with SessionLocal() as session:
        try:
            await dp.feed_update(
                bot,
                update,
                session=session,
            )
        except Exception:
            await session.rollback()
            raise

    return JSONResponse({"ok": True})


@app.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None),
) -> JSONResponse:
    if stripe_signature is None:
        raise HTTPException(status_code=400, detail="missing stripe-signature header")

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid stripe payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="invalid stripe signature")

    async with SessionLocal() as session:
        already_processed = await session.execute(
            select(ProviderEvent)
            .where(ProviderEvent.provider == "stripe")
            .where(ProviderEvent.event_id == event["id"])
        )

        if already_processed.scalar_one_or_none() is not None:
            return JSONResponse({"received": True, "duplicate": True})

        session.add(
            ProviderEvent(
                provider="stripe",
                event_id=event["id"],
                event_type=event["type"],
                payload={
                    "type": event["type"],
                    "object_id": event["data"]["object"].get("id"),
                },
            )
        )

        delivery_message = None
        if event["type"] == "checkout.session.completed":
            checkout_session = event["data"]["object"]
            delivery_message = await handle_checkout_session_completed(session, checkout_session)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return JSONResponse({"received": True, "duplicate": True})

    if delivery_message is not None:
        try:
            await bot.send_message(**delivery_message)
        except Exception:
            return JSONResponse({"received": True, "delivery_message_sent": False})

    return JSONResponse({"received": True})


async def handle_checkout_session_completed(session, checkout_session) -> dict | None:
    metadata = dict(checkout_session.get("metadata") or {})
    order_id_raw = checkout_session.get("client_reference_id") or metadata.get("order_id")

    if not order_id_raw:
        raise HTTPException(
            status_code=400,
            detail="checkout session missing order_id metadata",
        )

    try:
        order_id = uuid.UUID(order_id_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid order_id metadata")

    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.product),
            selectinload(Order.payments),
        )
        .where(Order.id == order_id)
    )

    order = result.scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    if checkout_session.get("payment_status") != "paid":
        return None

    payment = next(
        (
            candidate
            for candidate in order.payments
            if candidate.provider == "stripe"
            and candidate.provider_session_id == checkout_session.get("id")
        ),
        None,
    )

    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")

    payment.provider_payment_id = checkout_session.get("payment_intent")
    payment.raw_amount_minor = checkout_session.get("amount_total")
    payment.raw_currency = checkout_session.get("currency")

    if payment.raw_amount_minor != order.amount_cents or (payment.raw_currency or "").lower() != order.currency.lower():
        payment.status = "amount_mismatch"
        order.status = "payment_mismatch"
        return None

    result = await fulfill_paid_order(session, order.id, payment.id, "stripe")
    if not result.fulfilled or result.delivery_token is None:
        return None

    delivery_url = await build_delivery_url(result.delivery_token)
    return {
        "chat_id": order.user.telegram_id,
        "text": (
            f"payment confirmed for <b>{order.product.title}</b>.\n\n"
            f"here’s your access link:\n{delivery_url}\n\n"
            "keep this link private."
        ),
    }


@app.get("/dl/{raw_token}")
async def delivery(raw_token: str) -> RedirectResponse:
    async with SessionLocal() as session:
        target = await redeem_delivery_token(session, raw_token)
        await session.commit()

    if target is None or target.url is None:
        raise HTTPException(status_code=404, detail="invalid or expired delivery link")

    return RedirectResponse(target.url, status_code=302)


@app.get("/success")
async def success() -> HTMLResponse:
    return HTMLResponse(
        """
        <html>
          <body style="font-family: system-ui; max-width: 640px; margin: 4rem auto;">
            <h1>payment received</h1>
            <p>you can return to telegram. the bot will send the delivery link once the webhook confirms.</p>
          </body>
        </html>
        """
    )


@app.get("/cancel")
async def cancel() -> HTMLResponse:
    return HTMLResponse(
        """
        <html>
          <body style="font-family: system-ui; max-width: 640px; margin: 4rem auto;">
            <h1>payment canceled</h1>
            <p>nothing was charged. go back to telegram if you want to try again.</p>
          </body>
        </html>
        """
    )

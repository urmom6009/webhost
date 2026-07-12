import uuid
import time
from collections import Counter
from contextlib import asynccontextmanager
from html import escape

import stripe
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.bot import bot, configure_command_menu, dp
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.fulfillment import build_delivery_url, fulfill_paid_order
from app.models import AccessGrant, Buyer, Order, Payment, Product, ProviderEvent, utcnow
from app.portal import router as portal_router
from app.security import valid_deeplink_payload
from app.services.delivery import redeem_delivery_token
from app.services.stripe_service import configure_stripe, create_checkout_session

settings = get_settings()
REQUEST_TOTAL: Counter[tuple[str, str, str]] = Counter()
REQUEST_DURATION_SUM: Counter[tuple[str, str, str]] = Counter()


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(portal_router)


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", request.url.path)
    labels = (request.method, route, str(response.status_code))
    REQUEST_TOTAL[labels] += 1
    REQUEST_DURATION_SUM[labels] += time.perf_counter() - started
    return response


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


def metric_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")


@app.get("/metrics")
async def metrics() -> Response:
    db_ready = 0
    try:
        async with SessionLocal() as session:
            await session.execute(text("select 1"))
        db_ready = 1
    except Exception:
        db_ready = 0

    lines = [
        "# HELP hh88trance_app_info Application metadata.",
        "# TYPE hh88trance_app_info gauge",
        f'hh88trance_app_info{{version="{metric_label(settings.app_version)}"}} 1',
        "# HELP hh88trance_db_ready Database readiness status.",
        "# TYPE hh88trance_db_ready gauge",
        f"hh88trance_db_ready {db_ready}",
        "# HELP hh88trance_http_requests_total HTTP requests by method, route, and status.",
        "# TYPE hh88trance_http_requests_total counter",
    ]
    for (method, route, status), count in sorted(REQUEST_TOTAL.items()):
        lines.append(
            'hh88trance_http_requests_total{'
            f'method="{metric_label(method)}",route="{metric_label(route)}",status="{metric_label(status)}"'
            f"}} {count}"
        )
    lines.extend(
        [
            "# HELP hh88trance_http_request_duration_seconds_sum Total HTTP request duration by method, route, and status.",
            "# TYPE hh88trance_http_request_duration_seconds_sum counter",
        ]
    )
    for (method, route, status), total in sorted(REQUEST_DURATION_SUM.items()):
        lines.append(
            'hh88trance_http_request_duration_seconds_sum{'
            f'method="{metric_label(method)}",route="{metric_label(route)}",status="{metric_label(status)}"'
            f"}} {total:.6f}"
        )
    lines.extend(
        [
            "# HELP hh88trance_http_request_duration_seconds_count HTTP request duration sample count by method, route, and status.",
            "# TYPE hh88trance_http_request_duration_seconds_count counter",
        ]
    )
    for (method, route, status), count in sorted(REQUEST_TOTAL.items()):
        lines.append(
            'hh88trance_http_request_duration_seconds_count{'
            f'method="{metric_label(method)}",route="{metric_label(route)}",status="{metric_label(status)}"'
            f"}} {count}"
        )

    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


def public_catalog_product(product: Product) -> dict:
    return {
        "slug": product.slug,
        "title": product.title,
        "description": product.description,
        "preview_caption": product.preview_caption,
        "price_cents": product.price_cents,
        "currency": product.currency,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


@app.get("/catalog")
async def catalog() -> dict:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Product)
            .where(Product.active.is_(True))
            .order_by(Product.created_at.desc())
        )
        products = list(result.scalars().all())

    return {
        "products": [public_catalog_product(product) for product in products],
        "count": len(products),
    }


def checkout_customer_details(checkout_session) -> dict:
    details = checkout_session.get("customer_details") or {}
    if not isinstance(details, dict):
        return {}
    return details


async def upsert_buyer_from_checkout(session, checkout_session, fallback_buyer: Buyer | None = None) -> Buyer:
    details = checkout_customer_details(checkout_session)
    customer_id = checkout_session.get("customer")
    email = details.get("email")
    name = details.get("name")

    buyer = fallback_buyer
    if buyer is None and customer_id:
        result = await session.execute(select(Buyer).where(Buyer.stripe_customer_id == customer_id))
        buyer = result.scalar_one_or_none()
    if buyer is None and email:
        result = await session.execute(select(Buyer).where(Buyer.email == email).order_by(Buyer.first_seen_at.desc()))
        buyer = result.scalars().first()
    if buyer is None:
        buyer = Buyer(first_seen_at=utcnow(), last_seen_at=utcnow())
        session.add(buyer)

    buyer.email = email or buyer.email
    buyer.name = name or buyer.name
    buyer.stripe_customer_id = customer_id or buyer.stripe_customer_id
    buyer.last_seen_at = utcnow()
    await session.flush()
    return buyer


async def resolve_product_from_checkout(session, checkout_session, metadata: dict) -> Product | None:
    product_id_raw = metadata.get("product_id")
    if product_id_raw:
        try:
            product_id = uuid.UUID(product_id_raw)
        except ValueError:
            product_id = None
        if product_id is not None:
            result = await session.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()
            if product is not None:
                return product

    product_slug = metadata.get("product_slug")
    if product_slug:
        result = await session.execute(select(Product).where(Product.slug == product_slug))
        product = result.scalar_one_or_none()
        if product is not None:
            return product

    payment_link_id = checkout_session.get("payment_link")
    if payment_link_id:
        result = await session.execute(select(Product).where(Product.stripe_payment_link_id == payment_link_id))
        return result.scalar_one_or_none()

    return None


async def ensure_order_for_checkout(session, checkout_session, metadata: dict) -> Order:
    order_id_raw = checkout_session.get("client_reference_id") or metadata.get("order_id")
    if order_id_raw:
        try:
            order_id = uuid.UUID(order_id_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid order_id metadata")

        result = await session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.buyer),
                selectinload(Order.product),
                selectinload(Order.payments),
                selectinload(Order.access_grants),
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        if order.buyer_id is not None:
            order.buyer = await upsert_buyer_from_checkout(session, checkout_session, order.buyer)
        return order

    product = await resolve_product_from_checkout(session, checkout_session, metadata)
    if product is None:
        raise HTTPException(status_code=400, detail="checkout session missing order_id or product metadata")

    buyer = await upsert_buyer_from_checkout(session, checkout_session)
    order = Order(
        buyer_id=buyer.id,
        product_id=product.id,
        status="pending",
        amount_cents=product.price_cents,
        currency=product.currency,
    )
    session.add(order)
    await session.flush()

    payment = Payment(
        order_id=order.id,
        buyer_id=buyer.id,
        provider="stripe",
        provider_session_id=checkout_session.get("id"),
        status="pending",
        amount_minor=order.amount_cents,
        currency=order.currency,
    )
    session.add(payment)
    await session.flush()

    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.buyer),
            selectinload(Order.product),
            selectinload(Order.payments),
            selectinload(Order.access_grants),
        )
        .where(Order.id == order.id)
    )
    return result.scalar_one()


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


@app.get("/buy/{product_slug}")
async def product_purchase_redirect(product_slug: str) -> RedirectResponse:
    if not valid_deeplink_payload(product_slug):
        raise HTTPException(status_code=404, detail="product not found")

    async with SessionLocal() as session:
        try:
            result = await session.execute(
                select(Product)
                .where(Product.slug == product_slug)
                .where(Product.active.is_(True))
            )
            product = result.scalar_one_or_none()
            if product is None:
                raise HTTPException(status_code=404, detail="product not found")

            buyer = Buyer(first_seen_at=utcnow(), last_seen_at=utcnow())
            session.add(buyer)
            await session.flush()

            order = Order(
                buyer_id=buyer.id,
                product_id=product.id,
                status="pending",
                amount_cents=product.price_cents,
                currency=product.currency,
            )
            session.add(order)
            await session.flush()

            payment = Payment(
                order_id=order.id,
                buyer_id=buyer.id,
                provider="stripe",
                status="pending",
                amount_minor=order.amount_cents,
                currency=order.currency,
            )
            session.add(payment)
            await session.flush()

            checkout = create_checkout_session(order=order, buyer=buyer, product=product)
            payment.provider_session_id = checkout.id
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise HTTPException(status_code=502, detail="could not create checkout session")

    return RedirectResponse(checkout.url, status_code=303)


async def handle_checkout_session_completed(session, checkout_session) -> dict | None:
    metadata = dict(checkout_session.get("metadata") or {})
    order = await ensure_order_for_checkout(session, checkout_session, metadata)

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
        payment = Payment(
            order_id=order.id,
            user_id=order.user_id,
            buyer_id=order.buyer_id,
            provider="stripe",
            provider_session_id=checkout_session.get("id"),
            status="pending",
            amount_minor=order.amount_cents,
            currency=order.currency,
        )
        session.add(payment)
        await session.flush()

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

    if order.user is None or order.user.telegram_id is None:
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


async def delivery_url_for_checkout_session(session_id: str) -> str | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Payment)
            .options(
                selectinload(Payment.order)
                .selectinload(Order.access_grants)
                .selectinload(AccessGrant.delivery_tokens)
            )
            .where(Payment.provider == "stripe")
            .where(Payment.provider_session_id == session_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None or payment.order.fulfilled_at is None:
            return None
        grant = next((grant for grant in payment.order.access_grants if grant.status == "active"), None)
        if grant is None:
            return None
        from app.services.delivery import create_delivery_token

        raw_token = await create_delivery_token(session, grant)
        await session.commit()
        return await build_delivery_url(raw_token)


@app.get("/success")
async def success(session_id: str | None = None) -> HTMLResponse:
    delivery_link = None
    if session_id:
        delivery_link = await delivery_url_for_checkout_session(session_id)
    if delivery_link:
        body = f"""
            <h1>payment confirmed</h1>
            <p>Your access link is ready.</p>
            <p><a href="{escape(delivery_link)}">Download your content</a></p>
            <p>Keep this link private.</p>
        """
    else:
        body = """
            <h1>payment received</h1>
            <p>Your payment is being confirmed by Stripe. Refresh this page in a moment if the access link is not visible yet.</p>
        """
    return HTMLResponse(
        f"""
        <html>
          <body style="font-family: system-ui; max-width: 640px; margin: 4rem auto;">
            {body}
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

import stripe

from app.config import get_settings
from app.models import Buyer, Order, Product, User


STRIPE_API_VERSION = "2026-02-25.clover"


def configure_stripe() -> None:
    stripe.api_key = get_settings().stripe_secret_key
    stripe.api_version = STRIPE_API_VERSION


def stripe_value(obj, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def product_metadata(product: Product) -> dict[str, str]:
    return {
        "product_id": str(product.id),
        "product_slug": product.slug,
    }


def checkout_metadata(
    order: Order,
    product: Product,
    *,
    user: User | None = None,
    buyer: Buyer | None = None,
) -> dict[str, str]:
    metadata = {
        "order_id": str(order.id),
        "product_id": str(product.id),
        "product_slug": product.slug,
    }
    if user is not None:
        metadata["user_id"] = str(user.id)
        metadata["telegram_id"] = str(user.telegram_id)
    if buyer is not None:
        metadata["buyer_id"] = str(buyer.id)
        if buyer.email:
            metadata["buyer_email"] = buyer.email
    return metadata


def checkout_line_item(product: Product) -> dict:
    if product.stripe_price_id:
        return {"price": product.stripe_price_id, "quantity": 1}
    return {
        "price_data": {
            "currency": product.currency,
            "unit_amount": product.price_cents,
            "product_data": {
                "name": product.title,
                "description": product.description or "full quality, full length video.",
                "metadata": product_metadata(product),
            },
        },
        "quantity": 1,
    }


def create_checkout_session(
    order: Order,
    product: Product,
    *,
    user: User | None = None,
    buyer: Buyer | None = None,
) -> stripe.checkout.Session:
    settings = get_settings()
    configure_stripe()
    metadata = checkout_metadata(order, product, user=user, buyer=buyer)

    session_args = {
        "mode": "payment",
        "client_reference_id": str(order.id),
        "success_url": f"{settings.public_base_url.rstrip('/')}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.public_base_url.rstrip('/')}/cancel",
        "line_items": [checkout_line_item(product)],
        "metadata": metadata,
        "payment_intent_data": {"metadata": metadata},
    }
    if buyer is not None and buyer.stripe_customer_id:
        session_args["customer"] = buyer.stripe_customer_id
    elif buyer is not None:
        session_args["customer_creation"] = "always"

    return stripe.checkout.Session.create(**session_args)


def sync_product_to_stripe(product: Product, *, create_payment_link: bool = True) -> None:
    configure_stripe()
    metadata = product_metadata(product)
    description = product.description or "full quality, full length video."

    if product.stripe_product_id:
        stripe_product = stripe.Product.modify(
            product.stripe_product_id,
            name=product.title,
            description=description,
            active=product.active,
            metadata=metadata,
        )
    else:
        stripe_product = stripe.Product.create(
            name=product.title,
            description=description,
            active=product.active,
            metadata=metadata,
        )
        product.stripe_product_id = stripe_value(stripe_product, "id")

    price_currency = product.currency.lower()
    needs_price = (
        not product.stripe_price_id
        or product.stripe_price_amount_cents != product.price_cents
        or (product.stripe_price_currency or "").lower() != price_currency
    )

    if needs_price:
        stripe_price = stripe.Price.create(
            product=product.stripe_product_id,
            currency=price_currency,
            unit_amount=product.price_cents,
            metadata=metadata,
        )
        product.stripe_price_id = stripe_value(stripe_price, "id")
        product.stripe_price_amount_cents = product.price_cents
        product.stripe_price_currency = price_currency

        if product.stripe_payment_link_id:
            stripe.PaymentLink.modify(product.stripe_payment_link_id, active=False)
            product.stripe_payment_link_id = None
            product.stripe_payment_link_url = None

    if not create_payment_link or not product.stripe_price_id:
        return

    if product.stripe_payment_link_id:
        stripe.PaymentLink.modify(
            product.stripe_payment_link_id,
            active=product.active,
            metadata=metadata,
        )
        return

    payment_link = stripe.PaymentLink.create(
        line_items=[{"price": product.stripe_price_id, "quantity": 1}],
        metadata=metadata,
    )
    product.stripe_payment_link_id = stripe_value(payment_link, "id")
    product.stripe_payment_link_url = stripe_value(payment_link, "url")
    if not product.active:
        stripe.PaymentLink.modify(product.stripe_payment_link_id, active=False)

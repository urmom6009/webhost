import stripe

from app.config import get_settings
from app.models import Order, Product, User


def configure_stripe() -> None:
    stripe.api_key = get_settings().stripe_secret_key


def create_checkout_session(order: Order, user: User, product: Product) -> stripe.checkout.Session:
    settings = get_settings()
    configure_stripe()

    return stripe.checkout.Session.create(
        mode="payment",
        client_reference_id=str(order.id),
        success_url=f"{settings.public_base_url.rstrip('/')}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.public_base_url.rstrip('/')}/cancel",
        line_items=[
            {
                "price_data": {
                    "currency": product.currency,
                    "unit_amount": product.price_cents,
                    "product_data": {
                        "name": product.title,
                        "description": product.description or "full quality, full length video.",
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "order_id": str(order.id),
            "user_id": str(user.id),
            "telegram_id": str(user.telegram_id),
            "product_id": str(product.id),
            "product_slug": product.slug,
        },
    )

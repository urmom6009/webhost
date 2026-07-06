import argparse
import asyncio

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Product


async def main() -> None:
    parser = argparse.ArgumentParser(description="create or update a product")

    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--price-cents", type=int, required=True)
    parser.add_argument("--currency", default="usd")
    parser.add_argument("--onedrive-url", required=True)

    args = parser.parse_args()

    await init_db()

    async with SessionLocal() as session:
        result = await session.execute(
            select(Product).where(Product.slug == args.slug)
        )

        product = result.scalar_one_or_none()

        if product is None:
            product = Product(slug=args.slug)
            session.add(product)

        product.title = args.title
        product.description = args.description
        product.price_cents = args.price_cents
        product.currency = args.currency.lower()
        product.onedrive_url = args.onedrive_url
        product.active = True

        await session.commit()

        print(f"saved product: {product.slug}")


if __name__ == "__main__":
    asyncio.run(main())

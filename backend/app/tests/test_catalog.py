import pytest

from app import main
from app.models import Product, utcnow


class SessionContext:
    def __init__(self, products):
        self.products = products

    async def __aenter__(self):
        return FakeSession(self.products)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, products):
        self.products = products

    async def execute(self, query):
        return FakeResult([product for product in self.products if product.active])


class FakeResult:
    def __init__(self, products):
        self.products = products

    def scalars(self):
        return self

    def all(self):
        return self.products


@pytest.mark.asyncio
async def test_catalog_lists_only_active_public_product_fields(monkeypatch):
    now = utcnow()
    active = Product(
        slug="file-12",
        title="File 12",
        description="Full quality release",
        preview_caption="Live preview copy",
        price_cents=8000,
        currency="usd",
        onedrive_url="https://private.example/active",
        active=True,
        updated_at=now,
    )
    inactive = Product(
        slug="file-hidden",
        title="Hidden File",
        price_cents=8000,
        currency="usd",
        onedrive_url="https://private.example/inactive",
        active=False,
        updated_at=now,
    )

    monkeypatch.setattr(main, "SessionLocal", lambda: SessionContext([active, inactive]))

    response = await main.catalog()

    assert response["count"] == 1
    assert response["products"][0] == {
        "slug": "file-12",
        "title": "File 12",
        "description": "Full quality release",
        "preview_caption": "Live preview copy",
        "price_cents": 8000,
        "currency": "usd",
        "updated_at": now.isoformat(),
    }
    assert "onedrive_url" not in response["products"][0]


@pytest.mark.asyncio
async def test_public_catalog_product_serializes_display_fields():
    now = utcnow()
    product = Product(
        slug="custom-5",
        title="Custom 5",
        description=None,
        preview_caption=None,
        price_cents=20000,
        currency="usd",
        onedrive_url="https://private.example/custom",
        active=True,
        updated_at=now,
    )

    assert main.public_catalog_product(product)["slug"] == "custom-5"
    assert main.public_catalog_product(product)["price_cents"] == 20000
    assert "onedrive_url" not in main.public_catalog_product(product)

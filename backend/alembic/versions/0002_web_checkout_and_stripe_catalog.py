"""web checkout and stripe catalog

Revision ID: 0002_web_checkout_stripe_catalog
Revises: 0001_initial_schema
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_web_checkout_stripe_catalog"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buyers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_buyers_email", "buyers", ["email"])

    op.add_column("products", sa.Column("stripe_product_id", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("stripe_price_id", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("stripe_price_amount_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("stripe_price_currency", sa.String(length=8), nullable=True))
    op.add_column("products", sa.Column("stripe_payment_link_id", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("stripe_payment_link_url", sa.Text(), nullable=True))

    op.add_column("orders", sa.Column("buyer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_orders_buyer_id_buyers", "orders", "buyers", ["buyer_id"], ["id"])
    op.create_index("ix_orders_buyer_id", "orders", ["buyer_id"])
    op.alter_column("orders", "user_id", existing_type=sa.Uuid(), nullable=True)

    op.add_column("payments", sa.Column("buyer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_payments_buyer_id_buyers", "payments", "buyers", ["buyer_id"], ["id"])
    op.create_index("ix_payments_buyer_id", "payments", ["buyer_id"])
    op.alter_column("payments", "user_id", existing_type=sa.Uuid(), nullable=True)

    op.add_column("access_grants", sa.Column("buyer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_access_grants_buyer_id_buyers", "access_grants", "buyers", ["buyer_id"], ["id"])
    op.create_index("ix_access_grants_buyer_id", "access_grants", ["buyer_id"])
    op.create_unique_constraint(
        "uq_grant_buyer_product_order",
        "access_grants",
        ["buyer_id", "product_id", "order_id"],
    )
    op.alter_column("access_grants", "user_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("access_grants", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint("uq_grant_buyer_product_order", "access_grants", type_="unique")
    op.drop_index("ix_access_grants_buyer_id", table_name="access_grants")
    op.drop_constraint("fk_access_grants_buyer_id_buyers", "access_grants", type_="foreignkey")
    op.drop_column("access_grants", "buyer_id")

    op.alter_column("payments", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_payments_buyer_id", table_name="payments")
    op.drop_constraint("fk_payments_buyer_id_buyers", "payments", type_="foreignkey")
    op.drop_column("payments", "buyer_id")

    op.alter_column("orders", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_orders_buyer_id", table_name="orders")
    op.drop_constraint("fk_orders_buyer_id_buyers", "orders", type_="foreignkey")
    op.drop_column("orders", "buyer_id")

    op.drop_column("products", "stripe_payment_link_url")
    op.drop_column("products", "stripe_payment_link_id")
    op.drop_column("products", "stripe_price_currency")
    op.drop_column("products", "stripe_price_amount_cents")
    op.drop_column("products", "stripe_price_id")
    op.drop_column("products", "stripe_product_id")

    op.drop_index("ix_buyers_email", table_name="buyers")
    op.drop_table("buyers")

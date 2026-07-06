import shlex
import uuid
import os
import asyncio
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.fulfillment import build_delivery_url
from app.models import (
    AccessGrant,
    AuditEvent,
    DeliveryToken,
    File,
    Order,
    Payment,
    Product,
    User,
    utcnow,
)
from app.security import valid_deeplink_payload
from app.services.delivery import (
    create_delivery_token,
    local_file_path,
    safe_storage_key,
)

router = Router()
pending_admin_flows: dict[int, dict] = {}


def admin_ids() -> set[int]:
    raw = get_settings().admin_telegram_ids
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return ids


def actor_id(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id


def is_admin(message: Message) -> bool:
    actor = actor_id(message)
    return actor is not None and actor in admin_ids()


async def audit(
    session: AsyncSession,
    message: Message,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    success: bool = True,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_telegram_id=actor_id(message),
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=success,
            reason=reason,
            event_metadata=metadata or {},
        )
    )


async def require_admin(session: AsyncSession, message: Message, action: str) -> bool:
    if is_admin(message):
        return True
    await audit(session, message, action, success=False, reason="admin_denied")
    await session.commit()
    await message.answer("admin access required.")
    return False


def pending_admin(message: Message) -> bool:
    actor = actor_id(message)
    return actor is not None and actor in pending_admin_flows


def start_product_flow(message: Message) -> None:
    actor = actor_id(message)
    if actor is None:
        return
    pending_admin_flows[actor] = {
        "kind": "product_create",
        "step": "slug",
        "data": {},
    }


def parse_args(raw: str | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in shlex.split(raw or ""):
        if "=" not in token:
            raise ValueError(f"expected key=value, got {token!r}")
        key, value = token.split("=", 1)
        key = key.strip().lower().replace("-", "_")
        if not key:
            raise ValueError("empty argument key")
        values[key] = value.strip()
    return values


def require_fields(values: dict[str, str], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not values.get(field)]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "active", "enabled"}


async def find_product(session: AsyncSession, slug: str) -> Product | None:
    result = await session.execute(select(Product).where(Product.slug == slug))
    return result.scalar_one_or_none()


def apply_product_values(product: Product, values: dict[str, str]) -> list[str]:
    changed: list[str] = []
    for field in (
        "title",
        "description",
        "currency",
        "preview_caption",
        "storage_provider",
        "file_id",
        "onedrive_url",
    ):
        if field in values:
            setattr(product, field, values[field])
            changed.append(field)
    if "price_cents" in values:
        product.price_cents = int(values["price_cents"])
        changed.append("price_cents")
    if "active" in values:
        product.active = parse_bool(values["active"])
        changed.append("active")
    if changed:
        product.updated_at = utcnow()
    return changed


async def attach_local_file(
    session: AsyncSession,
    product: Product,
    storage_key: str,
    *,
    display_name: str | None = None,
    content_type: str | None = None,
) -> File:
    # ensure storage_key is normalized
    safe_key = safe_storage_key(storage_key)
    path = local_file_path(safe_key)

    base_dir = Path(get_settings().local_storage_dir)
    try:
        if not path.resolve().is_relative_to(base_dir.resolve()):
            raise ValueError("resolved path outside dir")
    except AttributeError:
        if not str(path.resolve()).startswith(str(base_dir.resolve()) + os.sep):
            raise ValueError("resolved path outside dir")

    try:
        exists = await asynchio.to_thread(path.is_file)
    except Exception as exc:
        raise ValueError(
            f"could not check file existence for storage_key: {safe_key}"
        ) from exc

    if not exists:
        raise ValueError(f"local file not found for storage_key: {safe_key}")

    try:
        stat = await asynchio.to_thread(path.stat)
        size_bytes = stat.st_size
    except Exception as exc:
        raise ValueError(
            f"could not stat local file for storage_key: {safe_key}"
        ) from exc

    # deactivate previous active files with a single UPDATE for efficiency
    await session.execute(
        update(File)
        .where(File.product_id == product.id)
        .where(File.active.is_(True))
        .values(active=False, updated_at=utcnow())
    )

    # create the  new file record
    file = File(
        product_id=product.id,
        storage_provider="local_hdd",
        storage_key=safe_key,
        display_name=display_name or path.name,
        content_type=content_type,
        size_bytes=size_bytes,
        active=True,
    )

    session.add(file)

    # flush so the field can be used in the same session
    await session.flush()
    return file


@router.message(Command("admin_help"))
async def admin_help(message: Message, session: AsyncSession) -> None:
    if not await require_admin(session, message, "admin_help"):
        return
    await audit(session, message, "admin_help")
    await session.commit()
    await message.answer(
        "admin commands:\n"
        "/help\n"
        "/product_create\n"
        '/product_create slug="v_aircraft_001" title="aircraft video 001" price_cents=999 currency="usd" onedrive_url="https://..."\n'
        '/product_update slug="v_aircraft_001" title="new title" price_cents=1299 description="..."\n'
        '/product_disable slug="v_aircraft_001"\n'
        '/product_show slug="v_aircraft_001"\n'
        "/product_list\n"
        '/asset_replace slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4" title="new title" price_cents=1299 display_name="Aircraft Video 001.mp4" content_type="video/mp4"\n'
        '/file_attach slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4" display_name="Aircraft Video 001.mp4" content_type="video/mp4"\n'
        '/file_show slug="v_aircraft_001"\n'
        '/file_disable slug="v_aircraft_001"\n'
        '/caption slug="v_aircraft_001"\n'
        '/order_lookup query="order_id_or_stripe_session_or_telegram_id"\n'
        "/user_lookup telegram_id=123\n"
        "/debug_clear_me confirm=yes\n"
        '/resend_delivery order_id="..."\n'
        '/revoke_access telegram_id=123 slug="v_aircraft_001"\n'
        '/refund_note order_id="..." note="manual refund note"'
    )


@router.message(Command("product_create"))
async def product_create(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "product_create"):
        return
    if not command.args:
        start_product_flow(message)
        await audit(session, message, "product_create_started")
        await session.commit()
        await message.answer("slug?")
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug", "title", "price_cents", "currency"))
        if not valid_deeplink_payload(values["slug"]):
            raise ValueError(
                "slug may only contain letters, numbers, underscore, and dash"
            )
        product = Product(
            slug=values["slug"],
            title=values["title"],
            description=values.get("description"),
            price_cents=int(values["price_cents"]),
            currency=values["currency"].lower(),
            preview_caption=values.get("preview_caption"),
            storage_provider=values.get("storage_provider", "static_onedrive"),
            file_id=values.get("file_id"),
            onedrive_url=values.get(
                "onedrive_url", "https://example.invalid/local-file"
            ),
            active=True,
        )
        session.add(product)
        await session.flush()
        if values.get("storage_key"):
            await attach_local_file(
                session,
                product,
                values["storage_key"],
                display_name=values.get("display_name"),
                content_type=values.get("content_type"),
            )
            product.storage_provider = "local_hdd"
        await audit(
            session,
            message,
            "product_created",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug},
        )
        await session.commit()
        await message.answer(f"product created: {product.slug}")
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "product_created", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not create product: {exc}")


@router.message(Command("cancel"))
async def cancel_admin_flow(message: Message, session: AsyncSession) -> None:
    actor = actor_id(message)
    if actor is not None and actor in pending_admin_flows:
        pending_admin_flows.pop(actor, None)
        await audit(session, message, "admin_flow_cancelled")
        await session.commit()
        await message.answer("cancelled.")


@router.message(F.text, pending_admin)
async def handle_admin_flow(message: Message, session: AsyncSession) -> None:
    if not await require_admin(session, message, "admin_flow"):
        return

    actor = actor_id(message)
    if actor is None:
        return
    flow = pending_admin_flows.get(actor)
    if flow is None:
        return

    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "cancel"}:
        pending_admin_flows.pop(actor, None)
        await audit(session, message, "admin_flow_cancelled")
        await session.commit()
        await message.answer("cancelled.")
        return

    data = flow["data"]
    step = flow["step"]

    try:
        if step == "slug":
            if not valid_deeplink_payload(text):
                raise ValueError(
                    "slug may only contain letters, numbers, underscore, and dash"
                )
            if await find_product(session, text) is not None:
                raise ValueError("product slug already exists")
            data["slug"] = text
            flow["step"] = "title"
            await message.answer("title?")
            return

        if step == "title":
            if not text:
                raise ValueError("title cannot be empty")
            data["title"] = text
            flow["step"] = "price_cents"
            await message.answer("price in cents? example: 999")
            return

        if step == "price_cents":
            data["price_cents"] = int(text)
            if data["price_cents"] < 0:
                raise ValueError("price cannot be negative")
            flow["step"] = "currency"
            await message.answer("currency? send blank or usd")
            return

        if step == "currency":
            data["currency"] = (text or "usd").lower()
            flow["step"] = "description"
            await message.answer("description? send - to skip")
            return

        if step == "description":
            data["description"] = None if text == "-" else text
            flow["step"] = "storage_key"
            await message.answer(
                "local storage key? example: test-product/test-file.zip"
            )
            return

        if step == "storage_key":
            data["storage_key"] = safe_storage_key(text)
            flow["step"] = "display_name"
            await message.answer("download filename? send - to use the file name")
            return

        if step == "display_name":
            data["display_name"] = None if text == "-" else text
            flow["step"] = "content_type"
            await message.answer(
                "content type? example: video/mp4 or application/zip. send - to skip"
            )
            return

        if step == "content_type":
            data["content_type"] = None if text == "-" else text
            product = Product(
                slug=data["slug"],
                title=data["title"],
                description=data.get("description"),
                price_cents=data["price_cents"],
                currency=data["currency"],
                storage_provider="local_hdd",
                onedrive_url="https://example.invalid/local-file",
                active=True,
            )
            session.add(product)
            await session.flush()
            file = await attach_local_file(
                session,
                product,
                data["storage_key"],
                display_name=data.get("display_name"),
                content_type=data.get("content_type"),
            )
            await audit(
                session,
                message,
                "product_created",
                target_type="product",
                target_id=str(product.id),
                metadata={
                    "slug": product.slug,
                    "storage_key": file.storage_key,
                    "interactive": True,
                },
            )
            await session.commit()
            pending_admin_flows.pop(actor, None)
            await message.answer(
                f"product created: {product.slug}\n"
                f"file attached: {file.storage_key}\n"
                f"price: {product.price_cents} {product.currency.upper()}"
            )
            return

        raise ValueError("unknown admin flow step")
    except Exception as exc:
        await session.rollback()
        await message.answer(f"{exc}\ntry again, or send /cancel.")


@router.message(Command("product_update"))
async def product_update(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "product_update"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug",))
        product = await find_product(session, values["slug"])
        if product is None:
            raise ValueError("product not found")
        changed = apply_product_values(product, values)
        await audit(
            session,
            message,
            "product_updated",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug, "changed": changed},
        )
        await session.commit()
        await message.answer(f"product updated: {product.slug}")
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "product_updated", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not update product: {exc}")


@router.message(Command("asset_replace", "asset_update"))
async def asset_replace(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "asset_replace"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug",))
        product = await find_product(session, values["slug"])
        if product is None:
            raise ValueError("product not found")

        changed = apply_product_values(product, values)
        file = None
        if values.get("storage_key"):
            file = await attach_local_file(
                session,
                product,
                values["storage_key"],
                display_name=values.get("display_name"),
                content_type=values.get("content_type"),
            )
            product.storage_provider = "local_hdd"
            product.updated_at = utcnow()
            changed.append("storage_key")

        if not changed:
            raise ValueError("no update fields provided")

        await audit(
            session,
            message,
            "asset_replaced",
            target_type="product",
            target_id=str(product.id),
            metadata={
                "slug": product.slug,
                "changed": changed,
                "storage_key": file.storage_key if file else None,
            },
        )
        await session.commit()

        lines = [
            f"asset updated: {product.slug}",
            f"title: {product.title}",
            f"price: {product.price_cents} {product.currency.upper()}",
            f"active: {product.active}",
        ]
        if file is not None:
            lines.append(f"active file: {file.storage_key}")
        await message.answer("\n".join(lines))
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "asset_replaced", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not update asset: {exc}")


@router.message(Command("product_disable"))
async def product_disable(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "product_disable"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug",))
        product = await find_product(session, values["slug"])
        if product is None:
            raise ValueError("product not found")
        product.active = False
        product.updated_at = utcnow()
        await audit(
            session,
            message,
            "product_disabled",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug},
        )
        await session.commit()
        await message.answer(f"product disabled: {product.slug}")
    except Exception as exc:
        await session.rollback()
        await audit(
            session, message, "product_disabled", success=False, reason=str(exc)
        )
        await session.commit()
        await message.answer(f"could not disable product: {exc}")


@router.message(Command("product_show"))
async def product_show(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "product_show"):
        return
    values = parse_args(command.args)
    require_fields(values, ("slug",))
    product = await find_product(session, values["slug"])
    await audit(
        session,
        message,
        "product_show",
        target_type="product",
        target_id=str(product.id) if product else None,
        success=product is not None,
    )
    await session.commit()
    if product is None:
        await message.answer("product not found.")
        return
    await message.answer(
        f"slug: {product.slug}\n"
        f"title: {product.title}\n"
        f"price: {product.price_cents} {product.currency.upper()}\n"
        f"active: {product.active}\n"
        f"storage: {product.storage_provider}"
    )


@router.message(Command("product_list"))
async def product_list(message: Message, session: AsyncSession) -> None:
    if not await require_admin(session, message, "product_list"):
        return
    result = await session.execute(select(Product).order_by(Product.created_at.desc()))
    products = result.scalars().all()
    await audit(session, message, "product_list")
    await session.commit()
    if not products:
        await message.answer("no products found.")
        return
    await message.answer(
        "\n".join(
            f"{p.slug} | {p.price_cents} {p.currency.upper()} | active={p.active}"
            for p in products
        )
    )


@router.message(Command("file_attach"))
async def file_attach(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "file_attach"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug", "storage_key"))
        product = await find_product(session, values["slug"])
        if product is None:
            raise ValueError("product not found")

        file = await attach_local_file(
            session,
            product,
            values["storage_key"],
            display_name=values.get("display_name"),
            content_type=values.get("content_type"),
        )
        product.storage_provider = "local_hdd"
        await audit(
            session,
            message,
            "file_attached",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug, "storage_key": file.storage_key},
        )
        await session.commit()
        await message.answer(f"file attached: {product.slug} -> {file.storage_key}")
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "file_attached", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not attach file: {exc}")


@router.message(Command("file_show"))
async def file_show(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "file_show"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug",))
        product = await find_product(session, values["slug"])
        if product is None:
            raise ValueError("product not found")
        result = await session.execute(
            select(File)
            .where(File.product_id == product.id)
            .order_by(File.active.desc(), File.created_at.desc())
        )
        files = result.scalars().all()
        await audit(
            session,
            message,
            "file_show",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug},
        )
        await session.commit()
        if not files:
            await message.answer("no files attached.")
            return
        lines = [f"files for {product.slug}:"]
        for file in files:
            lines.append(
                f"{'active' if file.active else 'inactive'} | {file.storage_provider} | {file.storage_key} | {file.size_bytes or 0} bytes"
            )
        await message.answer("\n".join(lines))
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "file_show", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not show files: {exc}")


@router.message(Command("file_disable"))
async def file_disable(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "file_disable"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("slug",))
        product = await find_product(session, values["slug"])
        if product is None:
            raise ValueError("product not found")
        result = await session.execute(
            select(File)
            .where(File.product_id == product.id)
            .where(File.active.is_(True))
        )
        files = result.scalars().all()
        for file in files:
            file.active = False
            file.updated_at = utcnow()
        await audit(
            session,
            message,
            "file_disabled",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug, "disabled_count": len(files)},
        )
        await session.commit()
        await message.answer(f"disabled files: {len(files)}")
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "file_disabled", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not disable files: {exc}")


@router.message(Command("caption"))
async def caption(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "caption"):
        return
    values = parse_args(command.args)
    require_fields(values, ("slug",))
    product = await find_product(session, values["slug"])
    await audit(
        session,
        message,
        "caption_generated",
        target_type="product",
        target_id=str(product.id) if product else None,
        success=product is not None,
    )
    await session.commit()
    if product is None:
        await message.answer("product not found.")
        return
    link = f"https://t.me/{get_settings().telegram_bot_username}?start={product.slug}"
    caption_text = (
        product.preview_caption
        or f"{product.title}\n{product.description or ''}".strip()
    )
    await message.answer(f"{caption_text}\n\n{link}")


@router.message(Command("order_lookup"))
async def order_lookup(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "order_lookup"):
        return
    values = parse_args(command.args)
    query = (
        values.get("query")
        or values.get("order_id")
        or values.get("stripe_session_id")
        or values.get("telegram_id")
    )
    if not query:
        await message.answer("missing query.")
        return
    stmt = select(Order).options(
        selectinload(Order.user),
        selectinload(Order.product),
        selectinload(Order.payments),
    )
    try:
        order_uuid = uuid.UUID(query)
        stmt = stmt.where(Order.id == order_uuid)
    except ValueError:
        if query.isdigit():
            stmt = stmt.join(User).where(User.telegram_id == int(query))
        else:
            stmt = stmt.join(Payment).where(Payment.provider_session_id == query)
    result = await session.execute(stmt.order_by(Order.created_at.desc()))
    orders = result.unique().scalars().all()
    await audit(
        session,
        message,
        "order_lookup",
        success=bool(orders),
        metadata={"query_kind": "safe_lookup"},
    )
    await session.commit()
    if not orders:
        await message.answer("no matching orders.")
        return
    lines = []
    for order in orders[:5]:
        payment = order.payments[0] if order.payments else None
        lines.append(
            f"{order.id} | tg={order.user.telegram_id} | {order.product.slug} | "
            f"order={order.status} | payment={payment.status if payment else 'none'}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("user_lookup"))
async def user_lookup(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "user_lookup"):
        return
    values = parse_args(command.args)
    require_fields(values, ("telegram_id",))
    result = await session.execute(
        select(User).where(User.telegram_id == int(values["telegram_id"]))
    )
    user = result.scalar_one_or_none()
    await audit(
        session,
        message,
        "user_lookup",
        target_type="user",
        target_id=str(user.id) if user else values["telegram_id"],
        success=user is not None,
    )
    await session.commit()
    if user is None:
        await message.answer("user not found.")
        return
    await message.answer(
        f"telegram_id: {user.telegram_id}\nusername: {user.username or ''}\nfirst_name: {user.first_name or ''}"
    )


@router.message(Command("debug_clear_me"))
async def debug_clear_me(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "debug_clear_me"):
        return
    try:
        values = parse_args(command.args)
        if not parse_bool(values.get("confirm", "")):
            await message.answer(
                "this clears your buyer user, orders, payments, grants, and delivery tokens. rerun with /debug_clear_me confirm=yes"
            )
            return

        actor = actor_id(message)
        if actor is None:
            raise ValueError("telegram actor missing")

        result = await session.execute(select(User).where(User.telegram_id == actor))
        user = result.scalar_one_or_none()
        if user is None:
            await audit(
                session,
                message,
                "debug_clear_me",
                target_type="user",
                target_id=str(actor),
                metadata={"deleted": False},
            )
            await session.commit()
            await message.answer("no buyer entries found for your Telegram account.")
            return

        grant_ids = select(AccessGrant.id).where(AccessGrant.user_id == user.id)
        token_result = await session.execute(
            delete(DeliveryToken)
            .where(DeliveryToken.access_grant_id.in_(grant_ids))
            .execution_options(synchronize_session=False)
        )
        grant_result = await session.execute(
            delete(AccessGrant)
            .where(AccessGrant.user_id == user.id)
            .execution_options(synchronize_session=False)
        )
        payment_result = await session.execute(
            delete(Payment)
            .where(Payment.user_id == user.id)
            .execution_options(synchronize_session=False)
        )
        order_result = await session.execute(
            delete(Order)
            .where(Order.user_id == user.id)
            .execution_options(synchronize_session=False)
        )
        await session.delete(user)

        counts = {
            "delivery_tokens": token_result.rowcount or 0,
            "access_grants": grant_result.rowcount or 0,
            "payments": payment_result.rowcount or 0,
            "orders": order_result.rowcount or 0,
            "users": 1,
        }
        await audit(
            session,
            message,
            "debug_clear_me",
            target_type="user",
            target_id=str(actor),
            metadata=counts,
        )
        await session.commit()
        await message.answer(
            "cleared your test buyer entries:\n"
            f"users={counts['users']} orders={counts['orders']} payments={counts['payments']} "
            f"grants={counts['access_grants']} tokens={counts['delivery_tokens']}"
        )
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "debug_clear_me", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not clear your entries: {exc}")


@router.message(Command("resend_delivery"))
async def resend_delivery(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "resend_delivery"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("order_id",))
        order_id = uuid.UUID(values["order_id"])
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
            raise ValueError("order not found")
        grant = next(
            (
                candidate
                for candidate in order.access_grants
                if candidate.status == "active"
            ),
            None,
        )
        if grant is None:
            raise ValueError("active grant not found")
        raw_token = await create_delivery_token(session, grant)
        delivery_url = await build_delivery_url(raw_token)
        await audit(
            session,
            message,
            "delivery_resent",
            target_type="order",
            target_id=str(order.id),
        )
        await session.commit()
        await message.answer(
            f"fresh delivery link for {order.product.slug}:\n{delivery_url}"
        )
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "delivery_resent", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not resend delivery: {exc}")


@router.message(Command("revoke_access"))
async def revoke_access(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "revoke_access"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("telegram_id", "slug"))
        result = await session.execute(
            select(AccessGrant)
            .join(User, AccessGrant.user_id == User.id)
            .join(Product, AccessGrant.product_id == Product.id)
            .where(User.telegram_id == int(values["telegram_id"]))
            .where(Product.slug == values["slug"])
            .where(AccessGrant.status == "active")
        )
        grants = result.scalars().all()
        for grant in grants:
            grant.status = "revoked"
            grant.revoked_at = utcnow()
        await audit(
            session,
            message,
            "access_revoked",
            target_type="product",
            target_id=values["slug"],
            metadata={"grant_count": len(grants)},
        )
        await session.commit()
        await message.answer(f"revoked grants: {len(grants)}")
    except Exception as exc:
        await session.rollback()
        await audit(session, message, "access_revoked", success=False, reason=str(exc))
        await session.commit()
        await message.answer(f"could not revoke access: {exc}")


@router.message(Command("refund_note"))
async def refund_note(
    message: Message, command: CommandObject, session: AsyncSession
) -> None:
    if not await require_admin(session, message, "refund_note"):
        return
    try:
        values = parse_args(command.args)
        require_fields(values, ("order_id", "note"))
        order_id = uuid.UUID(values["order_id"])
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("order not found")
        await audit(
            session,
            message,
            "manual_refund_recorded",
            target_type="order",
            target_id=str(order.id),
            metadata={"note": values["note"][:500]},
        )
        await session.commit()
        await message.answer("refund note recorded.")
    except Exception as exc:
        await session.rollback()
        await audit(
            session, message, "manual_refund_recorded", success=False, reason=str(exc)
        )
        await session.commit()
        await message.answer(f"could not record refund note: {exc}")

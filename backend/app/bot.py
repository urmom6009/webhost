import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User as TelegramUser,
)
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.admin import admin_ids, is_admin, router as admin_router
from app.fulfillment import build_delivery_url
from app.models import AccessGrant, Order, Payment, Product, User, utcnow
from app.security import valid_deeplink_payload
from app.services.delivery import create_delivery_token
from app.services.stripe_service import create_checkout_session

settings = get_settings()

bot = Bot(
    token=settings.telegram_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()
router = Router()
dp.include_router(admin_router)
dp.include_router(router)


DEFAULT_BOT_COMMANDS = [
    BotCommand(command="start", description="Browse available assets"),
    BotCommand(command="catalog", description="Browse available assets"),
    BotCommand(command="my_purchases", description="Get fresh access links"),
    BotCommand(command="help", description="Show available commands"),
]


ADMIN_BOT_COMMANDS = DEFAULT_BOT_COMMANDS + [
    BotCommand(command="admin_help", description="Show admin commands"),
    BotCommand(command="product_list", description="List assets"),
    BotCommand(command="asset_replace", description="Update asset details or file"),
    BotCommand(command="debug_clear_me", description="Clear your test buyer entries"),
]


async def configure_command_menu() -> None:
    await bot.set_my_commands(DEFAULT_BOT_COMMANDS, scope=BotCommandScopeDefault())
    for telegram_id in admin_ids():
        await bot.set_my_commands(ADMIN_BOT_COMMANDS, scope=BotCommandScopeChat(chat_id=telegram_id))


async def upsert_telegram_user(session: AsyncSession, tg_user: TelegramUser | None) -> User:
    if tg_user is None:
        raise ValueError("telegram update has no user")

    result = await session.execute(
        select(User).where(User.telegram_id == tg_user.id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            first_seen_at=utcnow(),
            last_seen_at=utcnow(),
        )
        session.add(user)
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_seen_at = utcnow()

    await session.flush()

    return user


async def upsert_user(session: AsyncSession, message: Message) -> User:
    return await upsert_telegram_user(session, message.from_user)


def public_user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    if user.first_name:
        return user.first_name
    return "your Telegram account"


async def user_has_access(
    session: AsyncSession,
    user: User,
    product: Product,
) -> AccessGrant | None:
    result = await session.execute(
        select(AccessGrant)
        .where(AccessGrant.user_id == user.id)
        .where(AccessGrant.product_id == product.id)
        .where(AccessGrant.status == "active")
        .order_by(AccessGrant.created_at.desc())
    )

    return result.scalar_one_or_none()


def format_price(product: Product) -> str:
    return f"{product.price_cents / 100:.2f} {product.currency.upper()}"


def product_catalog_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{product.title} - {format_price(product)}",
                    callback_data=f"buy:{product.id}",
                )
            ]
            for product in products
        ]
    )


async def send_product_catalog(message: Message, session: AsyncSession, user: User) -> None:
    result = await session.execute(
        select(Product)
        .where(Product.active.is_(True))
        .order_by(Product.created_at.desc())
    )
    products = list(result.scalars().all())

    await session.commit()

    if not products:
        await message.answer("you're linked, but there are no assets available right now.")
        return

    await message.answer(
        (
            "you're linked for current and future purchases.\n"
            f"account: <b>{public_user_label(user)}</b>\n\n"
            "choose an asset:"
        ),
        reply_markup=product_catalog_keyboard(products),
    )


async def handle_catalog_request(message: Message, session: AsyncSession) -> None:
    user = await upsert_user(session, message)
    await send_product_catalog(message, session, user)


async def send_product_checkout(message: Message, session: AsyncSession, user: User, product: Product) -> None:
    existing_grant = await user_has_access(session, user, product)

    if existing_grant is not None:
        raw_token = await create_delivery_token(session, existing_grant)
        await session.commit()

        delivery_url = await build_delivery_url(raw_token)

        await message.answer(
            f"you already own <b>{product.title}</b>. here's a fresh access link:\n{delivery_url}"
        )
        return

    order = Order(
        user_id=user.id,
        product_id=product.id,
        status="pending",
        amount_cents=product.price_cents,
        currency=product.currency,
    )

    session.add(order)
    await session.flush()

    payment = Payment(
        order_id=order.id,
        user_id=user.id,
        provider="stripe",
        status="pending",
        amount_minor=order.amount_cents,
        currency=order.currency,
    )
    session.add(payment)
    await session.flush()

    checkout = create_checkout_session(
        order=order,
        user=user,
        product=product,
    )

    payment.provider_session_id = checkout.id

    await session.commit()

    text = (
        f"<b>{product.title}</b>\n"
        f"{product.description or ''}\n\n"
        f"price: <b>{format_price(product)}</b>\n"
        "pay with stripe below. once payment confirms, i'll send the access link."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="pay with stripe",
                    url=checkout.url,
                )
            ]
        ]
    )

    await message.answer(text, reply_markup=keyboard)


@router.message(CommandStart())
async def handle_start(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    payload = command.args

    if not payload:
        await handle_catalog_request(message, session)
        return

    product_slug = payload.strip()
    if not valid_deeplink_payload(product_slug):
        await message.answer("i couldn't find that product. check the preview post link and try again.")
        return

    result = await session.execute(
        select(Product)
        .where(Product.slug == product_slug)
        .where(Product.active.is_(True))
    )

    product = result.scalar_one_or_none()

    if product is None:
        await message.answer(
            "i couldn't find that product. either the link is wrong or reality is being difficult again."
        )
        return

    user = await upsert_user(session, message)
    await send_product_checkout(message, session, user, product)


@router.message(Command("catalog"))
async def handle_catalog(
    message: Message,
    session: AsyncSession,
) -> None:
    await handle_catalog_request(message, session)


@router.callback_query(F.data.startswith("buy:"))
async def handle_buy_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    if callback.message is None:
        await callback.answer("open the bot and send /start to choose an asset.", show_alert=True)
        return

    product_id_raw = (callback.data or "").removeprefix("buy:")
    try:
        product_id = uuid.UUID(product_id_raw)
    except ValueError:
        await callback.answer("that asset is no longer available.", show_alert=True)
        return

    result = await session.execute(
        select(Product)
        .where(Product.id == product_id)
        .where(Product.active.is_(True))
    )
    product = result.scalar_one_or_none()

    if product is None:
        await callback.answer("that asset is no longer available.", show_alert=True)
        return

    user = await upsert_telegram_user(session, callback.from_user)
    await send_product_checkout(callback.message, session, user, product)
    await callback.answer()


@router.message(Command("my_purchases", "purchases"))
async def handle_my_purchases(
    message: Message,
    session: AsyncSession,
) -> None:
    user = await upsert_user(session, message)
    result = await session.execute(
        select(AccessGrant)
        .options(selectinload(AccessGrant.order).selectinload(Order.product))
        .where(AccessGrant.user_id == user.id)
        .where(AccessGrant.status == "active")
        .order_by(AccessGrant.created_at.desc())
    )
    grants = result.scalars().all()

    if not grants:
        await message.answer("no purchases found for this telegram account.")
        return

    lines = ["your purchases:"]
    for grant in grants:
        raw_token = await create_delivery_token(session, grant)
        delivery_url = await build_delivery_url(raw_token)
        lines.append(f"- <b>{grant.order.product.title}</b>: {delivery_url}")

    await session.commit()
    await message.answer("\n".join(lines))


@router.message(Command("help", "commands"))
async def handle_help(
    message: Message,
    session: AsyncSession,
) -> None:
    user = await upsert_user(session, message)
    await session.commit()

    lines = [
        f"account: {public_user_label(user)}",
        "",
        "customer commands:",
        "/start - browse available assets",
        "/catalog - browse available assets",
        "/my_purchases - get fresh access links",
        "/help - show this list",
    ]
    if is_admin(message):
        lines.extend(
            [
                "",
                "admin commands:",
                "/admin_help - show admin tools",
                "/product_list - list assets",
                "/asset_replace - update an asset or swap its file",
                "/debug_clear_me confirm=yes - clear your test buyer entries",
            ]
        )

    await message.answer("\n".join(lines))

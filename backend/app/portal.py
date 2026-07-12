import hashlib
import hmac
import mimetypes
import os
import re
import secrets
import stat
import time
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request, Response, UploadFile
from fastapi import File as UploadFormFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import attach_local_file
from app.config import get_settings
from app.db import SessionLocal
from app.models import AuditEvent, File as ProductFile, Order, Product, utcnow
from app.security import valid_deeplink_payload
from app.services.delivery import local_file_path, safe_storage_key
from app.services.stripe_service import sync_product_to_stripe

router = APIRouter()

COOKIE_NAME = "storefront_admin_session"
COOKIE_VERSION = "v1"
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def settings():
    return get_settings()


def portal_token() -> str:
    token = settings().admin_portal_token
    if not token:
        raise HTTPException(status_code=503, detail="admin portal token is not configured")
    return token


def sign_session(timestamp: int) -> str:
    payload = f"{COOKIE_VERSION}:{timestamp}"
    return hmac.new(portal_token().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session_cookie() -> str:
    timestamp = int(time.time())
    return f"{COOKIE_VERSION}:{timestamp}:{sign_session(timestamp)}"


def valid_session_cookie(raw_cookie: str | None) -> bool:
    if not raw_cookie:
        return False
    try:
        version, timestamp_raw, provided = raw_cookie.split(":", 2)
        timestamp = int(timestamp_raw)
    except ValueError:
        return False
    if version != COOKIE_VERSION:
        return False
    max_age = max(1, settings().admin_portal_session_hours) * 3600
    if time.time() - timestamp > max_age:
        return False
    expected = sign_session(timestamp)
    return secrets.compare_digest(provided, expected)


def is_admin_request(request: Request) -> bool:
    try:
        return valid_session_cookie(request.cookies.get(COOKIE_NAME))
    except HTTPException:
        return False


def admin_redirect() -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=303)


def set_admin_cookie(response: Response) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_session_cookie(),
        max_age=max(1, settings().admin_portal_session_hours) * 3600,
        httponly=True,
        secure=settings().public_base_url.startswith("https://"),
        samesite="lax",
    )


def clear_admin_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def money(cents: int, currency: str) -> str:
    return f"{Decimal(cents) / Decimal(100):.2f} {currency.upper()}"


def parse_price_cents(value: str) -> int:
    try:
        amount = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("price must be a number")
    if amount < 0:
        raise ValueError("price cannot be negative")
    return int((amount * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def slug_from_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", title.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:64] or "content"


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = SAFE_FILENAME_RE.sub("-", name).strip(".-")
    if not name:
        raise ValueError("upload filename cannot be empty")
    return name[:180]


def title_from_storage_key(storage_key: str) -> str:
    name = Path(storage_key).name
    stem = Path(name).stem or name
    cleaned = re.sub(r"[_-]+", " ", stem).strip()
    return cleaned.title() or "New Video Product"


def content_type_from_storage_key(storage_key: str) -> str:
    guessed, _ = mimetypes.guess_type(storage_key)
    return guessed or ""


def content_type_for(upload: UploadFile | None, fallback: str | None) -> str | None:
    if fallback:
        return fallback.strip()
    if upload is not None and upload.content_type:
        return upload.content_type
    return None


def storage_root() -> Path:
    return Path(settings().download_storage_root).resolve()


def storage_root_label() -> str:
    return str(storage_root())


def resolve_storage_prefix(prefix: str | None) -> tuple[str, Path]:
    root = storage_root()
    if not prefix or not prefix.strip():
        return "", root
    safe_prefix = safe_storage_key(prefix)
    path = (root / safe_prefix).resolve()
    if os.path.commonpath([str(root), str(path)]) != str(root):
        raise ValueError("path escapes storage root")
    return safe_prefix, path


def format_bytes(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def format_mtime(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def breadcrumb_links(prefix: str) -> str:
    crumbs = [f'<a href="/admin/files">{escape(storage_root_label())}</a>']
    current_parts: list[str] = []
    for part in prefix.split("/"):
        if not part:
            continue
        current_parts.append(part)
        joined = "/".join(current_parts)
        crumbs.append(f'<a href="/admin/files?prefix={quote(joined)}">{escape(part)}</a>')
    return '<div class="crumbs">' + '<span>/</span>'.join(crumbs) + "</div>"


def path_is_dir_no_follow(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.stat(follow_symlinks=False).st_mode)
    except OSError:
        return False


async def write_upload(upload: UploadFile, slug: str) -> str:
    filename = safe_filename(upload.filename or "")
    storage_key = safe_storage_key(f"{slug}/{filename}")
    path = local_file_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stem = path.stem[:80]
        suffix = path.suffix[:20]
        storage_key = safe_storage_key(f"{slug}/{stem}-{int(time.time())}{suffix}")
        path = local_file_path(storage_key)

    max_bytes = max(1, settings().admin_portal_max_upload_mb) * 1024 * 1024
    tmp_path = path.with_name(f".{path.name}.{secrets.token_hex(6)}.part")
    written = 0
    try:
        with tmp_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError(f"upload exceeds {settings().admin_portal_max_upload_mb} MB")
                handle.write(chunk)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return storage_key


def form_value(value: str | int | None) -> str:
    return escape("" if value is None else str(value), quote=True)


def textarea_value(value: str | None) -> str:
    return escape(value or "")


def checked_attr(value: bool) -> str:
    return " checked" if value else ""


def page_shell(title: str, body: str, *, authenticated: bool, notice: str | None = None, active_nav: str = "content") -> HTMLResponse:
    escaped_title = escape(title)
    notice_html = f'<div class="notice">{escape(notice)}</div>' if notice else ""
    nav = ""
    if authenticated:
        content_class = "nav-active" if active_nav == "content" else ""
        files_class = "nav-active" if active_nav == "files" else ""
        nav = f"""
          <aside class="sidebar">
            <a class="brand" href="/admin/content">
              <span class="brand-mark">TG</span>
              <span><strong>Store Admin</strong><small>Digital Storefront</small></span>
            </a>
            <nav>
              <a class="{content_class}" href="/admin/content">Content</a>
              <a class="{files_class}" href="/admin/files">Files</a>
              <form action="/admin/logout" method="post"><button type="submit">Log out</button></form>
            </nav>
          </aside>
        """
    layout_class = "layout" if authenticated else "layout guest"
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f9fc;
      --surface: #ffffff;
      --ink: #111827;
      --muted: #667085;
      --line: #d9e0ea;
      --accent: #1769e0;
      --accent-dark: #0f55bd;
      --success: #15803d;
      --danger: #b42318;
      --soft-blue: #eef5ff;
      --soft-green: #edf8f0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); }}
    a {{ color: inherit; text-decoration: none; }}
    .layout {{ display: grid; grid-template-columns: 232px minmax(0, 1fr); min-height: 100vh; }}
    .layout.guest {{ grid-template-columns: minmax(0, 1fr); }}
    .sidebar {{ background: var(--surface); border-right: 1px solid var(--line); padding: 22px 16px; display: flex; flex-direction: column; gap: 28px; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand-mark {{ display: grid; place-items: center; width: 42px; height: 42px; border-radius: 8px; background: var(--accent); color: white; font-weight: 800; font-size: 13px; }}
    .brand small {{ display: block; color: var(--muted); margin-top: 2px; }}
    nav {{ display: grid; gap: 8px; }}
    nav a, nav button {{ width: 100%; border: 0; border-radius: 8px; padding: 11px 12px; background: transparent; color: #1f2937; font: inherit; text-align: left; cursor: pointer; }}
    nav .nav-active, nav a:hover, nav button:hover {{ background: var(--soft-blue); color: var(--accent-dark); }}
    main {{ padding: 28px; }}
    .content-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 24px; align-items: start; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 20px; }}
    h1 {{ margin: 0; font-size: 25px; line-height: 1.2; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 17px; line-height: 1.3; letter-spacing: 0; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .muted {{ color: var(--muted); }}
    .panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04); }}
    .panel-pad {{ padding: 18px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 14px 14px; text-align: left; vertical-align: middle; }}
    th {{ color: #475467; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    td {{ font-size: 14px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .slug {{ color: var(--muted); font-size: 12px; margin-top: 3px; overflow-wrap: anywhere; }}
    .badge {{ display: inline-flex; align-items: center; border-radius: 8px; border: 1px solid var(--line); padding: 4px 8px; font-size: 12px; font-weight: 700; }}
    .badge.active {{ color: var(--success); background: var(--soft-green); border-color: #b7e4c7; }}
    .badge.inactive {{ color: #5b6472; background: #f2f4f7; }}
    .file-ready {{ color: var(--success); font-weight: 700; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .button, button {{ border: 1px solid var(--line); background: var(--surface); color: var(--ink); border-radius: 8px; padding: 10px 12px; font: 700 14px/1.1 inherit; cursor: pointer; }}
    .button.primary, button.primary {{ background: var(--accent); color: white; border-color: var(--accent); }}
    .button.primary:hover, button.primary:hover {{ background: var(--accent-dark); }}
    .button.danger {{ color: var(--danger); }}
    .button[aria-disabled="true"] {{ color: var(--muted); pointer-events: none; background: #f2f4f7; }}
    form {{ margin: 0; }}
    .form-grid {{ display: grid; gap: 14px; }}
    label {{ display: grid; gap: 7px; font-size: 13px; font-weight: 700; color: #344054; }}
    input, textarea, select {{ width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px 11px; font: 14px/1.35 inherit; background: white; color: var(--ink); }}
    textarea {{ min-height: 86px; resize: vertical; }}
    .two {{ display: grid; grid-template-columns: 1fr 132px; gap: 12px; }}
    .check-row {{ display: flex; align-items: center; gap: 10px; font-weight: 700; color: #344054; }}
    .check-row input {{ width: auto; }}
    .help {{ color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .notice {{ background: #ecfdf3; border: 1px solid #abefc6; color: #067647; border-radius: 8px; padding: 11px 13px; margin-bottom: 16px; font-weight: 700; }}
    .error {{ background: #fef3f2; border: 1px solid #fecdca; color: var(--danger); }}
    .tile-preview {{ display: grid; grid-template-columns: 72px 1fr; gap: 13px; align-items: center; border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfdff; }}
    .thumb {{ display: grid; place-items: center; width: 72px; height: 72px; border-radius: 8px; background: #111827; color: white; font-weight: 800; text-align: center; font-size: 12px; }}
    .preview-card {{ display: grid; gap: 14px; }}
    .preview-hero {{ display: grid; grid-template-columns: 96px 1fr; gap: 16px; align-items: center; border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fbfdff; }}
    .preview-thumb {{ display: grid; place-items: center; width: 96px; height: 96px; border-radius: 8px; background: #111827; color: white; font-weight: 900; text-align: center; }}
    .preview-meta {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .split-actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .file-toolbar {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin: 12px 0 16px; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: #fbfdff; }}
    .crumbs {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-weight: 800; overflow-wrap: anywhere; }}
    .crumbs span {{ color: var(--muted); font-weight: 700; }}
    .crumbs a {{ color: var(--accent-dark); }}
    .file-list {{ display: grid; gap: 8px; }}
    .file-row {{ display: grid; grid-template-columns: 26px minmax(0, 1fr) auto; gap: 12px; align-items: center; border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--surface); }}
    .file-row.folder {{ background: #fbfdff; }}
    .file-icon {{ display: grid; place-items: center; width: 26px; height: 26px; border-radius: 6px; background: var(--soft-blue); color: var(--accent-dark); font-size: 14px; font-weight: 900; }}
    .file-row.blocked .file-icon {{ background: #fef3f2; color: var(--danger); }}
    .file-main {{ min-width: 0; }}
    .file-name {{ font-weight: 800; overflow-wrap: anywhere; }}
    .file-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 4px; color: var(--muted); font-size: 12px; }}
    code {{ background: #f2f4f7; border: 1px solid var(--line); border-radius: 6px; padding: 2px 5px; }}
    .login {{ max-width: 440px; margin: 10vh auto; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; border-right: 0; border-bottom: 1px solid var(--line); }}
      .content-grid {{ grid-template-columns: 1fr; }}
      main {{ padding: 18px; }}
      .two {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="{layout_class}">
    {nav}
    <main>
      {notice_html}
      {body}
    </main>
  </div>
</body>
</html>"""
    )


def login_page(error: str | None = None) -> HTMLResponse:
    err = f'<div class="notice error">{escape(error)}</div>' if error else ""
    body = f"""
      <section class="login panel panel-pad">
        <h1>Store Admin</h1>
        <p>Connect to the server portal to publish Telegram catalog products and manage delivery files.</p>
        {err}
        <form class="form-grid" action="/admin/login" method="post">
          <label>Admin token
            <input name="token" type="password" autocomplete="current-password" required autofocus>
          </label>
          <button class="primary" type="submit">Connect</button>
        </form>
      </section>
    """
    return page_shell("Store Admin Login", body, authenticated=False)


async def product_rows(session: AsyncSession):
    products = (
        await session.execute(select(Product).order_by(Product.created_at.desc()))
    ).scalars().all()
    files = (
        await session.execute(
            select(ProductFile)
            .where(ProductFile.active.is_(True))
            .order_by(ProductFile.created_at.desc())
        )
    ).scalars().all()
    active_files: dict[str, ProductFile] = {}
    for file in files:
        active_files.setdefault(str(file.product_id), file)
    order_counts = dict(
        (
            await session.execute(
                select(Order.product_id, func.count(Order.id)).group_by(Order.product_id)
            )
        ).all()
    )
    return products, active_files, order_counts


async def active_file_for_product(session: AsyncSession, product_id: uuid.UUID) -> ProductFile | None:
    result = await session.execute(
        select(ProductFile)
        .where(ProductFile.product_id == product_id)
        .where(ProductFile.active.is_(True))
        .order_by(ProductFile.created_at.desc())
    )
    return result.scalars().first()


def product_table(products: list[Product], active_files: dict[str, ProductFile], order_counts: dict) -> str:
    if not products:
        return '<div class="panel panel-pad"><h2>No content yet</h2><p>Upload a file and save a product to publish your first Telegram catalog item.</p></div>'
    rows = []
    for product in products:
        file = active_files.get(str(product.id))
        file_label = "Ready" if file else "No active file"
        file_class = "file-ready" if file else "muted"
        created = product.created_at.strftime("%Y-%m-%d") if isinstance(product.created_at, datetime) else ""
        buy_link = f"{settings().public_base_url.rstrip('/')}/buy/{quote(product.slug)}"
        stripe_link = product.stripe_payment_link_url or ""
        toggle_label = "Disable" if product.active else "Enable"
        can_buy = product.active and file is not None
        rows.append(
            f"""
            <tr>
              <td><strong>{escape(product.title)}</strong><div class="slug">{escape(product.slug)}</div></td>
              <td><span class="badge {'active' if product.active else 'inactive'}">{'Active' if product.active else 'Inactive'}</span></td>
              <td>{escape(money(product.price_cents, product.currency))}</td>
              <td><span class="{file_class}">{file_label}</span><div class="slug">{escape(file.storage_key if file else '')}</div></td>
              <td>{int(order_counts.get(product.id, 0))}</td>
              <td>{escape(created)}</td>
              <td>
                <div class="actions">
                  <a class="button" href="{escape(buy_link)}" target="_blank" rel="noreferrer" {'aria-disabled="true"' if not can_buy else ""}>Buy link</a>
                  {f'<a class="button" href="{escape(stripe_link)}" target="_blank" rel="noreferrer">Stripe link</a>' if stripe_link else ''}
                  <a class="button" href="/admin/content/{product.id}">Preview / edit</a>
                  <form action="/admin/content/{product.id}/toggle" method="post"><button type="submit">{toggle_label}</button></form>
                </div>
              </td>
            </tr>
            """
        )
    return f"""
      <section class="panel table-wrap">
        <table>
          <thead><tr><th>Product</th><th>Status</th><th>Price</th><th>File</th><th>Orders</th><th>Added</th><th>Actions</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </section>
    """


def product_form(
    *,
    action: str = "/admin/content",
    product: Product | None = None,
    active_file: ProductFile | None = None,
    storage_key: str = "",
    title: str = "",
    content_type: str = "",
    active_default: bool = True,
    submit_label: str = "Save Product",
) -> str:
    is_edit = product is not None
    clean_storage_key = storage_key or ("" if is_edit else (active_file.storage_key if active_file else ""))
    clean_title = product.title if product else title
    clean_slug = product.slug if product else ""
    clean_price = f"{Decimal(product.price_cents) / Decimal(100):.2f}" if product else ""
    clean_currency = product.currency if product else "usd"
    clean_description = product.description if product else ""
    clean_caption = product.preview_caption if product else ""
    clean_display_name = active_file.display_name if active_file else ""
    clean_content_type = content_type or (active_file.content_type if active_file else "")
    active_checked = product.active if product else active_default
    heading = "Edit Product" if is_edit else "Upload / Add New Content"
    help_text = (
        "Review the preview, then enable Active in catalog when the product is ready to sell."
        if is_edit
        else "Leave Active unchecked to save a draft and preview it before it appears in the public catalog."
    )
    storage_help = (
        f"Currently attached: {escape(active_file.storage_key)}"
        if active_file
        else "Use this when the file already exists under the delivery storage root."
    )
    return f"""
      <section class="panel panel-pad">
        <h2>{escape(heading)}</h2>
        <form class="form-grid" action="{escape(action)}" method="post" enctype="multipart/form-data">
          <label>Title
            <input name="title" value="{form_value(clean_title)}" placeholder="Video Editing LUT Pack" required>
          </label>
          <label>Slug
            <input name="slug" value="{form_value(clean_slug)}" placeholder="video-editing-lut-pack">
            <span class="help">Leave blank to generate from the title. Use letters, numbers, dashes, or underscores.</span>
          </label>
          <div class="two">
            <label>Price
              <input name="price" value="{form_value(clean_price)}" inputmode="decimal" placeholder="15.00" required>
            </label>
            <label>Currency
              <input name="currency" value="{form_value(clean_currency)}" maxlength="8" required>
            </label>
          </div>
          <label>Upload file
            <input name="upload" type="file">
            <span class="help">Uploads into the server storage root and makes it the active delivery file.</span>
          </label>
          <label>Or attach existing server file
            <input name="storage_key" value="{form_value(clean_storage_key)}" placeholder="my-product/original.mp4">
            <span class="help">{storage_help}</span>
          </label>
          <label>Download filename
            <input name="display_name" value="{form_value(clean_display_name)}" placeholder="Video Editing LUT Pack.mp4">
          </label>
          <label>Content type
            <input name="content_type" value="{form_value(clean_content_type)}" placeholder="video/mp4">
          </label>
          <label>Description
            <textarea name="description" placeholder="Short buyer-facing description.">{textarea_value(clean_description)}</textarea>
          </label>
          <label>Preview caption
            <textarea name="preview_caption" placeholder="Caption text for Telegram preview posts.">{textarea_value(clean_caption)}</textarea>
          </label>
          <label class="check-row"><input type="checkbox" name="active" value="yes"{checked_attr(active_checked)}> Active in catalog</label>
          <p class="help">Saving creates or updates the matching Stripe Product, Price, and Payment Link. Price changes create a new Stripe Price.</p>
          <div class="tile-preview">
            <div class="thumb">NEW<br>TILE</div>
            <div>
              <strong>{escape(clean_title or "Generated catalog item")}</strong>
              <div class="slug">{escape(help_text)}</div>
            </div>
          </div>
          <button class="primary" type="submit">{escape(submit_label)}</button>
        </form>
      </section>
    """


def product_preview(product: Product, active_file: ProductFile | None) -> str:
    buy_link = f"{settings().public_base_url.rstrip('/')}/buy/{quote(product.slug)}"
    stripe_link = product.stripe_payment_link_url or ""
    file_label = active_file.storage_key if active_file else "No active delivery file"
    can_buy = product.active and active_file is not None
    return f"""
      <section class="panel panel-pad preview-card">
        <div class="preview-hero">
          <div class="preview-thumb">VIDEO<br>FILE</div>
          <div>
            <h2>{escape(product.title)}</h2>
            <p>{escape(product.description or "No description set.")}</p>
            <div class="preview-meta">
              <span class="badge {'active' if product.active else 'inactive'}">{'Live in catalog' if product.active else 'Draft preview'}</span>
              <span class="badge">{escape(money(product.price_cents, product.currency))}</span>
              <span class="badge">{escape(product.slug)}</span>
            </div>
          </div>
        </div>
        <div>
          <strong>Delivery file</strong>
          <div class="slug">{escape(file_label)}</div>
        </div>
        <div>
          <strong>Telegram preview caption</strong>
          <p>{escape(product.preview_caption or "No preview caption set.")}</p>
        </div>
        <div class="split-actions">
          <a class="button" href="{escape(buy_link)}" target="_blank" rel="noreferrer" {'aria-disabled="true"' if not can_buy else ""}>Test buy link</a>
          {f'<a class="button" href="{escape(stripe_link)}" target="_blank" rel="noreferrer">Stripe payment link</a>' if stripe_link else ''}
          <a class="button" href="/admin/files">Attach another server file</a>
        </div>
      </section>
    """


def file_browser(prefix: str, current_path: Path) -> str:
    root = storage_root()
    if not root.exists():
        return f"""
          <section class="panel panel-pad">
            <h2>Server Files</h2>
            <p>The storage root does not exist yet: <code>{escape(storage_root_label())}</code></p>
          </section>
        """
    if not current_path.exists():
        return f"""
          <section class="panel panel-pad">
            <h2>Server Files</h2>
            <p>Path not found under storage root: <code>{escape(prefix)}</code></p>
            <a class="button" href="/admin/files">Back to root</a>
          </section>
        """
    if not current_path.is_dir():
        return f"""
          <section class="panel panel-pad">
            <h2>Server Files</h2>
            <p>This path is a file, not a folder: <code>{escape(prefix)}</code></p>
            <a class="button" href="/admin/files">Back to root</a>
          </section>
        """

    rows = []
    if prefix:
        parent = "/".join(prefix.split("/")[:-1])
        rows.append(
            f"""
            <div class="file-row folder">
              <div class="file-icon">..</div>
              <div class="file-main">
                <a class="file-name" href="/admin/files?prefix={quote(parent)}">../</a>
                <div class="file-meta"><span>Parent folder</span></div>
              </div>
            </div>
            """
        )

    children = sorted(current_path.iterdir(), key=lambda item: (not path_is_dir_no_follow(item), item.name.lower()))
    visible_children = children[:500]
    for child in visible_children:
        child_prefix = f"{prefix}/{child.name}" if prefix else child.name
        try:
            child_stat = child.stat(follow_symlinks=False)
        except OSError as exc:
            rows.append(
                f"""
                <div class="file-row blocked">
                  <div class="file-icon">!</div>
                  <div class="file-main">
                    <div class="file-name">{escape(child.name)}</div>
                    <div class="file-meta"><span>Cannot read metadata</span><span>{escape(str(exc))}</span></div>
                  </div>
                </div>
                """
            )
            continue
        if stat.S_ISLNK(child_stat.st_mode):
            rows.append(
                f"""
                <div class="file-row blocked">
                  <div class="file-icon">!</div>
                  <div class="file-main">
                    <div class="file-name">{escape(child.name)}</div>
                    <div class="file-meta"><span>Symlink blocked</span><span>Not browsable from the admin portal</span></div>
                  </div>
                </div>
                """
            )
            continue
        if stat.S_ISDIR(child_stat.st_mode):
            rows.append(
                f"""
                <div class="file-row folder">
                  <div class="file-icon">/</div>
                  <div class="file-main">
                    <a class="file-name" href="/admin/files?prefix={quote(child_prefix)}">{escape(child.name)}/</a>
                    <div class="file-meta"><span>Folder</span><span>Modified {escape(format_mtime(child_stat.st_mtime))}</span></div>
                  </div>
                </div>
                """
            )
            continue
        rows.append(
            f"""
            <div class="file-row">
              <div class="file-icon">F</div>
              <div class="file-main">
                <div class="file-name">{escape(child.name)}</div>
                <div class="slug">Storage key: <code>{escape(child_prefix)}</code></div>
                <div class="file-meta"><span>Modified {escape(format_mtime(child_stat.st_mtime))}</span></div>
              </div>
              <div class="actions">
                <span class="muted">{escape(format_bytes(child_stat.st_size))}</span>
                <a class="button" href="/admin/content/new?storage_key={quote(child_prefix)}">Create product</a>
              </div>
            </div>
            """
        )

    extra = ""
    if len(children) > len(visible_children):
        extra = f'<p class="muted">Showing first {len(visible_children)} of {len(children)} entries in this folder.</p>'

    return f"""
      <section class="panel panel-pad">
        <h2>Server Files</h2>
        <p>Browsing is locked to <code>{escape(storage_root_label())}</code>. Use a file's storage key in the content form to attach existing server content.</p>
        <div class="file-toolbar">
          <div>
            <div class="help">Current folder</div>
            {breadcrumb_links(prefix)}
          </div>
          <div class="help">Storage keys are always relative to this mounted root.</div>
        </div>
        <div class="file-list">
          {''.join(rows) if rows else '<p class="muted">This folder is empty.</p>'}
        </div>
        {extra}
      </section>
    """


async def create_audit(
    session: AsyncSession,
    action: str,
    *,
    success: bool = True,
    target_type: str | None = None,
    target_id: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_telegram_id=None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=success,
            reason=reason,
            event_metadata=metadata or {},
        )
    )


async def save_product_from_form(
    session: AsyncSession,
    *,
    title: str,
    slug: str,
    price: str,
    currency: str,
    description: str | None,
    preview_caption: str | None,
    active: str | None,
    upload: UploadFile | None,
    storage_key: str | None,
    display_name: str | None,
    content_type: str | None,
    product: Product | None = None,
) -> Product:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("title is required")
    clean_slug = (slug or slug_from_title(clean_title)).strip()
    if not valid_deeplink_payload(clean_slug):
        raise ValueError("slug may only contain letters, numbers, underscore, and dash")
    existing = (await session.execute(select(Product).where(Product.slug == clean_slug))).scalar_one_or_none()
    if existing is not None and (product is None or existing.id != product.id):
        raise ValueError("product slug already exists")

    if product is None:
        product = Product(
            slug=clean_slug,
            title=clean_title,
            description=(description or "").strip() or None,
            price_cents=parse_price_cents(price),
            currency=currency.strip().lower() or "usd",
            preview_caption=(preview_caption or "").strip() or None,
            storage_provider="static_onedrive",
            onedrive_url="https://example.invalid/local-file",
            active=active == "yes",
        )
        session.add(product)
        await session.flush()
        action = "portal_product_created"
    else:
        product.slug = clean_slug
        product.title = clean_title
        product.description = (description or "").strip() or None
        product.price_cents = parse_price_cents(price)
        product.currency = currency.strip().lower() or "usd"
        product.preview_caption = (preview_caption or "").strip() or None
        product.active = active == "yes"
        product.updated_at = utcnow()
        action = "portal_product_updated"

    attached_key = None
    upload_has_file = upload is not None and bool(upload.filename)
    if upload_has_file:
        attached_key = await write_upload(upload, product.slug)
    elif storage_key:
        attached_key = safe_storage_key(storage_key)
    elif product.active and await active_file_for_product(session, product.id) is None:
        raise ValueError("active products need an uploaded file or existing storage key")

    if attached_key:
        file = await attach_local_file(
            session,
            product,
            attached_key,
            display_name=(display_name or "").strip() or None,
            content_type=content_type_for(upload, content_type),
        )
        product.storage_provider = "local_hdd"
        product.updated_at = utcnow()
        await create_audit(
            session,
            action,
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug, "storage_key": file.storage_key},
        )
    else:
        await create_audit(
            session,
            action,
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug, "storage_key": None},
        )

    sync_product_to_stripe(product)
    product.updated_at = utcnow()

    return product


@router.get("/", include_in_schema=False)
async def root_admin_redirect() -> RedirectResponse:
    return RedirectResponse("/admin", status_code=303)


@router.get("/admin", include_in_schema=False)
async def admin_root(request: Request) -> RedirectResponse:
    if not is_admin_request(request):
        return admin_redirect()
    return RedirectResponse("/admin/content", status_code=303)


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request) -> Response:
    if is_admin_request(request):
        return RedirectResponse("/admin/content", status_code=303)
    if not settings().admin_portal_token:
        return login_page("ADMIN_PORTAL_TOKEN is not configured on the server.")
    return login_page()


@router.post("/admin/login")
async def admin_login_post(token: Annotated[str, Form(...)]) -> Response:
    if not settings().admin_portal_token:
        return login_page("ADMIN_PORTAL_TOKEN is not configured on the server.")
    if not secrets.compare_digest(token, portal_token()):
        return login_page("That token did not match.")
    response = RedirectResponse("/admin/content", status_code=303)
    set_admin_cookie(response)
    return response


@router.post("/admin/logout")
async def admin_logout() -> RedirectResponse:
    response = RedirectResponse("/admin/login", status_code=303)
    clear_admin_cookie(response)
    return response


@router.get("/admin/content", response_class=HTMLResponse)
async def admin_content(request: Request, notice: str | None = None) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    async with SessionLocal() as session:
        products, active_files, order_counts = await product_rows(session)
    body = f"""
      <div class="topbar">
        <div>
          <h1>Content</h1>
          <p>Upload files and publish products to the Telegram catalog from one place.</p>
        </div>
        <a class="button" href="/admin/files">Browse Files</a>
      </div>
      <div class="content-grid">
        {product_table(products, active_files, order_counts)}
        {product_form(active_default=False)}
      </div>
    """
    return page_shell("Store Admin Content", body, authenticated=True, notice=notice)


@router.get("/admin/content/new", response_class=HTMLResponse)
async def admin_content_new(
    request: Request,
    storage_key: str | None = None,
    notice: str | None = None,
) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    safe_key = ""
    title = ""
    content_type = ""
    if storage_key:
        try:
            safe_key = safe_storage_key(storage_key)
            path = local_file_path(safe_key)
            if not path.is_file():
                raise ValueError("selected storage key is not a file")
            title = title_from_storage_key(safe_key)
            content_type = content_type_from_storage_key(safe_key)
        except Exception as exc:
            return await admin_content(request, notice=f"Could not use selected file: {exc}")
    body = f"""
      <div class="topbar">
        <div>
          <h1>New Product</h1>
          <p>Create a draft from a server file, preview it, then publish when the product is ready.</p>
        </div>
        <a class="button" href="/admin/files">Browse Files</a>
      </div>
      <div class="content-grid">
        {product_form(storage_key=safe_key, title=title, content_type=content_type, active_default=False)}
        <section class="panel panel-pad preview-card">
          <h2>Draft preview</h2>
          <p>The saved product remains hidden until Active in catalog is checked. This lets you verify title, price, delivery file, and checkout wiring before buyers can purchase it.</p>
          <div class="preview-hero">
            <div class="preview-thumb">VIDEO<br>FILE</div>
            <div>
              <strong>{escape(title or "Selected video product")}</strong>
              <div class="slug">{escape(safe_key or "Choose a file from the explorer or upload one here.")}</div>
            </div>
          </div>
        </section>
      </div>
    """
    return page_shell("New Product", body, authenticated=True, notice=notice)


@router.get("/admin/files", response_class=HTMLResponse)
async def admin_files(request: Request, prefix: str | None = None, notice: str | None = None) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    try:
        safe_prefix, current_path = resolve_storage_prefix(prefix)
        browser = file_browser(safe_prefix, current_path)
    except Exception as exc:
        browser = f"""
          <section class="panel panel-pad">
            <h2>Server Files</h2>
            <p class="notice error">Could not browse files: {escape(str(exc))}</p>
            <a class="button" href="/admin/files">Back to root</a>
          </section>
        """
    body = f"""
      <div class="topbar">
        <div>
          <h1>Files</h1>
          <p>Visually browse uploaded and server-side content under the delivery storage root.</p>
        </div>
        <a class="button" href="/admin/content">Add Content</a>
      </div>
      {browser}
    """
    return page_shell("Server Files", body, authenticated=True, notice=notice, active_nav="files")


@router.post("/admin/content")
async def admin_content_create(
    request: Request,
    title: Annotated[str, Form(...)],
    price: Annotated[str, Form(...)],
    currency: Annotated[str, Form(...)],
    slug: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    preview_caption: Annotated[str, Form()] = "",
    active: Annotated[str | None, Form()] = None,
    storage_key: Annotated[str, Form()] = "",
    display_name: Annotated[str, Form()] = "",
    content_type: Annotated[str, Form()] = "",
    upload: Annotated[UploadFile | None, UploadFormFile()] = None,
) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    async with SessionLocal() as session:
        try:
            product = await save_product_from_form(
                session,
                title=title,
                slug=slug,
                price=price,
                currency=currency,
                description=description,
                preview_caption=preview_caption,
                active=active,
                upload=upload,
                storage_key=storage_key,
                display_name=display_name,
                content_type=content_type,
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await create_audit(session, "portal_product_created", success=False, reason=str(exc))
            await session.commit()
            return await admin_content(request, notice=f"Could not save product: {exc}")
    return RedirectResponse(f"/admin/content?notice=Saved+{quote(product.slug)}", status_code=303)


@router.get("/admin/content/{product_id}", response_class=HTMLResponse)
async def admin_content_edit(request: Request, product_id: str, notice: str | None = None) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    try:
        product_uuid = uuid.UUID(product_id)
    except ValueError:
        return await admin_content(request, notice="Product not found.")
    async with SessionLocal() as session:
        product = await session.get(Product, product_uuid)
        if product is None:
            return await admin_content(request, notice="Product not found.")
        active_file = await active_file_for_product(session, product.id)
        body = f"""
          <div class="topbar">
            <div>
              <h1>Preview / Edit</h1>
              <p>Review the exact product state before making it live in the public catalog.</p>
            </div>
            <a class="button" href="/admin/content">All Content</a>
          </div>
          <div class="content-grid">
            {product_form(action=f"/admin/content/{product.id}", product=product, active_file=active_file, submit_label="Save Changes")}
            {product_preview(product, active_file)}
          </div>
        """
    return page_shell("Preview Product", body, authenticated=True, notice=notice)


@router.post("/admin/content/{product_id}")
async def admin_content_update(
    request: Request,
    product_id: str,
    title: Annotated[str, Form(...)],
    price: Annotated[str, Form(...)],
    currency: Annotated[str, Form(...)],
    slug: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    preview_caption: Annotated[str, Form()] = "",
    active: Annotated[str | None, Form()] = None,
    storage_key: Annotated[str, Form()] = "",
    display_name: Annotated[str, Form()] = "",
    content_type: Annotated[str, Form()] = "",
    upload: Annotated[UploadFile | None, UploadFormFile()] = None,
) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    try:
        product_uuid = uuid.UUID(product_id)
    except ValueError:
        return await admin_content(request, notice="Product not found.")
    async with SessionLocal() as session:
        product = await session.get(Product, product_uuid)
        if product is None:
            return await admin_content(request, notice="Product not found.")
        try:
            saved = await save_product_from_form(
                session,
                title=title,
                slug=slug,
                price=price,
                currency=currency,
                description=description,
                preview_caption=preview_caption,
                active=active,
                upload=upload,
                storage_key=storage_key,
                display_name=display_name,
                content_type=content_type,
                product=product,
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await create_audit(session, "portal_product_updated", success=False, target_type="product", target_id=product_id, reason=str(exc))
            await session.commit()
            return await admin_content_edit(request, product_id, notice=f"Could not save product: {exc}")
    return RedirectResponse(f"/admin/content/{saved.id}?notice=Saved+{quote(saved.slug)}", status_code=303)


@router.post("/admin/content/{product_id}/toggle")
async def admin_content_toggle(request: Request, product_id: str) -> Response:
    if not is_admin_request(request):
        return admin_redirect()
    async with SessionLocal() as session:
        try:
            product_uuid = uuid.UUID(product_id)
        except ValueError:
            return await admin_content(request, notice="Product not found.")
        product = await session.get(Product, product_uuid)
        if product is None:
            return await admin_content(request, notice="Product not found.")
        product.active = not product.active
        product.updated_at = utcnow()
        sync_product_to_stripe(product)
        await create_audit(
            session,
            "portal_product_toggled",
            target_type="product",
            target_id=str(product.id),
            metadata={"slug": product.slug, "active": product.active},
        )
        await session.commit()
    return RedirectResponse("/admin/content?notice=Product+visibility+updated", status_code=303)

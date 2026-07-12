import io

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from app import portal
from app.config import get_settings
from app.main import app
from app.models import AuditEvent, File, Product


@pytest.mark.asyncio
async def test_admin_session_cookie_round_trips(monkeypatch):
    monkeypatch.setenv("ADMIN_PORTAL_TOKEN", "portal-test-token")
    get_settings.cache_clear()

    cookie = portal.make_session_cookie()

    assert portal.valid_session_cookie(cookie) is True
    assert portal.valid_session_cookie(cookie + "tampered") is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_portal_create_product_uploads_file_and_attaches_it(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(portal, "sync_product_to_stripe", lambda product: None)
    get_settings.cache_clear()
    upload = UploadFile(file=io.BytesIO(b"zip-bytes"), filename="../Video Pack.zip")

    product = await portal.save_product_from_form(
        session,
        title="Video Pack",
        slug="",
        price="15.00",
        currency="usd",
        description="Downloadable video pack",
        preview_caption="Preview copy",
        active="yes",
        upload=upload,
        storage_key="",
        display_name="Video Pack.zip",
        content_type="application/zip",
    )
    await session.commit()

    product = (await session.execute(select(Product))).scalar_one()
    file = (await session.execute(select(File))).scalar_one()
    event = (await session.execute(select(AuditEvent))).scalar_one()

    assert product.slug == "video-pack"
    assert product.active is True
    assert product.storage_provider == "local_hdd"
    assert file.product_id == product.id
    assert file.storage_key == "video-pack/Video-Pack.zip"
    assert file.display_name == "Video Pack.zip"
    assert (tmp_path / file.storage_key).read_bytes() == b"zip-bytes"
    assert event.action == "portal_product_created"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_portal_creates_draft_product_from_existing_file(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(portal, "sync_product_to_stripe", lambda product: None)
    get_settings.cache_clear()
    source = tmp_path / "clips" / "alpha-video.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")

    product = await portal.save_product_from_form(
        session,
        title="Alpha Video",
        slug="alpha-video",
        price="20.00",
        currency="usd",
        description="Draft product",
        preview_caption="Preview before launch",
        active=None,
        upload=None,
        storage_key="clips/alpha-video.mp4",
        display_name="Alpha Video.mp4",
        content_type="video/mp4",
    )
    await session.commit()

    file = (await session.execute(select(File))).scalar_one()

    assert product.active is False
    assert product.storage_provider == "local_hdd"
    assert file.storage_key == "clips/alpha-video.mp4"
    assert file.content_type == "video/mp4"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_portal_updates_product_and_can_publish_existing_file(session, tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setattr(portal, "sync_product_to_stripe", lambda product: None)
    get_settings.cache_clear()
    source = tmp_path / "clips" / "beta-video.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")

    product = await portal.save_product_from_form(
        session,
        title="Beta Video",
        slug="beta-video",
        price="20.00",
        currency="usd",
        description="Draft product",
        preview_caption="Draft caption",
        active=None,
        upload=None,
        storage_key="clips/beta-video.mp4",
        display_name="Beta Video.mp4",
        content_type="video/mp4",
    )
    await session.flush()

    updated = await portal.save_product_from_form(
        session,
        title="Beta Video Live",
        slug="beta-video",
        price="25.00",
        currency="usd",
        description="Live product",
        preview_caption="Live caption",
        active="yes",
        upload=None,
        storage_key="",
        display_name="",
        content_type="",
        product=product,
    )
    await session.commit()

    files = (await session.execute(select(File))).scalars().all()
    event_actions = (await session.execute(select(AuditEvent.action))).scalars().all()

    assert updated.active is True
    assert updated.title == "Beta Video Live"
    assert updated.price_cents == 2500
    assert len(files) == 1
    assert "portal_product_updated" in event_actions
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_portal_rejects_active_product_without_file(session):
    with pytest.raises(ValueError, match="active products need"):
        await portal.save_product_from_form(
            session,
            title="No File",
            slug="no-file",
            price="5.00",
            currency="usd",
            description="",
            preview_caption="",
            active="yes",
            upload=None,
            storage_key="",
            display_name="",
            content_type="",
        )


def test_public_store_route_is_not_registered():
    assert "/store" not in {route.path for route in app.routes if hasattr(route, "path")}


def test_file_browser_lists_storage_keys_and_blocks_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    nested = tmp_path / "pack" / "video.mp4"
    nested.parent.mkdir()
    nested.write_bytes(b"video")

    prefix, path = portal.resolve_storage_prefix("pack")
    html = portal.file_browser(prefix, path)

    assert prefix == "pack"
    assert "Storage key:" in html
    assert "pack/video.mp4" in html
    assert "/admin/content/new?storage_key=pack/video.mp4" in html
    with pytest.raises(ValueError):
        portal.resolve_storage_prefix("../etc")
    get_settings.cache_clear()


def test_file_form_prefills_selected_video_without_making_it_live():
    html = portal.product_form(
        storage_key="pack/video.mp4",
        title=portal.title_from_storage_key("pack/video.mp4"),
        content_type=portal.content_type_from_storage_key("pack/video.mp4"),
        active_default=False,
    )

    assert 'value="pack/video.mp4"' in html
    assert 'value="Video"' in html
    assert 'value="video/mp4"' in html
    assert 'name="active" value="yes" checked' not in html


def test_file_browser_blocks_symlinks_without_following_them(tmp_path, monkeypatch):
    root = tmp_path / "media"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "private.txt").write_text("outside root")
    (root / "escape").symlink_to(outside, target_is_directory=True)

    monkeypatch.setenv("DOWNLOAD_STORAGE_ROOT", str(root))
    get_settings.cache_clear()

    prefix, path = portal.resolve_storage_prefix(None)
    html = portal.file_browser(prefix, path)

    assert "Symlink blocked" in html
    assert "private.txt" not in html
    with pytest.raises(ValueError):
        portal.resolve_storage_prefix("escape")
    get_settings.cache_clear()

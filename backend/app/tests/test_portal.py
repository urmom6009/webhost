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
    with pytest.raises(ValueError):
        portal.resolve_storage_prefix("../etc")
    get_settings.cache_clear()

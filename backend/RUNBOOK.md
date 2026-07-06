# Runbook

## Deploy

```bash
sudo -iu storebot
cd /srv/storebot/app
docker compose build
docker compose up -d
docker compose exec app alembic upgrade head
scripts/set_webhook.sh
curl -fsS "$PUBLIC_BASE_URL/ready"
```

## Backup

```bash
BACKUP_DIR=/srv/storebot/backups scripts/backup_db.sh
```

Backups contain Telegram identifiers and payment references. Keep them mode `600` and outside the repository.

## Restore

Restoring overwrites or merges into the current database depending on dump contents. Stop the app before restoring unless this is a tested disaster-recovery drill.

```bash
docker compose stop app
scripts/restore_db.sh /srv/storebot/backups/store_YYYY-MM-DD_HH-MM-SS.sql.gz
docker compose start app
docker compose exec app alembic upgrade head
curl -fsS "$PUBLIC_BASE_URL/ready"
```

## Stripe Test

1. Send a Telegram deep link for an active product.
2. Complete Stripe test checkout.
3. Confirm the Stripe webhook returns 200.
4. Confirm `orders.status=paid`, one `access_grants` row exists, and one delivery token was created.
5. Redeem the delivery URL once and verify redirect.

## Admin Smoke Test

```text
/help
/catalog
/admin_help
/product_list
/caption slug="v_aircraft_001"
/order_lookup query="TELEGRAM_ID_OR_ORDER_ID"
```

Only Telegram IDs in `ADMIN_TELEGRAM_IDS` should receive admin output. Denied admin attempts should create failed `audit_events` rows.

## Admin Portal Smoke Test

Open:

```text
https://api.hh88trance.com/admin
```

Use the `ADMIN_PORTAL_TOKEN` from the server `.env` to connect. The portal should redirect to `/admin/content` and show the content list plus the upload form.

For browser uploads, the app container must have write access to `DOWNLOAD_STORAGE_ROOT`. The downloads container can remain read-only.

Open `/admin/files` after logging in to browse the delivery storage root visually and copy relative storage keys for existing server-side files.

Quick checks:

```bash
curl -fsS "$PUBLIC_BASE_URL/ready"
curl -fsS "$PUBLIC_BASE_URL/admin/login" >/dev/null
docker exec storefront-app sh -lc 'test -w /srv/storefront-media/products'
```

Saving an active product with an upload or existing storage key makes the product visible in Telegram `/catalog`.

## Asset Replacement

Copy the replacement file under `DOWNLOAD_STORAGE_ROOT`, then swap the active asset file and optional product details in one command:

```text
/asset_replace slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4" title="new title" price_cents=1299 display_name="Aircraft Video 001.mp4" content_type="video/mp4"
```

This deactivates the previously active local file for the product and makes the new file active. Use `/file_show slug="v_aircraft_001"` to verify the active storage key.

For repeat checkout testing as an admin, clear only your own buyer rows with:

```text
/debug_clear_me confirm=yes
```

## Video Storage Direction

Phase 1 redirects to static OneDrive URLs only after a delivery token is validated. For production full-length videos, move files into S3-compatible object storage and have the app mint short-lived signed URLs during delivery-token redemption.

Recommended path:

```text
Cloudflare R2 private bucket -> signed URL with 10-30 minute TTL -> app returns 302 redirect
```

This keeps the home server from proxying large video traffic, avoids permanent public links, and makes revocation practical.

## Rollback

Use the previous image tag when available. Database rollback depends on migration reversibility; inspect the migration before downgrade. If restoring from backup, treat it as destructive and preserve the current database first.

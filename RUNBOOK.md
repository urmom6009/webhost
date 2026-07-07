# Runbook

## Compose Runtime

This repository is now designed to run as a self-contained Docker Compose stack. The public entrypoint is the `web` container; it serves the React site and proxies backend paths to internal services.

Default local bindings:

- Site and API entrypoint: `http://127.0.0.1:8080`
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`

Keep those binds on localhost when Caddy, Cloudflare Tunnel, Tailscale, or another edge proxy publishes the service.

## First Deploy

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` and replace every `change_this...` value. At minimum, set:

```text
PUBLIC_BASE_URL
POSTGRES_PASSWORD
TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_USERNAME
TELEGRAM_WEBHOOK_SECRET
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
DOWNLOAD_URL_SECRET
ADMIN_PORTAL_TOKEN
GRAFANA_ADMIN_PASSWORD
```

Then build and start:

```bash
docker compose build
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:${WEB_HTTP_PORT:-8080}/ready
curl -fsS http://127.0.0.1:${WEB_HTTP_PORT:-8080}/metrics | head
```

The `migrate` service runs `alembic upgrade head` before the API starts. Do not enable `AUTO_MIGRATE` in production.

## Telegram Webhook

After the stack is healthy and `PUBLIC_BASE_URL` points to the Compose web entrypoint:

```bash
backend/scripts/set_webhook.sh
```

The public edge must route these paths to the Compose `web` entrypoint:

```text
/
/buy/*
/telegram/*
/stripe/*
/dl/*
/download-file/*
/admin*
/health
/ready
/metrics
```

## Observability

Prometheus scrapes:

- `api:8000/metrics`
- `postgres-exporter:9187`
- Prometheus itself

Grafana is provisioned with Prometheus as the default datasource. Open Grafana locally at:

```text
http://127.0.0.1:3000
```

Use `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` from `.env`.

Useful checks:

```bash
curl -fsS http://127.0.0.1:${WEB_HTTP_PORT:-8080}/health
curl -fsS http://127.0.0.1:${WEB_HTTP_PORT:-8080}/ready
curl -fsS http://127.0.0.1:${PROMETHEUS_PORT:-9090}/-/ready
docker compose logs --tail=100 api
docker compose logs --tail=100 web
docker compose logs --tail=100 prometheus
```

## Backup

```bash
BACKUP_DIR=/srv/storebot/backups backend/scripts/backup_db.sh
```

Backups contain Telegram identifiers and payment references. Keep them mode `600` and outside the repository.

## Restore

Restoring overwrites or merges into the current database depending on dump contents. Stop write traffic before restoring unless this is a tested disaster-recovery drill.

```bash
docker compose stop api
backend/scripts/restore_db.sh /srv/storebot/backups/store_YYYY-MM-DD_HH-MM-SS.sql.gz
docker compose up -d migrate api
curl -fsS http://127.0.0.1:${WEB_HTTP_PORT:-8080}/ready
```

## Stripe Test

1. Open a website purchase link such as `https://YOUR_DOMAIN/buy/file-11` and confirm it redirects to the Telegram bot for the matching active product.
2. Send a Telegram deep link for the same active product.
3. Complete Stripe test checkout.
4. Confirm the Stripe webhook returns 200.
5. Confirm `orders.status=paid`, one `access_grants` row exists, and one delivery token was created.
6. Redeem the delivery URL once and verify redirect.

Website purchase buttons must not create orders directly. They should only hit the backend `/buy/<slug>` redirect, and the bot should remain responsible for creating the Stripe Checkout Session after a Telegram account is linked.

## Admin Smoke Test

```text
/help
/catalog
/admin_help
/product_list
/caption slug="file-11"
/order_lookup query="TELEGRAM_ID_OR_ORDER_ID"
```

Only Telegram IDs in `ADMIN_TELEGRAM_IDS` should receive admin output. Denied admin attempts should create failed `audit_events` rows.

## Admin Portal Smoke Test

Open:

```text
https://YOUR_DOMAIN/admin
```

Use the `ADMIN_PORTAL_TOKEN` from `.env` to connect. The portal should redirect to `/admin/content` and show the content list plus the upload form.

For browser uploads, the `api` container must have write access to the `storefront_media` volume. The `downloads` container remains read-only.

Quick check:

```bash
docker compose exec api sh -lc 'test -w /srv/storefront-media/products'
```

Saving an active product with an upload or existing storage key makes the product visible in Telegram `/catalog`.

## Asset Replacement

Copy the replacement file under `DOWNLOAD_STORAGE_ROOT`, then swap the active asset file and optional product details in one command:

```text
/asset_replace slug="file-11" storage_key="file-11/original.mp4" title="File 11" price_cents=8000 display_name="File 11.mp4" content_type="video/mp4"
```

This deactivates the previously active local file for the product and makes the new file active. Use `/file_show slug="file-11"` to verify the active storage key.

For repeat checkout testing as an admin, clear only your own buyer rows with:

```text
/debug_clear_me confirm=yes
```

## Security Checks

```bash
backend/scripts/security_check.sh
docker compose config >/tmp/hh88trance-compose.yml
```

The database and internal services are not published. Only the web entrypoint and observability UIs bind to localhost by default.

## Rollback

Use the previous image tag when available. Database rollback depends on migration reversibility; inspect the migration before downgrade. If restoring from backup, treat it as destructive and preserve the current database first.

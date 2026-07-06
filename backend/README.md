# Telegram Storefront MVP

Secure Telegram storefront service for digital video delivery.

The phase 1 flow is:

```text
telegram preview caption -> bot deep link -> product lookup -> stripe checkout
-> verified stripe webhook -> database access grant -> gated delivery token
-> temporary redirect to static OneDrive URL
```

Static OneDrive URLs are retained only for phase 1 compatibility. Phase 3 should replace them with storage-provider generated expiring URLs.

## Deployment Boundary

Production files should live under:

```text
/srv/storebot/app
```

Create the dedicated service account:

```bash
sudo adduser --system --group --home /srv/storebot storebot
sudo mkdir -p /srv/storebot/app
sudo chown -R storebot:storebot /srv/storebot
sudo chmod 750 /srv/storebot
```

Copy the backend into `/srv/storebot/app`, create `/srv/storebot/app/.env`, then lock it down:

```bash
sudo chown storebot:storebot /srv/storebot/app/.env
sudo chmod 600 /srv/storebot/app/.env
```

If the bot/API owner is a different person, exchange secrets through an encrypted handoff outside the repository. Do not ask them to SSH into this machine or send plaintext secrets in chat.

Do not add `storebot` or a friend account to the `sudo` or `docker` groups.

## Runtime

Primary approach: rootless Docker as `storebot`.

```bash
sudo loginctl enable-linger storebot
sudo -iu storebot
dockerd-rootless-setuptool.sh install
cd /srv/storebot/app
docker compose build
docker compose up -d
docker compose exec app alembic upgrade head
```

Fallback: Podman Compose under `storebot` if rootless Docker is unavailable.

The default compose stack publishes no host ports. Cloudflare Tunnel connects outbound and routes the public hostname to `http://app:8000`.

For rootless Docker, install the user-level unit as `storebot`:

```bash
sudo -iu storebot
mkdir -p /srv/storebot/.config/systemd/user
cp /srv/storebot/app/deploy/storebot.service /srv/storebot/.config/systemd/user/storebot.service
systemctl --user daemon-reload
systemctl --user enable --now storebot.service
```

## Migrations

Production does not create tables on startup. Run:

```bash
docker compose exec app alembic upgrade head
```

Development may set `AUTO_MIGRATE=true`, but production should keep it false.

## Product Seed

After migrations:

```bash
docker compose exec app python -m app.seed \
  --slug v_aircraft_001 \
  --title "aircraft video 001" \
  --price-cents 999 \
  --currency usd \
  --onedrive-url "https://example.invalid/temporary-dev-link"
```

## Admin Commands

Set `ADMIN_TELEGRAM_IDS` to a comma-separated list of Telegram numeric user IDs.

Customer commands:

```text
/start
/catalog
/my_purchases
/help
```

Phase 2 admin commands:

```text
/admin_help
/product_create slug="v_aircraft_001" title="aircraft video 001" price_cents=999 currency="usd" onedrive_url="https://example.invalid/dev-link"
/product_update slug="v_aircraft_001" title="new title" price_cents=1299
/product_disable slug="v_aircraft_001"
/product_show slug="v_aircraft_001"
/product_list
/asset_replace slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4" title="new title" price_cents=1299 display_name="Aircraft Video 001.mp4" content_type="video/mp4"
/asset_update slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4"
/file_attach slug="v_aircraft_001" storage_key="v_aircraft_001/original.mp4" display_name="Aircraft Video 001.mp4" content_type="video/mp4"
/file_show slug="v_aircraft_001"
/file_disable slug="v_aircraft_001"
/caption slug="v_aircraft_001"
/order_lookup query="order_id_or_stripe_session_or_telegram_id"
/user_lookup telegram_id=123
/debug_clear_me confirm=yes
/resend_delivery order_id="..."
/revoke_access telegram_id=123 slug="v_aircraft_001"
/refund_note order_id="..." note="manual refund note"
```

All admin commands require authorization and write an audit event. `/debug_clear_me` only clears the caller's buyer-side rows for repeat checkout testing: user, orders, payments, grants, and delivery tokens.

## Admin Portal

The HTTP admin portal is available at:

```text
/admin
```

Set `ADMIN_PORTAL_TOKEN` in `.env` before exposing the app. The login form stores a signed HTTP-only session cookie. Keep this route behind the existing private/admin access boundary when possible.

The portal can:

- create a product from a title, slug, price, description, preview caption, and active/draft state
- upload a new file into `DOWNLOAD_STORAGE_ROOT`
- attach an existing server-side storage key under `DOWNLOAD_STORAGE_ROOT`
- visually browse server-side files under `DOWNLOAD_STORAGE_ROOT`
- automatically create the active `files` row for delivery
- publish active products to Telegram `/catalog`
- enable or disable products without deleting historical orders

Active products require either an uploaded file or an existing storage key, so a purchasable tile cannot be saved without a delivery target.

## Full-Length Video Delivery

The production target should be object storage with short-lived signed download URLs:

```text
delivery token -> app validates purchase/access -> app creates signed storage URL -> 302 redirect
```

Prefer Cloudflare R2, Backblaze B2, AWS S3, or another S3-compatible store. Do not stream large video files through this app unless there is a deliberate reason to pay the bandwidth and reliability cost. Static OneDrive URLs are acceptable only as a Phase 1 bridge.

## Health

```bash
curl -fsS https://store.example.com/health
curl -fsS https://store.example.com/ready
```

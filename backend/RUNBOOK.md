# Backend Runbook

The main runtime is the top-level Docker Compose stack. Use [../RUNBOOK.md](../RUNBOOK.md) for deploy, backup, restore, observability, and rollback commands.

## Backend Shell

```bash
docker compose exec api sh
```

## Product Seed

After the stack is healthy, seed or update a product from the API container:

```bash
docker compose exec api python -m app.seed \
  --slug file-11 \
  --title "File 11" \
  --price-cents 8000 \
  --currency usd \
  --onedrive-url "https://example.invalid/temporary-dev-link"
```

The public website links to these slugs through `/buy/<slug>`:

```text
custom-4-mtx
custom-3-cdl
custom-2-ritual
custom-1-power
file-11
file-10
file-9
file-8
```

Use the admin portal or seed command for each active delivery file. The `/buy/<slug>` route intentionally returns `404` for missing, disabled, or invalid slugs so inactive products cannot be purchased from stale website links.

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

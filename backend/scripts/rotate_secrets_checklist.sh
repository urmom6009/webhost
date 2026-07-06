#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Secret rotation checklist:
1. Disable public Cloudflare route or pause the tunnel if compromise is active.
2. Rotate TELEGRAM_BOT_TOKEN in BotFather and update /srv/storebot/app/.env.
3. Generate a new TELEGRAM_WEBHOOK_SECRET and run scripts/set_webhook.sh.
4. Rotate STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in Stripe Dashboard.
5. Rotate POSTGRES_PASSWORD and DATABASE_URL together.
6. Revoke and recreate CLOUDFLARE_TUNNEL_TOKEN.
7. Restart the service and verify /ready.
8. Review provider_events, audit_events, and recent app logs.
EOF

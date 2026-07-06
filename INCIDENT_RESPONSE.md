# Incident Response

## Immediate Containment

1. Disable the public Cloudflare route or stop the tunnel.
2. Snapshot current logs without exposing secrets.
3. Stop the app container if active abuse is ongoing.

## Rotate Secrets

1. Rotate Telegram bot token.
2. Rotate Telegram webhook secret and run `scripts/set_webhook.sh`.
3. Rotate Stripe secret key.
4. Rotate Stripe webhook secret.
5. Rotate database password and update `DATABASE_URL`.
6. Revoke and recreate Cloudflare tunnel token.
7. Restart the service and verify `/ready`.

## Review

Check `provider_events`, `orders`, `payments`, `access_grants`, and `delivery_tokens` for suspicious duplicates, mismatches, or excessive delivery attempts.

Notify affected users if required by law, payment provider rules, or platform policy.

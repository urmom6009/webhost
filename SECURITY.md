# Security

This service is internet-facing payment infrastructure.

## Hard Requirements

- Do not store card data. Stripe Checkout handles card collection.
- Do not fulfill orders from `/success`; only verified provider events can grant access.
- Do not expose Postgres, Redis, Docker socket, SSH, admin endpoints, or app ports publicly.
- Do not commit `.env`, API keys, bot tokens, Stripe keys, webhook secrets, database passwords, tunnel tokens, private keys, backups, or production logs.
- Do not run the service as the primary human account.
- Do not add a friend account to `sudo` or `docker`.
- Do not log raw webhook bodies, full user messages, delivery tokens, full OneDrive links, or secrets.

## Network Exposure

Preferred path:

```text
internet -> cloudflare tunnel -> compose network -> app:8000
```

If direct port forwarding is used, forward only `443` to a reverse proxy. Never forward app, Postgres, Redis, Docker daemon, or admin service ports.

Suggested firewall baseline:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/16 to any port 22 proto tcp
sudo ufw allow from 10.0.0.0/8 to any port 22 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Prefer SSH allow rules scoped to the WireGuard subnet when WireGuard is available.

## Secrets

The app rejects common placeholder values at startup. Production `.env` must be owned by `storebot:storebot` and mode `600`.

Run before deployment:

```bash
scripts/security_check.sh
```

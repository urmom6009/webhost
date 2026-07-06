#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /srv/storebot/secrets/stripe-secrets.env.age" >&2
  exit 2
fi

encrypted_path="$1"
secret_dir="${SECRET_DIR:-/srv/storebot/secrets}"
key_path="${AGE_KEY_PATH:-${secret_dir}/handoff.agekey}"
env_path="${ENV_PATH:-/srv/storebot/app/.env}"
service_user="${SERVICE_USER:-storebot}"
service_group="${SERVICE_GROUP:-storebot}"

if ! command -v age >/dev/null 2>&1; then
  echo "age is required. install age first." >&2
  exit 1
fi

if [[ ! -f "$encrypted_path" ]]; then
  echo "encrypted file not found: $encrypted_path" >&2
  exit 1
fi

if [[ ! -f "$key_path" ]]; then
  echo "age identity key not found: $key_path" >&2
  exit 1
fi

if [[ ! -f "$env_path" ]]; then
  echo "base env not found: $env_path" >&2
  echo "create it first with your non-Stripe values" >&2
  exit 1
fi

tmp="$(mktemp)"
merged="$(mktemp)"
trap 'rm -f "$tmp" "$merged"' EXIT

age -d -i "$key_path" -o "$tmp" "$encrypted_path"

if grep -Evq '^(STRIPE_SECRET_KEY|STRIPE_WEBHOOK_SECRET)=' "$tmp"; then
  echo "bundle must contain only STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET" >&2
  exit 1
fi

stripe_key="$(grep '^STRIPE_SECRET_KEY=' "$tmp" | tail -n1 | cut -d= -f2-)"
stripe_webhook="$(grep '^STRIPE_WEBHOOK_SECRET=' "$tmp" | tail -n1 | cut -d= -f2-)"

if [[ ! "$stripe_key" =~ ^sk_(test|live)_[A-Za-z0-9_]+$ ]]; then
  echo "STRIPE_SECRET_KEY does not look valid" >&2
  exit 1
fi

if [[ ! "$stripe_webhook" =~ ^whsec_[A-Za-z0-9_]+$ ]]; then
  echo "STRIPE_WEBHOOK_SECRET does not look valid" >&2
  exit 1
fi

grep -Ev '^(STRIPE_SECRET_KEY|STRIPE_WEBHOOK_SECRET)=' "$env_path" > "$merged"
{
  echo "STRIPE_SECRET_KEY=$stripe_key"
  echo "STRIPE_WEBHOOK_SECRET=$stripe_webhook"
} >> "$merged"

backup="${env_path}.before-stripe-merge.$(date +%Y%m%d_%H%M%S)"
cp "$env_path" "$backup"
install -m 600 -o "$service_user" -g "$service_group" "$merged" "$env_path"
chmod 600 "$backup"

echo "merged Stripe secrets into $env_path"
echo "previous env backup: $backup"

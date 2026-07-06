#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /srv/storebot/secrets/storebot.env.age" >&2
  exit 2
fi

encrypted_path="$1"
secret_dir="${SECRET_DIR:-/srv/storebot/secrets}"
key_path="${AGE_KEY_PATH:-${secret_dir}/handoff.agekey}"
env_path="${ENV_PATH:-/srv/storebot/app/.env}"

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

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

age -d -i "$key_path" -o "$tmp" "$encrypted_path"

if grep -Eq 'replace_me|changeme|sk_test_replace_me|whsec_replace_me' "$tmp"; then
  echo "decrypted env still contains placeholder values; refusing to install" >&2
  exit 1
fi

install -m 600 -o storebot -g storebot "$tmp" "$env_path"
echo "installed encrypted handoff result to $env_path"

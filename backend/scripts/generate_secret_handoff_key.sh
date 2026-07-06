#!/usr/bin/env bash
set -euo pipefail

secret_dir="${SECRET_DIR:-/srv/storebot/secrets}"
key_path="${secret_dir}/handoff.agekey"
recipient_path="${secret_dir}/handoff.recipient.txt"

if ! command -v age-keygen >/dev/null 2>&1; then
  echo "age-keygen is required. install age first." >&2
  exit 1
fi

mkdir -p "$secret_dir"
chmod 700 "$secret_dir"

if [[ -f "$key_path" ]]; then
  echo "refusing to overwrite existing key: $key_path" >&2
  exit 1
fi

age-keygen -o "$key_path"
chmod 600 "$key_path"

grep '^# public key:' "$key_path" | sed 's/^# public key: //' > "$recipient_path"
chmod 644 "$recipient_path"

echo "private key: $key_path"
echo "public recipient: $(cat "$recipient_path")"
echo "send only the public recipient to the secret owner"

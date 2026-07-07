#!/usr/bin/env bash
set -euo pipefail

backup_dir="${BACKUP_DIR:-/srv/storebot/backups}"
stamp="$(date +%Y-%m-%d_%H-%M-%S)"
backup_path="${backup_dir}/store_${stamp}.sql.gz"

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

docker compose exec -T db pg_dump -U storefront storefront | gzip > "$backup_path"
chmod 600 "$backup_path"

echo "wrote ${backup_path}"

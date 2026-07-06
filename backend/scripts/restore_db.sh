#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /srv/storebot/backups/store_YYYY-MM-DD_HH-MM-SS.sql.gz" >&2
  exit 2
fi

backup_path="$1"

if [[ ! -f "$backup_path" ]]; then
  echo "backup not found: $backup_path" >&2
  exit 1
fi

echo "restoring ${backup_path}"
gunzip -c "$backup_path" | docker compose exec -T postgres psql -U store store

#!/usr/bin/env bash
set -euo pipefail

src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest_dir="${DEST_DIR:-/srv/storebot/app}"
service_user="${SERVICE_USER:-storebot}"
service_group="${SERVICE_GROUP:-storebot}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo $0" >&2
  exit 1
fi

if ! id "$service_user" >/dev/null 2>&1; then
  adduser --system --group --home /srv/storebot "$service_user"
fi

mkdir -p "$dest_dir" /srv/storebot/secrets /srv/storebot/backups
chown -R "$service_user:$service_group" /srv/storebot
chmod 750 /srv/storebot
chmod 700 /srv/storebot/secrets /srv/storebot/backups

rsync -a --delete \
  --exclude '.env' \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'backups' \
  --exclude '*.pyc' \
  --exclude '*.log' \
  --exclude '*.sql' \
  --exclude '*.sql.gz' \
  "$src_dir/" "$dest_dir/"

chown -R "$service_user:$service_group" "$dest_dir"
find "$dest_dir" -type d -exec chmod 750 {} +
find "$dest_dir" -type f -exec chmod 640 {} +
find "$dest_dir/scripts" -type f -name '*.sh' -exec chmod 750 {} +

if [[ -f "$dest_dir/.env" ]]; then
  chown "$service_user:$service_group" "$dest_dir/.env"
  chmod 600 "$dest_dir/.env"
fi

echo "installed code to $dest_dir"
echo "next: install $dest_dir/.env with mode 600, then run compose as $service_user"

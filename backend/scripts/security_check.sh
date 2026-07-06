#!/usr/bin/env bash
set -euo pipefail

fail=0

if docker compose config | grep -qE 'published:|0\.0\.0\.0:5432|0\.0\.0\.0:6379|/var/run/docker.sock|network_mode: host|privileged: true'; then
  echo "compose security check failed: public/internal exposure or dangerous container setting found" >&2
  fail=1
fi

if [[ -f .env ]]; then
  mode="$(stat -c '%a' .env)"
  if [[ "$mode" != "600" ]]; then
    echo ".env should be chmod 600; current mode is ${mode}" >&2
    fail=1
  fi
fi

if find . -path ./.git -prune -o -type f \( -name '*.log' -o -name '*.sql' -o -name '*.sql.gz' \) -print | grep -q .; then
  echo "repo contains log or database dump files; remove them before deployment" >&2
  fail=1
fi

exit "$fail"

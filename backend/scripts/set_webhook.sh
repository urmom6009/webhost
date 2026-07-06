#!/usr/bin/env bash
set -euo pipefail

source .env

curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${PUBLIC_BASE_URL}/telegram/webhook/${TELEGRAM_WEBHOOK_SECRET}" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
  | python3 -m json.tool

DEFAULT_COMMANDS='[
  {"command":"start","description":"Browse available assets"},
  {"command":"catalog","description":"Browse available assets"},
  {"command":"my_purchases","description":"Get fresh access links"},
  {"command":"help","description":"Show available commands"}
]'

ADMIN_COMMANDS='[
  {"command":"start","description":"Browse available assets"},
  {"command":"catalog","description":"Browse available assets"},
  {"command":"my_purchases","description":"Get fresh access links"},
  {"command":"help","description":"Show available commands"},
  {"command":"admin_help","description":"Show admin commands"},
  {"command":"product_list","description":"List assets"},
  {"command":"asset_replace","description":"Update asset details or file"},
  {"command":"debug_clear_me","description":"Clear your test buyer entries"}
]'

curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setMyCommands" \
  -d "commands=${DEFAULT_COMMANDS}" \
  | python3 -m json.tool

IFS=',' read -ra ADMIN_IDS <<< "${ADMIN_TELEGRAM_IDS:-}"
for admin_id in "${ADMIN_IDS[@]}"; do
  admin_id="${admin_id//[[:space:]]/}"
  if [[ -z "${admin_id}" ]]; then
    continue
  fi
  curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setMyCommands" \
    -d "commands=${ADMIN_COMMANDS}" \
    -d "scope={\"type\":\"chat\",\"chat_id\":${admin_id}}" \
    | python3 -m json.tool
done

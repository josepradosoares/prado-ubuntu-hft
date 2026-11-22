#!/usr/bin/env bash
# Remove configurações antigas (data/prado_server_config.json / config.json) e reinicia o serviço prado-hft-web
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="prado-hft-web"

echo "Parando serviço ${SERVICE_NAME} (se ativo)..."
sudo systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true

for cfg in \
  "${APP_DIR}/data/prado_server_config.json" \
  "${APP_DIR}/data/config.json" \
  "${APP_DIR}/config.json"
do
  if [[ -f "${cfg}" ]]; then
    rm -f "${cfg}"
    echo "Removido arquivo antigo: ${cfg}"
  fi
done

echo "Reiniciando ${SERVICE_NAME} com configuração limpa..."
sudo systemctl start "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" --no-pager

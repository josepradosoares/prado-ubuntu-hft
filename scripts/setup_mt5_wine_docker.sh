#!/usr/bin/env bash
# ==============================================================================
# SETUP AUTOMÁTICO DO CONTAINER METATRADER 5 HEADLESS (WINE + RPyC BRIDGE) NO UBUNTU
# ==============================================================================
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
   echo "[ERRO] Execute com sudo: sudo bash scripts/setup_mt5_wine_docker.sh"
   exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${APP_DIR}/data/mt5_wine"
CONTAINER_NAME="prado-mt5-ubuntu"

echo "[MT5-UBUNTU] Verificando Docker Engine no Ubuntu..."
if ! command -v docker >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y docker.io
fi
systemctl enable --now docker || true

mkdir -p "${DATA_DIR}"

echo "[MT5-UBUNTU] Baixando e iniciando container MetaTrader 5 Headless (Wine + Python RPyC 18812 + WebVNC 3000)..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  -p 127.0.0.1:18812:18812 \
  -p 3000:3000 \
  -e TZ=America/Sao_Paulo \
  -v "${DATA_DIR}:/config" \
  gmag11/metatrader5_vnc:latest

if command -v ufw >/dev/null 2>&1; then
    ufw allow 3000/tcp >/dev/null 2>&1 || true
fi
if command -v iptables >/dev/null 2>&1; then
    iptables -I INPUT 1 -p tcp --dport 3000 -j ACCEPT >/dev/null 2>&1 || true
fi

SERVER_IP="$(curl -s --max-time 3 ifconfig.me || hostname -I 2>/dev/null | awk '{print $1}' || echo 'SEU_IP')"

echo "======================================================================"
echo "  ✅ METATRADER 5 HEADLESS INSTALADO E RODANDO NA VPS UBUNTU!"
echo "  - Ponte Python RPyC : 127.0.0.1:18812"
echo "  - Visualização Web  : http://${SERVER_IP}:3000"
echo "======================================================================"

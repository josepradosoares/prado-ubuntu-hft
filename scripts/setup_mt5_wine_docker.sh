#!/usr/bin/env bash
# ==============================================================================
# SETUP AUTOMÁTICO DO CONTAINER METATRADER 5 HEADLESS (WINE + RPyC BRIDGE) NO UBUNTU
# ==============================================================================
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
   echo "[ERRO] Execute com sudo: sudo bash scripts/setup_mt5_wine_docker.sh"
   exit 1
fi

echo "[MT5-UBUNTU] Instalando Docker Engine no Ubuntu..."
if ! command -v docker >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y docker.io docker-compose-v2 || apt-get install -y docker.io
    systemctl enable --now docker
fi

echo "[MT5-UBUNTU] Subindo container MetaTrader 5 Headless (Wine + Python RPyC na porta 18812 + WebVNC na porta 3000)..."
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${APP_DIR}"

docker compose up -d

echo "======================================================================"
echo "  ✅ CONTAINER METATRADER 5 HEADLESS ATIVO NO UBUNTU!"
echo "  - Ponte Python RPyC : 127.0.0.1:18812 (já pré-configurada no painel)"
echo "  - Visualização VNC  : http://$(hostname -I | awk '{print $1}'):3000"
echo "======================================================================"

#!/usr/bin/env bash
# ==============================================================================
# SETUP AUTOMÁTICO DO CONTAINER METATRADER 5 HEADLESS (WINE + MT5LINUX) NO UBUNTU
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

echo "[MT5-UBUNTU] Limpando container anterior e configurando rede host direta..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

# Limpa cache parcial caso a instalação anterior tenha falhado sem rede
if [[ ! -f "${DATA_DIR}/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe" ]]; then
    rm -rf "${DATA_DIR}"
fi
mkdir -p "${DATA_DIR}"

echo "[MT5-UBUNTU] Subindo container MetaTrader 5 Headless (--network host, porta mt5linux 8001 + WebVNC 3000)..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --network host \
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
echo "  ✅ METATRADER 5 HEADLESS INICIADO COM REDE DIRETA!"
echo "  - Acompanhe a instalação : sudo docker logs -f ${CONTAINER_NAME}"
echo "  - Ponte Python mt5linux  : 127.0.0.1:8001"
echo "  - Tela do MT5 no Navegador: http://${SERVER_IP}:3000"
echo "======================================================================"

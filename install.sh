#!/usr/bin/env bash
# ==============================================================================
# PRADO INSTITUTIONAL HFT & VWAP UNIVERSAL — INSTALADOR UBUNTU SERVER (CLOUD API)
# ==============================================================================
# Instala e configura o Painel Web + Motor Quantitativo Python 24/7 via MetaApi Cloud:
#   - Sem necessidade de MetaTrader aberto, sem Docker e sem Wine.
#   - Consumo mínimo (~80 MB de RAM).
#
# Uso após clonar do GitHub no Ubuntu (20.04 / 22.04 / 24.04 / 26.04):
#   chmod +x install.sh
#   sudo ./install.sh
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="prado-hft-web"
WEB_PORT="${PRADO_WEB_PORT:-8080}"
RUN_USER="${SUDO_USER:-$(whoami)}"

echo "======================================================================"
echo "  PRADO INSTITUTIONAL HFT & VWAP UNIVERSAL — UBUNTU CLOUD API INSTALLER"
echo "======================================================================"
echo "Diretório do projeto: ${APP_DIR}"
echo "Usuário de execução : ${RUN_USER}"
echo "Porta do Painel Web : ${WEB_PORT}"
echo ""

if [[ $EUID -ne 0 ]]; then
   echo "[ERRO] Execute este script com sudo: sudo ./install.sh"
   exit 1
fi

echo "[1/5] Atualizando pacotes do Ubuntu e instalando Python 3..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl ufw

echo "[2/5] Criando ambiente virtual Python (.venv) e instalando dependências..."
sudo -u "${RUN_USER}" python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[3/5] Preparando diretório de dados e validando testes automatizados..."
sudo -u "${RUN_USER}" mkdir -p "${APP_DIR}/data"
PYTHONPATH="${APP_DIR}" "${APP_DIR}/.venv/bin/pytest" "${APP_DIR}/tests" -q

echo "[4/5] Configurando serviço systemd (${SERVICE_NAME}.service) para rodar 24/7..."
cat >/etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Prado Institutional HFT & VWAP Universal Web Dashboard & MetaApi Cloud Engine
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONPATH=${APP_DIR}"
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/run_server.py --host 0.0.0.0 --port ${WEB_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "[5/5] Liberando porta ${WEB_PORT}/tcp no Firewall (UFW e iptables)..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow "${WEB_PORT}/tcp" >/dev/null 2>&1 || true
fi
if command -v iptables >/dev/null 2>&1; then
    iptables -I INPUT 1 -p tcp --dport "${WEB_PORT}" -j ACCEPT >/dev/null 2>&1 || true
fi

SERVER_IP="$(curl -s --max-time 3 ifconfig.me || hostname -I 2>/dev/null | awk '{print $1}' || echo 'SEU_IP_DO_SERVIDOR')"

echo ""
echo "======================================================================"
echo "  INSTALAÇÃO CONCLUÍDA E SERVIÇO CLOUD API ATIVO NO UBUNTU!"
echo "======================================================================"
echo "  Painel Web     : http://${SERVER_IP}:${WEB_PORT}"
echo "  Usuário Padrão : admin"
echo "  Senha Padrão   : prado2026"
echo ""
echo "  Próximo passo: Acesse o painel, abra 'Contas Demo e Real (MT5)',"
echo "  cole o seu MetaApi Token e conecte sua conta sem precisar de MT5!"
echo "======================================================================"

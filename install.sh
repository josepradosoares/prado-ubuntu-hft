#!/usr/bin/env bash
# ==============================================================================
# PRADO INSTITUTIONAL HFT & VWAP UNIVERSAL — INSTALADOR UBUNTU SERVER (CTRADER OPEN API + HTTPS)
# ==============================================================================
# Instala e configura o Painel Web + Motor Quantitativo Python 24/7 via cTrader Open API,
# com Proxy Reverso Nginx + HTTPS (Let's Encrypt) para o domínio configurado e
# redirecionamento automático de HTTP / IP / porta 8080 para HTTPS.
#
# Uso após clonar do GitHub no Ubuntu (20.04 / 22.04 / 24.04 / 26.04):
#   chmod +x install.sh update.sh
#   sudo ./install.sh
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="prado-hft-web"
DOMAIN="${PRADO_DOMAIN:-paineljose.duckdns.org}"
PUBLIC_LEGACY_PORT="${PRADO_WEB_PORT:-8080}"
INTERNAL_PORT="${PRADO_INTERNAL_PORT:-8081}"
CERTBOT_EMAIL="${PRADO_CERTBOT_EMAIL:-}"
RUN_USER="${SUDO_USER:-$(whoami)}"
NGINX_SITE="/etc/nginx/sites-available/prado-hft"
NGINX_LINK="/etc/nginx/sites-enabled/prado-hft"
CERT_FULLCHAIN="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
CERT_PRIVKEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"

echo "======================================================================"
echo "  PRADO INSTITUTIONAL HFT & VWAP UNIVERSAL — UBUNTU CTRADER INSTALLER"
echo "======================================================================"
echo "Diretório do projeto   : ${APP_DIR}"
echo "Usuário de execução    : ${RUN_USER}"
echo "Domínio HTTPS          : ${DOMAIN}"
echo "Porta interna Python   : 127.0.0.1:${INTERNAL_PORT}"
echo "Porta legada redirect  : ${PUBLIC_LEGACY_PORT} -> https://${DOMAIN}"
echo ""

if [[ $EUID -ne 0 ]]; then
   echo "[ERRO] Execute este script com sudo: sudo ./install.sh"
   exit 1
fi

echo "[1/6] Atualizando pacotes do Ubuntu e instalando Python, Nginx e Certbot..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl ufw nginx certbot python3-certbot-nginx

echo "[2/6] Criando/atualizando ambiente virtual Python (.venv) e dependências..."
if [[ ! -d "${APP_DIR}/.venv" ]]; then
    sudo -u "${RUN_USER}" python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[3/6] Preservando dados existentes e validando testes automatizados..."
sudo -u "${RUN_USER}" mkdir -p "${APP_DIR}/data"
PYTHONPATH="${APP_DIR}" "${APP_DIR}/.venv/bin/pytest" "${APP_DIR}/tests" -q

echo "[4/6] Configurando serviço systemd (${SERVICE_NAME}.service) em 127.0.0.1:${INTERNAL_PORT}..."
cat >/etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Prado Institutional HFT & VWAP Universal Web Dashboard & cTrader Open API Engine
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONPATH=${APP_DIR}"
Environment="CTRADER_REDIRECT_URI=https://${DOMAIN}/api/ctrader/oauth/callback"
EnvironmentFile=-${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/run_server.py --host 127.0.0.1 --port ${INTERNAL_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

BACKEND_READY=0
for _ in $(seq 1 15); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${INTERNAL_PORT}/health" >/dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi
    sleep 1
done
if [[ "${BACKEND_READY}" -ne 1 ]]; then
    echo "[ERRO] O backend Python não respondeu em http://127.0.0.1:${INTERNAL_PORT}/health após 15s."
    journalctl -u "${SERVICE_NAME}" -n 30 --no-pager || true
    exit 1
fi

echo "[5/6] Configurando Firewall (80, 443, ${PUBLIC_LEGACY_PORT}), Nginx e SSL Let's Encrypt (${DOMAIN})..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw allow "${PUBLIC_LEGACY_PORT}/tcp" >/dev/null 2>&1 || true
fi
if command -v iptables >/dev/null 2>&1; then
    for PORT_RULE in 80 443 "${PUBLIC_LEGACY_PORT}"; do
        iptables -C INPUT -p tcp --dport "${PORT_RULE}" -j ACCEPT >/dev/null 2>&1 || \
            iptables -I INPUT 1 -p tcp --dport "${PORT_RULE}" -j ACCEPT >/dev/null 2>&1 || true
    done
fi

mkdir -p /var/www/html
rm -f /etc/nginx/sites-enabled/default

cat >"${NGINX_SITE}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} _;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        allow all;
    }

    location / {
        proxy_pass http://127.0.0.1:${INTERNAL_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}

server {
    listen ${PUBLIC_LEGACY_PORT} default_server;
    listen [::]:${PUBLIC_LEGACY_PORT} default_server;
    server_name ${DOMAIN} _;

    location / {
        proxy_pass http://127.0.0.1:${INTERNAL_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF

ln -sf "${NGINX_SITE}" "${NGINX_LINK}"
nginx -t
systemctl enable nginx
systemctl restart nginx

if [[ ! -f "${CERT_FULLCHAIN}" || ! -f "${CERT_PRIVKEY}" ]]; then
    echo "Solicitando certificado SSL Let's Encrypt para ${DOMAIN}..."
    CERTBOT_ARGS=(
        certonly
        --webroot
        -w /var/www/html
        -d "${DOMAIN}"
        --non-interactive
        --agree-tos
        --keep-until-expiring
        --deploy-hook "systemctl reload nginx"
    )
    if [[ -n "${CERTBOT_EMAIL}" ]]; then
        CERTBOT_ARGS+=(-m "${CERTBOT_EMAIL}")
    else
        CERTBOT_ARGS+=(--register-unsafely-without-email)
    fi
    certbot "${CERTBOT_ARGS[@]}" || true
fi

SSL_ACTIVE=0
if [[ -f "${CERT_FULLCHAIN}" && -f "${CERT_PRIVKEY}" ]]; then
    SSL_ACTIVE=1
    cat >"${NGINX_SITE}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${DOMAIN} _;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type "text/plain";
        allow all;
    }

    location / {
        return 301 https://${DOMAIN}\$request_uri;
    }
}

server {
    listen ${PUBLIC_LEGACY_PORT} default_server;
    listen [::]:${PUBLIC_LEGACY_PORT} default_server;
    server_name ${DOMAIN} _;

    location / {
        return 301 https://${DOMAIN}\$request_uri;
    }
}

server {
    listen 443 ssl http2 default_server;
    listen [::]:443 ssl http2 default_server;
    server_name ${DOMAIN};

    ssl_certificate ${CERT_FULLCHAIN};
    ssl_certificate_key ${CERT_PRIVKEY};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    if (\$host != "${DOMAIN}") {
        return 301 https://${DOMAIN}\$request_uri;
    }

    location / {
        proxy_pass http://127.0.0.1:${INTERNAL_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF
    nginx -t
    systemctl reload nginx
    systemctl enable --now certbot.timer >/dev/null 2>&1 || true
else
    echo ""
    echo "[AVISO] Não foi possível emitir o certificado HTTPS agora para ${DOMAIN}."
    echo "Verifique se:"
    echo "  1) ${DOMAIN} está apontando para o IP público deste servidor Ubuntu."
    echo "  2) As portas 80 e 443 estão abertas no Security Group / Firewall da sua VPS."
    echo "Depois de corrigir DNS/firewall, execute novamente: sudo ${APP_DIR}/install.sh"
fi

echo "[6/6] Finalizando verificação de serviço e exibindo acesso..."
SERVER_IP="$(curl -s --max-time 3 ifconfig.me || hostname -I 2>/dev/null | awk '{print $1}' || echo 'SEU_IP_DO_SERVIDOR')"

echo ""
echo "======================================================================"
echo "  INSTALAÇÃO CONCLUÍDA — PRADO CTRADER OPEN API NO UBUNTU"
echo "======================================================================"
if [[ "${SSL_ACTIVE}" -eq 1 ]]; then
    echo "  Painel HTTPS   : https://${DOMAIN}"
    echo "  Redirect ativo : http://${SERVER_IP} | http://${SERVER_IP}:${PUBLIC_LEGACY_PORT} | http://${DOMAIN} -> https://${DOMAIN}"
    echo "  OAuth Callback : https://${DOMAIN}/api/ctrader/oauth/callback"
else
    echo "  Painel HTTP    : http://${SERVER_IP}:${PUBLIC_LEGACY_PORT} (HTTPS pendente de DNS/porta 80)"
    echo "  OAuth Callback : http://${SERVER_IP}:${PUBLIC_LEGACY_PORT}/api/ctrader/oauth/callback"
fi
echo "  Usuário Padrão : admin"
echo "  Senha Padrão   : prado2026"
echo "======================================================================"

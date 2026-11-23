#!/usr/bin/env bash
# ==============================================================================
# PRADO INSTITUTIONAL HFT — SCRIPT DE ATUALIZAÇÃO EM 1 COMANDO (GITHUB -> UBUNTU)
# ==============================================================================
# Atualiza o código via git pull (preservando .env e data/*.json) e reaplica
# install.sh (dependências, testes, systemd, Nginx HTTPS e redirecionamentos).
#
# Uso no servidor Ubuntu:
#   sudo ./update.sh
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-$(whoami)}"

if [[ $EUID -ne 0 ]]; then
    echo "[ERRO] Execute com sudo: sudo ./update.sh"
    exit 1
fi

echo "======================================================================"
echo "  ATUALIZANDO PRADO HFT VIA GITHUB (${APP_DIR})"
echo "======================================================================"

if [[ -d "${APP_DIR}/.git" ]]; then
    sudo -u "${RUN_USER}" git config --global --add safe.directory "${APP_DIR}" >/dev/null 2>&1 || true
    sudo -u "${RUN_USER}" git -C "${APP_DIR}" fetch origin main
    if [[ -n "$(sudo -u "${RUN_USER}" git -C "${APP_DIR}" -c core.fileMode=false status --porcelain --untracked-files=no)" ]]; then
        STAMP="$(date +%Y%m%d%H%M%S)"
        echo "[INFO] Salvando alterações locais em stash (prado-auto-backup-${STAMP})..."
        sudo -u "${RUN_USER}" git -C "${APP_DIR}" stash push -m "prado-auto-backup-${STAMP}"
    fi
    sudo -u "${RUN_USER}" git -C "${APP_DIR}" checkout main
    sudo -u "${RUN_USER}" git -C "${APP_DIR}" -c core.fileMode=false pull --ff-only origin main
else
    echo "[AVISO] Diretório .git não encontrado; pulando git pull e executando install.sh..."
fi

chmod +x "${APP_DIR}/install.sh" "${APP_DIR}/update.sh"
exec "${APP_DIR}/install.sh"

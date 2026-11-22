# 🏛️ Prado Institutional HFT & VWAP Universal — Ubuntu Server (Deriv Multipliers Edition)

Plataforma 100% em Python puro para **Servidor Ubuntu**, com **Painel Web Institucional**, **Cofre de Tokens da Deriv (Demo & Real)**, **Frota de Robôs Matemáticos** e **Backtester Tick-a-Tick** — sem MetaTrader, sem Docker/Wine e 100% gratuita via WebSocket oficial da Deriv.

---

## ✨ Recursos da Plataforma

- **Conexão Direta Deriv WebSocket (`wss://ws.derivws.com/websockets/v3`)**: lê ticks reais, saldo e executa **Multipliers (`MULTUP` / `MULTDOWN`)** com Stop Loss, Take Profit e encerramento imediato.
- **Área de Tokens no Painel (`Tokens e Contas Deriv`)**: salve seu Token Demo e Real da Deriv direto pelo navegador, valide automaticamente e alterne entre eles com 1 clique.
- **Motor 100% Matemático (Sem Gráficos):** VWAP, Bandas $\pm 1\sigma / \pm 2\sigma$, Z-Score de Agressão, Imbalance e Correlação de Cesta.

---

## 🐧 Como Instalar e Rodar no Servidor Ubuntu (1 Comando)

```bash
git clone https://github.com/josepradosoares/prado-ubuntu-hft.git
cd prado-ubuntu-hft
chmod +x install.sh
sudo ./install.sh
```

Depois de concluir, abra no navegador:
- **URL:** `http://IP_DO_SEU_SERVIDOR_UBUNTU:8080`
- **Usuário:** `admin`
- **Senha:** `prado2026`

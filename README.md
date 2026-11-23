# 🏛️ Prado Institutional HFT & VWAP Universal — Ubuntu Server (cTrader Open API Edition)

Plataforma 100% em Python puro para **Servidor Ubuntu**, com **Painel Web Institucional**, **Integração OAuth 2.0 & Cofre de Contas cTrader (Demo & Real)**, **Frota de Robôs Matemáticos** e **Backtester Tick-a-Tick** — sem MetaTrader, sem Docker/Wine e via WebSocket JSON oficial da **cTrader Open API** (`wss://demo.ctraderapi.com:5036` e `wss://live.ctraderapi.com:5036`).

---

## ✨ Recursos da Plataforma

- **Conexão Direta cTrader Open API (Porta 5036)**: lê spots Bid/Ask reais, trendbars históricos, saldo e executa ordens em **Lotes (Forex, Metais, Índices e Cripto)** com Stop Loss e Take Profit relativos obrigatórios e encerramento imediato.
- **Autenticação OAuth 2.0 cTID & Cofre de Contas (`Contas cTrader`)**: conecte seu `Client ID` e `Client Secret` de `https://openapi.ctrader.com/apps`, autorize com 1 clique via OAuth (ou cole seu token do Playground), sincronize suas contas Demo/Real e alterne entre elas com 1 clique.
- **HTTPS Automático (Nginx + Let's Encrypt)**: `install.sh` configura proxy reverso Nginx, emite certificado SSL para `paineljose.duckdns.org` (ou variável `PRADO_DOMAIN`) e redireciona automaticamente acessos via HTTP, IP direto ou porta `8080` para `https://paineljose.duckdns.org`.
- **Motor Quantitativo Completo:** VWAP, Bandas $\pm 1\sigma / \pm 2\sigma$, Z-Score de Agressão, Imbalance, Correlação de Cesta, 21 Indicadores, Modelos Python Customizados, Grid Linear e News Scout.

---

## 🐧 Como Instalar no Servidor Ubuntu (Instalação Limpa)

```bash
git clone https://github.com/josepradosoares/prado-ubuntu-hft.git
cd prado-ubuntu-hft
chmod +x install.sh update.sh
sudo ./install.sh
```

## 🔄 Como Atualizar o Servidor Ubuntu Existente

Se o projeto já está clonado no servidor Ubuntu, execute na pasta do projeto:

```bash
sudo ./update.sh
```

Ou, se ainda estiver na versão antiga sem `update.sh`, execute:

```bash
git pull origin main && chmod +x install.sh update.sh && sudo ./update.sh
```

Depois de concluir, abra no navegador:
- **URL Principal (HTTPS):** `https://paineljose.duckdns.org`
- **Redirect URI (para cadastrar em `https://openapi.ctrader.com/apps`):** `https://paineljose.duckdns.org/api/ctrader/oauth/callback`
- **Usuário:** `admin`
- **Senha:** `prado2026`

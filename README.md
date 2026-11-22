# 🏛️ Prado Institutional HFT & VWAP Universal — Ubuntu Server (Cloud API Edition)

Plataforma 100% em Python puro para **Servidor Ubuntu**, com **Painel Web Institucional**, **Contas Demo & Real via MetaApi Cloud** (sem precisar deixar o MetaTrader aberto em lugar nenhum), **Frota de Robôs Matemáticos** e **Backtester Tick-a-Tick**.

---

## ✨ Arquitetura Cloud API (Leve e 24/7)

- **Zero MetaTrader aberto** (nem no PC Windows, nem na VPS Ubuntu via Wine/Docker).
- **Consumo mínimo na VPS:** ~80 MB de RAM.
- **Conexão direta via MetaApi Cloud (`https://app.metaapi.cloud`)**: lê saldo, equity, ativos da corretora, ticks ao vivo e envia ordens reais/demo via HTTPS em Python puro.

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

# 🏛️ Prado Institutional HFT & VWAP Universal — Ubuntu Server & Web Command Center

Plataforma completa em Python com **Painel Web de Monitoramento em Tempo Real**, **Tela de Login**, **Conexão Direta à Conta MetaTrader 5** e **Configuração Operacional Fiel à Entrevista do Broker Institucional de Wall Street ("Fio")**, pronta para instalar e rodar 24/7 no **Ubuntu Server** com um único comando.

---

## ✨ O que este Sistema Faz

1. **Tela de Login Web Segura (`/login`)**:
   - Autenticação via token HMAC-SHA256 para você acessar o painel pelo navegador (PC ou celular).
   - Credencial inicial padrão: Usuário `admin` / Senha `prado2026` (pode ser alterada direto no painel).
2. **Conexão Direta com a Conta do MetaTrader 5 via Python**:
   - Aba dedicada no painel web para digitar **Login da Conta MT5**, **Senha** e **Servidor da Corretora** (ex.: `XPInvestimentos-PRD`, `ClearInvestimentos-PRD`, `MetaQuotes-Demo`, etc.).
   - Suporta **MT5 Headless no Ubuntu (Wine / RPyC Docker Bridge)**, **MT5 Nativo** e **Modo Simulação Quantitativa** (funciona imediatamente mesmo antes de configurar a corretora).
3. **Estratégia Fiel ao Broker Institucional de Wall Street (`.txt`)**:
   - **VWAP Intraday + Bandas de Desvio Padrão ($\pm 1\sigma, \pm 2\sigma$)** com detecção automática de Volume Real (B3) e Tick Volume (Forex, Índices, Cripto).
   - **Fala 1 — Trem Institucional (`BUY_FLOW` / `SELL_FLOW`)**: Seguidor de fluxo quando o Z-Score de agressão e o Imbalance rompem o limiar estatístico a favor da VWAP.
   - **Fala 2 — Giro HFT na Média (`BUY_REVERT_VWAP` / `SELL_REVERT_VWAP`)**: Provisão de liquidez não-direcional nas bandas externas ($\pm 2\sigma$) quando o fluxo mostra exaustão.
   - **Bússola de Correlação Multi-Ativo**: Filtra entradas usando a cesta correlacionada (ex.: `PETR4` + `VALE3` para `WIN$N`, `Crypto_10#` para `BTCUSD#`).
   - **Guarda-Costas de Risco & Fim de Dia**: Trava de perda máxima diária, meta diária, botão **🚨 ZERAR TUDO AGORA** e zeração obrigatória no horário configurável (*"HFT sempre dorme zerado"*).

---

## 🚀 1. Como Subir Esta Pasta para o GitHub (No seu Windows)

Abra o terminal na pasta `C:\Projeto\Prado\prado-ubuntu-hft` e execute:

```powershell
cd C:\Projeto\Prado\prado-ubuntu-hft
git init
git add .
git commit -m "feat: Prado Institutional HFT Ubuntu Web Server & MT5 Quant Engine"
git branch -M main
git remote add origin https://github.com/josepradosoares/prado-ubuntu-hft.git
git push -u origin main
```

---

## 🐧 2. Como Instalar e Rodar no Servidor Ubuntu (1 Comando)

Conecte-se ao seu servidor Ubuntu via SSH e execute:

```bash
git clone https://github.com/josepradosoares/prado-ubuntu-hft.git
cd prado-ubuntu-hft
chmod +x install.sh
sudo ./install.sh
```

O script `install.sh` faz tudo sozinho:
- Instala Python 3, `venv`, dependências e firewall (`ufw`);
- Roda a suíte de testes automatizados (`pytest`) para garantir que a matemática VWAP/Fluxo e a API estão 100% íntegras;
- Cria e ativa o serviço `systemd` (`prado-hft-web.service`) para iniciar automaticamente com o Ubuntu e reiniciar sozinho caso caia;
- Disponibiliza o script `sudo bash scripts/setup_mt5_wine_docker.sh` para subir o terminal MetaTrader 5 Headless dentro do Ubuntu.

Depois de concluir, basta abrir no navegador:
- **URL:** `http://IP_DO_SEU_SERVIDOR_UBUNTU:8080`
- **Usuário:** `admin`
- **Senha:** `prado2026`

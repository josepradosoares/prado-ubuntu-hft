"""HTML templates for Prado Institutional HFT Login & Pure Mathematical Multi-Robot Command Center.
Designed following the frontend-design skill: institutional quant desk identity, tabular precision,
sentence-case clarity, and split-pane workspace hierarchy without generic SaaS-card clutter.
"""
from __future__ import annotations

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prado Institutional HFT — Acesso à Mesa Quantitativa</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {
      --obsidian: #0a0e14;
      --slate: #111722;
      --hairline: #1e2838;
      --bullion: #d4a853;
      --emerald: #10b981;
      --crimson: #e11d48;
      --text: #eef2f6;
      --muted: #8b9bb4;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--obsidian);
      background-image:
        linear-gradient(to right, rgba(30, 40, 56, 0.25) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(30, 40, 56, 0.25) 1px, transparent 1px);
      background-size: 48px 48px;
      color: var(--text);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .login-shell {
      width: 100%;
      max-width: 440px;
      background: var(--slate);
      border: 1px solid var(--hairline);
      border-top: 2px solid var(--bullion);
    }
    .login-header {
      padding: 28px 32px 20px;
      border-bottom: 1px solid var(--hairline);
    }
    .desk-tag {
      font-family: 'IBM Plex Mono', monospace;
      font-size: 12px;
      color: var(--bullion);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .desk-tag::before {
      content: "";
      width: 6px;
      height: 6px;
      background: var(--emerald);
      display: inline-block;
    }
    h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #fff;
      margin-bottom: 6px;
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .login-body {
      padding: 24px 32px 28px;
    }
    .field {
      margin-bottom: 18px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 6px;
    }
    input {
      width: 100%;
      background: var(--obsidian);
      border: 1px solid var(--hairline);
      color: #fff;
      padding: 11px 13px;
      font-size: 14px;
      font-family: 'IBM Plex Mono', monospace;
      outline: none;
      transition: border-color 0.15s;
    }
    input:focus {
      border-color: var(--bullion);
    }
    button {
      width: 100%;
      background: var(--bullion);
      color: #080b10;
      border: none;
      padding: 12px 16px;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
      transition: filter 0.15s;
    }
    button:hover {
      filter: brightness(1.08);
    }
    .err {
      color: #fda4af;
      background: rgba(225, 29, 72, 0.12);
      border-left: 3px solid var(--crimson);
      padding: 10px 12px;
      font-size: 13px;
      margin-bottom: 18px;
      display: none;
    }
    .login-footer {
      padding: 14px 32px;
      background: rgba(10, 14, 20, 0.55);
      border-top: 1px solid var(--hairline);
      font-family: 'IBM Plex Mono', monospace;
      font-size: 12px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <main class="login-shell">
    <div class="login-header">
      <div class="desk-tag">Motor quantitativo • Ubuntu Server</div>
      <h1>Prado Institutional HFT</h1>
      <p class="subtitle">Execução matemática pura de VWAP, bandas de desvio padrão e fluxo de agressão via Python MetaTrader 5.</p>
    </div>
    <div class="login-body">
      <div id="errBox" class="err"></div>
      <form id="loginForm">
        <div class="field">
          <label for="username">Usuário do operador</label>
          <input id="username" name="username" type="text" value="admin" required autocomplete="username" />
        </div>
        <div class="field">
          <label for="password">Senha de acesso</label>
          <input id="password" name="password" type="password" placeholder="••••••••" required autocomplete="current-password" />
        </div>
        <button type="submit">Entrar na mesa de execução</button>
      </form>
    </div>
    <div class="login-footer">
      <span>Acesso inicial: admin</span>
      <span>Senha: prado2026</span>
    </div>
  </main>
  <script>
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errBox = document.getElementById('errBox');
      errBox.style.display = 'none';
      const username = document.getElementById('username').value.trim();
      const password = document.getElementById('password').value;
      try {
        const res = await fetch('/api/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({username, password})
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          window.location.href = '/';
        } else {
          errBox.textContent = data.error || 'Credenciais inválidas. Verifique usuário e senha.';
          errBox.style.display = 'block';
        }
      } catch (err) {
        errBox.textContent = 'Não foi possível comunicar com o servidor Ubuntu.';
        errBox.style.display = 'block';
      }
    });
  </script>
</body>
</html>
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prado Institutional HFT — Mesa Quantitativa Multi-Robôs</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {
      --obsidian: #0a0e14;
      --slate: #101620;
      --slate-hover: #161e2c;
      --hairline: #1e2838;
      --bullion: #d4a853;
      --emerald: #10b981;
      --crimson: #e11d48;
      --cyan: #38bdf8;
      --text: #eef2f6;
      --muted: #8b9bb4;
      --mono: 'IBM Plex Mono', Consolas, monospace;
      --sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--obsidian);
      color: var(--text);
      font-family: var(--sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      font-size: 13px;
    }
    .num {
      font-family: var(--mono);
      font-variant-numeric: tabular-nums;
    }

    /* 1. Top Command & Telemetry Strip (Hero) */
    .command-bar {
      background: var(--slate);
      border-bottom: 1px solid var(--hairline);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 14px;
    }
    .identity {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .live-pulse {
      width: 8px;
      height: 8px;
      background: var(--emerald);
      box-shadow: 0 0 8px var(--emerald);
    }
    .identity-title {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #fff;
    }
    .engine-badge {
      font-family: var(--mono);
      font-size: 11px;
      color: var(--bullion);
      background: rgba(212, 168, 83, 0.1);
      border: 1px solid rgba(212, 168, 83, 0.35);
      padding: 2px 8px;
    }
    .command-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .account-switcher {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--obsidian);
      border: 1px solid var(--hairline);
      padding: 5px 10px;
    }
    .account-switcher span {
      font-size: 12px;
      color: var(--muted);
    }
    .account-switcher select {
      background: transparent;
      color: var(--bullion);
      border: none;
      font-family: var(--mono);
      font-weight: 600;
      font-size: 12px;
      outline: none;
      cursor: pointer;
    }
    .account-switcher select option {
      background: var(--slate);
      color: var(--text);
    }

    /* Telemetry Strip (Replaces generic SaaS KPI cards) */
    .telemetry-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      background: #0d121a;
      border-bottom: 1px solid var(--hairline);
    }
    .telemetry-cell {
      padding: 12px 20px;
      border-right: 1px solid var(--hairline);
      display: flex;
      flex-direction: column;
      justify-content: center;
    }
    .telemetry-cell:last-child { border-right: none; }
    .telemetry-label {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .telemetry-value {
      font-family: var(--mono);
      font-variant-numeric: tabular-nums;
      font-size: 18px;
      font-weight: 600;
      color: #fff;
    }
    .telemetry-sub {
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
      margin-top: 2px;
    }

    /* Navigation Bar */
    .workspace-nav {
      background: var(--slate);
      border-bottom: 1px solid var(--hairline);
      padding: 0 20px;
      display: flex;
      gap: 4px;
      overflow-x: auto;
    }
    .tab-btn {
      padding: 11px 16px;
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--muted);
      font-family: var(--sans);
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      white-space: nowrap;
      transition: color 0.15s, border-color 0.15s;
    }
    .tab-btn:hover {
      color: var(--text);
    }
    .tab-btn.active {
      color: var(--bullion);
      border-bottom-color: var(--bullion);
      background: rgba(212, 168, 83, 0.05);
    }

    /* Buttons */
    .btn {
      padding: 7px 12px;
      font-family: var(--sans);
      font-size: 12px;
      font-weight: 600;
      border: 1px solid var(--hairline);
      background: var(--slate);
      color: var(--text);
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .btn:hover { border-color: var(--bullion); }
    .btn-gold {
      background: var(--bullion);
      color: #080b10;
      border-color: var(--bullion);
      font-weight: 700;
    }
    .btn-gold:hover { filter: brightness(1.08); }
    .btn-green {
      background: rgba(16, 185, 129, 0.14);
      color: #34d399;
      border-color: rgba(16, 185, 129, 0.4);
    }
    .btn-green:hover { background: var(--emerald); color: #04130d; }
    .btn-danger {
      background: rgba(225, 29, 72, 0.14);
      color: #fda4af;
      border-color: rgba(225, 29, 72, 0.4);
    }
    .btn-danger:hover { background: var(--crimson); color: #fff; }
    .btn-cyan {
      background: rgba(56, 189, 248, 0.12);
      color: var(--cyan);
      border-color: rgba(56, 189, 248, 0.35);
    }
    .btn-cyan:hover { background: var(--cyan); color: #06131f; }

    /* Main Workspace Panels */
    .workspace {
      max-width: 1600px;
      width: 100%;
      margin: 0 auto;
      padding: 20px;
      flex: 1;
    }
    .tab-content { display: none; }
    .tab-content.active { display: grid; gap: 20px; }

    .panel {
      background: var(--slate);
      border: 1px solid var(--hairline);
    }
    .panel-header {
      padding: 12px 18px;
      border-bottom: 1px solid var(--hairline);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
      background: rgba(10, 14, 20, 0.35);
    }
    .panel-title {
      font-size: 14px;
      font-weight: 700;
      color: #fff;
    }
    .panel-subtitle {
      font-size: 12px;
      color: var(--muted);
      font-weight: 400;
    }
    .panel-body {
      padding: 18px;
      overflow-x: auto;
    }
    .panel-body.flush {
      padding: 0;
    }

    /* Data Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid var(--hairline);
    }
    th {
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      background: rgba(10, 14, 20, 0.45);
      white-space: nowrap;
    }
    th.num-col, td.num-col {
      text-align: right;
      font-family: var(--mono);
      font-variant-numeric: tabular-nums;
    }
    tr.clickable-row {
      cursor: pointer;
      transition: background 0.12s;
    }
    tr.clickable-row:hover td {
      background: var(--slate-hover);
    }

    /* Status Badges */
    .tag {
      display: inline-block;
      padding: 2px 8px;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 600;
      border: 1px solid transparent;
    }
    .tag-up { background: rgba(16, 185, 129, 0.14); color: #34d399; border-color: rgba(16, 185, 129, 0.35); }
    .tag-down { background: rgba(225, 29, 72, 0.14); color: #fda4af; border-color: rgba(225, 29, 72, 0.35); }
    .tag-hft { background: rgba(56, 189, 248, 0.14); color: var(--cyan); border-color: rgba(56, 189, 248, 0.35); }
    .tag-gold { background: rgba(212, 168, 83, 0.15); color: var(--bullion); border-color: rgba(212, 168, 83, 0.4); }
    .tag-neutral { background: rgba(139, 155, 180, 0.12); color: var(--muted); border-color: rgba(139, 155, 180, 0.25); }

    /* Forms */
    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }
    .field { position: relative; }
    .field label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 6px;
    }
    .field input, .field select {
      width: 100%;
      background: var(--obsidian);
      border: 1px solid var(--hairline);
      color: #fff;
      padding: 9px 12px;
      font-size: 13px;
      font-family: var(--sans);
    }
    .field input.mono-input {
      font-family: var(--mono);
    }
    .field input:focus, .field select:focus {
      border-color: var(--bullion);
      outline: none;
    }
    .field small {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-top: 4px;
    }

    /* Broker Server Autocomplete Dropdown */
    .autocomplete-box {
      position: absolute;
      top: 64px;
      left: 0;
      right: 0;
      background: #0c111a;
      border: 1px solid var(--bullion);
      max-height: 220px;
      overflow-y: auto;
      z-index: 600;
      display: none;
      box-shadow: 0 14px 32px rgba(0, 0, 0, 0.75);
    }
    .autocomplete-item {
      padding: 9px 12px;
      font-family: var(--mono);
      font-size: 12px;
      cursor: pointer;
      border-bottom: 1px solid var(--hairline);
      display: flex;
      justify-content: space-between;
    }
    .autocomplete-item:hover {
      background: rgba(212, 168, 83, 0.18);
      color: var(--bullion);
    }

    .mode-switch {
      display: inline-flex;
      border: 1px solid var(--hairline);
      background: var(--obsidian);
    }
    .mode-btn {
      padding: 6px 12px;
      border: none;
      font-family: var(--sans);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      background: transparent;
      color: var(--muted);
    }
    .mode-btn.active {
      background: var(--bullion);
      color: #080b10;
    }

    .formula-banner {
      background: var(--obsidian);
      border: 1px solid var(--hairline);
      border-left: 3px solid var(--cyan);
      padding: 12px 16px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--cyan);
      margin: 14px 0 8px;
    }
    .brief-note {
      background: rgba(212, 168, 83, 0.06);
      border-left: 3px solid var(--bullion);
      padding: 10px 14px;
      font-size: 12px;
      color: #cbd5e1;
      margin-bottom: 16px;
      line-height: 1.5;
    }
    .toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: var(--emerald);
      color: #04120c;
      padding: 11px 18px;
      font-weight: 700;
      font-size: 13px;
      display: none;
      box-shadow: 0 10px 25px rgba(0,0,0,0.6);
      z-index: 1000;
    }
  </style>
</head>
<body>
  <!-- Top Command Strip -->
  <header class="command-bar">
    <div class="identity">
      <div class="live-pulse"></div>
      <span class="identity-title">Prado Institutional HFT</span>
      <span class="engine-badge" id="connBadge">Inicializando motor...</span>
    </div>
    <div class="command-controls">
      <div class="account-switcher">
        <span>Conta ativa:</span>
        <select id="headerAccountSelect" onchange="quickSwitchAccount(this.value)"></select>
      </div>
      <button class="btn btn-cyan" onclick="resetDailyRisk()">Destravar risco diário</button>
      <button class="btn btn-green" id="toggleAutoBtn" onclick="toggleAutoTrading()">Execução automática: Ativa</button>
      <button class="btn btn-danger" onclick="panicFlatten()">Zerar todas as posições</button>
      <button class="btn" onclick="logout()">Sair</button>
    </div>
  </header>

  <!-- Live Telemetry Strip -->
  <section class="telemetry-strip">
    <div class="telemetry-cell">
      <div class="telemetry-label">
        <span>Credencial MetaTrader 5</span>
        <span id="kpiAccBadge" class="tag tag-hft">DEMO</span>
      </div>
      <div class="telemetry-value" id="kpiAccount">---</div>
      <div class="telemetry-sub" id="kpiServer">Servidor: ---</div>
    </div>
    <div class="telemetry-cell">
      <div class="telemetry-label"><span>Patrimônio líquido (Equity)</span></div>
      <div class="telemetry-value" id="kpiEquity">R$ 0,00</div>
      <div class="telemetry-sub" id="kpiBalance">Saldo base: R$ 0,00</div>
    </div>
    <div class="telemetry-cell">
      <div class="telemetry-label"><span>Frota de robôs matemáticos</span></div>
      <div class="telemetry-value" id="kpiBotsRunning" style="color:var(--bullion);">0 / 0</div>
      <div class="telemetry-sub" id="kpiRiskStatus">Guarda-costas: Operacional</div>
    </div>
    <div class="telemetry-cell">
      <div class="telemetry-label"><span>Vetor de correlação da cesta</span></div>
      <div class="telemetry-value" id="kpiCorr">0.0%</div>
      <div class="telemetry-sub" id="lastUpdate">Sincronizando ticks...</div>
    </div>
  </section>

  <!-- Workspace Navigation -->
  <nav class="workspace-nav">
    <button class="tab-btn active" onclick="switchTab('running-bots', this)">Robôs em execução (<span id="tabBotCount">0</span>)</button>
    <button class="tab-btn" onclick="switchTab('create-bot', this)">Criar ou editar robô</button>
    <button class="tab-btn" onclick="switchTab('backtest', this)">Backtest matemático tick a tick</button>
    <button class="tab-btn" onclick="switchTab('categories', this)">Categorias de ativos</button>
    <button class="tab-btn" onclick="switchTab('mt5', this)">Contas Demo e Real (MT5)</button>
    <button class="tab-btn" onclick="switchTab('monitor', this)">Matriz matemática VWAP e Z-Score</button>
  </nav>

  <main class="workspace">
    <!-- TAB 1: RUNNING BOTS & POSITIONS -->
    <div id="tab-running-bots" class="tab-content active">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Frota de robôs matemáticos em execução</div>
            <div class="panel-subtitle">Clique em qualquer linha para editar lote, conta ou parâmetros do robô</div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn btn-gold" onclick="startNewBotForm()">Novo robô matemático</button>
            <button class="btn btn-danger" onclick="deleteAllBots()">Apagar todos os robôs</button>
          </div>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Robô e modelo matemático</th>
                <th>Conta vinculada</th>
                <th>Ativo</th>
                <th class="num-col">Lote</th>
                <th class="num-col">Preço / VWAP (&Sigma;PV/&Sigma;V)</th>
                <th class="num-col">Z-Score / Imbalance</th>
                <th>Regime detectado</th>
                <th>Decisão</th>
                <th>Estado</th>
                <th>Controles operacionais</th>
              </tr>
            </thead>
            <tbody id="runningBotsBody"></tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Posições abertas no MetaTrader 5</div>
            <div class="panel-subtitle">Acompanhamento em tempo real com Stop Loss e Take Profit baseados no desvio padrão (&sigma;)</div>
          </div>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Bilhete</th>
                <th>Ativo</th>
                <th>Direção</th>
                <th class="num-col">Volume</th>
                <th class="num-col">Preço de entrada</th>
                <th class="num-col">Preço atual</th>
                <th class="num-col">Stop Loss (&sigma;)</th>
                <th class="num-col">Take Profit (&sigma;)</th>
                <th class="num-col">Resultado aberto</th>
                <th>Robô de origem</th>
                <th>Ação</th>
              </tr>
            </thead>
            <tbody id="positionsBody"></tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Histórico de operações encerradas na sessão</div>
            <div class="panel-subtitle">Registro auditável de saídas por Take Profit, Stop Loss ou encerramento manual</div>
          </div>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Bilhete</th>
                <th>Horário</th>
                <th>Ativo</th>
                <th>Direção</th>
                <th class="num-col">Volume</th>
                <th class="num-col">Entrada</th>
                <th class="num-col">Saída</th>
                <th class="num-col">Resultado líquido</th>
                <th>Motivo do encerramento</th>
                <th>Robô</th>
              </tr>
            </thead>
            <tbody id="dealsHistoryBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- TAB 2: CREATE / EDIT MATHEMATICAL BOT -->
    <div id="tab-create-bot" class="tab-content">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title" id="botFormTitle">Configurar novo robô matemático</div>
            <div class="panel-subtitle">Operação puramente algorítmica sobre arrays de ticks do MetaTrader 5, sem sobrecarga de gráficos</div>
          </div>
          <div class="mode-switch">
            <button type="button" id="btnModeMain" class="mode-btn active" onclick="setSymbolMode('PRINCIPAIS')">Ativos principais</button>
            <button type="button" id="btnModeAll" class="mode-btn" onclick="setSymbolMode('TODOS')">Todos os ativos da corretora</button>
          </div>
        </div>
        <div class="panel-body">
          <form id="createBotForm" onsubmit="createAndRunBot(event)">
            <input type="hidden" id="editing_bot_id" value="" />
            <div class="form-grid">
              <div class="field" style="grid-column: span 2;">
                <label for="bot_template_id">Algoritmo matemático do robô</label>
                <select id="bot_template_id" onchange="onBotTemplateChange()"></select>
              </div>
              <div class="field">
                <label for="bot_name">Nome identificador do robô</label>
                <input type="text" id="bot_name" placeholder="Ex: Desk BTC Fluxo Institucional" required />
              </div>
              <div class="field">
                <label for="bot_account_id">Conta MetaTrader 5 (Demo ou Real)</label>
                <select id="bot_account_id"></select>
              </div>
              <div class="field">
                <label for="bot_category_filter">Filtrar por categoria da corretora</label>
                <select id="bot_category_filter" onchange="loadBrokerSymbols()">
                  <option value="">Todas as categorias</option>
                </select>
              </div>
              <div class="field">
                <label for="bot_symbol">Ativo da corretora (<span id="symModeLabel">PRINCIPAIS</span>)</label>
                <select id="bot_symbol"></select>
                <small id="symCountHint">Carregando lista de ativos...</small>
              </div>
              <div class="field">
                <label for="bot_lot_size">Volume / Lote (ex: 0.01 cripto, 1.0 futuros)</label>
                <input type="number" step="0.01" id="bot_lot_size" class="mono-input" value="0.10" required />
              </div>
              <div class="field">
                <label for="bot_window_ticks">Janela de amostragem (ticks)</label>
                <input type="number" id="bot_window_ticks" class="mono-input" value="120" required />
              </div>
              <div class="field">
                <label for="bot_zscore">Limiar estatístico Z-Score (|Z|)</label>
                <input type="number" step="0.1" id="bot_zscore" class="mono-input" value="1.8" required />
              </div>
              <div class="field">
                <label for="bot_imbalance">Desequilíbrio mínimo (Imbalance)</label>
                <input type="number" step="0.05" id="bot_imbalance" class="mono-input" value="0.35" required />
              </div>
              <div class="field">
                <label for="bot_revert_sigma">Banda de reversão à média (&plusmn;k&middot;&sigma;)</label>
                <input type="number" step="0.1" id="bot_revert_sigma" class="mono-input" value="2.0" required />
              </div>
              <div class="field">
                <label for="bot_corr_basket">Cesta de correlação multi-ativo</label>
                <input type="text" id="bot_corr_basket" class="mono-input" value="PETR4, VALE3, Crypto_10#" />
              </div>
            </div>

            <div class="formula-banner" id="botFormulaDisplay">
              Equação: VWAP = Σ(Pᵢ·Vᵢ)/ΣVᵢ | Z = (μ_w - μ)/(σ/√(w/4))
            </div>
            <p id="botDescDisplay" style="font-size:12px;color:var(--muted);margin-bottom:18px;"></p>

            <div style="display:flex; gap:10px; flex-wrap:wrap;">
              <button type="submit" id="botSubmitBtn" class="btn btn-gold" style="padding:10px 20px;font-size:13px;">
                Criar e iniciar execução automática
              </button>
              <button type="button" id="botCancelEditBtn" class="btn" style="display:none;" onclick="cancelBotEdit()">
                Cancelar edição
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>

    <!-- TAB 3: MATHEMATICAL BACKTESTER -->
    <div id="tab-backtest" class="tab-content">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Simulador e backtester matemático tick a tick</div>
            <div class="panel-subtitle">Valide expectativa matemática, taxa de acerto, fator de lucro e drawdown antes de ligar o robô em produção</div>
          </div>
        </div>
        <div class="panel-body">
          <form onsubmit="runMathBacktest(event)">
            <div class="form-grid">
              <div class="field">
                <label for="bt_template_id">Modelo matemático</label>
                <select id="bt_template_id"></select>
              </div>
              <div class="field">
                <label for="bt_symbol">Ativo analisado</label>
                <select id="bt_symbol"></select>
              </div>
              <div class="field">
                <label for="bt_ticks">Amostra histórica (ticks)</label>
                <input type="number" id="bt_ticks" class="mono-input" value="1200" min="200" max="5000" required />
              </div>
              <div class="field">
                <label for="bt_capital">Capital inicial alocado</label>
                <input type="number" id="bt_capital" class="mono-input" value="50000" required />
              </div>
              <div class="field">
                <label for="bt_lots">Volume / Lote simulado</label>
                <input type="number" step="0.01" id="bt_lots" class="mono-input" value="1.0" required />
              </div>
              <div class="field">
                <label for="bt_zscore">Limiar Z-Score</label>
                <input type="number" step="0.1" id="bt_zscore" class="mono-input" value="1.5" required />
              </div>
              <div class="field">
                <label for="bt_imbalance">Imbalance mínimo</label>
                <input type="number" step="0.05" id="bt_imbalance" class="mono-input" value="0.25" required />
              </div>
              <div class="field">
                <label for="bt_sigma">Desvio padrão de reversão (&sigma;)</label>
                <input type="number" step="0.1" id="bt_sigma" class="mono-input" value="1.8" required />
              </div>
            </div>
            <div style="margin-top:18px;">
              <button type="submit" class="btn btn-gold" style="padding:10px 20px;">Executar backtest matemático</button>
            </div>
          </form>
        </div>
      </section>

      <section class="panel" id="btResultCard" style="display:none;">
        <div class="panel-header">
          <div class="panel-title">Relatório estatístico do backtest</div>
        </div>
        <div class="telemetry-strip" id="btKpiGrid" style="border-top:none;"></div>
        <div class="panel-body">
          <div class="formula-banner" id="btFormulaUsed" style="margin-top:0;"></div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Direção</th>
                <th>Gatilho matemático</th>
                <th class="num-col">Preço de entrada</th>
                <th class="num-col">Preço de saída</th>
                <th class="num-col">Resultado líquido</th>
                <th class="num-col">Curva de patrimônio</th>
              </tr>
            </thead>
            <tbody id="btTradesBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- TAB 4: BROKER SYMBOL CATEGORIES -->
    <div id="tab-categories" class="tab-content">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Criar ou editar categoria de ativos da corretora</div>
            <div class="panel-subtitle">Clique em qualquer categoria da lista abaixo para carregar seus ativos e editar</div>
          </div>
        </div>
        <div class="panel-body">
          <form onsubmit="saveCustomCategory(event)">
            <div class="form-grid">
              <div class="field">
                <label for="new_cat_name">Nome da categoria</label>
                <input type="text" id="new_cat_name" placeholder="Ex: Futuros B3 Alta Liquidez" required />
              </div>
              <div class="field">
                <label for="new_cat_symbols">Símbolos vinculados (separados por vírgula)</label>
                <input type="text" id="new_cat_symbols" class="mono-input" placeholder="Ex: WIN$N, WDO$N, IND$N, DOL$N" required />
              </div>
            </div>
            <div style="margin-top:14px;">
              <button type="submit" class="btn btn-gold">Salvar categoria de ativos</button>
            </div>
          </form>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title">Categorias cadastradas</div>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Categoria</th>
                <th>Ativos vinculados</th>
                <th>Controles</th>
              </tr>
            </thead>
            <tbody id="categoriesBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- TAB 5: DEMO & REAL MT5 ACCOUNTS -->
    <div id="tab-mt5" class="tab-content">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title" id="accountFormTitle">Contas Demo e Real do MetaTrader 5</div>
            <div class="panel-subtitle">Suas contas XM Global Demo (346595704) e Real (382177116) já estão cadastradas. Clique em qualquer conta para editar.</div>
          </div>
        </div>
        <div class="panel-body">
          <form id="mt5Form" onsubmit="saveMt5Account(event)">
            <input type="hidden" id="editing_account_id" value="" />
            <div class="form-grid">
              <div class="field">
                <label for="acc_type">Ambiente da conta</label>
                <select id="acc_type">
                  <option value="DEMO">Conta Demo (Homologação / Simulação)</option>
                  <option value="REAL">Conta Real (Produção na Corretora)</option>
                </select>
              </div>
              <div class="field">
                <label for="acc_label">Nome de identificação</label>
                <input type="text" id="acc_label" placeholder="Ex: Jose XM Global Demo" required />
              </div>
              <div class="field">
                <label for="mt5_login">Login da conta MT5</label>
                <input type="text" id="mt5_login" class="mono-input" placeholder="Ex: 346595704" required />
              </div>
              <div class="field">
                <label for="mt5_password">Senha da conta MT5</label>
                <input type="password" id="mt5_password" class="mono-input" placeholder="Deixe em branco ao editar para manter a atual" />
              </div>
              <div class="field">
                <label for="mt5_server">Servidor da corretora (autocompletar ao digitar)</label>
                <input
                  type="text"
                  id="mt5_server"
                  class="mono-input"
                  list="brokerServersDatalist"
                  placeholder="Digite XMGlobal, XP, Clear, ICMarkets..."
                  autocomplete="off"
                  oninput="onServerInputAutocomplete(this.value)"
                  onfocus="onServerInputAutocomplete(this.value)"
                  required
                />
                <datalist id="brokerServersDatalist"></datalist>
                <div id="serverAutocompleteBox" class="autocomplete-box"></div>
                <small>Digite as primeiras letras da corretora para carregar os servidores oficiais.</small>
              </div>
            </div>
            <div style="margin-top: 18px; display:flex; gap:10px;">
              <button type="submit" id="accSubmitBtn" class="btn btn-gold">Salvar conta e conectar</button>
              <button type="button" id="accCancelEditBtn" class="btn" style="display:none;" onclick="cancelAccountEdit()">Cancelar edição</button>
            </div>
          </form>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Contas disponíveis para operação</div>
            <div class="panel-subtitle">Alterne entre Demo e Real com um clique ou edite/apague credenciais</div>
          </div>
          <button class="btn btn-danger" onclick="deleteAllAccounts()">Apagar todas as contas</button>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Ambiente</th>
                <th>Identificação</th>
                <th>Login MT5</th>
                <th>Servidor da corretora</th>
                <th>Status</th>
                <th>Controles</th>
              </tr>
            </thead>
            <tbody id="accountsBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- TAB 6: VWAP & Z-SCORE MATHEMATICAL MATRIX -->
    <div id="tab-monitor" class="tab-content">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Matriz matemática em tempo real — VWAP, Bandas (&plusmn;1&sigma; / &plusmn;2&sigma;) e Z-Score</div>
            <div class="panel-subtitle">Leitura contínua de fluxo de agressão e desvio padrão para todos os ativos monitorados</div>
          </div>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Ativo</th>
                <th class="num-col">Preço atual (P)</th>
                <th class="num-col">VWAP (&Sigma;PV/&Sigma;V)</th>
                <th class="num-col">Banda -2&sigma;</th>
                <th class="num-col">Banda +2&sigma;</th>
                <th class="num-col">Desvio (&sigma;)</th>
                <th class="num-col">Imbalance</th>
                <th class="num-col">Z-Score</th>
                <th>Regime estatístico</th>
                <th>Sinal calculado</th>
              </tr>
            </thead>
            <tbody id="symbolsBody"></tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title">Registro de eventos do motor e guarda-costas de risco</div>
        </div>
        <div class="panel-body flush">
          <table>
            <thead>
              <tr>
                <th>Horário</th>
                <th>Subsistema</th>
                <th>Descrição do evento</th>
              </tr>
            </thead>
            <tbody id="eventsBody"></tbody>
          </table>
        </div>
      </section>
    </div>
  </main>

  <div id="toast" class="toast">Alterações salvas.</div>

  <script>
    let currentConfig = {};
    let currentSymbolMode = 'PRINCIPAIS';
    let botTemplates = [];
    let allBrokerServers = [];
    let latestBotsList = [];

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3400);
    }

    function switchTab(name, btn) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      if (btn) btn.classList.add('active');
    }

    function regimePill(regime) {
      if (regime === 'INSTITUTIONAL_TREND_UP') return '<span class="tag tag-up">Trem VWAP (+Z)</span>';
      if (regime === 'INSTITUTIONAL_TREND_DOWN') return '<span class="tag tag-down">Trem VWAP (-Z)</span>';
      if (regime === 'HFT_MEAN_REVERSION') return '<span class="tag tag-hft">Reversão HFT (&plusmn;2&sigma;)</span>';
      return '<span class="tag tag-neutral">Equilíbrio (0)</span>';
    }

    function actionPill(action) {
      if ((action || '').startsWith('BUY')) return `<span class="tag tag-up">${action}</span>`;
      if ((action || '').startsWith('SELL')) return `<span class="tag tag-down">${action}</span>`;
      return `<span class="tag tag-neutral">${action || 'WAIT'}</span>`;
    }

    async function loadBrokerServersCatalog() {
      const res = await fetch('/api/broker-servers');
      if (!res.ok) return;
      const data = await res.json();
      allBrokerServers = data.servers || [];
      const dl = document.getElementById('brokerServersDatalist');
      dl.innerHTML = allBrokerServers.map(s => `<option value="${s}"></option>`).join('');
    }

    function onServerInputAutocomplete(query) {
      const box = document.getElementById('serverAutocompleteBox');
      const q = (query || '').trim().toLowerCase();
      const matches = q
        ? allBrokerServers.filter(s => s.toLowerCase().includes(q))
        : allBrokerServers.slice(0, 18);
      if (matches.length === 0) {
        box.style.display = 'none';
        return;
      }
      box.innerHTML = matches.map(s => `
        <div class="autocomplete-item" onmousedown="selectBrokerServer('${s.replace(/'/g, "\\'")}')">
          <span>${s}</span>
          <span style="color:var(--muted);">MT5 Server</span>
        </div>
      `).join('');
      box.style.display = 'block';
    }

    function selectBrokerServer(serverName) {
      document.getElementById('mt5_server').value = serverName;
      document.getElementById('serverAutocompleteBox').style.display = 'none';
    }

    document.addEventListener('click', (e) => {
      const box = document.getElementById('serverAutocompleteBox');
      const inp = document.getElementById('mt5_server');
      if (box && e.target !== inp && !box.contains(e.target)) {
        box.style.display = 'none';
      }
    });

    async function loadBotTemplates() {
      const res = await fetch('/api/bot-templates');
      if (!res.ok) return;
      const data = await res.json();
      botTemplates = data.templates || [];
      const selCreate = document.getElementById('bot_template_id');
      const selBt = document.getElementById('bt_template_id');
      const opts = botTemplates.map(t => `<option value="${t.template_id}">${t.name}</option>`).join('');
      selCreate.innerHTML = opts;
      selBt.innerHTML = opts;
      onBotTemplateChange();
    }

    function onBotTemplateChange() {
      const id = document.getElementById('bot_template_id').value;
      const tpl = botTemplates.find(t => t.template_id === id) || botTemplates[0];
      if (!tpl) return;
      if (!document.getElementById('editing_bot_id').value) {
        document.getElementById('bot_window_ticks').value = tpl.window_ticks;
        document.getElementById('bot_zscore').value = tpl.zscore_threshold;
        document.getElementById('bot_imbalance').value = tpl.imbalance_threshold;
        document.getElementById('bot_revert_sigma').value = tpl.revert_sigma;
      }
      document.getElementById('botFormulaDisplay').textContent = `Equação: ${tpl.formula}`;
      document.getElementById('botDescDisplay').textContent = tpl.description;
    }

    async function setSymbolMode(mode) {
      currentSymbolMode = mode;
      document.getElementById('symModeLabel').textContent = mode;
      document.getElementById('btnModeMain').classList.toggle('active', mode === 'PRINCIPAIS');
      document.getElementById('btnModeAll').classList.toggle('active', mode === 'TODOS');
      await loadBrokerSymbols();
    }

    async function loadBrokerSymbols(selectedSymbol) {
      const cat = document.getElementById('bot_category_filter').value;
      const url = `/api/symbols?mode=${encodeURIComponent(currentSymbolMode)}&category=${encodeURIComponent(cat)}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const syms = data.symbols || [];
      const htmlOpts = syms.map(s => `<option value="${s.name}">${s.name} — ${s.description || s.category}</option>`).join('');
      const botSymSel = document.getElementById('bot_symbol');
      botSymSel.innerHTML = htmlOpts;
      if (selectedSymbol) botSymSel.value = selectedSymbol;
      const btSym = document.getElementById('bt_symbol');
      if (!btSym.innerHTML) btSym.innerHTML = htmlOpts;
      document.getElementById('symCountHint').textContent = `${syms.length} ativo(s) carregado(s) no modo ${currentSymbolMode}.`;
    }

    function renderCategoriesAndAccounts(categories, accounts, activeAccountId) {
      const catSel = document.getElementById('bot_category_filter');
      const prevCat = catSel.value;
      const catNames = Object.keys(categories || {});
      catSel.innerHTML = '<option value="">Todas as categorias</option>' +
        catNames.map(c => `<option value="${c}">${c} (${(categories[c] || []).length})</option>`).join('');
      if (catNames.includes(prevCat)) catSel.value = prevCat;

      const catBody = document.getElementById('categoriesBody');
      catBody.innerHTML = catNames.map(c => {
        const symsStr = (categories[c] || []).join(', ');
        return `
          <tr class="clickable-row" onclick="editCategory('${c.replace(/'/g, "\\'")}', '${symsStr.replace(/'/g, "\\'")}')">
            <td><strong>${c}</strong></td>
            <td>${(categories[c] || []).map(s => `<span class="tag tag-neutral" style="margin:2px;">${s}</span>`).join(' ')}</td>
            <td onclick="event.stopPropagation();" style="display:flex;gap:6px;">
              <button class="btn btn-cyan" onclick="editCategory('${c.replace(/'/g, "\\'")}', '${symsStr.replace(/'/g, "\\'")}')">Editar</button>
              <button class="btn btn-danger" onclick="deleteCategory('${c.replace(/'/g, "\\'")}')">Apagar</button>
            </td>
          </tr>
        `;
      }).join('');

      const accSel = document.getElementById('bot_account_id');
      const hdrSel = document.getElementById('headerAccountSelect');
      const list = accounts || [];
      if (list.length === 0) {
        const defOpt = '<option value="default">[DEMO] Simulador Quantitativo</option>';
        accSel.innerHTML = defOpt;
        hdrSel.innerHTML = defOpt;
      } else {
        const opts = list.map(a => {
          const badge = a.account_type === 'REAL' ? 'REAL' : 'DEMO';
          const selected = a.account_id === activeAccountId ? 'selected' : '';
          return `<option value="${a.account_id}" ${selected}>[${badge}] ${a.label} (${a.mt5_login} @ ${a.mt5_server})</option>`;
        }).join('');
        accSel.innerHTML = opts;
        hdrSel.innerHTML = opts;
      }

      const accBody = document.getElementById('accountsBody');
      if (list.length === 0) {
        accBody.innerHTML = '<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:20px;">Nenhuma conta cadastrada. Preencha os dados da corretora acima para adicionar uma conta Demo ou Real.</td></tr>';
      } else {
        accBody.innerHTML = list.map(a => {
          const isReal = a.account_type === 'REAL';
          const isActive = a.account_id === activeAccountId;
          return `
            <tr class="clickable-row" onclick="editAccount('${a.account_id}')">
              <td><span class="tag ${isReal ? 'tag-gold' : 'tag-hft'}">${isReal ? 'Conta Real' : 'Conta Demo'}</span></td>
              <td><strong>${a.label}</strong></td>
              <td class="num">${a.mt5_login}</td>
              <td class="num"><strong>${a.mt5_server}</strong></td>
              <td>${isActive ? '<span class="tag tag-up">Ativa na mesa</span>' : '<span class="tag tag-neutral">Disponível</span>'}</td>
              <td onclick="event.stopPropagation();" style="display:flex;gap:6px;flex-wrap:wrap;">
                ${isActive
                  ? '<button class="btn" disabled>Em uso</button>'
                  : `<button class="btn btn-gold" onclick="quickSwitchAccount('${a.account_id}')">Usar conta</button>`
                }
                <button class="btn btn-cyan" onclick="editAccount('${a.account_id}')">Editar</button>
                <button class="btn btn-danger" onclick="deleteAccount('${a.account_id}')">Apagar</button>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    function editCategory(catName, symsCsv) {
      document.getElementById('new_cat_name').value = catName;
      document.getElementById('new_cat_symbols').value = symsCsv;
      document.getElementById('new_cat_name').focus();
      showToast(`Editando categoria "${catName}".`);
    }

    function editAccount(accountId) {
      const list = currentConfig.accounts || [];
      const acc = list.find(a => a.account_id === accountId);
      if (!acc) return;
      document.getElementById('editing_account_id').value = acc.account_id;
      document.getElementById('acc_type').value = acc.account_type || 'DEMO';
      document.getElementById('acc_label').value = acc.label || '';
      document.getElementById('mt5_login').value = acc.mt5_login || '';
      document.getElementById('mt5_password').value = '';
      document.getElementById('mt5_server').value = acc.mt5_server || '';
      document.getElementById('accountFormTitle').textContent = `Editando conta: ${acc.label} (${acc.mt5_login})`;
      document.getElementById('accSubmitBtn').textContent = 'Salvar alterações da conta';
      document.getElementById('accCancelEditBtn').style.display = 'inline-block';
      switchTab('mt5', document.querySelectorAll('.tab-btn')[4]);
      showToast(`Conta ${acc.mt5_login} carregada para edição.`);
    }

    function cancelAccountEdit() {
      document.getElementById('editing_account_id').value = '';
      document.getElementById('acc_label').value = '';
      document.getElementById('mt5_login').value = '';
      document.getElementById('mt5_password').value = '';
      document.getElementById('mt5_server').value = '';
      document.getElementById('accountFormTitle').textContent = 'Contas Demo e Real do MetaTrader 5';
      document.getElementById('accSubmitBtn').textContent = 'Salvar conta e conectar';
      document.getElementById('accCancelEditBtn').style.display = 'none';
    }

    async function deleteAccount(accountId) {
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'DELETE', account_id: accountId})
      });
      const data = await res.json();
      if (data.ok) {
        currentConfig.accounts = data.accounts;
        renderCategoriesAndAccounts(currentConfig.custom_categories, data.accounts, currentConfig.active_account_id);
        showToast('Conta apagada.');
      }
    }

    async function deleteAllAccounts() {
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'DELETE_ALL'})
      });
      const data = await res.json();
      if (data.ok) {
        currentConfig.accounts = [];
        renderCategoriesAndAccounts(currentConfig.custom_categories, [], '');
        showToast('Todas as contas foram apagadas.');
      }
    }

    async function deleteAllBots() {
      const res = await fetch('/api/bots/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'DELETE_ALL'})
      });
      const data = await res.json();
      if (data.ok) {
        showToast('Todos os robôs foram apagados.');
        refreshStatus();
      }
    }

    function startNewBotForm() {
      cancelBotEdit();
      switchTab('create-bot', document.querySelectorAll('.tab-btn')[1]);
    }

    async function editBot(botId) {
      const bot = latestBotsList.find(b => b.bot_id === botId);
      if (!bot) return;
      document.getElementById('editing_bot_id').value = bot.bot_id;
      document.getElementById('bot_template_id').value = bot.bot_template_id || 'WALL_STREET_HYBRID_BOTH';
      document.getElementById('bot_name').value = bot.name || '';
      document.getElementById('bot_account_id').value = bot.account_id || currentConfig.active_account_id;
      document.getElementById('bot_category_filter').value = '';
      await loadBrokerSymbols(bot.symbol);
      document.getElementById('bot_symbol').value = bot.symbol;
      document.getElementById('bot_lot_size').value = bot.lot_size;
      document.getElementById('bot_window_ticks').value = bot.window_ticks || 120;
      document.getElementById('bot_zscore').value = bot.zscore_threshold || 1.8;
      document.getElementById('bot_imbalance').value = bot.imbalance_threshold || 0.35;
      document.getElementById('bot_revert_sigma').value = bot.revert_sigma || 2.0;
      document.getElementById('bot_corr_basket').value = (bot.correlated_basket || []).join(', ');
      document.getElementById('botFormTitle').textContent = `Editando robô: ${bot.name} (${bot.symbol})`;
      document.getElementById('botSubmitBtn').textContent = 'Salvar alterações do robô';
      document.getElementById('botCancelEditBtn').style.display = 'inline-block';
      switchTab('create-bot', document.querySelectorAll('.tab-btn')[1]);
      showToast(`Robô "${bot.name}" carregado para edição.`);
    }

    function cancelBotEdit() {
      document.getElementById('editing_bot_id').value = '';
      document.getElementById('bot_name').value = '';
      document.getElementById('bot_lot_size').value = '0.10';
      document.getElementById('botFormTitle').textContent = 'Configurar novo robô matemático';
      document.getElementById('botSubmitBtn').textContent = 'Criar e iniciar execução automática';
      document.getElementById('botCancelEditBtn').style.display = 'none';
      onBotTemplateChange();
    }

    async function resetDailyRisk() {
      const res = await fetch('/api/risk/reset', {method: 'POST'});
      const data = await res.json();
      if (data.ok) {
        showToast('Trava de perda diária resetada e robôs liberados.');
        refreshStatus();
      }
    }

    async function quickSwitchAccount(accountId) {
      if (!accountId || accountId === 'default') return;
      const res = await fetch('/api/accounts/select', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({account_id: accountId})
      });
      const data = await res.json();
      if (data.ok) {
        currentConfig.active_account_id = accountId;
        renderCategoriesAndAccounts(currentConfig.custom_categories, data.accounts, accountId);
        showToast(`Conta ativa alterada para ${data.active_account.label}.`);
        refreshStatus();
      }
    }

    async function loadConfig() {
      const res = await fetch('/api/config');
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      currentConfig = data.config || {};
      await loadBrokerServersCatalog();
      await loadBotTemplates();
      renderCategoriesAndAccounts(
        currentConfig.custom_categories,
        currentConfig.accounts,
        currentConfig.active_account_id
      );
      await loadBrokerSymbols();
    }

    async function refreshStatus() {
      try {
        const res = await fetch('/api/status');
        if (res.status === 401) { window.location.href = '/login'; return; }
        const snap = await res.json();
        const acc = snap.account || {};
        const accType = acc.account_type || 'DEMO';
        document.getElementById('connBadge').textContent = `${acc.backend || 'ONLINE'} • ${acc.login || ''}`;
        const accBadge = document.getElementById('kpiAccBadge');
        accBadge.textContent = accType;
        accBadge.className = `tag ${accType === 'REAL' ? 'tag-gold' : 'tag-hft'}`;
        document.getElementById('kpiAccount').textContent = acc.login || '---';
        document.getElementById('kpiServer').textContent = `Servidor: ${acc.server || '---'}`;
        document.getElementById('kpiEquity').textContent = `${acc.currency || 'R$'} ${(acc.equity || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        document.getElementById('kpiBalance').textContent = `Saldo base: ${(acc.balance || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;

        const bots = snap.bots || [];
        latestBotsList = bots;
        const runningCount = bots.filter(b => b.status === 'RUNNING').length;
        document.getElementById('kpiBotsRunning').textContent = `${runningCount} ativos / ${bots.length} total`;
        document.getElementById('tabBotCount').textContent = runningCount;

        const rStatus = document.getElementById('kpiRiskStatus');
        rStatus.textContent = snap.risk_status || 'Operacional';
        rStatus.style.color = snap.risk_locked ? 'var(--crimson)' : 'var(--emerald)';

        const corr = Number(snap.correlation_bias || 0);
        const kpiCorr = document.getElementById('kpiCorr');
        kpiCorr.textContent = `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(1)}%`;
        kpiCorr.style.color = corr > 0.15 ? 'var(--emerald)' : (corr < -0.15 ? 'var(--crimson)' : '#fff');

        const autoBtn = document.getElementById('toggleAutoBtn');
        if (snap.auto_trading_enabled) {
          autoBtn.textContent = 'Execução automática: Ativa';
          autoBtn.className = 'btn btn-green';
        } else {
          autoBtn.textContent = 'Execução automática: Pausada';
          autoBtn.className = 'btn btn-danger';
        }

        const botsBody = document.getElementById('runningBotsBody');
        if (bots.length === 0) {
          botsBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:24px;">Nenhum robô matemático configurado. Acesse a aba <strong>Criar ou editar robô</strong> para selecionar um algoritmo e iniciar a execução.</td></tr>';
        } else {
          botsBody.innerHTML = bots.map(b => {
            const isRun = b.status === 'RUNNING';
            const bType = b.account_type || 'DEMO';
            return `
              <tr class="clickable-row" onclick="editBot('${b.bot_id}')" title="Clique para editar este robô">
                <td>
                  <strong>${b.name}</strong><br/>
                  <small style="color:var(--cyan);font-family:var(--mono);">${b.bot_template_name || b.operation_mode}</small><br/>
                  <small style="color:var(--muted)">Ordens disparadas: ${b.trades_executed || 0}</small>
                </td>
                <td><span class="tag ${bType === 'REAL' ? 'tag-gold' : 'tag-hft'}">${bType}</span><br/><small style="color:var(--muted)">${b.account_label || ''}</small></td>
                <td><strong class="num">${b.symbol}</strong><br/><small style="color:var(--muted)">${b.category || ''}</small></td>
                <td class="num-col"><strong>${b.lot_size}</strong></td>
                <td class="num-col"><strong>${b.last_price || '---'}</strong><br/><small style="color:var(--bullion)">VWAP: ${b.vwap || '---'}</small></td>
                <td class="num-col">Z: <strong>${Number(b.aggression_zscore || 0).toFixed(2)}</strong><br/>Imb: ${(Number(b.imbalance_ratio || 0) * 100).toFixed(1)}%</td>
                <td>${regimePill(b.last_regime)}</td>
                <td>${actionPill(b.last_signal)}</td>
                <td>
                  <span class="tag ${isRun ? 'tag-up' : 'tag-down'}">
                    ${isRun ? 'Em execução' : 'Pausado'}
                  </span>
                </td>
                <td onclick="event.stopPropagation();" style="display:flex;gap:5px;flex-wrap:wrap;">
                  <button class="btn btn-green" title="Disparar compra imediata" onclick="botAction('${b.bot_id}', 'FIRE_BUY')">Comprar</button>
                  <button class="btn btn-danger" title="Disparar venda imediata" onclick="botAction('${b.bot_id}', 'FIRE_SELL')">Vender</button>
                  <button class="btn btn-cyan" onclick="editBot('${b.bot_id}')">Editar</button>
                  ${isRun
                    ? `<button class="btn btn-danger" onclick="botAction('${b.bot_id}', 'STOP')">Pausar</button>`
                    : `<button class="btn btn-green" onclick="botAction('${b.bot_id}', 'START')">Iniciar</button>`
                  }
                  <button class="btn btn-danger" onclick="botAction('${b.bot_id}', 'DELETE')">Apagar</button>
                </td>
              </tr>
            `;
          }).join('');
        }

        document.getElementById('lastUpdate').textContent = `Último ciclo: ${snap.timestamp || ''}`;

        const symBody = document.getElementById('symbolsBody');
        const syms = Object.values(snap.symbols || {});
        symBody.innerHTML = syms.map(s => `
          <tr>
            <td class="num"><strong>${s.symbol}</strong></td>
            <td class="num-col"><strong>${s.last_price}</strong></td>
            <td class="num-col" style="color:var(--bullion);font-weight:600;">${s.vwap}</td>
            <td class="num-col" style="color:var(--emerald);">${s.lower_2}</td>
            <td class="num-col" style="color:var(--crimson);">${s.upper_2}</td>
            <td class="num-col">${s.distance_sigma >= 0 ? '+' : ''}${s.distance_sigma}&sigma;</td>
            <td class="num-col" style="color:${s.imbalance_ratio >= 0 ? 'var(--emerald)' : 'var(--crimson)'};font-weight:600;">
              ${(s.imbalance_ratio * 100).toFixed(1)}%
            </td>
            <td class="num-col" style="font-weight:600;">${s.aggression_zscore.toFixed(2)}</td>
            <td>${regimePill(s.regime)}</td>
            <td>${actionPill(s.action)}</td>
          </tr>
        `).join('');

        const posBody = document.getElementById('positionsBody');
        const positions = snap.positions || [];
        if (positions.length === 0) {
          posBody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--muted);padding:18px;">Nenhuma posição aberta no momento. O robô abrirá automaticamente quando o Z-Score e o Imbalance atingirem o limiar, ou clique em Comprar / Vender na linha do robô.</td></tr>';
        } else {
          posBody.innerHTML = positions.map(p => `
            <tr>
              <td class="num">#${p.ticket}</td>
              <td class="num"><strong>${p.symbol}</strong></td>
              <td><span class="tag ${p.type === 'BUY' ? 'tag-up' : 'tag-down'}">${p.type}</span></td>
              <td class="num-col">${p.volume}</td>
              <td class="num-col">${p.price_open}</td>
              <td class="num-col">${p.price_current}</td>
              <td class="num-col">${p.sl}</td>
              <td class="num-col">${p.tp}</td>
              <td class="num-col" style="font-weight:600;color:${p.profit >= 0 ? 'var(--emerald)' : 'var(--crimson)'};">${p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}</td>
              <td>${p.comment}</td>
              <td><button class="btn btn-danger" onclick="closeSinglePosition(${p.ticket})">Encerrar</button></td>
            </tr>
          `).join('');
        }

        const dealsBody = document.getElementById('dealsHistoryBody');
        const deals = snap.deals_history || [];
        if (deals.length === 0) {
          dealsBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:18px;">Nenhuma operação encerrada nesta sessão.</td></tr>';
        } else {
          dealsBody.innerHTML = deals.map(d => `
            <tr>
              <td class="num">#${d.ticket}</td>
              <td class="num" style="color:var(--muted);">${d.time}</td>
              <td class="num"><strong>${d.symbol}</strong></td>
              <td><span class="tag ${d.type === 'BUY' ? 'tag-up' : 'tag-down'}">${d.type}</span></td>
              <td class="num-col">${d.volume}</td>
              <td class="num-col">${d.price_open}</td>
              <td class="num-col">${d.price_close}</td>
              <td class="num-col" style="font-weight:600;color:${d.profit >= 0 ? 'var(--emerald)' : 'var(--crimson)'};">${d.profit >= 0 ? '+' : ''}${Number(d.profit).toFixed(2)}</td>
              <td><span class="tag tag-neutral">${d.reason}</span></td>
              <td>${d.comment}</td>
            </tr>
          `).join('');
        }

        const evBody = document.getElementById('eventsBody');
        evBody.innerHTML = (snap.events || []).map(ev => `
          <tr>
            <td class="num" style="color:var(--muted);width:110px;">${ev.time}</td>
            <td style="width:150px;"><span class="tag tag-neutral">${ev.category}</span></td>
            <td>${ev.message}</td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function createAndRunBot(e) {
      e.preventDefault();
      const editingId = document.getElementById('editing_bot_id').value.trim();
      const catSel = document.getElementById('bot_category_filter');
      const payload = {
        bot_template_id: document.getElementById('bot_template_id').value,
        name: document.getElementById('bot_name').value.trim(),
        account_id: document.getElementById('bot_account_id').value,
        symbol: document.getElementById('bot_symbol').value,
        category: catSel.value || 'Corretora MT5',
        lot_size: Number(document.getElementById('bot_lot_size').value || 0.10),
        window_ticks: Number(document.getElementById('bot_window_ticks').value || 120),
        zscore_threshold: Number(document.getElementById('bot_zscore').value || 1.8),
        imbalance_threshold: Number(document.getElementById('bot_imbalance').value || 0.35),
        revert_sigma: Number(document.getElementById('bot_revert_sigma').value || 2.0),
        correlated_basket: document.getElementById('bot_corr_basket').value.split(',').map(s => s.trim()).filter(Boolean)
      };
      if (editingId) {
        payload.bot_id = editingId;
      } else {
        payload.auto_start = true;
      }
      const res = await fetch('/api/bots', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        showToast(editingId ? `Robô "${data.bot.name}" atualizado.` : `Robô "${data.bot.name}" criado e em execução.`);
        cancelBotEdit();
        switchTab('running-bots', document.querySelectorAll('.tab-btn')[0]);
        refreshStatus();
      }
    }

    async function runMathBacktest(e) {
      e.preventDefault();
      const payload = {
        bot_template_id: document.getElementById('bt_template_id').value,
        symbol: document.getElementById('bt_symbol').value,
        tick_count: Number(document.getElementById('bt_ticks').value || 1200),
        initial_capital: Number(document.getElementById('bt_capital').value || 50000),
        lot_size: Number(document.getElementById('bt_lots').value || 1.0),
        zscore_threshold: Number(document.getElementById('bt_zscore').value || 1.5),
        imbalance_threshold: Number(document.getElementById('bt_imbalance').value || 0.25),
        revert_sigma: Number(document.getElementById('bt_sigma').value || 1.8)
      };
      const res = await fetch('/api/backtest', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok && data.report) {
        const r = data.report;
        document.getElementById('btResultCard').style.display = 'block';
        document.getElementById('btFormulaUsed').textContent = `Modelo avaliado: ${r.bot_template_name} | Equação: ${r.formula}`;
        const isPos = r.net_profit >= 0;
        document.getElementById('btKpiGrid').innerHTML = `
          <div class="telemetry-cell">
            <div class="telemetry-label"><span>Resultado líquido (${r.symbol})</span></div>
            <div class="telemetry-value" style="color:${isPos ? 'var(--emerald)' : 'var(--crimson)'};">${isPos ? '+' : ''}${r.net_profit.toFixed(2)} (${r.return_pct}%)</div>
            <div class="telemetry-sub">Patrimônio final: ${r.final_equity.toFixed(2)}</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-label"><span>Taxa de acerto (Win Rate)</span></div>
            <div class="telemetry-value">${r.win_rate_pct}%</div>
            <div class="telemetry-sub">${r.winning_trades} ganhos / ${r.losing_trades} perdas (${r.total_trades} operações)</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-label"><span>Fator de lucro (Profit Factor)</span></div>
            <div class="telemetry-value" style="color:var(--bullion);">${r.profit_factor}</div>
            <div class="telemetry-sub">Lucro bruto: +${r.gross_profit} / Perda bruta: -${r.gross_loss}</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-label"><span>Drawdown máximo</span></div>
            <div class="telemetry-value" style="color:var(--crimson);">-${r.max_drawdown.toFixed(2)}</div>
            <div class="telemetry-sub">${r.ticks_processed} ticks avaliados</div>
          </div>
        `;
        const tbody = document.getElementById('btTradesBody');
        const trades = r.trades || [];
        if (trades.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:16px;">Nenhuma operação disparada com esses parâmetros. Reduza o Z-Score para aumentar a sensibilidade.</td></tr>';
        } else {
          tbody.innerHTML = trades.map(t => `
            <tr>
              <td class="num">#${t.id}</td>
              <td><span class="tag ${t.type === 'BUY' ? 'tag-up' : 'tag-down'}">${t.type}</span></td>
              <td class="num">${t.signal}</td>
              <td class="num-col">${t.entry}</td>
              <td class="num-col">${t.exit}</td>
              <td class="num-col" style="font-weight:600;color:${t.pnl >= 0 ? 'var(--emerald)' : 'var(--crimson)'};">${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</td>
              <td class="num-col"><strong>${t.equity_after.toFixed(2)}</strong></td>
            </tr>
          `).join('');
        }
        showToast(`Backtest concluído em ${r.symbol}: ${r.total_trades} operações.`);
      }
    }

    async function botAction(botId, action) {
      const res = await fetch('/api/bots/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({bot_id: botId, action})
      });
      const data = await res.json();
      if (data.ok) {
        const msgMap = {
          'START': 'Robô iniciado.',
          'STOP': 'Robô pausado.',
          'DELETE': 'Robô apagado.',
          'FIRE_BUY': 'Ordem de compra disparada.',
          'FIRE_SELL': 'Ordem de venda disparada.'
        };
        showToast(msgMap[action] || 'Ação executada.');
        refreshStatus();
      }
    }

    async function saveCustomCategory(e) {
      e.preventDefault();
      const category_name = document.getElementById('new_cat_name').value.trim();
      const symbols = document.getElementById('new_cat_symbols').value.split(',').map(s => s.trim()).filter(Boolean);
      const res = await fetch('/api/categories', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'SAVE', category_name, symbols})
      });
      const data = await res.json();
      if (data.ok) {
        document.getElementById('new_cat_name').value = '';
        document.getElementById('new_cat_symbols').value = '';
        renderCategoriesAndAccounts(data.categories, currentConfig.accounts, currentConfig.active_account_id);
        await loadBrokerSymbols();
        showToast(`Categoria "${category_name}" salva.`);
      }
    }

    async function deleteCategory(catName) {
      const res = await fetch('/api/categories', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'DELETE', category_name: catName})
      });
      const data = await res.json();
      if (data.ok) {
        renderCategoriesAndAccounts(data.categories, currentConfig.accounts, currentConfig.active_account_id);
        await loadBrokerSymbols();
        showToast(`Categoria "${catName}" apagada.`);
      }
    }

    async function saveMt5Account(e) {
      e.preventDefault();
      const editingId = document.getElementById('editing_account_id').value.trim();
      const payload = {
        account_type: document.getElementById('acc_type').value,
        label: document.getElementById('acc_label').value.trim(),
        mt5_login: document.getElementById('mt5_login').value.trim(),
        mt5_password: document.getElementById('mt5_password').value,
        mt5_server: document.getElementById('mt5_server').value.trim(),
        connect_now: true
      };
      if (editingId) payload.account_id = editingId;

      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        currentConfig.accounts = data.accounts;
        currentConfig.active_account_id = data.account.account_id;
        cancelAccountEdit();
        renderCategoriesAndAccounts(currentConfig.custom_categories, data.accounts, data.account.account_id);
        await loadBrokerServersCatalog();
        await loadBrokerSymbols();
        showToast(`Conta "${data.account.label}" salva e conectada.`);
        refreshStatus();
      }
    }

    async function toggleAutoTrading() {
      const nextState = !(currentConfig.auto_trading_enabled ?? true);
      currentConfig.auto_trading_enabled = nextState;
      await fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({auto_trading_enabled: nextState})
      });
      showToast(nextState ? 'Execução automática ativada.' : 'Execução automática pausada.');
      refreshStatus();
    }

    async function panicFlatten() {
      const res = await fetch('/api/flatten', {method: 'POST'});
      const data = await res.json();
      showToast(data.message || 'Todas as posições foram encerradas.');
      refreshStatus();
    }

    async function closeSinglePosition(ticket) {
      const res = await fetch('/api/flatten', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ticket})
      });
      const data = await res.json();
      showToast(data.message || `Posição #${ticket} encerrada.`);
      refreshStatus();
    }

    async function logout() {
      await fetch('/api/logout', {method: 'POST'});
      window.location.href = '/login';
    }

    loadConfig();
    refreshStatus();
    setInterval(refreshStatus, 1000);
  </script>
</body>
</html>
"""

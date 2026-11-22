"""HTML templates for Prado Institutional HFT Login & Deriv Multipliers Command Center.
Designed under the anthropics/frontend-design skill: institutional quant desk identity,
tabular numeric alignment, single-line action strips, and dedicated Deriv Token Vault.
"""
from __future__ import annotations

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prado Institutional HFT — Acesso à Mesa Deriv</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {
      --canvas: #080b10;
      --surface: #0e131b;
      --rule: #1c2533;
      --gold: #c89d42;
      --bid: #0ca678;
      --ask: #e03131;
      --ink: #ecf0f5;
      --muted: #7f8ea3;
      --mono: 'IBM Plex Mono', Consolas, monospace;
      --sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--canvas);
      background-image:
        linear-gradient(to right, rgba(28, 37, 51, 0.28) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(28, 37, 51, 0.28) 1px, transparent 1px);
      background-size: 40px 40px;
      color: var(--ink);
      font-family: var(--sans);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .login-frame {
      width: 100%;
      max-width: 420px;
      background: var(--surface);
      border: 1px solid var(--rule);
      border-top: 2px solid var(--gold);
    }
    .login-head { padding: 28px 32px 20px; border-bottom: 1px solid var(--rule); }
    .status-line {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--gold);
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-line::before { content: ""; width: 6px; height: 6px; background: var(--bid); display: inline-block; }
    h1 { font-size: 21px; font-weight: 700; letter-spacing: -0.02em; color: #fff; margin-bottom: 6px; }
    .lead { color: var(--muted); font-size: 13px; line-height: 1.5; }
    .login-form-wrap { padding: 24px 32px 28px; }
    .field { margin-bottom: 18px; }
    label { display: block; font-size: 13px; font-weight: 500; color: var(--ink); margin-bottom: 6px; }
    input {
      width: 100%;
      background: var(--canvas);
      border: 1px solid var(--rule);
      color: #fff;
      padding: 10px 12px;
      font-size: 14px;
      font-family: var(--mono);
      outline: none;
    }
    input:focus { border-color: var(--gold); }
    button {
      width: 100%;
      background: var(--gold);
      color: #080b10;
      border: none;
      padding: 11px 16px;
      font-family: var(--sans);
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
    }
    button:hover { filter: brightness(1.08); }
    .err {
      color: #ffc9c9;
      background: rgba(224, 49, 49, 0.14);
      border-left: 2px solid var(--ask);
      padding: 10px 12px;
      font-size: 13px;
      margin-bottom: 18px;
      display: none;
    }
    .login-foot {
      padding: 12px 32px;
      background: var(--canvas);
      border-top: 1px solid var(--rule);
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <main class="login-frame">
    <div class="login-head">
      <div class="status-line">Motor quantitativo • Deriv WebSocket API</div>
      <h1>Prado Institutional HFT</h1>
      <p class="lead">Execução algorítmica de VWAP, desvio padrão e fluxo de agressão em Deriv Multipliers.</p>
    </div>
    <div class="login-form-wrap">
      <div id="errBox" class="err"></div>
      <form id="loginForm">
        <div class="field">
          <label for="username">Usuário</label>
          <input id="username" name="username" type="text" value="admin" required autocomplete="username" />
        </div>
        <div class="field">
          <label for="password">Senha</label>
          <input id="password" name="password" type="password" placeholder="••••••••" required autocomplete="current-password" />
        </div>
        <button type="submit">Entrar na mesa de execução</button>
      </form>
    </div>
    <div class="login-foot">
      <span>Operador: admin</span>
      <span>Credencial: prado2026</span>
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
          errBox.textContent = data.error || 'Usuário ou senha incorretos.';
          errBox.style.display = 'block';
        }
      } catch (err) {
        errBox.textContent = 'Falha de comunicação com o servidor Ubuntu.';
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
  <title>Prado Institutional HFT — Mesa Deriv Multipliers</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {
      --canvas: #080b10;
      --surface: #0e131b;
      --elevated: #141b26;
      --rule: #1c2533;
      --gold: #c89d42;
      --bid: #0ca678;
      --ask: #e03131;
      --cyan: #38bdf8;
      --ink: #ecf0f5;
      --muted: #7f8ea3;
      --mono: 'IBM Plex Mono', Consolas, monospace;
      --sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--canvas);
      color: var(--ink);
      font-family: var(--sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      font-size: 13px;
      line-height: 1.4;
      -webkit-font-smoothing: antialiased;
    }
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--rule);
      height: 48px;
      padding: 0 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .topbar-left { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .status-dot { width: 7px; height: 7px; background: var(--bid); flex-shrink: 0; }
    .desk-name { font-size: 14px; font-weight: 700; letter-spacing: -0.01em; color: #fff; white-space: nowrap; }
    .feed-indicator {
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
      border-left: 1px solid var(--rule);
      padding-left: 12px;
      white-space: nowrap;
    }
    .topbar-right { display: flex; align-items: center; gap: 8px; }
    .account-picker {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--canvas);
      border: 1px solid var(--rule);
      height: 30px;
      padding: 0 10px;
    }
    .account-picker span { font-size: 12px; color: var(--muted); white-space: nowrap; }
    .account-picker select {
      background: transparent;
      color: var(--gold);
      border: none;
      font-family: var(--mono);
      font-size: 12px;
      font-weight: 500;
      outline: none;
      cursor: pointer;
    }
    .account-picker select option { background: var(--surface); color: var(--ink); }

    .ledger-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      background: var(--canvas);
      border-bottom: 1px solid var(--rule);
    }
    @media (max-width: 960px) {
      .ledger-strip { grid-template-columns: repeat(2, 1fr); }
      .topbar { height: auto; padding: 10px 16px; flex-wrap: wrap; }
      .topbar-right { flex-wrap: wrap; }
    }
    .ledger-cell {
      padding: 12px 20px;
      border-right: 1px solid var(--rule);
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .ledger-cell:last-child { border-right: none; }
    .ledger-head { font-size: 12px; color: var(--muted); display: flex; align-items: center; justify-content: space-between; }
    .ledger-figure {
      font-family: var(--mono);
      font-variant-numeric: tabular-nums;
      font-size: 17px;
      font-weight: 600;
      color: #fff;
    }
    .ledger-meta { font-family: var(--mono); font-size: 11px; color: var(--muted); }

    .nav-strip {
      background: var(--surface);
      border-bottom: 1px solid var(--rule);
      padding: 0 20px;
      display: flex;
      gap: 2px;
      overflow-x: auto;
    }
    .nav-tab {
      padding: 10px 16px;
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--muted);
      font-family: var(--sans);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .nav-tab:hover { color: var(--ink); }
    .nav-tab.active { color: #fff; border-bottom-color: var(--gold); background: rgba(200, 157, 66, 0.06); }
    .nav-count { font-family: var(--mono); font-size: 11px; color: var(--gold); margin-left: 4px; }

    .btn {
      height: 30px;
      padding: 0 11px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-family: var(--sans);
      font-size: 12px;
      font-weight: 600;
      border: 1px solid var(--rule);
      background: var(--elevated);
      color: var(--ink);
      cursor: pointer;
      white-space: nowrap;
    }
    .btn:hover { border-color: var(--gold); }
    .btn-primary { background: var(--gold); color: #080b10; border-color: var(--gold); font-weight: 700; }
    .btn-primary:hover { filter: brightness(1.07); }
    .btn-bid { background: rgba(12, 166, 120, 0.12); color: #38d9a9; border-color: rgba(12, 166, 120, 0.4); }
    .btn-bid:hover { background: var(--bid); color: #04130e; }
    .btn-ask { background: rgba(224, 49, 49, 0.12); color: #ffa8a8; border-color: rgba(224, 49, 49, 0.4); }
    .btn-ask:hover { background: var(--ask); color: #fff; }
    .btn-quiet { background: transparent; color: var(--muted); border-color: var(--rule); }
    .btn-quiet:hover { color: var(--ink); border-color: var(--muted); }

    .action-strip {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--rule);
      background: var(--canvas);
      white-space: nowrap;
    }
    .action-strip button {
      height: 26px;
      padding: 0 9px;
      border: none;
      border-right: 1px solid var(--rule);
      background: transparent;
      color: var(--ink);
      font-family: var(--sans);
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .action-strip button:last-child { border-right: none; }
    .action-strip button:hover { background: var(--elevated); }
    .action-strip button.act-bid { color: #38d9a9; }
    .action-strip button.act-bid:hover { background: var(--bid); color: #04130e; }
    .action-strip button.act-ask { color: #ffa8a8; }
    .action-strip button.act-ask:hover { background: var(--ask); color: #fff; }
    .action-strip button.act-edit { color: var(--cyan); }
    .action-strip button.act-del { color: var(--muted); }
    .action-strip button.act-del:hover { background: var(--ask); color: #fff; }

    .workspace { flex: 1; width: 100%; max-width: 1680px; margin: 0 auto; padding: 16px 20px 36px; }
    .tab-pane { display: none; }
    .tab-pane.active { display: grid; gap: 16px; }
    .section-block { background: var(--surface); border: 1px solid var(--rule); }
    .section-bar {
      padding: 10px 16px;
      border-bottom: 1px solid var(--rule);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: rgba(8, 11, 16, 0.45);
    }
    .section-title { font-size: 13px; font-weight: 700; color: #fff; }
    .section-hint { font-size: 12px; color: var(--muted); margin-left: 10px; font-weight: 400; }
    .section-body { padding: 16px; overflow-x: auto; }
    .section-body.bleed { padding: 0; }

    table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
    th, td { padding: 9px 14px; text-align: left; border-bottom: 1px solid var(--rule); vertical-align: middle; }
    th { font-size: 11.5px; font-weight: 600; color: var(--muted); background: var(--canvas); white-space: nowrap; }
    th.num, td.num { text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
    td.code { font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
    tr.interactive-row { cursor: pointer; }
    tr.interactive-row:hover td { background: var(--elevated); }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 7px;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 500;
      border-left: 2px solid transparent;
      background: rgba(127, 142, 163, 0.1);
      color: var(--muted);
      white-space: nowrap;
    }
    .badge-bid { border-left-color: var(--bid); background: rgba(12, 166, 120, 0.12); color: #38d9a9; }
    .badge-ask { border-left-color: var(--ask); background: rgba(224, 49, 49, 0.12); color: #ffa8a8; }
    .badge-hft { border-left-color: var(--cyan); background: rgba(56, 189, 248, 0.12); color: var(--cyan); }
    .badge-gold { border-left-color: var(--gold); background: rgba(200, 157, 66, 0.14); color: var(--gold); }

    .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }
    .field { position: relative; }
    .field label { display: block; font-size: 12px; font-weight: 600; color: var(--ink); margin-bottom: 5px; }
    .field input, .field select {
      width: 100%;
      height: 34px;
      background: var(--canvas);
      border: 1px solid var(--rule);
      color: #fff;
      padding: 0 10px;
      font-size: 13px;
      font-family: var(--sans);
    }
    .field input.mono { font-family: var(--mono); }
    .field input:focus, .field select:focus { border-color: var(--gold); outline: none; }
    .field small { display: block; color: var(--muted); font-size: 11px; margin-top: 4px; }

    .equation-bar {
      background: var(--canvas);
      border: 1px solid var(--rule);
      border-left: 2px solid var(--gold);
      padding: 10px 14px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--gold);
      margin: 14px 0 8px;
    }
    .toast {
      position: fixed;
      bottom: 18px;
      right: 18px;
      background: var(--surface);
      color: var(--ink);
      border: 1px solid var(--rule);
      border-left: 3px solid var(--bid);
      padding: 10px 16px;
      font-size: 12.5px;
      font-weight: 600;
      display: none;
      box-shadow: 0 10px 24px rgba(0,0,0,0.7);
      z-index: 1000;
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-left">
      <span class="status-dot"></span>
      <span class="desk-name">Prado Institutional HFT • Deriv</span>
      <span class="feed-indicator" id="connBadge">Conectando...</span>
    </div>
    <div class="topbar-right">
      <div class="account-picker">
        <span>Token em operação:</span>
        <select id="headerAccountSelect" onchange="quickSwitchAccount(this.value)"></select>
      </div>
      <button class="btn btn-quiet" onclick="resetDailyRisk()">Destravar limite diário</button>
      <button class="btn btn-bid" id="toggleAutoBtn" onclick="toggleAutoTrading()">Execução automática: Ativa</button>
      <button class="btn btn-ask" onclick="panicFlatten()">Zerar todas as posições</button>
      <button class="btn btn-quiet" onclick="logout()">Sair</button>
    </div>
  </header>

  <section class="ledger-strip">
    <div class="ledger-cell">
      <div class="ledger-head">
        <span>Conta Deriv conectada</span>
        <span id="kpiAccBadge" class="badge badge-hft">Demo</span>
      </div>
      <div class="ledger-figure" id="kpiAccount">---</div>
      <div class="ledger-meta" id="kpiServer">Deriv WebSocket API</div>
    </div>
    <div class="ledger-cell">
      <div class="ledger-head"><span>Saldo / Equity</span></div>
      <div class="ledger-figure" id="kpiEquity">$ 0.00</div>
      <div class="ledger-meta" id="kpiBalance">Saldo base: $ 0.00</div>
    </div>
    <div class="ledger-cell">
      <div class="ledger-head"><span>Robôs matemáticos ativos</span></div>
      <div class="ledger-figure" id="kpiBotsRunning" style="color:var(--gold);">0 / 0</div>
      <div class="ledger-meta" id="kpiRiskStatus">Risco diário: Operacional</div>
    </div>
    <div class="ledger-cell">
      <div class="ledger-head"><span>Vetor de correlação da cesta</span></div>
      <div class="ledger-figure" id="kpiCorr">0.0%</div>
      <div class="ledger-meta" id="lastUpdate">Sincronizando...</div>
    </div>
  </section>

  <nav class="nav-strip">
    <button class="nav-tab active" onclick="switchTab('running-bots', this)">Mesa de execução e robôs <span class="nav-count" id="tabBotCount">0</span></button>
    <button class="nav-tab" onclick="switchTab('create-bot', this)">Configurar robô matemático</button>
    <button class="nav-tab" onclick="switchTab('backtest', this)">Backtest tick a tick</button>
    <button class="nav-tab" onclick="switchTab('categories', this)">Categorias de ativos</button>
    <button class="nav-tab" onclick="switchTab('deriv-tokens', this)">Tokens e Contas Deriv (Demo e Real)</button>
    <button class="nav-tab" onclick="switchTab('monitor', this)">Matriz VWAP e Z-Score</button>
  </nav>

  <main class="workspace">
    <!-- PANE 1: RUNNING BOTS & POSITIONS -->
    <div id="tab-running-bots" class="tab-pane active">
      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Frota de robôs matemáticos (Deriv Multipliers)</span>
            <span class="section-hint">Clique em qualquer linha para editar Stake, Multiplicador ou parâmetros</span>
          </div>
          <div style="display:flex;gap:8px;">
            <button class="btn btn-primary" onclick="startNewBotForm()">Novo robô matemático</button>
            <button class="btn btn-quiet" onclick="deleteAllBots()">Limpar frota</button>
          </div>
        </div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Robô / Modelo matemático</th>
                <th>Token vinculado</th>
                <th>Ativo</th>
                <th class="num">Stake / Mult</th>
                <th class="num">Preço atual</th>
                <th class="num">VWAP (&Sigma;PV/&Sigma;V)</th>
                <th class="num">Z-Score</th>
                <th class="num">Imbalance</th>
                <th>Regime estatístico</th>
                <th>Sinal</th>
                <th>Estado</th>
                <th style="text-align:right;">Operações e edição</th>
              </tr>
            </thead>
            <tbody id="runningBotsBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Contratos abertos na Deriv</span>
            <span class="section-hint">Acompanhamento em tempo real com Stop Loss e Take Profit</span>
          </div>
        </div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Contrato</th>
                <th>Ativo</th>
                <th>Lado</th>
                <th class="num">Stake (USD)</th>
                <th class="num">Entrada</th>
                <th class="num">Atual</th>
                <th class="num">Stop Loss</th>
                <th class="num">Take Profit</th>
                <th class="num">Lucro / Prejuízo</th>
                <th>Tipo</th>
                <th style="text-align:right;">Comando</th>
              </tr>
            </thead>
            <tbody id="positionsBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Histórico de contratos encerrados</span>
            <span class="section-hint">Saídas por Take Profit, Stop Loss ou encerramento direto</span>
          </div>
        </div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Contrato</th>
                <th>Horário</th>
                <th>Ativo</th>
                <th>Lado</th>
                <th class="num">Stake</th>
                <th class="num">Entrada</th>
                <th class="num">Saída</th>
                <th class="num">Resultado líquido</th>
                <th>Motivo da saída</th>
                <th>Robô</th>
              </tr>
            </thead>
            <tbody id="dealsHistoryBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- PANE 2: CREATE / EDIT BOT -->
    <div id="tab-create-bot" class="tab-pane">
      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title" id="botFormTitle">Configurar robô matemático (Deriv Multipliers)</span>
            <span class="section-hint">Operação pura por matriz de ticks via WebSocket oficial da Deriv</span>
          </div>
          <div class="action-strip">
            <button type="button" id="btnModeMain" class="act-bid" onclick="setSymbolMode('PRINCIPAIS')">Ativos principais</button>
            <button type="button" id="btnModeAll" onclick="setSymbolMode('TODOS')">Todos os ativos Deriv</button>
          </div>
        </div>
        <div class="section-body">
          <form id="createBotForm" onsubmit="createAndRunBot(event)">
            <input type="hidden" id="editing_bot_id" value="" />
            <div class="form-grid">
              <div class="field" style="grid-column: span 2;">
                <label for="bot_template_id">Modelo matemático</label>
                <select id="bot_template_id" onchange="onBotTemplateChange()"></select>
              </div>
              <div class="field">
                <label for="bot_name">Identificação do robô</label>
                <input type="text" id="bot_name" placeholder="Ex: Desk Volatility 100" required />
              </div>
              <div class="field">
                <label for="bot_account_id">Token / Conta Deriv</label>
                <select id="bot_account_id"></select>
              </div>
              <div class="field">
                <label for="bot_category_filter">Filtro por categoria</label>
                <select id="bot_category_filter" onchange="loadBrokerSymbols()">
                  <option value="">Todas as categorias</option>
                </select>
              </div>
              <div class="field">
                <label for="bot_symbol">Ativo Deriv (<span id="symModeLabel">PRINCIPAIS</span>)</label>
                <select id="bot_symbol"></select>
                <small id="symCountHint">Carregando ativos...</small>
              </div>
              <div class="field">
                <label for="bot_lot_size">Stake por entrada (USD)</label>
                <input type="number" step="0.5" id="bot_lot_size" class="mono" value="10.0" required />
              </div>
              <div class="field">
                <label for="bot_multiplier">Multiplicador (alavancagem)</label>
                <select id="bot_multiplier">
                  <option value="20">20x</option>
                  <option value="50">50x</option>
                  <option value="100" selected>100x</option>
                  <option value="200">200x</option>
                  <option value="400">400x</option>
                </select>
              </div>
              <div class="field">
                <label for="bot_window_ticks">Janela de amostragem (ticks)</label>
                <input type="number" id="bot_window_ticks" class="mono" value="120" required />
              </div>
              <div class="field">
                <label for="bot_zscore">Limiar Z-Score (|Z|)</label>
                <input type="number" step="0.1" id="bot_zscore" class="mono" value="1.8" required />
              </div>
              <div class="field">
                <label for="bot_imbalance">Imbalance mínimo</label>
                <input type="number" step="0.05" id="bot_imbalance" class="mono" value="0.35" required />
              </div>
              <div class="field">
                <label for="bot_revert_sigma">Banda de reversão (&plusmn;k&middot;&sigma;)</label>
                <input type="number" step="0.1" id="bot_revert_sigma" class="mono" value="2.0" required />
              </div>
              <div class="field">
                <label for="bot_corr_basket">Cesta de correlação</label>
                <input type="text" id="bot_corr_basket" class="mono" value="R_50, R_25" />
              </div>
            </div>

            <div class="equation-bar" id="botFormulaDisplay">
              Equação: VWAP = Σ(Pᵢ·Vᵢ)/ΣVᵢ | Z = (μ_w - μ)/(σ/√(w/4))
            </div>
            <p id="botDescDisplay" style="font-size:12px;color:var(--muted);margin-bottom:16px;"></p>

            <div style="display:flex; gap:8px;">
              <button type="submit" id="botSubmitBtn" class="btn btn-primary">Criar e iniciar execução automática</button>
              <button type="button" id="botCancelEditBtn" class="btn btn-quiet" style="display:none;" onclick="cancelBotEdit()">Cancelar edição</button>
            </div>
          </form>
        </div>
      </section>
    </div>

    <!-- PANE 3: BACKTEST -->
    <div id="tab-backtest" class="tab-pane">
      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Backtester matemático tick a tick</span>
            <span class="section-hint">Valide expectativa matemática, taxa de acerto e drawdown antes de ligar o robô</span>
          </div>
        </div>
        <div class="section-body">
          <form onsubmit="runMathBacktest(event)">
            <div class="form-grid">
              <div class="field">
                <label for="bt_template_id">Modelo matemático</label>
                <select id="bt_template_id"></select>
              </div>
              <div class="field">
                <label for="bt_symbol">Ativo</label>
                <select id="bt_symbol"></select>
              </div>
              <div class="field">
                <label for="bt_ticks">Amostra de ticks</label>
                <input type="number" id="bt_ticks" class="mono" value="1200" min="200" max="5000" required />
              </div>
              <div class="field">
                <label for="bt_capital">Capital inicial (USD)</label>
                <input type="number" id="bt_capital" class="mono" value="10000" required />
              </div>
              <div class="field">
                <label for="bt_lots">Stake simulado (USD)</label>
                <input type="number" step="0.5" id="bt_lots" class="mono" value="10.0" required />
              </div>
              <div class="field">
                <label for="bt_zscore">Limiar Z-Score</label>
                <input type="number" step="0.1" id="bt_zscore" class="mono" value="1.5" required />
              </div>
              <div class="field">
                <label for="bt_imbalance">Imbalance mínimo</label>
                <input type="number" step="0.05" id="bt_imbalance" class="mono" value="0.25" required />
              </div>
              <div class="field">
                <label for="bt_sigma">Banda de reversão (&sigma;)</label>
                <input type="number" step="0.1" id="bt_sigma" class="mono" value="1.8" required />
              </div>
            </div>
            <div style="margin-top:16px;">
              <button type="submit" class="btn btn-primary">Executar backtest matemático</button>
            </div>
          </form>
        </div>
      </section>

      <section class="section-block" id="btResultCard" style="display:none;">
        <div class="section-bar"><span class="section-title">Relatório estatístico do backtest</span></div>
        <div class="ledger-strip" id="btKpiGrid"></div>
        <div class="section-body">
          <div class="equation-bar" id="btFormulaUsed" style="margin-top:0;"></div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Lado</th>
                <th>Gatilho matemático</th>
                <th class="num">Entrada</th>
                <th class="num">Saída</th>
                <th class="num">Resultado líquido</th>
                <th class="num">Patrimônio acumulado</th>
              </tr>
            </thead>
            <tbody id="btTradesBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- PANE 4: CATEGORIES -->
    <div id="tab-categories" class="tab-pane">
      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Categorias de ativos da Deriv</span>
            <span class="section-hint">Clique em qualquer categoria abaixo para editar seus símbolos</span>
          </div>
        </div>
        <div class="section-body">
          <form onsubmit="saveCustomCategory(event)">
            <div class="form-grid">
              <div class="field">
                <label for="new_cat_name">Nome da categoria</label>
                <input type="text" id="new_cat_name" placeholder="Ex: Volatility 24/7" required />
              </div>
              <div class="field">
                <label for="new_cat_symbols">Símbolos vinculados (separados por vírgula)</label>
                <input type="text" id="new_cat_symbols" class="mono" placeholder="Ex: R_100, R_75, 1HZ100V" required />
              </div>
            </div>
            <div style="margin-top:14px;">
              <button type="submit" class="btn btn-primary">Salvar categoria</button>
            </div>
          </form>
        </div>
      </section>

      <section class="section-block">
        <div class="section-bar"><span class="section-title">Categorias cadastradas</span></div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Categoria</th>
                <th>Ativos vinculados</th>
                <th style="text-align:right;">Controles</th>
              </tr>
            </thead>
            <tbody id="categoriesBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- PANE 5: DERIV TOKEN VAULT (SAVE & ACTIVATE TOKENS) -->
    <div id="tab-deriv-tokens" class="tab-pane">
      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title" id="accountFormTitle">Cofre de Tokens da Deriv (Demo e Real)</span>
            <span class="section-hint">Salve seu Token da Deriv (home.deriv.com/dashboard/profile/api-tokens) com permissões Read + Trade para negociar 24/7 na VPS</span>
          </div>
        </div>
        <div class="section-body">
          <form id="derivForm" onsubmit="saveDerivAccount(event)">
            <input type="hidden" id="editing_account_id" value="" />
            <div class="form-grid">
              <div class="field">
                <label for="acc_type">Ambiente do token</label>
                <select id="acc_type">
                  <option value="DEMO">Conta Demo Deriv (VRTC)</option>
                  <option value="REAL">Conta Real Deriv (CR)</option>
                </select>
              </div>
              <div class="field">
                <label for="acc_label">Nome de identificação</label>
                <input type="text" id="acc_label" placeholder="Ex: Deriv Demo Principal" required />
              </div>
              <div class="field" style="grid-column: span 2;">
                <label for="deriv_token">Deriv API Token (usado nas negociações)</label>
                <input type="password" id="deriv_token" class="mono" placeholder="Cole seu token pat_... gerado na Deriv" />
                <small>O token é salvo com segurança apenas no seu servidor Ubuntu e usado para autenticar e enviar ordens.</small>
              </div>
              <div class="field">
                <label for="deriv_app_id">Deriv App ID</label>
                <input type="text" id="deriv_app_id" class="mono" value="1089" />
              </div>
              <div class="field">
                <label for="default_stake_usd">Stake padrão (USD)</label>
                <input type="number" step="0.5" id="default_stake_usd" class="mono" value="10.0" />
              </div>
              <div class="field">
                <label for="default_multiplier">Multiplicador padrão</label>
                <select id="default_multiplier">
                  <option value="20">20x</option>
                  <option value="50">50x</option>
                  <option value="100" selected>100x</option>
                  <option value="200">200x</option>
                  <option value="400">400x</option>
                </select>
              </div>
              <div class="field">
                <label for="connection_mode">Modo de execução</label>
                <select id="connection_mode">
                  <option value="DERIV_CLOUD">Deriv WebSocket Live (Negociação Real/Demo)</option>
                  <option value="SIMULATION">Simulador Quantitativo Interno</option>
                </select>
              </div>
            </div>
            <div style="margin-top: 16px; display:flex; gap:8px;">
              <button type="submit" id="accSubmitBtn" class="btn btn-primary">Salvar token e conectar na Deriv</button>
              <button type="button" id="accCancelEditBtn" class="btn btn-quiet" style="display:none;" onclick="cancelAccountEdit()">Cancelar edição</button>
            </div>
          </form>
        </div>
      </section>

      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Tokens salvos para negociação</span>
            <span class="section-hint">Clique em qualquer token para editar ou em "Ativar" para operar com ele</span>
          </div>
          <button class="btn btn-quiet" onclick="deleteAllAccounts()">Limpar tokens</button>
        </div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Ambiente</th>
                <th>Identificação</th>
                <th>Login ID Deriv</th>
                <th>Stake / Mult</th>
                <th>Status</th>
                <th style="text-align:right;">Controles</th>
              </tr>
            </thead>
            <tbody id="accountsBody"></tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- PANE 6: MATRIX -->
    <div id="tab-monitor" class="tab-pane">
      <section class="section-block">
        <div class="section-bar">
          <div>
            <span class="section-title">Matriz matemática — VWAP, Bandas (&plusmn;1&sigma; / &plusmn;2&sigma;) e Z-Score</span>
            <span class="section-hint">Cálculo contínuo sobre os ativos monitorados na Deriv</span>
          </div>
        </div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Ativo</th>
                <th class="num">Preço atual (P)</th>
                <th class="num">VWAP (&Sigma;PV/&Sigma;V)</th>
                <th class="num">Banda -2&sigma;</th>
                <th class="num">Banda +2&sigma;</th>
                <th class="num">Desvio (&sigma;)</th>
                <th class="num">Imbalance</th>
                <th class="num">Z-Score</th>
                <th>Regime estatístico</th>
                <th>Sinal calculado</th>
              </tr>
            </thead>
            <tbody id="symbolsBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section-block">
        <div class="section-bar"><span class="section-title">Diário de execução do motor quantitativo</span></div>
        <div class="section-body bleed">
          <table>
            <thead>
              <tr>
                <th>Horário</th>
                <th>Módulo</th>
                <th>Registro</th>
              </tr>
            </thead>
            <tbody id="eventsBody"></tbody>
          </table>
        </div>
      </section>
    </div>
  </main>

  <div id="toast" class="toast">Operação concluída.</div>

  <script>
    let currentConfig = {};
    let currentSymbolMode = 'PRINCIPAIS';
    let botTemplates = [];
    let latestBotsList = [];

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3400);
    }

    function switchTab(name, btn) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      if (btn) btn.classList.add('active');
    }

    function regimeBadge(regime) {
      if (regime === 'INSTITUTIONAL_TREND_UP') return '<span class="badge badge-bid">Trem VWAP (+Z)</span>';
      if (regime === 'INSTITUTIONAL_TREND_DOWN') return '<span class="badge badge-ask">Trem VWAP (-Z)</span>';
      if (regime === 'HFT_MEAN_REVERSION') return '<span class="badge badge-hft">Reversão HFT (&plusmn;2&sigma;)</span>';
      return '<span class="badge">Equilíbrio (0)</span>';
    }

    function actionBadge(action) {
      if ((action || '').startsWith('BUY')) return `<span class="badge badge-bid">${action}</span>`;
      if ((action || '').startsWith('SELL')) return `<span class="badge badge-ask">${action}</span>`;
      return `<span class="badge">${action || 'WAIT'}</span>`;
    }

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
      document.getElementById('btnModeMain').className = mode === 'PRINCIPAIS' ? 'act-bid' : '';
      document.getElementById('btnModeAll').className = mode === 'TODOS' ? 'act-bid' : '';
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
      document.getElementById('symCountHint').textContent = `${syms.length} ativo(s) disponíveis no modo ${currentSymbolMode}.`;
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
          <tr class="interactive-row" onclick="editCategory('${c.replace(/'/g, "\\'")}', '${symsStr.replace(/'/g, "\\'")}')">
            <td><strong>${c}</strong></td>
            <td>${(categories[c] || []).map(s => `<span class="badge" style="margin:2px;">${s}</span>`).join(' ')}</td>
            <td onclick="event.stopPropagation();" style="text-align:right;">
              <div class="action-strip">
                <button class="act-edit" onclick="editCategory('${c.replace(/'/g, "\\'")}', '${symsStr.replace(/'/g, "\\'")}')">Editar</button>
                <button class="act-del" onclick="deleteCategory('${c.replace(/'/g, "\\'")}')">Apagar</button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      const accSel = document.getElementById('bot_account_id');
      const hdrSel = document.getElementById('headerAccountSelect');
      const list = accounts || [];
      if (list.length === 0) {
        const defOpt = '<option value="default">[Demo] Simulador Quantitativo</option>';
        accSel.innerHTML = defOpt;
        hdrSel.innerHTML = defOpt;
      } else {
        const opts = list.map(a => {
          const badge = a.account_type === 'REAL' ? 'Real' : 'Demo';
          const selected = a.account_id === activeAccountId ? 'selected' : '';
          return `<option value="${a.account_id}" ${selected}>[${badge}] ${a.label} (${a.loginid || 'Deriv'})</option>`;
        }).join('');
        accSel.innerHTML = opts;
        hdrSel.innerHTML = opts;
      }

      const accBody = document.getElementById('accountsBody');
      if (list.length === 0) {
        accBody.innerHTML = '<tr><td colspan="6" style="color:var(--muted);text-align:center;padding:20px;">Nenhum token salvo ainda. Cole seu Deriv API Token acima para operar ao vivo na Deriv.</td></tr>';
      } else {
        accBody.innerHTML = list.map(a => {
          const isReal = a.account_type === 'REAL';
          const isActive = a.account_id === activeAccountId;
          return `
            <tr class="interactive-row" onclick="editAccount('${a.account_id}')">
              <td><span class="badge ${isReal ? 'badge-gold' : 'badge-hft'}">${isReal ? 'Real' : 'Demo'}</span></td>
              <td><strong>${a.label}</strong></td>
              <td class="code">${a.loginid || '---'}</td>
              <td class="code">$${a.default_stake_usd || 10} • ${a.default_multiplier || 100}x</td>
              <td>${isActive ? '<span class="badge badge-bid">Em operação</span>' : '<span class="badge">Disponível</span>'}</td>
              <td onclick="event.stopPropagation();" style="text-align:right;">
                <div class="action-strip">
                  ${isActive
                    ? '<button disabled style="color:var(--muted);">Ativo</button>'
                    : `<button class="act-bid" onclick="quickSwitchAccount('${a.account_id}')">Ativar</button>`
                  }
                  <button class="act-edit" onclick="editAccount('${a.account_id}')">Editar</button>
                  <button class="act-del" onclick="deleteAccount('${a.account_id}')">Apagar</button>
                </div>
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
      showToast(`Categoria "${catName}" carregada para edição.`);
    }

    function editAccount(accountId) {
      const list = currentConfig.accounts || [];
      const acc = list.find(a => a.account_id === accountId);
      if (!acc) return;
      document.getElementById('editing_account_id').value = acc.account_id;
      document.getElementById('acc_type').value = acc.account_type || 'DEMO';
      document.getElementById('acc_label').value = acc.label || '';
      document.getElementById('deriv_token').value = '';
      document.getElementById('deriv_app_id').value = acc.deriv_app_id || '1089';
      document.getElementById('default_stake_usd').value = acc.default_stake_usd || 10.0;
      document.getElementById('default_multiplier').value = acc.default_multiplier || 100;
      document.getElementById('connection_mode').value = acc.connection_mode || 'DERIV_CLOUD';
      document.getElementById('accountFormTitle').textContent = `Editando token: ${acc.label}`;
      document.getElementById('accSubmitBtn').textContent = 'Salvar alterações do token';
      document.getElementById('accCancelEditBtn').style.display = 'inline-flex';
      switchTab('deriv-tokens', document.querySelectorAll('.nav-tab')[4]);
      showToast(`Token "${acc.label}" carregado para edição.`);
    }

    function cancelAccountEdit() {
      document.getElementById('editing_account_id').value = '';
      document.getElementById('acc_label').value = '';
      document.getElementById('deriv_token').value = '';
      document.getElementById('accountFormTitle').textContent = 'Cofre de Tokens da Deriv (Demo e Real)';
      document.getElementById('accSubmitBtn').textContent = 'Salvar token e conectar na Deriv';
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
        showToast('Token apagado.');
        refreshStatus();
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
        showToast('Todos os tokens foram removidos.');
        refreshStatus();
      }
    }

    async function deleteAllBots() {
      const res = await fetch('/api/bots/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'DELETE_ALL'})
      });
      if (res.ok) {
        showToast('Frota de robôs limpa.');
        refreshStatus();
      }
    }

    function startNewBotForm() {
      cancelBotEdit();
      switchTab('create-bot', document.querySelectorAll('.nav-tab')[1]);
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
      document.getElementById('bot_multiplier').value = bot.multiplier || 100;
      document.getElementById('bot_window_ticks').value = bot.window_ticks || 120;
      document.getElementById('bot_zscore').value = bot.zscore_threshold || 1.8;
      document.getElementById('bot_imbalance').value = bot.imbalance_threshold || 0.35;
      document.getElementById('bot_revert_sigma').value = bot.revert_sigma || 2.0;
      document.getElementById('bot_corr_basket').value = (bot.correlated_basket || []).join(', ');
      document.getElementById('botFormTitle').textContent = `Editando robô: ${bot.name} (${bot.symbol})`;
      document.getElementById('botSubmitBtn').textContent = 'Salvar alterações do robô';
      document.getElementById('botCancelEditBtn').style.display = 'inline-flex';
      switchTab('create-bot', document.querySelectorAll('.nav-tab')[1]);
      showToast(`Robô "${bot.name}" carregado para edição.`);
    }

    function cancelBotEdit() {
      document.getElementById('editing_bot_id').value = '';
      document.getElementById('bot_name').value = '';
      document.getElementById('bot_lot_size').value = '10.0';
      document.getElementById('botFormTitle').textContent = 'Configurar robô matemático (Deriv Multipliers)';
      document.getElementById('botSubmitBtn').textContent = 'Criar e iniciar execução automática';
      document.getElementById('botCancelEditBtn').style.display = 'none';
      onBotTemplateChange();
    }

    async function resetDailyRisk() {
      const res = await fetch('/api/risk/reset', {method: 'POST'});
      const data = await res.json();
      if (data.ok) {
        showToast('Limite diário destravado.');
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
        showToast(`Token ativo alterado para ${data.active_account.label}.`);
        refreshStatus();
      }
    }

    async function loadConfig() {
      const res = await fetch('/api/config');
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      currentConfig = data.config || {};
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
        accBadge.textContent = accType === 'REAL' ? 'Real' : 'Demo';
        accBadge.className = `badge ${accType === 'REAL' ? 'badge-gold' : 'badge-hft'}`;
        document.getElementById('kpiAccount').textContent = acc.login || '---';
        document.getElementById('kpiServer').textContent = acc.server || 'Deriv WebSocket';
        document.getElementById('kpiEquity').textContent = `${acc.currency || 'USD'} ${(acc.equity || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        document.getElementById('kpiBalance').textContent = `Saldo base: ${(acc.balance || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;

        const bots = snap.bots || [];
        latestBotsList = bots;
        const runningCount = bots.filter(b => b.status === 'RUNNING').length;
        document.getElementById('kpiBotsRunning').textContent = `${runningCount} ativos de ${bots.length}`;
        document.getElementById('tabBotCount').textContent = runningCount;

        const rStatus = document.getElementById('kpiRiskStatus');
        rStatus.textContent = snap.risk_status || 'Operacional';
        rStatus.style.color = snap.risk_locked ? 'var(--ask)' : 'var(--bid)';

        const corr = Number(snap.correlation_bias || 0);
        const kpiCorr = document.getElementById('kpiCorr');
        kpiCorr.textContent = `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(1)}%`;
        kpiCorr.style.color = corr > 0.15 ? 'var(--bid)' : (corr < -0.15 ? 'var(--ask)' : '#fff');

        const autoBtn = document.getElementById('toggleAutoBtn');
        if (snap.auto_trading_enabled) {
          autoBtn.textContent = 'Execução automática: Ativa';
          autoBtn.className = 'btn btn-bid';
        } else {
          autoBtn.textContent = 'Execução automática: Pausada';
          autoBtn.className = 'btn btn-ask';
        }

        const botsBody = document.getElementById('runningBotsBody');
        if (bots.length === 0) {
          botsBody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--muted);padding:24px;">Nenhum robô configurado. Selecione <strong>Novo robô matemático</strong> para iniciar.</td></tr>';
        } else {
          botsBody.innerHTML = bots.map(b => {
            const isRun = b.status === 'RUNNING';
            const bType = b.account_type || 'DEMO';
            return `
              <tr class="interactive-row" onclick="editBot('${b.bot_id}')" title="Clique para editar este robô">
                <td>
                  <strong>${b.name}</strong>
                  <div style="color:var(--muted);font-size:11.5px;">${b.bot_template_name || b.operation_mode} • ${b.trades_executed || 0} ordens</div>
                </td>
                <td>
                  <span class="badge ${bType === 'REAL' ? 'badge-gold' : 'badge-hft'}">${bType === 'REAL' ? 'Real' : 'Demo'}</span>
                  <span style="color:var(--muted);font-size:12px;margin-left:6px;">${b.account_label || ''}</span>
                </td>
                <td class="code"><strong>${b.symbol}</strong></td>
                <td class="num">$${b.lot_size} • ${b.multiplier || 100}x</td>
                <td class="num"><strong>${b.last_price || '---'}</strong></td>
                <td class="num" style="color:var(--gold);">${b.vwap || '---'}</td>
                <td class="num"><strong>${Number(b.aggression_zscore || 0).toFixed(2)}</strong></td>
                <td class="num">${(Number(b.imbalance_ratio || 0) * 100).toFixed(1)}%</td>
                <td>${regimeBadge(b.last_regime)}</td>
                <td>${actionBadge(b.last_signal)}</td>
                <td><span class="badge ${isRun ? 'badge-bid' : 'badge-ask'}">${isRun ? 'Ativo' : 'Pausado'}</span></td>
                <td onclick="event.stopPropagation();" style="text-align:right;">
                  <div class="action-strip">
                    <button class="act-bid" onclick="botAction('${b.bot_id}', 'FIRE_BUY')">Comprar</button>
                    <button class="act-ask" onclick="botAction('${b.bot_id}', 'FIRE_SELL')">Vender</button>
                    <button class="act-edit" onclick="editBot('${b.bot_id}')">Editar</button>
                    ${isRun
                      ? `<button onclick="botAction('${b.bot_id}', 'STOP')">Pausar</button>`
                      : `<button class="act-bid" onclick="botAction('${b.bot_id}', 'START')">Iniciar</button>`
                    }
                    <button class="act-del" onclick="botAction('${b.bot_id}', 'DELETE')">Apagar</button>
                  </div>
                </td>
              </tr>
            `;
          }).join('');
        }

        document.getElementById('lastUpdate').textContent = `Ciclo: ${snap.timestamp || ''}`;

        const symBody = document.getElementById('symbolsBody');
        symBody.innerHTML = Object.values(snap.symbols || {}).map(s => `
          <tr>
            <td class="code"><strong>${s.symbol}</strong></td>
            <td class="num"><strong>${s.last_price}</strong></td>
            <td class="num" style="color:var(--gold);font-weight:600;">${s.vwap}</td>
            <td class="num" style="color:var(--bid);">${s.lower_2}</td>
            <td class="num" style="color:var(--ask);">${s.upper_2}</td>
            <td class="num">${s.distance_sigma >= 0 ? '+' : ''}${s.distance_sigma}&sigma;</td>
            <td class="num" style="color:${s.imbalance_ratio >= 0 ? 'var(--bid)' : 'var(--ask)'};font-weight:600;">
              ${(s.imbalance_ratio * 100).toFixed(1)}%
            </td>
            <td class="num" style="font-weight:600;">${s.aggression_zscore.toFixed(2)}</td>
            <td>${regimeBadge(s.regime)}</td>
            <td>${actionBadge(s.action)}</td>
          </tr>
        `).join('');

        const posBody = document.getElementById('positionsBody');
        const positions = snap.positions || [];
        if (positions.length === 0) {
          posBody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--muted);padding:18px;">Nenhum contrato aberto no momento.</td></tr>';
        } else {
          posBody.innerHTML = positions.map(p => `
            <tr>
              <td class="code">#${p.ticket}</td>
              <td class="code"><strong>${p.symbol}</strong></td>
              <td><span class="badge ${p.type === 'BUY' ? 'badge-bid' : 'badge-ask'}">${p.type}</span></td>
              <td class="num">$${p.volume}</td>
              <td class="num">${p.price_open}</td>
              <td class="num">${p.price_current}</td>
              <td class="num">${p.sl}</td>
              <td class="num">${p.tp}</td>
              <td class="num" style="font-weight:600;color:${p.profit >= 0 ? 'var(--bid)' : 'var(--ask)'};">${p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}</td>
              <td class="code" style="color:var(--muted);">${p.comment}</td>
              <td style="text-align:right;">
                <div class="action-strip">
                  <button class="act-ask" onclick="closeSinglePosition('${p.ticket}')">Encerrar</button>
                </div>
              </td>
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
              <td class="code">#${d.ticket}</td>
              <td class="code" style="color:var(--muted);">${d.time}</td>
              <td class="code"><strong>${d.symbol}</strong></td>
              <td><span class="badge ${d.type === 'BUY' ? 'badge-bid' : 'badge-ask'}">${d.type}</span></td>
              <td class="num">$${d.volume}</td>
              <td class="num">${d.price_open}</td>
              <td class="num">${d.price_close}</td>
              <td class="num" style="font-weight:600;color:${d.profit >= 0 ? 'var(--bid)' : 'var(--ask)'};">${d.profit >= 0 ? '+' : ''}${Number(d.profit).toFixed(2)}</td>
              <td><span class="badge">${d.reason}</span></td>
              <td class="code" style="color:var(--muted);">${d.comment}</td>
            </tr>
          `).join('');
        }

        document.getElementById('eventsBody').innerHTML = (snap.events || []).map(ev => `
          <tr>
            <td class="code" style="color:var(--muted);width:100px;">${ev.time}</td>
            <td style="width:140px;"><span class="badge">${ev.category}</span></td>
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
        category: catSel.value || 'Deriv',
        lot_size: Number(document.getElementById('bot_lot_size').value || 10.0),
        multiplier: Number(document.getElementById('bot_multiplier').value || 100),
        window_ticks: Number(document.getElementById('bot_window_ticks').value || 120),
        zscore_threshold: Number(document.getElementById('bot_zscore').value || 1.8),
        imbalance_threshold: Number(document.getElementById('bot_imbalance').value || 0.35),
        revert_sigma: Number(document.getElementById('bot_revert_sigma').value || 2.0),
        correlated_basket: document.getElementById('bot_corr_basket').value.split(',').map(s => s.trim()).filter(Boolean)
      };
      if (editingId) payload.bot_id = editingId;
      else payload.auto_start = true;

      const res = await fetch('/api/bots', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        showToast(editingId ? `Robô "${data.bot.name}" atualizado.` : `Robô "${data.bot.name}" em execução.`);
        cancelBotEdit();
        switchTab('running-bots', document.querySelectorAll('.nav-tab')[0]);
        refreshStatus();
      }
    }

    async function runMathBacktest(e) {
      e.preventDefault();
      const payload = {
        bot_template_id: document.getElementById('bt_template_id').value,
        symbol: document.getElementById('bt_symbol').value,
        tick_count: Number(document.getElementById('bt_ticks').value || 1200),
        initial_capital: Number(document.getElementById('bt_capital').value || 10000),
        lot_size: Number(document.getElementById('bt_lots').value || 10.0),
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
        document.getElementById('btFormulaUsed').textContent = `Modelo: ${r.bot_template_name} | Equação: ${r.formula}`;
        const isPos = r.net_profit >= 0;
        document.getElementById('btKpiGrid').innerHTML = `
          <div class="ledger-cell">
            <div class="ledger-head"><span>Resultado líquido (${r.symbol})</span></div>
            <div class="ledger-figure" style="color:${isPos ? 'var(--bid)' : 'var(--ask)'};">${isPos ? '+' : ''}${r.net_profit.toFixed(2)} (${r.return_pct}%)</div>
            <div class="ledger-meta">Patrimônio final: ${r.final_equity.toFixed(2)}</div>
          </div>
          <div class="ledger-cell">
            <div class="ledger-head"><span>Taxa de acerto (Win Rate)</span></div>
            <div class="ledger-figure">${r.win_rate_pct}%</div>
            <div class="ledger-meta">${r.winning_trades} ganhos / ${r.losing_trades} perdas (${r.total_trades} trades)</div>
          </div>
          <div class="ledger-cell">
            <div class="ledger-head"><span>Fator de lucro</span></div>
            <div class="ledger-figure" style="color:var(--gold);">${r.profit_factor}</div>
            <div class="ledger-meta">Bruto: +${r.gross_profit} / -${r.gross_loss}</div>
          </div>
          <div class="ledger-cell">
            <div class="ledger-head"><span>Drawdown máximo</span></div>
            <div class="ledger-figure" style="color:var(--ask);">-${r.max_drawdown.toFixed(2)}</div>
            <div class="ledger-meta">${r.ticks_processed} ticks processados</div>
          </div>
        `;
        const tbody = document.getElementById('btTradesBody');
        const trades = r.trades || [];
        tbody.innerHTML = trades.length === 0
          ? '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:16px;">Nenhuma operação disparada.</td></tr>'
          : trades.map(t => `
            <tr>
              <td class="code">#${t.id}</td>
              <td><span class="badge ${t.type === 'BUY' ? 'badge-bid' : 'badge-ask'}">${t.type}</span></td>
              <td class="code">${t.signal}</td>
              <td class="num">${t.entry}</td>
              <td class="num">${t.exit}</td>
              <td class="num" style="font-weight:600;color:${t.pnl >= 0 ? 'var(--bid)' : 'var(--ask)'};">${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</td>
              <td class="num"><strong>${t.equity_after.toFixed(2)}</strong></td>
            </tr>
          `).join('');
        showToast(`Backtest concluído em ${r.symbol}.`);
      }
    }

    async function botAction(botId, action) {
      const res = await fetch('/api/bots/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({bot_id: botId, action})
      });
      if (res.ok) {
        showToast('Comando executado.');
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

    async function saveDerivAccount(e) {
      e.preventDefault();
      const editingId = document.getElementById('editing_account_id').value.trim();
      const payload = {
        account_type: document.getElementById('acc_type').value,
        label: document.getElementById('acc_label').value.trim(),
        deriv_token: document.getElementById('deriv_token').value.trim(),
        deriv_app_id: document.getElementById('deriv_app_id').value.trim() || '1089',
        default_stake_usd: Number(document.getElementById('default_stake_usd').value || 10.0),
        default_multiplier: Number(document.getElementById('default_multiplier').value || 100),
        connection_mode: document.getElementById('connection_mode').value
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
        await loadBrokerSymbols();
        showToast(data.message || 'Token Deriv salvo e conectado!');
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
      showToast(data.message || 'Contratos encerrados.');
      refreshStatus();
    }

    async function closeSinglePosition(ticket) {
      const res = await fetch('/api/flatten', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ticket})
      });
      const data = await res.json();
      showToast(data.message || `Contrato #${ticket} encerrado.`);
      refreshStatus();
    }

    async function logout() {
      await fetch('/api/logout', {method: 'POST'});
      window.location.href = '/login';
    }

    loadConfig();
    refreshStatus();
    setInterval(refreshStatus, 1200);
  </script>
</body>
</html>
"""

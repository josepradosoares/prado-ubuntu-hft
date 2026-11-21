"""HTML templates for Prado Institutional HFT Login & Pure Mathematical Multi-Robot Command Center."""
from __future__ import annotations

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prado Institutional HFT — Login</title>
  <style>
    :root {
      --bg: #080c14;
      --panel: #101726;
      --border: #1f2b44;
      --gold: #f5b942;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
    body {
      background: radial-gradient(circle at top, #131d31 0%, var(--bg) 70%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      width: 100%;
      max-width: 420px;
      padding: 32px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.6);
    }
    .badge {
      display: inline-block;
      background: rgba(245, 185, 66, 0.14);
      color: var(--gold);
      border: 1px solid rgba(245, 185, 66, 0.4);
      padding: 4px 12px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 14px;
    }
    h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; color: #fff; }
    p.sub { color: var(--muted); font-size: 13px; margin-bottom: 24px; line-height: 1.5; }
    label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; font-weight: 600; }
    input {
      width: 100%;
      background: #0a101d;
      border: 1px solid var(--border);
      color: #fff;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 14px;
      margin-bottom: 16px;
      outline: none;
    }
    input:focus { border-color: var(--gold); }
    button {
      width: 100%;
      background: linear-gradient(135deg, #f5b942 0%, #d99b26 100%);
      color: #090d16;
      border: none;
      padding: 13px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
    }
    .err {
      color: var(--danger);
      background: rgba(239,68,68,0.12);
      border: 1px solid rgba(239,68,68,0.3);
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 13px;
      margin-bottom: 16px;
      display: none;
    }
    .hint {
      margin-top: 18px;
      font-size: 12px;
      color: var(--muted);
      text-align: center;
      border-top: 1px solid var(--border);
      padding-top: 14px;
    }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Motor 100% Matemático • Ubuntu MetaTrader 5</span>
    <h1>Prado Institutional HFT</h1>
    <p class="sub">Central Quantitativa Multi-Robôs (Sem Gráficos • Execução Direta por Matemática VWAP &amp; Z-Score)</p>
    <div id="errBox" class="err"></div>
    <form id="loginForm">
      <label for="username">USUÁRIO DO PAINEL</label>
      <input id="username" name="username" type="text" value="admin" required autocomplete="username" />
      <label for="password">SENHA DE ACESSO</label>
      <input id="password" name="password" type="password" placeholder="••••••••" required autocomplete="current-password" />
      <button type="submit">ACESSAR CENTRAL QUANTITATIVA</button>
    </form>
    <div class="hint">Credencial padrão inicial: <strong>admin</strong> / <strong>prado2026</strong></div>
  </div>
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
          errBox.textContent = data.error || 'Usuário ou senha inválidos.';
          errBox.style.display = 'block';
        }
      } catch (err) {
        errBox.textContent = 'Erro de conexão com o servidor.';
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
  <title>Prado Institutional HFT — Motor 100% Matemático (Ubuntu Server)</title>
  <style>
    :root {
      --bg: #070b12;
      --panel: #0f1624;
      --panel-alt: #131c2e;
      --border: #1e293b;
      --gold: #f5b942;
      --cyan: #22d3ee;
      --green: #10b981;
      --red: #ef4444;
      --text: #f1f5f9;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 40px; }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .brand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .brand-dot { width: 12px; height: 12px; border-radius: 50%; background: var(--gold); box-shadow: 0 0 12px var(--gold); }
    .brand h1 { font-size: 18px; font-weight: 700; color: #fff; }
    .brand span { font-size: 12px; color: var(--gold); background: rgba(245,185,66,0.12); padding: 3px 10px; border-radius: 999px; border: 1px solid rgba(245,185,66,0.3); }
    .top-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .btn {
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid var(--border);
      cursor: pointer;
      background: var(--panel-alt);
      color: var(--text);
      transition: 0.15s;
    }
    .btn:hover { border-color: var(--gold); }
    .btn-gold { background: var(--gold); color: #090d16; border-color: var(--gold); }
    .btn-danger { background: rgba(239,68,68,0.18); color: #fca5a5; border-color: rgba(239,68,68,0.45); }
    .btn-danger:hover { background: var(--red); color: #fff; }
    .btn-green { background: rgba(16,185,129,0.18); color: #6ee7b7; border-color: rgba(16,185,129,0.45); }
    .btn-green:hover { background: var(--green); color: #05130d; }
    .btn-cyan { background: rgba(34,211,238,0.16); color: #22d3ee; border-color: rgba(34,211,238,0.4); }

    .container { max-width: 1440px; margin: 20px auto; padding: 0 20px; display: grid; gap: 20px; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
    .kpi {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
    }
    .kpi .label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }
    .kpi .val { font-size: 20px; font-weight: 700; color: #fff; }
    .kpi .sub { font-size: 12px; color: var(--muted); margin-top: 4px; }

    .tabs { display: flex; gap: 10px; border-bottom: 1px solid var(--border); padding-bottom: 10px; flex-wrap: wrap; }
    .tab-btn {
      padding: 10px 16px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--muted);
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
    }
    .tab-btn.active { background: rgba(245,185,66,0.15); color: var(--gold); border-color: var(--gold); }
    .tab-content { display: none; }
    .tab-content.active { display: grid; gap: 20px; }

    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      overflow-x: auto;
    }
    .card h2 {
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 14px;
      color: var(--gold);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
    tr.clickable-row { cursor: pointer; transition: background 0.15s; }
    tr.clickable-row:hover td { background: rgba(245,185,66,0.08); }
    .pill {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
    }
    .pill-up { background: rgba(16,185,129,0.16); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }
    .pill-down { background: rgba(239,68,68,0.16); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
    .pill-hft { background: rgba(34,211,238,0.16); color: #22d3ee; border: 1px solid rgba(34,211,238,0.4); }
    .pill-gold { background: rgba(245,185,66,0.16); color: var(--gold); border: 1px solid rgba(245,185,66,0.4); }
    .pill-wait { background: rgba(148,163,184,0.14); color: #94a3b8; }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 16px;
    }
    .field { position: relative; }
    .field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; font-weight: 600; }
    .field input, .field select {
      width: 100%;
      background: #080d17;
      border: 1px solid var(--border);
      color: #fff;
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 13px;
    }
    .field input:focus, .field select:focus { border-color: var(--gold); outline: none; }
    .field small { display: block; color: var(--muted); font-size: 11px; margin-top: 4px; }

    .autocomplete-box {
      position: absolute;
      top: 66px;
      left: 0;
      right: 0;
      background: #0b1220;
      border: 1px solid var(--gold);
      border-radius: 8px;
      max-height: 210px;
      overflow-y: auto;
      z-index: 500;
      display: none;
      box-shadow: 0 12px 30px rgba(0,0,0,0.7);
    }
    .autocomplete-item {
      padding: 9px 12px;
      font-size: 13px;
      cursor: pointer;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .autocomplete-item:hover { background: rgba(245,185,66,0.2); color: var(--gold); }

    .mode-switch { display: inline-flex; gap: 6px; background: #080d17; padding: 4px; border-radius: 8px; border: 1px solid var(--border); }
    .mode-btn {
      padding: 6px 12px;
      border-radius: 6px;
      border: none;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      background: transparent;
      color: var(--muted);
    }
    .mode-btn.active { background: var(--gold); color: #090d16; }
    .formula-box {
      background: #060911;
      border: 1px solid #1e2d4a;
      border-radius: 8px;
      padding: 12px 16px;
      font-family: 'Consolas', monospace;
      font-size: 12px;
      color: var(--cyan);
      margin: 12px 0;
    }
    .quote-box {
      background: rgba(245,185,66,0.07);
      border-left: 3px solid var(--gold);
      padding: 12px 16px;
      font-size: 12px;
      color: #cbd5e1;
      margin-bottom: 16px;
      line-height: 1.5;
    }
    .toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #10b981;
      color: #06110d;
      padding: 12px 18px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 13px;
      display: none;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      z-index: 1000;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-dot"></div>
      <h1>PRADO INSTITUTIONAL HFT • MOTOR 100% MATEMÁTICO (SEM GRÁFICOS)</h1>
      <span id="connBadge">CONECTANDO...</span>
    </div>
    <div class="top-actions">
      <div style="display:flex;align-items:center;gap:6px;background:#080d17;padding:4px 10px;border-radius:8px;border:1px solid var(--border);">
        <span style="font-size:11px;color:var(--muted);font-weight:700;">CONTA EM USO:</span>
        <select id="headerAccountSelect" onchange="quickSwitchAccount(this.value)" style="background:transparent;color:var(--gold);border:none;font-weight:700;font-size:12px;outline:none;cursor:pointer;"></select>
      </div>
      <button class="btn btn-cyan" onclick="resetDailyRisk()">🔄 DESTRAVAR RISCO DIÁRIO</button>
      <button class="btn btn-green" id="toggleAutoBtn" onclick="toggleAutoTrading()">CHAVE GERAL: ATIVA</button>
      <button class="btn btn-danger" onclick="panicFlatten()">🚨 ZERAR TUDO AGORA</button>
      <button class="btn" onclick="logout()">SAIR</button>
    </div>
  </header>

  <div class="container">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="label">CONTA ATIVA (DEMO / REAL)</div>
        <div class="val" id="kpiAccount">---</div>
        <div class="sub" id="kpiServer">Servidor: ---</div>
      </div>
      <div class="kpi">
        <div class="label">SALDO / EQUITY</div>
        <div class="val" id="kpiEquity">R$ 0,00</div>
        <div class="sub" id="kpiBalance">Saldo: R$ 0,00</div>
      </div>
      <div class="kpi">
        <div class="label">ROBÔS MATEMÁTICOS RODANDO</div>
        <div class="val" id="kpiBotsRunning" style="color:var(--gold);">0</div>
        <div class="sub" id="kpiRiskStatus">Status: OPERACIONAL</div>
      </div>
      <div class="kpi">
        <div class="label">VETOR DE CORRELAÇÃO (CESTA)</div>
        <div class="val" id="kpiCorr">0.0%</div>
        <div class="sub">Cálculo Matricial Multi-Ativo</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('running-bots', this)">🤖 Robôs Rodando (<span id="tabBotCount">0</span>)</button>
      <button class="tab-btn" onclick="switchTab('create-bot', this)">🧮 Criar / Editar Robô Matemático</button>
      <button class="tab-btn" onclick="switchTab('backtest', this)">🧪 Backtest Matemático Tick-a-Tick</button>
      <button class="tab-btn" onclick="switchTab('categories', this)">🗂️ Categorias de Ativos da Corretora</button>
      <button class="tab-btn" onclick="switchTab('mt5', this)">🔌 Contas DEMO &amp; REAL (MetaTrader 5)</button>
      <button class="tab-btn" onclick="switchTab('monitor', this)">📐 Matriz Matemática VWAP &amp; Z-Score</button>
    </div>

    <!-- ABA 1: ROBÔS RODANDO -->
    <div id="tab-running-bots" class="tab-content active">
      <div class="card">
        <h2>
          <span>🤖 FROTA DE ROBÔS MATEMÁTICOS EM EXECUÇÃO (CLIQUE EM QUALQUER ROBÔ OU EM "✏️ EDITAR" PARA ALTERAR LOTE, CONTA OU ATIVO)</span>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn btn-gold" onclick="startNewBotForm()">+ ESCOLHER &amp; CRIAR NOVO ROBÔ</button>
            <button class="btn btn-danger" onclick="deleteAllBots()">🗑️ APAGAR TODOS OS ROBÔS</button>
          </div>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Robô / Algoritmo Matemático</th>
              <th>Ambiente / Conta</th>
              <th>Ativo</th>
              <th>Lote</th>
              <th>Preço / VWAP (&Sigma;PV/&Sigma;V)</th>
              <th>Z-Score / Imbalance</th>
              <th>Estado Matemático</th>
              <th>Decisão</th>
              <th>Status</th>
              <th>Controle / Editar</th>
            </tr>
          </thead>
          <tbody id="runningBotsBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>ORDENS &amp; POSIÇÕES ABERTAS NO METATRADER 5</h2>
        <table>
          <thead>
            <tr>
              <th>Ticket</th>
              <th>Ativo</th>
              <th>Direção</th>
              <th>Lote</th>
              <th>Preço Entrada</th>
              <th>Preço Atual</th>
              <th>Stop Loss (&sigma;)</th>
              <th>Take Profit (&sigma;)</th>
              <th>Lucro / Prejuízo</th>
              <th>Robô</th>
            </tr>
          </thead>
          <tbody id="positionsBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 2: CRIAR & EDITAR ROBÔ MATEMÁTICO -->
    <div id="tab-create-bot" class="tab-content">
      <div class="card">
        <h2>
          <span id="botFormTitle">🧮 CATÁLOGO DE ROBÔS 100% MATEMÁTICOS (CRIAR OU EDITAR ROBÔ)</span>
          <div class="mode-switch">
            <button type="button" id="btnModeMain" class="mode-btn active" onclick="setSymbolMode('PRINCIPAIS')">⭐ Ativos Principais</button>
            <button type="button" id="btnModeAll" class="mode-btn" onclick="setSymbolMode('TODOS')">🌐 Todos os Ativos da Corretora</button>
          </div>
        </h2>
        <div class="quote-box">
          Nenhum gráfico pesado é carregado: os robôs operam diretamente sobre arrays numéricos de ticks da biblioteca <code>MetaTrader5</code> em Python. Você pode <strong>criar um novo robô</strong> ou <strong>editar qualquer robô existente</strong> clicando nele na lista!
        </div>

        <form id="createBotForm" onsubmit="createAndRunBot(event)">
          <input type="hidden" id="editing_bot_id" value="" />
          <div class="form-grid">
            <div class="field" style="grid-column: span 2;">
              <label>Escolher Modelo Matemático do Robô (Todos os Bots Disponíveis)</label>
              <select id="bot_template_id" onchange="onBotTemplateChange()"></select>
            </div>
            <div class="field">
              <label>Nome Personalizado do Robô</label>
              <input type="text" id="bot_name" placeholder="Ex: Bot BTC Institucional #1" required />
            </div>
            <div class="field">
              <label>Escolher Conta MetaTrader 5 (DEMO ou REAL)</label>
              <select id="bot_account_id"></select>
            </div>
            <div class="field">
              <label>Filtrar por Categoria da Corretora</label>
              <select id="bot_category_filter" onchange="loadBrokerSymbols()">
                <option value="">-- Todas as Categorias --</option>
              </select>
            </div>
            <div class="field">
              <label>Selecionar Ativo da Corretora (<span id="symModeLabel">PRINCIPAIS</span>)</label>
              <select id="bot_symbol"></select>
              <small id="symCountHint">Carregando ativos...</small>
            </div>
            <div class="field">
              <label>Volume / Lote por Operação (Ex: 0.01 para BTC, 1.0 para WIN)</label>
              <input type="number" step="0.01" id="bot_lot_size" value="0.10" required />
            </div>
            <div class="field">
              <label>Janela de Amostragem (w Ticks)</label>
              <input type="number" id="bot_window_ticks" value="120" required />
            </div>
            <div class="field">
              <label>Limiar Estatístico Z-Score (|Z|)</label>
              <input type="number" step="0.1" id="bot_zscore" value="1.8" required />
            </div>
            <div class="field">
              <label>Coeficiente de Desequilíbrio (Imbalance)</label>
              <input type="number" step="0.05" id="bot_imbalance" value="0.35" required />
            </div>
            <div class="field">
              <label>Desvio Padrão de Reversão (&plusmn;k&middot;&sigma;)</label>
              <input type="number" step="0.1" id="bot_revert_sigma" value="2.0" required />
            </div>
            <div class="field">
              <label>Vetor Cesta de Correlação (Ativos)</label>
              <input type="text" id="bot_corr_basket" value="PETR4, VALE3, Crypto_10#" />
            </div>
          </div>

          <div class="formula-box" id="botFormulaDisplay">
            Fórmula Matemática: VWAP = Σ(Pᵢ·Vᵢ)/ΣVᵢ | Z = (μ_w - μ)/(σ/√(w/4))
          </div>
          <p id="botDescDisplay" style="font-size:12px;color:var(--muted);margin-bottom:16px;"></p>

          <div style="display:flex; gap:12px; flex-wrap:wrap;">
            <button type="submit" id="botSubmitBtn" class="btn btn-gold" style="font-size:14px;padding:12px 24px;">
              ▶ CRIAR E EXECUTAR ROBÔ AUTOMATICAMENTE
            </button>
            <button type="button" id="botCancelEditBtn" class="btn" style="display:none;" onclick="cancelBotEdit()">
              Cancelar Edição
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ABA 3: BACKTEST MATEMÁTICO -->
    <div id="tab-backtest" class="tab-content">
      <div class="card">
        <h2>🧪 SIMULADOR &amp; BACKTESTER MATEMÁTICO TICK-A-TICK (ALTA VELOCIDADE • SEM GRÁFICOS)</h2>
        <div class="quote-box">
          Teste qualquer um dos algoritmos matemáticos sobre a série de ticks do ativo antes de colocá-lo para rodar na Conta Demo ou Conta Real.
        </div>
        <form onsubmit="runMathBacktest(event)">
          <div class="form-grid">
            <div class="field">
              <label>Algoritmo Matemático do Robô</label>
              <select id="bt_template_id"></select>
            </div>
            <div class="field">
              <label>Ativo para Backtest</label>
              <select id="bt_symbol"></select>
            </div>
            <div class="field">
              <label>Amostra de Ticks (Histórico)</label>
              <input type="number" id="bt_ticks" value="1200" min="200" max="5000" required />
            </div>
            <div class="field">
              <label>Capital Inicial Simulado (R$ / USD)</label>
              <input type="number" id="bt_capital" value="50000" required />
            </div>
            <div class="field">
              <label>Lote Simulado</label>
              <input type="number" step="0.01" id="bt_lots" value="1.0" required />
            </div>
            <div class="field">
              <label>Limiar Z-Score</label>
              <input type="number" step="0.1" id="bt_zscore" value="1.5" required />
            </div>
            <div class="field">
              <label>Imbalance Mínimo</label>
              <input type="number" step="0.05" id="bt_imbalance" value="0.25" required />
            </div>
            <div class="field">
              <label>Desvio Padrão Reversão (&sigma;)</label>
              <input type="number" step="0.1" id="bt_sigma" value="1.8" required />
            </div>
          </div>
          <div style="margin-top:18px;">
            <button type="submit" class="btn btn-gold" style="padding:11px 22px;font-size:13px;">⚡ EXECUTAR BACKTEST MATEMÁTICO AGORA</button>
          </div>
        </form>
      </div>

      <div class="card" id="btResultCard" style="display:none;">
        <h2>📈 RESULTADO ESTATÍSTICO DO BACKTEST</h2>
        <div class="kpi-grid" id="btKpiGrid" style="margin-bottom:16px;"></div>
        <div class="formula-box" id="btFormulaUsed"></div>
        <h3 style="font-size:13px;color:var(--gold);margin:14px 0 8px;">ÚLTIMAS OPERAÇÕES MATEMÁTICAS DO BACKTEST</h3>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Tipo</th>
              <th>Gatilho Matemático</th>
              <th>Preço Entrada</th>
              <th>Preço Saída</th>
              <th>Resultado Financeiro</th>
              <th>Saldo Acumulado</th>
            </tr>
          </thead>
          <tbody id="btTradesBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 4: CATEGORIAS DE ATIVOS DA CORRETORA -->
    <div id="tab-categories" class="tab-content">
      <div class="card">
        <h2>🗂️ CRIAR / EDITAR CATEGORIA DE ATIVOS DA CORRETORA (CLIQUE EM UMA CATEGORIA ABAIXO PARA EDITAR)</h2>
        <form onsubmit="saveCustomCategory(event)">
          <div class="form-grid">
            <div class="field">
              <label>Nome da Categoria</label>
              <input type="text" id="new_cat_name" placeholder="Ex: Futuros B3 Liquidez Institucional" required />
            </div>
            <div class="field">
              <label>Códigos dos Ativos (separados por vírgula)</label>
              <input type="text" id="new_cat_symbols" placeholder="Ex: WIN$N, WDO$N, IND$N, DOL$N" required />
            </div>
          </div>
          <div style="margin-top:14px;">
            <button type="submit" class="btn btn-gold">💾 SALVAR / ATUALIZAR CATEGORIA</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>CATEGORIAS DISPONÍVEIS PARA OS ROBÔS (CLIQUE PARA EDITAR)</h2>
        <table>
          <thead>
            <tr>
              <th>Categoria</th>
              <th>Ativos Vinculados</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody id="categoriesBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 5: CONTAS DEMO & REAL METATRADER 5 -->
    <div id="tab-mt5" class="tab-content">
      <div class="card">
        <h2 id="accountFormTitle">🔌 GERENCIADOR DE CONTAS DEMO &amp; REAL METATRADER 5 (CLIQUE EM QUALQUER CONTA ABAIXO PARA EDITAR)</h2>
        <div class="quote-box">
          Suas contas <strong>XM Global Demo (346595704 @ XMGlobal-MT5 10)</strong> e <strong>XM Global Real (382177116 @ XMGlobal-MT5 13)</strong> já estão pré-cadastradas com a sua senha! Ao começar a digitar no campo <strong>Servidor da Corretora no MT5</strong>, a lista de servidores aparece automaticamente para você escolher.
        </div>
        <form id="mt5Form" onsubmit="saveMt5Account(event)">
          <input type="hidden" id="editing_account_id" value="" />
          <div class="form-grid">
            <div class="field">
              <label>Tipo da Conta (DEMO ou REAL)</label>
              <select id="acc_type">
                <option value="DEMO">🧪 CONTA DEMO (Simulação / Homologação na Corretora)</option>
                <option value="REAL">💰 CONTA REAL (Produção / Dinheiro Real na Corretora)</option>
              </select>
            </div>
            <div class="field">
              <label>Apelido de Identificação</label>
              <input type="text" id="acc_label" placeholder="Ex: Jose XM Global Demo" required />
            </div>
            <div class="field">
              <label>Login da Conta MT5 (Número)</label>
              <input type="text" id="mt5_login" placeholder="Ex: 346595704" required />
            </div>
            <div class="field">
              <label>Senha da Conta MT5</label>
              <input type="password" id="mt5_password" placeholder="Deixe em branco na edição para manter a senha atual" />
            </div>
            <div class="field">
              <label>Servidor da Corretora no MT5 (Comece a digitar para autocompletar)</label>
              <input
                type="text"
                id="mt5_server"
                list="brokerServersDatalist"
                placeholder="Digite ex: XMGlobal, XP, Clear, ICMarkets..."
                autocomplete="off"
                oninput="onServerInputAutocomplete(this.value)"
                onfocus="onServerInputAutocomplete(this.value)"
                required
              />
              <datalist id="brokerServersDatalist"></datalist>
              <div id="serverAutocompleteBox" class="autocomplete-box"></div>
              <small>Comece a escrever o nome da corretora (ex: XM, XP, Clear) e clique no servidor desejado.</small>
            </div>
          </div>
          <div style="margin-top: 18px; display:flex; gap:10px;">
            <button type="submit" id="accSubmitBtn" class="btn btn-gold">💾 SALVAR / ATUALIZAR CONTA &amp; CONECTAR</button>
            <button type="button" id="accCancelEditBtn" class="btn" style="display:none;" onclick="cancelAccountEdit()">Cancelar Edição</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>
          <span>CONTAS CADASTRADAS — CLIQUE EM "✏️ EDITAR", "🗑️ APAGAR" OU "USAR CONTA"</span>
          <button class="btn btn-danger" onclick="deleteAllAccounts()">🗑️ APAGAR TODAS AS CONTAS</button>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Ambiente</th>
              <th>Nome da Conta</th>
              <th>Login MT5</th>
              <th>Servidor da Corretora</th>
              <th>Status</th>
              <th>Ações (Escolher / Editar / Excluir)</th>
            </tr>
          </thead>
          <tbody id="accountsBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 6: MATRIZ MATEMÁTICA VWAP & Z-SCORE -->
    <div id="tab-monitor" class="tab-content">
      <div class="card">
        <h2>
          <span>📐 MATRIZ MATEMÁTICA PURA EM TEMPO REAL — VWAP, DESVIO PADRÃO (&plusmn;1&sigma; / &plusmn;2&sigma;) &amp; Z-SCORE</span>
          <span id="lastUpdate" style="font-size:12px;color:var(--muted);font-weight:400;"></span>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Ativo</th>
              <th>Preço (P)</th>
              <th>VWAP (&Sigma;PV/&Sigma;V)</th>
              <th>-2&sigma;</th>
              <th>+2&sigma;</th>
              <th>Desvio (&sigma;)</th>
              <th>Imbalance</th>
              <th>Z-Score</th>
              <th>Estado Matemático</th>
              <th>Vetor de Ação</th>
            </tr>
          </thead>
          <tbody id="symbolsBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>LOG DO MOTOR MATEMÁTICO &amp; GUARDA-COSTAS DE RISCO</h2>
        <table>
          <thead>
            <tr>
              <th>Horário</th>
              <th>Módulo</th>
              <th>Evento</th>
            </tr>
          </thead>
          <tbody id="eventsBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div id="toast" class="toast">Salvo!</div>

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
      if (regime === 'INSTITUTIONAL_TREND_UP') return '<span class="pill pill-up">TREM VWAP (+Z)</span>';
      if (regime === 'INSTITUTIONAL_TREND_DOWN') return '<span class="pill pill-down">TREM VWAP (-Z)</span>';
      if (regime === 'HFT_MEAN_REVERSION') return '<span class="pill pill-hft">REVERSÃO HFT (&plusmn;2&sigma;)</span>';
      return '<span class="pill pill-wait">EQUILÍBRIO (0)</span>';
    }

    function actionPill(action) {
      if ((action || '').startsWith('BUY')) return `<span class="pill pill-up">${action}</span>`;
      if ((action || '').startsWith('SELL')) return `<span class="pill pill-down">${action}</span>`;
      return `<span class="pill pill-wait">${action || 'WAIT'}</span>`;
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
          🏢 <strong>${s}</strong>
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
      document.getElementById('botFormulaDisplay').textContent = `Fórmula Matemática: ${tpl.formula}`;
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
      document.getElementById('symCountHint').textContent = `${syms.length} ativo(s) disponível(is) no modo ${currentSymbolMode}.`;
    }

    function renderCategoriesAndAccounts(categories, accounts, activeAccountId) {
      const catSel = document.getElementById('bot_category_filter');
      const prevCat = catSel.value;
      const catNames = Object.keys(categories || {});
      catSel.innerHTML = '<option value="">-- Todas as Categorias --</option>' +
        catNames.map(c => `<option value="${c}">${c} (${(categories[c] || []).length})</option>`).join('');
      if (catNames.includes(prevCat)) catSel.value = prevCat;

      const catBody = document.getElementById('categoriesBody');
      catBody.innerHTML = catNames.map(c => {
        const symsStr = (categories[c] || []).join(', ');
        return `
          <tr class="clickable-row" onclick="editCategory('${c.replace(/'/g, "\\'")}', '${symsStr.replace(/'/g, "\\'")}')">
            <td><strong>${c}</strong></td>
            <td>${(categories[c] || []).map(s => `<span class="pill pill-wait" style="margin:2px;">${s}</span>`).join(' ')}</td>
            <td onclick="event.stopPropagation();" style="display:flex;gap:6px;">
              <button class="btn btn-cyan" onclick="editCategory('${c.replace(/'/g, "\\'")}', '${symsStr.replace(/'/g, "\\'")}')">✏️ Editar</button>
              <button class="btn btn-danger" onclick="deleteCategory('${c.replace(/'/g, "\\'")}')">🗑️ Excluir</button>
            </td>
          </tr>
        `;
      }).join('');

      const accSel = document.getElementById('bot_account_id');
      const hdrSel = document.getElementById('headerAccountSelect');
      const list = accounts || [];
      if (list.length === 0) {
        const defOpt = '<option value="default">[DEMO] Conta Padrão Simulador</option>';
        accSel.innerHTML = defOpt;
        hdrSel.innerHTML = defOpt;
      } else {
        const opts = list.map(a => {
          const badge = a.account_type === 'REAL' ? '💰 REAL' : '🧪 DEMO';
          const selected = a.account_id === activeAccountId ? 'selected' : '';
          return `<option value="${a.account_id}" ${selected}>[${badge}] ${a.label} (${a.mt5_login} @ ${a.mt5_server})</option>`;
        }).join('');
        accSel.innerHTML = opts;
        hdrSel.innerHTML = opts;
      }

      const accBody = document.getElementById('accountsBody');
      if (list.length === 0) {
        accBody.innerHTML = '<tr><td colspan="6" style="color:var(--muted);text-align:center;">Nenhuma conta DEMO ou REAL cadastrada ainda.</td></tr>';
      } else {
        accBody.innerHTML = list.map(a => {
          const isReal = a.account_type === 'REAL';
          const isActive = a.account_id === activeAccountId;
          return `
            <tr class="clickable-row" onclick="editAccount('${a.account_id}')">
              <td><span class="pill ${isReal ? 'pill-gold' : 'pill-hft'}">${isReal ? '💰 CONTA REAL' : '🧪 CONTA DEMO'}</span></td>
              <td><strong>${a.label}</strong></td>
              <td><code>${a.mt5_login}</code></td>
              <td><strong>${a.mt5_server}</strong></td>
              <td>${isActive ? '<span class="pill pill-up">● EM USO AGORA</span>' : '<span class="pill pill-wait">DISPONÍVEL</span>'}</td>
              <td onclick="event.stopPropagation();" style="display:flex;gap:6px;flex-wrap:wrap;">
                ${isActive
                  ? '<button class="btn" disabled>Conectada</button>'
                  : `<button class="btn btn-gold" onclick="quickSwitchAccount('${a.account_id}')">Usar Conta</button>`
                }
                <button class="btn btn-cyan" onclick="editAccount('${a.account_id}')">✏️ Editar</button>
                <button class="btn btn-danger" onclick="deleteAccount('${a.account_id}')">🗑️ Apagar</button>
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
      showToast(`Editando categoria "${catName}" — altere os ativos e clique em Salvar.`);
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
      document.getElementById('accountFormTitle').textContent = `✏️ EDITANDO CONTA: ${acc.label} (${acc.mt5_login})`;
      document.getElementById('accSubmitBtn').textContent = '💾 SALVAR ALTERAÇÕES DA CONTA';
      document.getElementById('accCancelEditBtn').style.display = 'inline-block';
      switchTab('mt5', document.querySelectorAll('.tab-btn')[4]);
      showToast(`Editando conta ${acc.mt5_login} (${acc.mt5_server})`);
    }

    function cancelAccountEdit() {
      document.getElementById('editing_account_id').value = '';
      document.getElementById('acc_label').value = '';
      document.getElementById('mt5_login').value = '';
      document.getElementById('mt5_password').value = '';
      document.getElementById('mt5_server').value = '';
      document.getElementById('accountFormTitle').textContent = '🔌 GERENCIADOR DE CONTAS DEMO & REAL METATRADER 5 (CLIQUE EM QUALQUER CONTA ABAIXO PARA EDITAR)';
      document.getElementById('accSubmitBtn').textContent = '💾 SALVAR / ATUALIZAR CONTA & CONECTAR';
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
        showToast('Conta apagada com sucesso!');
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
        showToast('Todas as contas foram apagadas!');
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
        showToast('Todos os robôs foram apagados!');
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
      document.getElementById('botFormTitle').textContent = `✏️ EDITANDO ROBÔ: ${bot.name} (${bot.symbol})`;
      document.getElementById('botSubmitBtn').textContent = '💾 SALVAR ALTERAÇÕES DO ROBÔ';
      document.getElementById('botCancelEditBtn').style.display = 'inline-block';
      switchTab('create-bot', document.querySelectorAll('.tab-btn')[1]);
      showToast(`Editando robô "${bot.name}" — altere o lote, conta ou parâmetros e clique em Salvar.`);
    }

    function cancelBotEdit() {
      document.getElementById('editing_bot_id').value = '';
      document.getElementById('bot_name').value = '';
      document.getElementById('bot_lot_size').value = '0.10';
      document.getElementById('botFormTitle').textContent = '🧮 CATÁLOGO DE ROBÔS 100% MATEMÁTICOS (CRIAR OU EDITAR ROBÔ)';
      document.getElementById('botSubmitBtn').textContent = '▶ CRIAR E EXECUTAR ROBÔ AUTOMATICAMENTE';
      document.getElementById('botCancelEditBtn').style.display = 'none';
      onBotTemplateChange();
    }

    async function resetDailyRisk() {
      const res = await fetch('/api/risk/reset', {method: 'POST'});
      const data = await res.json();
      if (data.ok) {
        showToast('Trava de perda diária resetada e robôs liberados para operar!');
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
        showToast(`Conta ativa alterada para [${data.active_account.account_type}] ${data.active_account.label}!`);
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
        document.getElementById('connBadge').textContent = `[${accType}] ${acc.backend || 'ONLINE'} • ${acc.login || ''}`;
        document.getElementById('kpiAccount').innerHTML = `<span class="pill ${accType === 'REAL' ? 'pill-gold' : 'pill-hft'}">${accType}</span> ${acc.login || '---'}`;
        document.getElementById('kpiServer').textContent = `Servidor: ${acc.server || '---'}`;
        document.getElementById('kpiEquity').textContent = `${acc.currency || 'R$'} ${(acc.equity || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        document.getElementById('kpiBalance').textContent = `Saldo: ${(acc.balance || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;

        const bots = snap.bots || [];
        latestBotsList = bots;
        const runningCount = bots.filter(b => b.status === 'RUNNING').length;
        document.getElementById('kpiBotsRunning').textContent = `${runningCount} / ${bots.length}`;
        document.getElementById('tabBotCount').textContent = runningCount;

        const rStatus = document.getElementById('kpiRiskStatus');
        rStatus.textContent = snap.risk_status || 'OPERACIONAL';
        rStatus.style.color = snap.risk_locked ? 'var(--red)' : 'var(--green)';

        const corr = Number(snap.correlation_bias || 0);
        const kpiCorr = document.getElementById('kpiCorr');
        kpiCorr.textContent = `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(1)}%`;
        kpiCorr.style.color = corr > 0.15 ? 'var(--green)' : (corr < -0.15 ? 'var(--red)' : '#fff');

        const autoBtn = document.getElementById('toggleAutoBtn');
        if (snap.auto_trading_enabled) {
          autoBtn.textContent = 'CHAVE GERAL: ATIVA';
          autoBtn.className = 'btn btn-green';
        } else {
          autoBtn.textContent = 'CHAVE GERAL: PAUSADA';
          autoBtn.className = 'btn btn-danger';
        }

        const botsBody = document.getElementById('runningBotsBody');
        if (bots.length === 0) {
          botsBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:22px;">Nenhum robô matemático em execução. Clique na aba <strong>"🧮 Criar / Editar Robô Matemático"</strong> para escolher um algoritmo e iniciar!</td></tr>';
        } else {
          botsBody.innerHTML = bots.map(b => {
            const isRun = b.status === 'RUNNING';
            const bType = b.account_type || 'DEMO';
            return `
              <tr class="clickable-row" onclick="editBot('${b.bot_id}')" title="Clique para editar este robô">
                <td>
                  <strong>${b.name}</strong> <span style="font-size:11px;color:var(--gold);">✏️</span><br/>
                  <small style="color:var(--cyan);font-family:monospace;">${b.bot_template_name || b.operation_mode}</small><br/>
                  <small style="color:var(--muted)">Trades executados: ${b.trades_executed || 0}</small>
                </td>
                <td><span class="pill ${bType === 'REAL' ? 'pill-gold' : 'pill-hft'}">${bType}</span><br/><small>${b.account_label || ''}</small></td>
                <td><strong>${b.symbol}</strong><br/><small style="color:var(--muted)">${b.category || ''}</small></td>
                <td><strong>${b.lot_size}</strong></td>
                <td>P: <strong>${b.last_price || '---'}</strong><br/><small style="color:var(--gold)">VWAP: ${b.vwap || '---'}</small></td>
                <td>Z: <strong>${Number(b.aggression_zscore || 0).toFixed(2)}</strong><br/>Imb: ${(Number(b.imbalance_ratio || 0) * 100).toFixed(1)}%</td>
                <td>${regimePill(b.last_regime)}</td>
                <td>${actionPill(b.last_signal)}</td>
                <td>
                  <span class="pill ${isRun ? 'pill-up' : 'pill-down'}">
                    ${isRun ? '● RODANDO' : '■ PARADO'}
                  </span>
                </td>
                <td onclick="event.stopPropagation();" style="display:flex;gap:6px;flex-wrap:wrap;">
                  <button class="btn btn-cyan" onclick="editBot('${b.bot_id}')">✏️ Editar</button>
                  ${isRun
                    ? `<button class="btn btn-danger" onclick="botAction('${b.bot_id}', 'STOP')">⏸ Pausar</button>`
                    : `<button class="btn btn-green" onclick="botAction('${b.bot_id}', 'START')">▶ Executar</button>`
                  }
                  <button class="btn btn-danger" onclick="botAction('${b.bot_id}', 'DELETE')">🗑️ Apagar</button>
                </td>
              </tr>
            `;
          }).join('');
        }

        document.getElementById('lastUpdate').textContent = `Ciclo: ${snap.timestamp || ''}`;

        const symBody = document.getElementById('symbolsBody');
        const syms = Object.values(snap.symbols || {});
        symBody.innerHTML = syms.map(s => `
          <tr>
            <td><strong>${s.symbol}</strong></td>
            <td><strong>${s.last_price}</strong></td>
            <td style="color:var(--gold);font-weight:700;">${s.vwap}</td>
            <td style="color:var(--green);">${s.lower_2}</td>
            <td style="color:var(--red);">${s.upper_2}</td>
            <td>${s.distance_sigma >= 0 ? '+' : ''}${s.distance_sigma}&sigma;</td>
            <td style="color:${s.imbalance_ratio >= 0 ? 'var(--green)' : 'var(--red)'};font-weight:700;">
              ${(s.imbalance_ratio * 100).toFixed(1)}%
            </td>
            <td style="font-weight:700;">${s.aggression_zscore.toFixed(2)}</td>
            <td>${regimePill(s.regime)}</td>
            <td>${actionPill(s.action)}</td>
          </tr>
        `).join('');

        const posBody = document.getElementById('positionsBody');
        const positions = snap.positions || [];
        if (positions.length === 0) {
          posBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--muted);">Nenhuma posição aberta no momento.</td></tr>';
        } else {
          posBody.innerHTML = positions.map(p => `
            <tr>
              <td>#${p.ticket}</td>
              <td><strong>${p.symbol}</strong></td>
              <td><span class="pill ${p.type === 'BUY' ? 'pill-up' : 'pill-down'}">${p.type}</span></td>
              <td>${p.volume}</td>
              <td>${p.price_open}</td>
              <td>${p.price_current}</td>
              <td>${p.sl}</td>
              <td>${p.tp}</td>
              <td style="font-weight:700;color:${p.profit >= 0 ? 'var(--green)' : 'var(--red)'};">${p.profit.toFixed(2)}</td>
              <td>${p.comment}</td>
            </tr>
          `).join('');
        }

        const evBody = document.getElementById('eventsBody');
        evBody.innerHTML = (snap.events || []).map(ev => `
          <tr>
            <td style="color:var(--muted);width:110px;">${ev.time}</td>
            <td style="width:150px;"><span class="pill pill-wait">${ev.category}</span></td>
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
        showToast(editingId ? `Robô "${data.bot.name}" atualizado com sucesso!` : `Robô Matemático "${data.bot.name}" criado e RODANDO!`);
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
        document.getElementById('btFormulaUsed').textContent = `Modelo Testado: ${r.bot_template_name} | Fórmula: ${r.formula}`;
        const isPos = r.net_profit >= 0;
        document.getElementById('btKpiGrid').innerHTML = `
          <div class="kpi">
            <div class="label">LUCRO LÍQUIDO (${r.symbol})</div>
            <div class="val" style="color:${isPos ? 'var(--green)' : 'var(--red)'};">${isPos ? '+' : ''}${r.net_profit.toFixed(2)} (${r.return_pct}%)</div>
            <div class="sub">Saldo Final: ${r.final_equity.toFixed(2)}</div>
          </div>
          <div class="kpi">
            <div class="label">TAXA DE ACERTO (WIN RATE)</div>
            <div class="val">${r.win_rate_pct}%</div>
            <div class="sub">${r.winning_trades} Gains / ${r.losing_trades} Losses (${r.total_trades} trades)</div>
          </div>
          <div class="kpi">
            <div class="label">PROFIT FACTOR (FATOR DE LUCRO)</div>
            <div class="val" style="color:var(--gold);">${r.profit_factor}</div>
            <div class="sub">Bruto: +${r.gross_profit} / -${r.gross_loss}</div>
          </div>
          <div class="kpi">
            <div class="label">DRAWDOWN MÁXIMO</div>
            <div class="val" style="color:var(--red);">-${r.max_drawdown.toFixed(2)}</div>
            <div class="sub">${r.ticks_processed} ticks processados</div>
          </div>
        `;
        const tbody = document.getElementById('btTradesBody');
        const trades = r.trades || [];
        if (trades.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);">Nenhum trade disparado com esses limiares.</td></tr>';
        } else {
          tbody.innerHTML = trades.map(t => `
            <tr>
              <td>#${t.id}</td>
              <td><span class="pill ${t.type === 'BUY' ? 'pill-up' : 'pill-down'}">${t.type}</span></td>
              <td><code>${t.signal}</code></td>
              <td>${t.entry}</td>
              <td>${t.exit}</td>
              <td style="font-weight:700;color:${t.pnl >= 0 ? 'var(--green)' : 'var(--red)'};">${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</td>
              <td><strong>${t.equity_after.toFixed(2)}</strong></td>
            </tr>
          `).join('');
        }
        showToast(`Backtest concluído em ${r.symbol}: ${r.total_trades} operações simuladas!`);
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
        showToast(action === 'START' ? 'Robô em execução automática!' : (action === 'STOP' ? 'Robô pausado.' : 'Robô removido.'));
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
        showToast(`Categoria "${category_name}" salva!`);
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
        showToast(`Categoria "${catName}" removida.`);
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
        showToast(`Conta [${data.account.account_type}] "${data.account.label}" salva e conectada!`);
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
      showToast(nextState ? 'Chave Geral ATIVADA!' : 'Chave Geral PAUSADA!');
      refreshStatus();
    }

    async function panicFlatten() {
      const res = await fetch('/api/flatten', {method: 'POST'});
      const data = await res.json();
      showToast(data.message || 'Ordens zeradas!');
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

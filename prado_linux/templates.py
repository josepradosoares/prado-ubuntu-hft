"""HTML templates for Prado Institutional HFT Login & Multi-Robot Command Center."""
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
    <span class="badge">Wall Street Desk • Ubuntu MetaTrader 5</span>
    <h1>Prado Institutional HFT</h1>
    <p class="sub">Central Multi-Robôs VWAP + Fluxo de Agressão (B3, Forex, Índices &amp; Cripto)</p>
    <div id="errBox" class="err"></div>
    <form id="loginForm">
      <label for="username">USUÁRIO DO PAINEL</label>
      <input id="username" name="username" type="text" value="admin" required autocomplete="username" />
      <label for="password">SENHA DE ACESSO</label>
      <input id="password" name="password" type="password" placeholder="••••••••" required autocomplete="current-password" />
      <button type="submit">ACESSAR CENTRAL DE ROBÔS</button>
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
  <title>Prado Institutional HFT &amp; VWAP Universal — Ubuntu Multi-Robot Command Center</title>
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
    .brand { display: flex; align-items: center; gap: 12px; }
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

    .container { max-width: 1440px; margin: 20px auto; padding: 0 20px; display: grid; gap: 20px; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
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
      padding: 10px 18px;
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
    tr:hover td { background: rgba(255,255,255,0.02); }
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
    .pill-wait { background: rgba(148,163,184,0.14); color: #94a3b8; }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 16px;
    }
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
    .field small { display: block; color: var(--muted); font-size: 11px; margin-top: 4px; }
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
    .quote-box {
      background: rgba(245,185,66,0.07);
      border-left: 3px solid var(--gold);
      padding: 12px 16px;
      font-size: 12px;
      color: #cbd5e1;
      margin-bottom: 16px;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-dot"></div>
      <h1>PRADO INSTITUTIONAL HFT &amp; VWAP UNIVERSAL</h1>
      <span id="connBadge">CONECTANDO...</span>
    </div>
    <div class="top-actions">
      <button class="btn btn-green" id="toggleAutoBtn" onclick="toggleAutoTrading()">CHAVE GERAL: ATIVA</button>
      <button class="btn btn-danger" onclick="panicFlatten()">🚨 ZERAR TUDO AGORA</button>
      <button class="btn" onclick="logout()">SAIR</button>
    </div>
  </header>

  <div class="container">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="label">CONTA METATRADER 5 ATIVA</div>
        <div class="val" id="kpiAccount">---</div>
        <div class="sub" id="kpiServer">Servidor: ---</div>
      </div>
      <div class="kpi">
        <div class="label">SALDO / EQUITY</div>
        <div class="val" id="kpiEquity">R$ 0,00</div>
        <div class="sub" id="kpiBalance">Saldo: R$ 0,00</div>
      </div>
      <div class="kpi">
        <div class="label">ROBÔS RODANDO AGORA</div>
        <div class="val" id="kpiBotsRunning" style="color:var(--gold);">0</div>
        <div class="sub" id="kpiRiskStatus">Status: OPERACIONAL</div>
      </div>
      <div class="kpi">
        <div class="label">BÚSSOLA DE CORRELAÇÃO (CESTA)</div>
        <div class="val" id="kpiCorr">0.0%</div>
        <div class="sub">Filtro Institucional Multi-Ativo</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('running-bots', this)">🤖 Robôs Rodando (<span id="tabBotCount">0</span>)</button>
      <button class="tab-btn" onclick="switchTab('create-bot', this)">🚀 Criar &amp; Executar Novo Robô</button>
      <button class="tab-btn" onclick="switchTab('categories', this)">🗂️ Categorias de Ativos da Corretora</button>
      <button class="tab-btn" onclick="switchTab('monitor', this)">📊 Radar VWAP &amp; Fluxo Geral</button>
      <button class="tab-btn" onclick="switchTab('mt5', this)">🔌 Contas MetaTrader 5 (Python)</button>
      <button class="tab-btn" onclick="switchTab('strategy', this)">🏛️ Regras Globais do Broker (.txt)</button>
    </div>

    <!-- ABA 1: ROBÔS RODANDO -->
    <div id="tab-running-bots" class="tab-content active">
      <div class="card">
        <h2>
          <span>🤖 FROTA DE ROBÔS EM EXECUÇÃO AUTOMÁTICA (PYTHON + METATRADER 5)</span>
          <button class="btn btn-gold" onclick="switchTab('create-bot', document.querySelectorAll('.tab-btn')[1])">+ NOVO ROBÔ</button>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Nome do Robô</th>
              <th>Conta MT5</th>
              <th>Ativo / Categoria</th>
              <th>Modo (.txt)</th>
              <th>Lote</th>
              <th>Preço / VWAP</th>
              <th>Z-Score / Imbalance</th>
              <th>Regime Atual</th>
              <th>Sinal</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody id="runningBotsBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>POSIÇÕES ABERTAS NO METATRADER 5</h2>
        <table>
          <thead>
            <tr>
              <th>Ticket</th>
              <th>Ativo</th>
              <th>Direção</th>
              <th>Lote</th>
              <th>Preço Entrada</th>
              <th>Preço Atual</th>
              <th>Stop Loss</th>
              <th>Take Profit</th>
              <th>Lucro / Prejuízo</th>
              <th>Robô / Origem</th>
            </tr>
          </thead>
          <tbody id="positionsBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 2: CRIAR & EXECUTAR ROBÔ -->
    <div id="tab-create-bot" class="tab-content">
      <div class="card">
        <h2>
          <span>🚀 LANÇAR NOVO ROBÔ HFT / VWAP NA CONTA METATRADER 5</span>
          <div class="mode-switch">
            <button type="button" id="btnModeMain" class="mode-btn active" onclick="setSymbolMode('PRINCIPAIS')">⭐ Ativos Principais</button>
            <button type="button" id="btnModeAll" class="mode-btn" onclick="setSymbolMode('TODOS')">🌐 Todos os Ativos da Corretora</button>
          </div>
        </h2>
        <div class="quote-box">
          Selecione a <strong>Conta MetaTrader 5</strong>, filtre os ativos por <strong>Principais</strong>, <strong>Todos da Corretora</strong> ou por uma <strong>Categoria Personalizada</strong>, calibre o operacional e clique em <strong>▶ CRIAR E EXECUTAR ROBÔ AUTOMATICAMENTE</strong>.
        </div>
        <form id="createBotForm" onsubmit="createAndRunBot(event)">
          <div class="form-grid">
            <div class="field">
              <label>Nome Identificador do Robô</label>
              <input type="text" id="bot_name" placeholder="Ex: Robô Mini Índice Institucional" required />
            </div>
            <div class="field">
              <label>Selecionar Conta MetaTrader 5</label>
              <select id="bot_account_id"></select>
              <small>Cadastre novas contas na aba "Contas MetaTrader 5".</small>
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
              <small id="symCountHint">Carregando ativos da corretora...</small>
            </div>
            <div class="field">
              <label>Modo Operacional (Regras do Broker .txt)</label>
              <select id="bot_operation_mode">
                <option value="BOTH">AMBOS (Fala 1: Trem Institucional + Fala 2: Giro HFT na Média)</option>
                <option value="TREND_ONLY">FALA 1: SOMENTE TREM INSTITUCIONAL (Fluxo VWAP)</option>
                <option value="REVERT_ONLY">FALA 2: SOMENTE GIRO HFT NA MÉDIA (Bandas &plusmn;2&sigma;)</option>
              </select>
            </div>
            <div class="field">
              <label>Volume / Lote da Ordem</label>
              <input type="number" step="0.01" id="bot_lot_size" value="1.0" required />
            </div>
            <div class="field">
              <label>Limiar Z-Score de Agressão (Trem Institucional)</label>
              <input type="number" step="0.1" id="bot_zscore" value="1.8" required />
            </div>
            <div class="field">
              <label>Desequilíbrio Mínimo (Imbalance 0.1 a 0.9)</label>
              <input type="number" step="0.05" id="bot_imbalance" value="0.35" required />
            </div>
            <div class="field">
              <label>Banda de Desvio Padrão p/ Giro HFT (&sigma;)</label>
              <input type="number" step="0.1" id="bot_revert_sigma" value="2.0" required />
            </div>
            <div class="field">
              <label>Cesta de Correlação Bússola (separada por vírgula)</label>
              <input type="text" id="bot_corr_basket" value="PETR4, VALE3" />
            </div>
          </div>
          <div style="margin-top: 20px; display:flex; gap:12px;">
            <button type="submit" class="btn btn-gold" style="font-size:14px;padding:12px 22px;">
              ▶ CRIAR E EXECUTAR ROBÔ AUTOMATICAMENTE
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ABA 3: CATEGORIAS DE ATIVOS DA CORRETORA -->
    <div id="tab-categories" class="tab-content">
      <div class="card">
        <h2>🗂️ CRIAR / EDITAR CATEGORIA PERSONALIZADA DE ATIVOS DA CORRETORA</h2>
        <div class="quote-box">
          Agrupe os ativos da sua corretora por setor ou estratégia (ex.: <em>"Futuros B3 Liquidez Alta"</em>, <em>"Cesta Gringa NY"</em>, <em>"Cripto Scalping"</em>) para selecionar rapidamente na criação dos robôs.
        </div>
        <form onsubmit="saveCustomCategory(event)">
          <div class="form-grid">
            <div class="field">
              <label>Nome da Categoria da Corretora</label>
              <input type="text" id="new_cat_name" placeholder="Ex: Minha Carteira B3 Institucional" required />
            </div>
            <div class="field">
              <label>Ativos da Categoria (separados por vírgula)</label>
              <input type="text" id="new_cat_symbols" placeholder="Ex: WIN$N, WDO$N, PETR4, VALE3, ITUB4" required />
            </div>
          </div>
          <div style="margin-top:14px;">
            <button type="submit" class="btn btn-gold">💾 SALVAR CATEGORIA DE ATIVOS</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>CATEGORIAS CADASTRADAS NO SISTEMA</h2>
        <table>
          <thead>
            <tr>
              <th>Categoria</th>
              <th>Ativos Vinculados</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody id="categoriesBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 4: RADAR VWAP & FLUXO GERAL -->
    <div id="tab-monitor" class="tab-content">
      <div class="card">
        <h2>
          <span>📊 RADAR QUANTITATIVO EM TEMPO REAL — VWAP, DESVIO PADRÃO (&plusmn;1&sigma; / &plusmn;2&sigma;) &amp; Z-SCORE</span>
          <span id="lastUpdate" style="font-size:12px;color:var(--muted);font-weight:400;"></span>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Ativo</th>
              <th>Preço Atual</th>
              <th>VWAP Intraday</th>
              <th>Banda -2&sigma;</th>
              <th>Banda +2&sigma;</th>
              <th>Distância (&sigma;)</th>
              <th>Imbalance (Delta)</th>
              <th>Z-Score Agressão</th>
              <th>Regime Institucional</th>
              <th>Sinal / Ação</th>
            </tr>
          </thead>
          <tbody id="symbolsBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>LOG DE EXECUÇÃO &amp; GUARDA-COSTAS HFT</h2>
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

    <!-- ABA 5: CONTAS METATRADER 5 -->
    <div id="tab-mt5" class="tab-content">
      <div class="card">
        <h2>🔌 CADASTRAR &amp; CONECTAR CONTA METATRADER 5 (BIBLIOTECA PYTHON METATRADER5)</h2>
        <div class="quote-box">
          Ao executar o <code>install.sh</code> no Ubuntu, a biblioteca oficial <code>MetaTrader5</code> + ponte Wine/Python são instaladas e configuradas automaticamente. Cadastre abaixo uma ou mais contas MT5 para usar nos seus robôs.
        </div>
        <form id="mt5Form" onsubmit="saveMt5Account(event)">
          <div class="form-grid">
            <div class="field">
              <label>Nome / Apelido da Conta</label>
              <input type="text" id="acc_label" placeholder="Ex: Conta XP B3 Principal" required />
            </div>
            <div class="field">
              <label>Login da Conta MT5 (Número)</label>
              <input type="text" id="mt5_login" placeholder="Ex: 10293847" required />
            </div>
            <div class="field">
              <label>Senha da Conta MT5</label>
              <input type="password" id="mt5_password" placeholder="Senha da conta na corretora" required />
            </div>
            <div class="field">
              <label>Servidor da Corretora no MT5</label>
              <input type="text" id="mt5_server" placeholder="Ex: XPInvestimentos-PRD ou MetaQuotes-Demo" required />
            </div>
            <div class="field">
              <label>Modo de Conexão Python</label>
              <select id="mt5_connection_mode">
                <option value="AUTO_MT5_WINE">Biblioteca Oficial MetaTrader5 (Nativo / Ubuntu Wine Python)</option>
                <option value="SIMULATION">Simulação Quantitativa (Teste sem corretora)</option>
              </select>
            </div>
          </div>
          <div style="margin-top: 18px;">
            <button type="submit" class="btn btn-gold">💾 SALVAR &amp; CONECTAR CONTA METATRADER 5</button>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>CONTAS METATRADER 5 SALVAS</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Identificação</th>
              <th>Login MT5</th>
              <th>Servidor da Corretora</th>
            </tr>
          </thead>
          <tbody id="accountsBody"></tbody>
        </table>
      </div>
    </div>

    <!-- ABA 6: REGRAS GLOBAIS DO BROKER (.TXT) -->
    <div id="tab-strategy" class="tab-content">
      <div class="card">
        <h2>🏛️ PARÂMETROS GLOBAIS DE RISCO &amp; HORÁRIO ("HFT SEMPRE DORME ZERADO")</h2>
        <form id="strategyForm" onsubmit="saveStrategyConfig(event)">
          <div class="form-grid">
            <div class="field">
              <label>Limite Global de Perda Diária (Moeda da Conta)</label>
              <input type="number" step="10" id="max_daily_loss_money" />
            </div>
            <div class="field">
              <label>Meta Global de Lucro Diário (Moeda da Conta)</label>
              <input type="number" step="10" id="daily_target_money" />
            </div>
            <div class="field">
              <label>Horário de Zeração Obrigatória ("HFT Dorme Zerado")</label>
              <input type="text" id="eod_flatten_time" placeholder="17:35" />
            </div>
            <div class="field">
              <label>Bloqueio de Correlação Contrária (0.1 a 0.9)</label>
              <input type="number" step="0.05" id="correlation_block_threshold" />
            </div>
            <div class="field">
              <label>Nova Senha de Login Web (opcional)</label>
              <input type="password" id="new_admin_password" placeholder="Deixe em branco para manter a atual" />
            </div>
          </div>
          <div style="margin-top: 18px;">
            <button type="submit" class="btn btn-gold">💾 SALVAR REGRAS GLOBAIS</button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <div id="toast" class="toast">Salvo!</div>

  <script>
    let currentConfig = {};
    let currentSymbolMode = 'PRINCIPAIS';

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3200);
    }

    function switchTab(name, btn) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      if (btn) btn.classList.add('active');
    }

    function regimePill(regime) {
      if (regime === 'INSTITUTIONAL_TREND_UP') return '<span class="pill pill-up">TREM INSTITUCIONAL ALTA</span>';
      if (regime === 'INSTITUTIONAL_TREND_DOWN') return '<span class="pill pill-down">TREM INSTITUCIONAL BAIXA</span>';
      if (regime === 'HFT_MEAN_REVERSION') return '<span class="pill pill-hft">GIRO HFT NA MÉDIA (&plusmn;2&sigma;)</span>';
      return '<span class="pill pill-wait">NEUTRO / AGUARDANDO</span>';
    }

    function actionPill(action) {
      if ((action || '').startsWith('BUY')) return `<span class="pill pill-up">${action}</span>`;
      if ((action || '').startsWith('SELL')) return `<span class="pill pill-down">${action}</span>`;
      return `<span class="pill pill-wait">${action || 'WAIT'}</span>`;
    }

    async function setSymbolMode(mode) {
      currentSymbolMode = mode;
      document.getElementById('symModeLabel').textContent = mode;
      document.getElementById('btnModeMain').classList.toggle('active', mode === 'PRINCIPAIS');
      document.getElementById('btnModeAll').classList.toggle('active', mode === 'TODOS');
      await loadBrokerSymbols();
    }

    async function loadBrokerSymbols() {
      const cat = document.getElementById('bot_category_filter').value;
      const url = `/api/symbols?mode=${encodeURIComponent(currentSymbolMode)}&category=${encodeURIComponent(cat)}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const sel = document.getElementById('bot_symbol');
      const syms = data.symbols || [];
      sel.innerHTML = syms.map(s => `<option value="${s.name}">${s.name} — ${s.description || s.category}</option>`).join('');
      document.getElementById('symCountHint').textContent = `${syms.length} ativo(s) carregado(s) no modo ${currentSymbolMode}.`;
    }

    function renderCategoriesAndAccounts(categories, accounts) {
      // Categories dropdown & table
      const catSel = document.getElementById('bot_category_filter');
      const prevCat = catSel.value;
      const catNames = Object.keys(categories || {});
      catSel.innerHTML = '<option value="">-- Todas as Categorias --</option>' +
        catNames.map(c => `<option value="${c}">${c} (${(categories[c] || []).length})</option>`).join('');
      if (catNames.includes(prevCat)) catSel.value = prevCat;

      const catBody = document.getElementById('categoriesBody');
      catBody.innerHTML = catNames.map(c => `
        <tr>
          <td><strong>${c}</strong></td>
          <td>${(categories[c] || []).map(s => `<span class="pill pill-wait" style="margin:2px;">${s}</span>`).join(' ')}</td>
          <td>
            <button class="btn btn-danger" onclick="deleteCategory('${c.replace(/'/g, "\\'")}')">Excluir</button>
          </td>
        </tr>
      `).join('');

      // Accounts dropdown & table
      const accSel = document.getElementById('bot_account_id');
      const prevAcc = accSel.value;
      const list = accounts || [];
      if (list.length === 0) {
        accSel.innerHTML = '<option value="default">Conta Principal MT5</option>';
      } else {
        accSel.innerHTML = list.map(a => `<option value="${a.account_id}">${a.label} (${a.mt5_login} @ ${a.mt5_server})</option>`).join('');
        if (list.some(a => a.account_id === prevAcc)) accSel.value = prevAcc;
      }

      const accBody = document.getElementById('accountsBody');
      if (list.length === 0) {
        accBody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center;">Nenhuma conta extra cadastrada ainda.</td></tr>';
      } else {
        accBody.innerHTML = list.map(a => `
          <tr>
            <td><code>${a.account_id}</code></td>
            <td><strong>${a.label}</strong></td>
            <td>${a.mt5_login}</td>
            <td>${a.mt5_server}</td>
          </tr>
        `).join('');
      }
    }

    async function loadConfig() {
      const res = await fetch('/api/config');
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      currentConfig = data.config || {};
      document.getElementById('mt5_connection_mode').value = currentConfig.mt5_connection_mode || 'AUTO_MT5_WINE';
      document.getElementById('mt5_login').value = currentConfig.mt5_login || '';
      document.getElementById('mt5_server').value = currentConfig.mt5_server || '';
      document.getElementById('correlation_block_threshold').value = currentConfig.correlation_block_threshold || 0.40;
      document.getElementById('max_daily_loss_money').value = currentConfig.max_daily_loss_money || 500;
      document.getElementById('daily_target_money').value = currentConfig.daily_target_money || 1000;
      document.getElementById('eod_flatten_time').value = currentConfig.eod_flatten_time || '17:35';

      renderCategoriesAndAccounts(currentConfig.custom_categories, currentConfig.accounts);
      await loadBrokerSymbols();
    }

    async function refreshStatus() {
      try {
        const res = await fetch('/api/status');
        if (res.status === 401) { window.location.href = '/login'; return; }
        const snap = await res.json();
        const acc = snap.account || {};
        document.getElementById('connBadge').textContent = `${acc.backend || 'ONLINE'} • ${acc.login || ''}`;
        document.getElementById('kpiAccount').textContent = `${acc.login || '---'}`;
        document.getElementById('kpiServer').textContent = `Servidor: ${acc.server || '---'}`;
        document.getElementById('kpiEquity').textContent = `${acc.currency || 'R$'} ${(acc.equity || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;
        document.getElementById('kpiBalance').textContent = `Saldo: ${(acc.balance || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`;

        const bots = snap.bots || [];
        const runningCount = bots.filter(b => b.status === 'RUNNING').length;
        document.getElementById('kpiBotsRunning').textContent = `${runningCount} / ${bots.length}`;
        document.getElementById('tabBotCount').textContent = runningCount;
        document.getElementById('kpiRiskStatus').textContent = snap.risk_status || 'OPERACIONAL';

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

        // Render Running Bots Table
        const botsBody = document.getElementById('runningBotsBody');
        if (bots.length === 0) {
          botsBody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--muted);padding:22px;">Nenhum robô criado ainda. Clique em <strong>"🚀 Criar &amp; Executar Novo Robô"</strong> para lançar seu primeiro robô automático!</td></tr>';
        } else {
          botsBody.innerHTML = bots.map(b => {
            const isRun = b.status === 'RUNNING';
            return `
              <tr>
                <td><strong>${b.name}</strong><br/><small style="color:var(--muted)">Ordens: ${b.trades_executed || 0}</small></td>
                <td>${b.account_label || b.account_id}</td>
                <td><strong>${b.symbol}</strong><br/><small style="color:var(--muted)">${b.category || ''}</small></td>
                <td><span class="pill pill-wait">${b.operation_mode}</span></td>
                <td>${b.lot_size}</td>
                <td><strong>${b.last_price || '---'}</strong><br/><small style="color:var(--gold)">VWAP: ${b.vwap || '---'}</small></td>
                <td>Z: <strong>${Number(b.aggression_zscore || 0).toFixed(2)}</strong><br/>Imb: ${(Number(b.imbalance_ratio || 0) * 100).toFixed(1)}%</td>
                <td>${regimePill(b.last_regime)}</td>
                <td>${actionPill(b.last_signal)}</td>
                <td>
                  <span class="pill ${isRun ? 'pill-up' : 'pill-down'}">
                    ${isRun ? '● RODANDO' : '■ PARADO'}
                  </span>
                </td>
                <td style="display:flex;gap:6px;">
                  ${isRun
                    ? `<button class="btn btn-danger" onclick="botAction('${b.bot_id}', 'STOP')">⏸ Pausar</button>`
                    : `<button class="btn btn-green" onclick="botAction('${b.bot_id}', 'START')">▶ Executar</button>`
                  }
                  <button class="btn" onclick="botAction('${b.bot_id}', 'DELETE')">🗑️</button>
                </td>
              </tr>
            `;
          }).join('');
        }

        document.getElementById('lastUpdate').textContent = `Atualizado: ${snap.timestamp || ''}`;

        const symBody = document.getElementById('symbolsBody');
        const syms = Object.values(snap.symbols || {});
        symBody.innerHTML = syms.map(s => `
          <tr>
            <td><strong>${s.symbol}</strong> <small style="color:var(--muted)">${s.is_real_volume ? 'B3 RealVol' : 'TickVol'}</small></td>
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
            <td style="width:140px;"><span class="pill pill-wait">${ev.category}</span></td>
            <td>${ev.message}</td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function createAndRunBot(e) {
      e.preventDefault();
      const catSel = document.getElementById('bot_category_filter');
      const payload = {
        name: document.getElementById('bot_name').value.trim(),
        account_id: document.getElementById('bot_account_id').value,
        symbol: document.getElementById('bot_symbol').value,
        category: catSel.value || 'Corretora MT5',
        operation_mode: document.getElementById('bot_operation_mode').value,
        lot_size: Number(document.getElementById('bot_lot_size').value || 1.0),
        zscore_threshold: Number(document.getElementById('bot_zscore').value || 1.8),
        imbalance_threshold: Number(document.getElementById('bot_imbalance').value || 0.35),
        revert_sigma: Number(document.getElementById('bot_revert_sigma').value || 2.0),
        correlated_basket: document.getElementById('bot_corr_basket').value.split(',').map(s => s.trim()).filter(Boolean),
        auto_start: true
      };
      const res = await fetch('/api/bots', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        showToast(`Robô "${data.bot.name}" criado e EXECUTANDO automaticamente!`);
        document.getElementById('bot_name').value = '';
        switchTab('running-bots', document.querySelectorAll('.tab-btn')[0]);
        refreshStatus();
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
        renderCategoriesAndAccounts(data.categories, currentConfig.accounts);
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
        renderCategoriesAndAccounts(data.categories, currentConfig.accounts);
        await loadBrokerSymbols();
        showToast(`Categoria "${catName}" removida.`);
      }
    }

    async function saveMt5Account(e) {
      e.preventDefault();
      const payload = {
        label: document.getElementById('acc_label').value.trim(),
        mt5_login: document.getElementById('mt5_login').value.trim(),
        mt5_password: document.getElementById('mt5_password').value,
        mt5_server: document.getElementById('mt5_server').value.trim(),
        connect_now: true
      };
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        currentConfig.accounts = data.accounts;
        renderCategoriesAndAccounts(currentConfig.custom_categories, data.accounts);
        await loadBrokerSymbols();
        showToast('Conta MetaTrader 5 salva e conectada via Python!');
        refreshStatus();
      }
    }

    async function saveStrategyConfig(e) {
      e.preventDefault();
      const payload = {
        correlation_block_threshold: Number(document.getElementById('correlation_block_threshold').value),
        max_daily_loss_money: Number(document.getElementById('max_daily_loss_money').value),
        daily_target_money: Number(document.getElementById('daily_target_money').value),
        eod_flatten_time: document.getElementById('eod_flatten_time').value.trim()
      };
      const newPwd = document.getElementById('new_admin_password').value;
      if (newPwd) payload.new_admin_password = newPwd;

      await fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      showToast('Regras globais atualizadas!');
      refreshStatus();
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

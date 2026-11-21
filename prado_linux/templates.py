"""HTML templates for Prado Institutional HFT Login & Web Dashboard."""
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
      --cyan: #22d3ee;
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
      transition: transform 0.1s, opacity 0.2s;
    }
    button:hover { opacity: 0.94; }
    button:active { transform: scale(0.99); }
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
    <span class="badge">Wall Street Desk • Ubuntu Server</span>
    <h1>Prado Institutional HFT</h1>
    <p class="sub">Painel de Controle Quantitativo VWAP + Fluxo de Agressão (B3, Forex, Índices &amp; Cripto)</p>
    <div id="errBox" class="err"></div>
    <form id="loginForm">
      <label for="username">USUÁRIO DO PAINEL</label>
      <input id="username" name="username" type="text" value="admin" required autocomplete="username" />
      <label for="password">SENHA DE ACESSO</label>
      <input id="password" name="password" type="password" placeholder="••••••••" required autocomplete="current-password" />
      <button type="submit">ACESSAR MESA INSTITUCIONAL</button>
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
  <title>Prado Institutional HFT &amp; VWAP Universal — Ubuntu Command Center</title>
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
      padding: 9px 18px;
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
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
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
      <button class="btn btn-green" id="toggleAutoBtn" onclick="toggleAutoTrading()">ROBO: ATIVO</button>
      <button class="btn btn-danger" onclick="panicFlatten()">🚨 ZERAR TUDO AGORA</button>
      <button class="btn" onclick="logout()">SAIR</button>
    </div>
  </header>

  <div class="container">
    <div class="kpi-grid">
      <div class="kpi">
        <div class="label">CONTA METATRADER 5</div>
        <div class="val" id="kpiAccount">---</div>
        <div class="sub" id="kpiServer">Servidor: ---</div>
      </div>
      <div class="kpi">
        <div class="label">SALDO / EQUITY</div>
        <div class="val" id="kpiEquity">R$ 0,00</div>
        <div class="sub" id="kpiBalance">Saldo: R$ 0,00</div>
      </div>
      <div class="kpi">
        <div class="label">P&amp;L ABERTO / DIA</div>
        <div class="val" id="kpiProfit">0.00</div>
        <div class="sub" id="kpiRiskStatus">Status: OPERACIONAL</div>
      </div>
      <div class="kpi">
        <div class="label">BÚSSOLA DE CORRELAÇÃO (CESTA)</div>
        <div class="val" id="kpiCorr">0.0000</div>
        <div class="sub">Filtro Institucional Multi-Ativo</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('monitor', this)">📊 Monitoramento VWAP &amp; Fluxo</button>
      <button class="tab-btn" onclick="switchTab('mt5', this)">🔌 Conta MetaTrader 5 (Conexão Python)</button>
      <button class="tab-btn" onclick="switchTab('strategy', this)">🏛️ Estratégia do Broker de Wall Street (.txt)</button>
    </div>

    <!-- ABA 1: MONITORAMENTO -->
    <div id="tab-monitor" class="tab-content active">
      <div class="card">
        <h2>
          <span>RADAR QUANTITATIVO EM TEMPO REAL — VWAP, DESVIO PADRÃO (&plusmn;1&sigma; / &plusmn;2&sigma;) &amp; Z-SCORE DE AGRESSÃO</span>
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
              <th>Origem</th>
            </tr>
          </thead>
          <tbody id="positionsBody"></tbody>
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

    <!-- ABA 2: CONTA MT5 -->
    <div id="tab-mt5" class="tab-content">
      <div class="card">
        <h2>CONEXÃO DIRETA PYTHON &leftrightarrow; CONTA METATRADER 5</h2>
        <div class="quote-box">
          Informe o Login, Senha e Servidor da sua conta MetaTrader 5. No Ubuntu, o serviço se conecta automaticamente ao terminal MT5 Headless (Wine/RPyC) ou nativo.
        </div>
        <form id="mt5Form" onsubmit="saveMt5Config(event)">
          <div class="form-grid">
            <div class="field">
              <label>Modo de Conexão no Servidor</label>
              <select id="mt5_connection_mode">
                <option value="AUTO_MT5_WINE">Automático (MT5 Nativo / Ubuntu Wine Headless Bridge)</option>
                <option value="SIMULATION">Simulação Quantitativa (Teste sem corretora)</option>
              </select>
              <small>No Ubuntu com install.sh, o container/serviço Wine sobe o MT5 automaticamente.</small>
            </div>
            <div class="field">
              <label>Login da Conta MT5 (Número)</label>
              <input type="text" id="mt5_login" placeholder="Ex: 10293847" />
            </div>
            <div class="field">
              <label>Senha da Conta MT5</label>
              <input type="password" id="mt5_password" placeholder="Senha da corretora no MT5" />
            </div>
            <div class="field">
              <label>Servidor da Corretora no MT5</label>
              <input type="text" id="mt5_server" placeholder="Ex: XPInvestimentos-PRD ou MetaQuotes-Demo" />
            </div>
            <div class="field">
              <label>Host RPyC Bridge (Ubuntu Wine)</label>
              <input type="text" id="rpyc_host" value="127.0.0.1" />
            </div>
            <div class="field">
              <label>Porta RPyC Bridge</label>
              <input type="number" id="rpyc_port" value="18812" />
            </div>
          </div>
          <div style="margin-top: 18px; display:flex; gap:12px;">
            <button type="submit" class="btn btn-gold">💾 SALVAR &amp; CONECTAR CONTA MT5</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ABA 3: ESTRATÉGIA DO BROKER (.TXT) -->
    <div id="tab-strategy" class="tab-content">
      <div class="card">
        <h2>CALIBRAGEM FIEL À ENTREVISTA: "BROKER DE WALL STREET REVELA O QUE OS GRINGOS FAZEM NA B3"</h2>
        <div class="quote-box">
          <strong>Regras do Broker Institucional ("Fio"):</strong><br/>
          • <strong>Fala 1 (Trem Institucional VWAP):</strong> Ordens institucionais chegam via protocolo FIX para executar na VWAP. Quando o Z-Score de agressão rompe o limiar a favor da VWAP, entramos a favor do fluxo.<br/>
          • <strong>Fala 2 (Giro HFT na Média):</strong> Provedores de liquidez não-direcionais vendem a banda superior (+2&sigma;) e compram a banda inferior (-2&sigma;) quando o fluxo mostra exaustão, buscando o retorno à VWAP.<br/>
          • <strong>Correlação &amp; Fim de Dia:</strong> Filtra entradas pela cesta correlacionada (ex: PETR4/VALE3 para WIN) e zera obrigatoriamente no fim do pregão ("HFT sempre dorme zerado").
        </div>
        <form id="strategyForm" onsubmit="saveStrategyConfig(event)">
          <div class="form-grid">
            <div class="field">
              <label>Modo Operacional</label>
              <select id="operation_mode">
                <option value="BOTH">AMBOS (Fala 1: Trem Institucional + Fala 2: Giro HFT na Média)</option>
                <option value="TREND_ONLY">SOMENTE TREM INSTITUCIONAL (Seguidor de Fluxo VWAP)</option>
                <option value="REVERT_ONLY">SOMENTE GIRO HFT NA MÉDIA (Reversão Bandas &plusmn;2&sigma;)</option>
              </select>
            </div>
            <div class="field">
              <label>Ativos Monitorados / Operados (separados por vírgula)</label>
              <input type="text" id="active_symbols" placeholder="WIN$N, WDO$N, BTCUSD#, US100Cash#" />
            </div>
            <div class="field">
              <label>Cesta de Correlação Bússola (separados por vírgula)</label>
              <input type="text" id="correlated_basket" placeholder="PETR4, VALE3, Crypto_10#" />
            </div>
            <div class="field">
              <label>Janela de Ticks para Fluxo (Window Ticks)</label>
              <input type="number" id="window_ticks" min="20" max="5000" />
            </div>
            <div class="field">
              <label>Limiar Z-Score de Agressão (Trem Institucional)</label>
              <input type="number" step="0.1" id="zscore_threshold" />
            </div>
            <div class="field">
              <label>Desequilíbrio Mínimo de Agressão (Imbalance 0.1 a 0.9)</label>
              <input type="number" step="0.05" id="imbalance_threshold" />
            </div>
            <div class="field">
              <label>Banda de Desvio Padrão p/ Giro HFT (&sigma;)</label>
              <input type="number" step="0.1" id="revert_sigma" />
            </div>
            <div class="field">
              <label>Bloqueio de Correlação Contrária (0.1 a 0.9)</label>
              <input type="number" step="0.05" id="correlation_block_threshold" />
            </div>
            <div class="field">
              <label>Lote Padrão por Ordem</label>
              <input type="number" step="0.01" id="default_lot_size" />
            </div>
            <div class="field">
              <label>Stop Loss Dinâmico (Multiplicador &sigma;)</label>
              <input type="number" step="0.1" id="sl_sigma_mult" />
            </div>
            <div class="field">
              <label>Take Profit Dinâmico (Multiplicador &sigma;)</label>
              <input type="number" step="0.1" id="tp_sigma_mult" />
            </div>
            <div class="field">
              <label>Limite de Perda Diária (Moeda da Conta)</label>
              <input type="number" step="10" id="max_daily_loss_money" />
            </div>
            <div class="field">
              <label>Meta de Lucro Diário (Moeda da Conta)</label>
              <input type="number" step="10" id="daily_target_money" />
            </div>
            <div class="field">
              <label>Horário de Zeração Obrigatória ("HFT Dorme Zerado")</label>
              <input type="text" id="eod_flatten_time" placeholder="17:35" />
            </div>
            <div class="field">
              <label>Nova Senha de Login Web (opcional)</label>
              <input type="password" id="new_admin_password" placeholder="Deixe em branco para manter a atual" />
            </div>
          </div>
          <div style="margin-top: 18px;">
            <button type="submit" class="btn btn-gold">💾 SALVAR CONFIGURAÇÃO OPERACIONAL</button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <div id="toast" class="toast">Configuração salva!</div>

  <script>
    let currentConfig = {};

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
      btn.classList.add('active');
    }

    function regimePill(regime) {
      if (regime === 'INSTITUTIONAL_TREND_UP') return '<span class="pill pill-up">TREM INSTITUCIONAL ALTA</span>';
      if (regime === 'INSTITUTIONAL_TREND_DOWN') return '<span class="pill pill-down">TREM INSTITUCIONAL BAIXA</span>';
      if (regime === 'HFT_MEAN_REVERSION') return '<span class="pill pill-hft">GIRO HFT NA MÉDIA (&plusmn;2&sigma;)</span>';
      return '<span class="pill pill-wait">NEUTRO / AGUARDANDO</span>';
    }

    function actionPill(action) {
      if (action.startsWith('BUY')) return `<span class="pill pill-up">${action}</span>`;
      if (action.startsWith('SELL')) return `<span class="pill pill-down">${action}</span>`;
      return `<span class="pill pill-wait">${action}</span>`;
    }

    async function loadConfig() {
      const res = await fetch('/api/config');
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      currentConfig = data.config || {};
      document.getElementById('mt5_connection_mode').value = currentConfig.mt5_connection_mode || 'AUTO_MT5_WINE';
      document.getElementById('mt5_login').value = currentConfig.mt5_login || '';
      document.getElementById('mt5_server').value = currentConfig.mt5_server || '';
      document.getElementById('rpyc_host').value = currentConfig.rpyc_host || '127.0.0.1';
      document.getElementById('rpyc_port').value = currentConfig.rpyc_port || 18812;

      document.getElementById('operation_mode').value = currentConfig.operation_mode || 'BOTH';
      document.getElementById('active_symbols').value = (currentConfig.active_symbols || []).join(', ');
      document.getElementById('correlated_basket').value = (currentConfig.correlated_basket || []).join(', ');
      document.getElementById('window_ticks').value = currentConfig.window_ticks || 120;
      document.getElementById('zscore_threshold').value = currentConfig.zscore_threshold || 1.8;
      document.getElementById('imbalance_threshold').value = currentConfig.imbalance_threshold || 0.35;
      document.getElementById('revert_sigma').value = currentConfig.revert_sigma || 2.0;
      document.getElementById('correlation_block_threshold').value = currentConfig.correlation_block_threshold || 0.40;
      document.getElementById('default_lot_size').value = currentConfig.default_lot_size || 1.0;
      document.getElementById('sl_sigma_mult').value = currentConfig.sl_sigma_mult || 1.0;
      document.getElementById('tp_sigma_mult').value = currentConfig.tp_sigma_mult || 1.8;
      document.getElementById('max_daily_loss_money').value = currentConfig.max_daily_loss_money || 500;
      document.getElementById('daily_target_money').value = currentConfig.daily_target_money || 1000;
      document.getElementById('eod_flatten_time').value = currentConfig.eod_flatten_time || '17:35';
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

        const prof = Number(acc.profit || 0);
        const kpiProf = document.getElementById('kpiProfit');
        kpiProf.textContent = `${prof >= 0 ? '+' : ''}${prof.toFixed(2)}`;
        kpiProf.style.color = prof >= 0 ? 'var(--green)' : 'var(--red)';
        document.getElementById('kpiRiskStatus').textContent = snap.risk_status || 'OPERACIONAL';

        const corr = Number(snap.correlation_bias || 0);
        const kpiCorr = document.getElementById('kpiCorr');
        kpiCorr.textContent = `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(1)}%`;
        kpiCorr.style.color = corr > 0.15 ? 'var(--green)' : (corr < -0.15 ? 'var(--red)' : '#fff');

        const autoBtn = document.getElementById('toggleAutoBtn');
        if (snap.auto_trading_enabled) {
          autoBtn.textContent = 'ROBÔ: ATIVO (AUTO)';
          autoBtn.className = 'btn btn-green';
        } else {
          autoBtn.textContent = 'ROBÔ: PAUSADO';
          autoBtn.className = 'btn btn-danger';
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

    async function saveMt5Config(e) {
      e.preventDefault();
      const payload = {
        mt5_connection_mode: document.getElementById('mt5_connection_mode').value,
        mt5_login: document.getElementById('mt5_login').value.trim(),
        mt5_server: document.getElementById('mt5_server').value.trim(),
        rpyc_host: document.getElementById('rpyc_host').value.trim(),
        rpyc_port: Number(document.getElementById('rpyc_port').value || 18812),
        reconnect: true
      };
      const pwd = document.getElementById('mt5_password').value;
      if (pwd) payload.mt5_password = pwd;

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      showToast(data.message || 'Conta MT5 atualizada!');
      refreshStatus();
    }

    async function saveStrategyConfig(e) {
      e.preventDefault();
      const syms = document.getElementById('active_symbols').value.split(',').map(s => s.trim()).filter(Boolean);
      const corr = document.getElementById('correlated_basket').value.split(',').map(s => s.trim()).filter(Boolean);
      const payload = {
        operation_mode: document.getElementById('operation_mode').value,
        active_symbols: syms,
        correlated_basket: corr,
        window_ticks: Number(document.getElementById('window_ticks').value),
        zscore_threshold: Number(document.getElementById('zscore_threshold').value),
        imbalance_threshold: Number(document.getElementById('imbalance_threshold').value),
        revert_sigma: Number(document.getElementById('revert_sigma').value),
        correlation_block_threshold: Number(document.getElementById('correlation_block_threshold').value),
        default_lot_size: Number(document.getElementById('default_lot_size').value),
        sl_sigma_mult: Number(document.getElementById('sl_sigma_mult').value),
        tp_sigma_mult: Number(document.getElementById('tp_sigma_mult').value),
        max_daily_loss_money: Number(document.getElementById('max_daily_loss_money').value),
        daily_target_money: Number(document.getElementById('daily_target_money').value),
        eod_flatten_time: document.getElementById('eod_flatten_time').value.trim()
      };
      const newPwd = document.getElementById('new_admin_password').value;
      if (newPwd) payload.new_admin_password = newPwd;

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      await res.json();
      showToast('Parâmetros operacionais salvos e aplicados em tempo real!');
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
      showToast(nextState ? 'Robô Automático ATIVADO!' : 'Robô Automático PAUSADO!');
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

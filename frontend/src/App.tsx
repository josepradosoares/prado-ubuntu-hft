import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
  ShieldCheck,
  Power,
  AlertTriangle,
  Unlock,
  LogOut,
  Settings,
  KeyRound,
  Layers,
  FlaskConical,
  BarChart3,
  Bot,
  Sliders,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import {
  BacktestReport,
  BotItem,
  BotTemplate,
  BrokerSymbol,
  ChartPoint,
  DerivAccount,
  ServerConfig,
  Snapshot,
} from './types'
import { LightweightChartPanel } from './components/LightweightChartPanel'
import { BotCardGrid } from './components/BotCardGrid'

type TabKey =
  | 'running-bots'
  | 'create-bot'
  | 'backtest'
  | 'categories'
  | 'deriv-config'
  | 'deriv-tokens'
  | 'monitor'

export default function App() {
  const [authChecked, setAuthChecked] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [loginUser, setLoginUser] = useState('admin')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')

  const [activeTab, setActiveTab] = useState<TabKey>('running-bots')
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [config, setConfig] = useState<ServerConfig | null>(null)
  const [templates, setTemplates] = useState<BotTemplate[]>([])
  const [symbols, setSymbols] = useState<BrokerSymbol[]>([])
  const [symbolMode, setSymbolMode] = useState<'PRINCIPAIS' | 'TODOS'>('PRINCIPAIS')
  const [chartSymbol, setChartSymbol] = useState('R_100')
  const [chartPoints, setChartPoints] = useState<ChartPoint[]>([])
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)

  // Bot form state
  const [editingBotId, setEditingBotId] = useState('')
  const [botName, setBotName] = useState('')
  const [botAccountId, setBotAccountId] = useState('')
  const [botTemplateId, setBotTemplateId] = useState('WALL_STREET_HYBRID_BOTH')
  const [botSymbol, setBotSymbol] = useState('R_100')
  const [botStake, setBotStake] = useState(10)
  const [botMult, setBotMult] = useState(100)
  const [botWindow, setBotWindow] = useState(120)
  const [botZscore, setBotZscore] = useState(1.8)
  const [botImb, setBotImb] = useState(0.35)
  const [botRevertSigma, setBotRevertSigma] = useState(2.0)

  // Backtest form state
  const [btSymbol, setBtSymbol] = useState('R_100')
  const [btTemplateId, setBtTemplateId] = useState('WALL_STREET_HYBRID_BOTH')
  const [btTicks, setBtTicks] = useState(400)
  const [btCapital, setBtCapital] = useState(10000)
  const [btStake, setBtStake] = useState(10)
  const [btResult, setBtResult] = useState<BacktestReport | null>(null)

  // Category form state
  const [catName, setCatName] = useState('')
  const [catSymbols, setCatSymbols] = useState('')

  // Config Deriv state
  const [cfgToken, setCfgToken] = useState('')
  const [cfgAppId, setCfgAppId] = useState('1089')
  const [cfgConnMode, setCfgConnMode] = useState('DERIV_CLOUD')

  // Account Vault form state
  const [editingAccId, setEditingAccId] = useState('')
  const [accType, setAccType] = useState<'DEMO' | 'REAL'>('DEMO')
  const [accLabel, setAccLabel] = useState('')
  const [accToken, setAccToken] = useState('')
  const [accAppId, setAccAppId] = useState('1089')
  const [accStake, setAccStake] = useState(10)
  const [accMult, setAccMult] = useState(100)
  const [accConnMode, setAccConnMode] = useState('DERIV_CLOUD')

  const showToast = useCallback((msg: string, err = false) => {
    setToast({ msg, err })
    setTimeout(() => setToast(null), 4500)
  }, [])

  const fetchChart = useCallback(async (sym: string) => {
    try {
      const res = await fetch(`/api/chart?symbol=${encodeURIComponent(sym)}`)
      if (!res.ok) return
      const data = await res.json()
      if (data.ok && Array.isArray(data.points)) {
        setChartPoints(data.points)
      }
    } catch {
      // ignore transient network errors
    }
  }, [])

  const loadAllInitial = useCallback(async () => {
    const [statusRes, cfgRes, tplRes, symRes] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/config'),
      fetch('/api/templates'),
      fetch(`/api/symbols?mode=${symbolMode}`),
    ])

    if (statusRes.status === 401) {
      setAuthenticated(false)
      setAuthChecked(true)
      return
    }

    setAuthenticated(true)
    setAuthChecked(true)

    if (statusRes.ok) {
      const snap: Snapshot = await statusRes.json()
      setSnapshot(snap)
    }
    if (cfgRes.ok) {
      const cfgData = await cfgRes.json()
      const c: ServerConfig = cfgData.config
      setConfig(c)
      setCfgAppId(c.deriv_app_id || '1089')
      setCfgConnMode(c.connection_mode || 'DERIV_CLOUD')
      setAccAppId(c.deriv_app_id || '1089')
      setAccConnMode(c.connection_mode || 'DERIV_CLOUD')
      if (c.accounts?.length && !botAccountId) {
        setBotAccountId(c.active_account_id || c.accounts[0].account_id)
      }
      if (c.active_symbols?.length) {
        setChartSymbol((prev) => (c.active_symbols.includes(prev) ? prev : c.active_symbols[0]))
      }
    }
    if (tplRes.ok) {
      const tData = await tplRes.json()
      setTemplates(tData.templates || [])
    }
    if (symRes.ok) {
      const sData = await symRes.json()
      setSymbols(sData.symbols || [])
    }
  }, [botAccountId, symbolMode])

  useEffect(() => {
    loadAllInitial()
  }, [loadAllInitial])

  useEffect(() => {
    if (!authenticated) return
    fetchChart(chartSymbol)
    const id = setInterval(async () => {
      try {
        const res = await fetch('/api/status')
        if (res.status === 401) {
          setAuthenticated(false)
          return
        }
        if (res.ok) {
          const snap: Snapshot = await res.json()
          setSnapshot(snap)
        }
        fetchChart(chartSymbol)
      } catch {
        // ignore polling blip
      }
    }, 2000)
    return () => clearInterval(id)
  }, [authenticated, chartSymbol, fetchChart])

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    setLoginError('')
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: loginUser, password: loginPass }),
    })
    const data = await res.json()
    if (res.ok && data.ok) {
      setAuthenticated(true)
      await loadAllInitial()
    } else {
      setLoginError(data.error || 'Usuário ou senha inválidos.')
    }
  }

  async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' })
    setAuthenticated(false)
    setSnapshot(null)
  }

  async function refreshSymbols(mode: 'PRINCIPAIS' | 'TODOS') {
    setSymbolMode(mode)
    const res = await fetch(`/api/symbols?mode=${mode}`)
    if (res.ok) {
      const d = await res.json()
      setSymbols(d.symbols || [])
    }
  }

  async function handleBotAction(botId: string, action: string) {
    const res = await fetch('/api/bots/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_id: botId, action }),
    })
    const d = await res.json()
    if (d.ok) {
      showToast(`Comando ${action} executado.`)
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    } else {
      showToast(d.error || 'Falha no comando do robô.', true)
    }
  }

  async function handleDeleteAllBots() {
    const res = await fetch('/api/bots/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'DELETE_ALL' }),
    })
    if (res.ok) {
      showToast('Frota de robôs limpa.')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  function startEditBot(b: BotItem) {
    setEditingBotId(b.bot_id)
    setBotName(b.name)
    setBotAccountId(b.account_id)
    setBotTemplateId(b.template_id)
    setBotSymbol(b.symbol)
    setBotStake(b.lot_size)
    setBotMult(b.multiplier)
    setBotWindow(b.window_ticks)
    setBotZscore(b.zscore_threshold)
    setBotImb(b.imbalance_threshold)
    setBotRevertSigma(b.revert_sigma)
    setActiveTab('create-bot')
  }

  async function saveBot(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      name: botName.trim() || `Bot ${botSymbol}`,
      account_id: botAccountId || config?.active_account_id || '',
      template_id: botTemplateId,
      symbol: botSymbol,
      lot_size: Number(botStake),
      multiplier: Number(botMult),
      window_ticks: Number(botWindow),
      zscore_threshold: Number(botZscore),
      imbalance_threshold: Number(botImb),
      revert_sigma: Number(botRevertSigma),
      auto_start: true,
    }
    if (editingBotId) payload.bot_id = editingBotId

    const res = await fetch('/api/bots', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const d = await res.json()
    if (d.ok) {
      setEditingBotId('')
      setBotName('')
      showToast('Robô matemático salvo!')
      setActiveTab('running-bots')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  async function runBacktest(e: FormEvent) {
    e.preventDefault()
    const res = await fetch('/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: btSymbol,
        template_id: btTemplateId,
        tick_count: Number(btTicks),
        initial_capital: Number(btCapital),
        lot_size: Number(btStake),
      }),
    })
    const d = await res.json()
    if (d.ok) {
      setBtResult(d.report)
      if (config) setConfig({ ...config, backtest_history: d.history || [] })
      showToast('Backtest concluído!')
    }
  }

  async function saveCategory(e: FormEvent) {
    e.preventDefault()
    const syms = catSymbols
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const res = await fetch('/api/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_name: catName.trim(), symbols: syms }),
    })
    const d = await res.json()
    if (d.ok && config) {
      setConfig({ ...config, custom_categories: d.categories })
      setCatName('')
      setCatSymbols('')
      showToast('Categoria salva!')
    }
  }

  async function saveDerivConfig(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      deriv_app_id: cfgAppId.trim() || '1089',
      connection_mode: cfgConnMode,
    }
    if (cfgToken.trim()) payload.deriv_token = cfgToken.trim()

    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const d = await res.json()
    if (d.ok) {
      setConfig(d.config)
      setCfgToken('')
      setAccAppId(d.config.deriv_app_id || '1089')
      setAccConnMode(d.config.connection_mode || 'DERIV_CLOUD')
      showToast('Configuração Deriv salva e carregada para criação de contas!')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  async function saveDerivAccount(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      account_type: accType,
      label: accLabel.trim(),
      deriv_token: accToken.trim(),
      deriv_app_id: accAppId.trim() || '1089',
      default_stake_usd: Number(accStake),
      default_multiplier: Number(accMult),
      connection_mode: accConnMode,
    }
    if (editingAccId) payload.account_id = editingAccId

    const res = await fetch('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const d = await res.json()
    if (d.ok) {
      setEditingAccId('')
      setAccLabel('')
      setAccToken('')
      if (config) {
        setConfig({ ...config, accounts: d.accounts, active_account_id: d.account.account_id })
      }
      showToast(d.message || 'Conta Deriv salva!')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  async function selectAccount(accountId: string) {
    const res = await fetch('/api/accounts/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id: accountId }),
    })
    const d = await res.json()
    if (d.ok) {
      if (config) setConfig({ ...config, active_account_id: accountId })
      showToast(d.message || 'Conta ativada.')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  async function deleteAccount(accountId: string) {
    const res = await fetch('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'DELETE', account_id: accountId }),
    })
    const d = await res.json()
    if (d.ok && config) {
      setConfig({ ...config, accounts: d.accounts })
      showToast('Token removido.')
    }
  }

  async function toggleAutoTrading() {
    const next = !(snapshot?.auto_trading_enabled ?? true)
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_trading_enabled: next }),
    })
    if (res.ok) {
      showToast(next ? 'Execução automática ativada.' : 'Execução automática pausada.')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  async function panicFlatten(ticket?: string | number) {
    const res = await fetch('/api/flatten', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ticket !== undefined ? { ticket } : {}),
    })
    const d = await res.json()
    if (d.ok) {
      showToast(d.message || 'Posições zeradas.')
      const stRes = await fetch('/api/status')
      if (stRes.ok) setSnapshot(await stRes.json())
    }
  }

  const monitoredSymbols = useMemo(() => {
    const set = new Set<string>(['R_100', 'cryBTCUSD', 'frxEURUSD'])
    if (snapshot?.symbols) {
      Object.keys(snapshot.symbols).forEach((s) => set.add(s))
    }
    snapshot?.bots?.forEach((b) => set.add(b.symbol))
    return Array.from(set)
  }, [snapshot])

  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-400 text-sm font-mono">
        Inicializando terminal Prado HFT...
      </div>
    )
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-[#0b111e]/95 p-8 shadow-2xl shadow-black/60">
          <div className="flex items-center gap-3 mb-6">
            <div className="h-10 w-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Prado Institutional HFT</h1>
              <p className="text-xs text-slate-400">Deriv Multipliers • Servidor Ubuntu 24/7</p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Usuário</label>
              <input
                type="text"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white focus:border-amber-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Senha</label>
              <input
                type="password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white focus:border-amber-500 focus:outline-none"
                required
              />
            </div>
            {loginError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                {loginError}
              </div>
            )}
            <button
              type="submit"
              className="w-full rounded-xl bg-amber-500 hover:bg-amber-400 py-2.5 text-sm font-semibold text-slate-950 transition shadow-lg shadow-amber-500/20"
            >
              Entrar no Terminal
            </button>
          </form>
        </div>
      </div>
    )
  }

  const acc = snapshot?.account
  const activeBots = snapshot?.bots?.filter((b) => b.active).length ?? 0
  const totalBots = snapshot?.bots?.length ?? 0
  const isConnected = Boolean(acc?.connected)

  const navItems: { key: TabKey; label: string; icon: JSX.Element; count?: number }[] = [
    { key: 'running-bots', label: 'Mesa de execução e robôs', icon: <Bot className="h-3.5 w-3.5" />, count: totalBots },
    { key: 'create-bot', label: 'Configurar robô matemático', icon: <Sliders className="h-3.5 w-3.5" /> },
    { key: 'backtest', label: 'Backtest tick a tick', icon: <FlaskConical className="h-3.5 w-3.5" /> },
    { key: 'categories', label: 'Categorias de ativos', icon: <Layers className="h-3.5 w-3.5" /> },
    { key: 'deriv-config', label: 'Configuração Deriv', icon: <Settings className="h-3.5 w-3.5" /> },
    { key: 'deriv-tokens', label: 'Tokens e Contas Deriv', icon: <KeyRound className="h-3.5 w-3.5" /> },
    { key: 'monitor', label: 'Matriz VWAP e Z-Score', icon: <BarChart3 className="h-3.5 w-3.5" /> },
  ]

  return (
    <div className="min-h-screen flex flex-col">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-xl border px-4 py-3 text-xs font-medium shadow-2xl ${
            toast.err
              ? 'border-rose-500/40 bg-rose-950/90 text-rose-200'
              : 'border-emerald-500/40 bg-slate-900/95 text-emerald-200'
          }`}
        >
          {toast.err ? <XCircle className="h-4 w-4 text-rose-400" /> : <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          {toast.msg}
        </div>
      )}

      {/* Topbar */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-[#070b12]/90 backdrop-blur-md">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isConnected ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.9)]' : 'bg-rose-500'
              }`}
            />
            <span className="text-sm font-bold tracking-tight text-white">Prado Institutional HFT • Deriv</span>
            <span className="hidden sm:inline-block rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-0.5 text-[11px] font-mono text-slate-400">
              {acc?.backend || 'DERIV_DISCONNECTED'} • {acc?.login || 'DESCONECTADO'}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={config?.active_account_id || ''}
              onChange={(e) => selectAccount(e.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
            >
              {!config?.accounts?.length && <option value="">Sem token salvo</option>}
              {config?.accounts?.map((a) => (
                <option key={a.account_id} value={a.account_id}>
                  [{a.account_type}] {a.label} ({a.loginid || 'Deriv'})
                </option>
              ))}
            </select>

            <button
              onClick={toggleAutoTrading}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
                snapshot?.auto_trading_enabled
                  ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25'
                  : 'border-slate-700 bg-slate-800 text-slate-300'
              }`}
            >
              <Power className="h-3.5 w-3.5" />
              {snapshot?.auto_trading_enabled ? 'Auto: Ativo' : 'Auto: Pausado'}
            </button>

            <button
              onClick={() => panicFlatten()}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/30 bg-rose-500/15 hover:bg-rose-500/25 px-3 py-1.5 text-xs font-semibold text-rose-300 transition"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              Zerar tudo
            </button>

            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900 hover:bg-slate-800 px-3 py-1.5 text-xs text-slate-300 transition"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sair
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 sm:px-6 py-5 space-y-5">
        {/* KPI Strip */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/90 p-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Conta Deriv conectada</span>
              <span
                className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                  acc?.account_type === 'REAL'
                    ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                    : 'bg-sky-500/15 text-sky-300 border border-sky-500/30'
                }`}
              >
                {acc?.account_type || 'DEMO'}
              </span>
            </div>
            <div className="mt-2 text-lg font-bold font-mono text-white truncate">
              {acc?.login || 'DESCONECTADO'}
            </div>
            <div className="mt-1 text-[11px] text-slate-400 truncate" title={acc?.status_note || acc?.server}>
              {acc?.status_note || acc?.server || 'Aguardando token'}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/90 p-4">
            <div className="text-xs text-slate-400">Saldo / Equity</div>
            <div className="mt-2 text-lg font-bold font-mono text-white">
              {acc?.currency || 'USD'} {(acc?.equity ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Saldo base: {(acc?.balance ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/90 p-4">
            <div className="text-xs text-slate-400">Robôs matemáticos ativos</div>
            <div className="mt-2 text-lg font-bold font-mono text-amber-300">
              {activeBots} ativos de {totalBots}
            </div>
            <div className="mt-1 text-[11px] text-emerald-400">Motor HFT operacional</div>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/90 p-4">
            <div className="text-xs text-slate-400">Vetor de correlação da cesta</div>
            <div
              className={`mt-2 text-lg font-bold font-mono ${
                (snapshot?.basket_bias ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {(snapshot?.basket_bias ?? 0) >= 0 ? '+' : ''}
              {((snapshot?.basket_bias ?? 0) * 100).toFixed(1)}%
            </div>
            <div className="mt-1 text-[11px] font-mono text-slate-400">
              Ciclo: {snapshot?.timestamp || '---'}
            </div>
          </div>
        </section>

        {/* Responsive Wrap-Friendly Tabs (zero horizontal scroll) */}
        <nav className="flex flex-wrap items-center gap-2 border-b border-slate-800/80 pb-3">
          {navItems.map((t) => {
            const active = activeTab === t.key
            return (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-medium transition ${
                  active
                    ? 'bg-amber-500 text-slate-950 font-semibold shadow-lg shadow-amber-500/20'
                    : 'bg-slate-900/70 text-slate-300 border border-slate-800 hover:bg-slate-800 hover:text-white'
                }`}
              >
                {t.icon}
                <span>{t.label}</span>
                {t.count !== undefined && (
                  <span
                    className={`rounded-md px-1.5 py-0.5 text-[10px] font-mono ${
                      active ? 'bg-slate-950/20 text-slate-950' : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    {t.count}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* TAB 1: RUNNING BOTS + CHART */}
        {activeTab === 'running-bots' && (
          <div className="space-y-6">
            <LightweightChartPanel
              symbol={chartSymbol}
              availableSymbols={monitoredSymbols}
              onSelectSymbol={setChartSymbol}
              points={chartPoints}
              symbolState={snapshot?.symbols?.[chartSymbol]}
            />

            <BotCardGrid
              bots={snapshot?.bots || []}
              symbols={snapshot?.symbols || {}}
              onAction={handleBotAction}
              onEdit={startEditBot}
              onNewBot={() => {
                setEditingBotId('')
                setActiveTab('create-bot')
              }}
              onDeleteAll={handleDeleteAllBots}
            />

            {/* Open Positions */}
            <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 overflow-hidden">
              <div className="border-b border-slate-800/80 px-5 py-3.5 bg-slate-900/40">
                <h3 className="text-sm font-semibold text-white">Contratos abertos na Deriv</h3>
                <p className="text-xs text-slate-400">Acompanhamento em tempo real com Stop Loss e Take Profit</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-800 text-[11px] uppercase text-slate-400 bg-slate-950/40">
                    <tr>
                      <th className="px-4 py-3">Contrato</th>
                      <th className="px-4 py-3">Ativo</th>
                      <th className="px-4 py-3">Lado</th>
                      <th className="px-4 py-3 text-right">Stake</th>
                      <th className="px-4 py-3 text-right">Entrada</th>
                      <th className="px-4 py-3 text-right">Atual</th>
                      <th className="px-4 py-3 text-right">Lucro</th>
                      <th className="px-4 py-3 text-right">Ação</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {!snapshot?.positions?.length ? (
                      <tr>
                        <td colSpan={8} className="px-4 py-8 text-center text-slate-500 font-sans">
                          Nenhum contrato aberto no momento.
                        </td>
                      </tr>
                    ) : (
                      snapshot.positions.map((p) => (
                        <tr key={String(p.ticket)} className="hover:bg-slate-900/40">
                          <td className="px-4 py-3 text-slate-300">#{p.ticket}</td>
                          <td className="px-4 py-3 font-semibold text-white">{p.symbol}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                                p.side === 'BUY' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-rose-500/15 text-rose-300'
                              }`}
                            >
                              {p.side}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">${p.volume}</td>
                          <td className="px-4 py-3 text-right">{p.price_open}</td>
                          <td className="px-4 py-3 text-right">{p.price_current}</td>
                          <td className={`px-4 py-3 text-right font-semibold ${p.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {p.profit >= 0 ? '+' : ''}
                            {p.profit.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => panicFlatten(p.ticket)}
                              className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[11px] text-rose-300 hover:bg-rose-500/20"
                            >
                              Encerrar
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Execution Log */}
            <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 overflow-hidden">
              <div className="border-b border-slate-800/80 px-5 py-3.5 bg-slate-900/40">
                <h3 className="text-sm font-semibold text-white">Diário de execução do motor quantitativo</h3>
              </div>
              <div className="max-h-64 overflow-y-auto divide-y divide-slate-800/50 text-xs font-mono">
                {snapshot?.logs?.slice(0, 25).map((l, idx) => (
                  <div key={idx} className="flex items-start gap-3 px-5 py-2.5">
                    <span className="shrink-0 text-slate-500">{l.time}</span>
                    <span className="shrink-0 rounded bg-slate-800 px-2 py-0.5 text-[10px] text-amber-300">
                      {l.module}
                    </span>
                    <span className="text-slate-300">{l.message}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* TAB 2: CREATE / EDIT BOT */}
        {activeTab === 'create-bot' && (
          <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 p-6">
            <h2 className="text-base font-semibold text-white mb-4">
              {editingBotId ? 'Editar robô matemático' : 'Configurar novo robô matemático'}
            </h2>
            <form onSubmit={saveBot} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Nome do robô</label>
                <input
                  type="text"
                  value={botName}
                  onChange={(e) => setBotName(e.target.value)}
                  placeholder="Ex: Bot R_100 Reversão"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Conta Deriv vinculada</label>
                <select
                  value={botAccountId}
                  onChange={(e) => setBotAccountId(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                >
                  {config?.accounts?.map((a) => (
                    <option key={a.account_id} value={a.account_id}>
                      [{a.account_type}] {a.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Ativo Deriv</label>
                <select
                  value={botSymbol}
                  onChange={(e) => setBotSymbol(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                >
                  {symbols.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name} — {s.description}
                    </option>
                  ))}
                </select>
              </div>
              <div className="md:col-span-2 lg:col-span-3">
                <label className="block text-xs text-slate-400 mb-1">Modelo matemático</label>
                <select
                  value={botTemplateId}
                  onChange={(e) => setBotTemplateId(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                >
                  {templates.map((t) => (
                    <option key={t.template_id} value={t.template_id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Stake (USD)</label>
                <input
                  type="number"
                  step="0.5"
                  value={botStake}
                  onChange={(e) => setBotStake(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Multiplicador</label>
                <select
                  value={botMult}
                  onChange={(e) => setBotMult(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                >
                  {[20, 50, 100, 200, 400].map((m) => (
                    <option key={m} value={m}>
                      {m}x
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Janela (ticks)</label>
                <input
                  type="number"
                  value={botWindow}
                  onChange={(e) => setBotWindow(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Z-Score mínimo</label>
                <input
                  type="number"
                  step="0.1"
                  value={botZscore}
                  onChange={(e) => setBotZscore(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Imbalance mínimo</label>
                <input
                  type="number"
                  step="0.05"
                  value={botImb}
                  onChange={(e) => setBotImb(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Desvio Reversão (σ)</label>
                <input
                  type="number"
                  step="0.1"
                  value={botRevertSigma}
                  onChange={(e) => setBotRevertSigma(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div className="md:col-span-2 lg:col-span-3 flex gap-2 pt-2">
                <button
                  type="submit"
                  className="rounded-xl bg-amber-500 hover:bg-amber-400 px-5 py-2.5 text-xs font-semibold text-slate-950 transition"
                >
                  {editingBotId ? 'Salvar alterações do robô' : 'Criar e ativar robô'}
                </button>
                {editingBotId && (
                  <button
                    type="button"
                    onClick={() => setEditingBotId('')}
                    className="rounded-xl border border-slate-700 px-4 py-2.5 text-xs text-slate-300"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>
          </section>
        )}

        {/* TAB 3: BACKTEST */}
        {activeTab === 'backtest' && (
          <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 p-6 space-y-6">
            <h2 className="text-base font-semibold text-white">Backtest tick a tick</h2>
            <form onSubmit={runBacktest} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Ativo</label>
                <select
                  value={btSymbol}
                  onChange={(e) => setBtSymbol(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                >
                  {symbols.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Modelo</label>
                <select
                  value={btTemplateId}
                  onChange={(e) => setBtTemplateId(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                >
                  {templates.map((t) => (
                    <option key={t.template_id} value={t.template_id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Ticks</label>
                <input
                  type="number"
                  value={btTicks}
                  onChange={(e) => setBtTicks(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Capital (USD)</label>
                <input
                  type="number"
                  value={btCapital}
                  onChange={(e) => setBtCapital(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                />
              </div>
              <div className="flex items-end">
                <button
                  type="submit"
                  className="w-full rounded-xl bg-amber-500 hover:bg-amber-400 py-2.5 text-xs font-semibold text-slate-950"
                >
                  Executar Backtest
                </button>
              </div>
            </form>

            {btResult && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 font-mono text-xs">
                <div>
                  <span className="text-slate-400">Trades</span>
                  <div className="text-base font-bold text-white mt-1">{btResult.total_trades}</div>
                </div>
                <div>
                  <span className="text-slate-400">Taxa de acerto</span>
                  <div className="text-base font-bold text-sky-400 mt-1">{btResult.win_rate}%</div>
                </div>
                <div>
                  <span className="text-slate-400">Lucro líquido</span>
                  <div className={`text-base font-bold mt-1 ${btResult.net_profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    ${btResult.net_profit}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Drawdown máx.</span>
                  <div className="text-base font-bold text-rose-400 mt-1">${btResult.max_drawdown}</div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* TAB 4: CATEGORIES */}
        {activeTab === 'categories' && (
          <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-white">Categorias e Ativos Deriv</h2>
                <p className="text-xs text-slate-400">Alterne entre Principais e Todos os pares carregados da Deriv</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => refreshSymbols('PRINCIPAIS')}
                  className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${
                    symbolMode === 'PRINCIPAIS' ? 'bg-amber-500 text-slate-950' : 'bg-slate-800 text-slate-300'
                  }`}
                >
                  Principais
                </button>
                <button
                  onClick={() => refreshSymbols('TODOS')}
                  className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${
                    symbolMode === 'TODOS' ? 'bg-amber-500 text-slate-950' : 'bg-slate-800 text-slate-300'
                  }`}
                >
                  Todos ({symbols.length})
                </button>
              </div>
            </div>

            <form onSubmit={saveCategory} className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <input
                type="text"
                value={catName}
                onChange={(e) => setCatName(e.target.value)}
                placeholder="Nome da categoria"
                className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                required
              />
              <input
                type="text"
                value={catSymbols}
                onChange={(e) => setCatSymbols(e.target.value)}
                placeholder="Ativos separados por vírgula (ex: R_100, cryBTCUSD)"
                className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                required
              />
              <button
                type="submit"
                className="rounded-xl bg-amber-500 hover:bg-amber-400 px-4 py-2 text-xs font-semibold text-slate-950"
              >
                Salvar categoria
              </button>
            </form>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(config?.custom_categories || {}).map(([name, list]) => (
                <div key={name} className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="text-sm font-semibold text-white">{name}</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {list.map((sym) => (
                      <span key={sym} className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-300">
                        {sym}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* TAB 5: DERIV CONFIG */}
        {activeTab === 'deriv-config' && (
          <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 p-6">
            <h2 className="text-base font-semibold text-white">Configuração Padrão Deriv (Token &amp; App ID)</h2>
            <p className="text-xs text-slate-400 mt-1 mb-5">
              Salve seu token uma única vez aqui; ele será carregado automaticamente ao criar suas contas Demo ou Real.
            </p>
            <form onSubmit={saveDerivConfig} className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
              <div className="md:col-span-2">
                <label className="block text-xs text-slate-400 mb-1">Deriv API Token padrão</label>
                <input
                  type="password"
                  value={cfgToken}
                  onChange={(e) => setCfgToken(e.target.value)}
                  placeholder={
                    config?.deriv_token_set
                      ? 'Token padrão já salvo (cole outro para substituir)'
                      : 'Cole seu token de app.deriv.com/account/api-token'
                  }
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm font-mono text-white"
                />
                <p className="mt-1.5 text-[11px] text-slate-400">
                  Tokens clássicos (app.deriv.com/account/api-token) funcionam direto com App ID 1089. Tokens pat_... exigem App ID de developers.deriv.com.
                </p>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Deriv App ID padrão</label>
                <input
                  type="text"
                  value={cfgAppId}
                  onChange={(e) => setCfgAppId(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Modo de execução padrão</label>
                <select
                  value={cfgConnMode}
                  onChange={(e) => setCfgConnMode(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white"
                >
                  <option value="DERIV_CLOUD">Deriv WebSocket Live (Negociação Real/Demo)</option>
                  <option value="SIMULATION">Simulador Quantitativo Interno</option>
                </select>
              </div>
              <div className="md:col-span-2 pt-2">
                <button
                  type="submit"
                  className="rounded-xl bg-amber-500 hover:bg-amber-400 px-5 py-2.5 text-xs font-semibold text-slate-950"
                >
                  Salvar configuração Deriv
                </button>
              </div>
            </form>
          </section>
        )}

        {/* TAB 6: DERIV ACCOUNTS VAULT */}
        {activeTab === 'deriv-tokens' && (
          <div className="space-y-6">
            <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 p-6">
              <h2 className="text-base font-semibold text-white mb-4">
                {editingAccId ? 'Editar conta Deriv' : 'Cofre de Tokens e Contas Deriv (Demo e Real)'}
              </h2>
              <form onSubmit={saveDerivAccount} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Ambiente</label>
                  <select
                    value={accType}
                    onChange={(e) => setAccType(e.target.value as 'DEMO' | 'REAL')}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                  >
                    <option value="DEMO">Conta Demo Deriv (VRTC)</option>
                    <option value="REAL">Conta Real Deriv (CR)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Nome de identificação</label>
                  <input
                    type="text"
                    value={accLabel}
                    onChange={(e) => setAccLabel(e.target.value)}
                    placeholder="Ex: Deriv Real Principal"
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Deriv App ID</label>
                  <input
                    type="text"
                    value={accAppId}
                    onChange={(e) => setAccAppId(e.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                  />
                </div>
                <div className="lg:col-span-3">
                  <label className="block text-xs text-slate-400 mb-1">Deriv API Token</label>
                  <input
                    type="password"
                    value={accToken}
                    onChange={(e) => setAccToken(e.target.value)}
                    placeholder={
                      config?.deriv_token_set
                        ? 'Token padrão carregado de Configuração Deriv (deixe em branco para usar o salvo)'
                        : 'Cole seu token da Deriv'
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Stake padrão (USD)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={accStake}
                    onChange={(e) => setAccStake(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Multiplicador padrão</label>
                  <select
                    value={accMult}
                    onChange={(e) => setAccMult(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-mono text-white"
                  >
                    {[20, 50, 100, 200, 400].map((m) => (
                      <option key={m} value={m}>
                        {m}x
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Modo</label>
                  <select
                    value={accConnMode}
                    onChange={(e) => setAccConnMode(e.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                  >
                    <option value="DERIV_CLOUD">Deriv WebSocket Live</option>
                    <option value="SIMULATION">Simulador Quant</option>
                  </select>
                </div>
                <div className="lg:col-span-3 flex gap-2 pt-2">
                  <button
                    type="submit"
                    className="rounded-xl bg-amber-500 hover:bg-amber-400 px-5 py-2.5 text-xs font-semibold text-slate-950"
                  >
                    Salvar conta e conectar na Deriv
                  </button>
                  {editingAccId && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditingAccId('')
                        setAccLabel('')
                        setAccToken('')
                      }}
                      className="rounded-xl border border-slate-700 px-4 py-2.5 text-xs text-slate-300"
                    >
                      Cancelar
                    </button>
                  )}
                </div>
              </form>
            </section>

            <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {config?.accounts?.map((a: DerivAccount) => {
                const isActive = a.account_id === config.active_account_id
                return (
                  <div
                    key={a.account_id}
                    className={`rounded-2xl border p-5 bg-[#0b111e]/95 ${
                      isActive ? 'border-emerald-500/40' : 'border-slate-800'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                          a.account_type === 'REAL'
                            ? 'bg-amber-500/15 text-amber-300'
                            : 'bg-sky-500/15 text-sky-300'
                        }`}
                      >
                        {a.account_type}
                      </span>
                      <span className="text-xs font-mono text-slate-400">{a.loginid || '---'}</span>
                    </div>
                    <h3 className="mt-2 text-sm font-bold text-white">{a.label}</h3>
                    <p className="mt-1 text-xs font-mono text-slate-400">
                      App ID: {a.deriv_app_id} • ${a.default_stake_usd} • {a.default_multiplier}x
                    </p>
                    <div className="mt-4 flex gap-2">
                      {!isActive ? (
                        <button
                          onClick={() => selectAccount(a.account_id)}
                          className="flex-1 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 py-1.5 text-xs font-semibold text-emerald-300"
                        >
                          Ativar
                        </button>
                      ) : (
                        <span className="flex-1 rounded-xl bg-slate-800 py-1.5 text-center text-xs text-emerald-400 font-semibold">
                          Em operação
                        </span>
                      )}
                      <button
                        onClick={() => {
                          setEditingAccId(a.account_id)
                          setAccType((a.account_type as 'DEMO' | 'REAL') || 'DEMO')
                          setAccLabel(a.label)
                          setAccAppId(a.deriv_app_id || '1089')
                          setAccStake(a.default_stake_usd || 10)
                          setAccMult(a.default_multiplier || 100)
                          setAccConnMode(a.connection_mode || 'DERIV_CLOUD')
                        }}
                        className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => deleteAccount(a.account_id)}
                        className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/20"
                      >
                        Apagar
                      </button>
                    </div>
                  </div>
                )
              })}
            </section>
          </div>
        )}

        {/* TAB 7: MATRIX */}
        {activeTab === 'monitor' && (
          <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 overflow-hidden">
            <div className="border-b border-slate-800/80 px-5 py-3.5 bg-slate-900/40">
              <h2 className="text-sm font-semibold text-white">Matriz matemática — VWAP, Bandas (±2σ) e Z-Score</h2>
              <p className="text-xs text-slate-400">Cálculo contínuo sobre os ativos monitorados na Deriv</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-800 text-[11px] uppercase text-slate-400 bg-slate-950/40">
                  <tr>
                    <th className="px-4 py-3">Ativo</th>
                    <th className="px-4 py-3 text-right">Preço (P)</th>
                    <th className="px-4 py-3 text-right">VWAP</th>
                    <th className="px-4 py-3 text-right">Banda -2σ</th>
                    <th className="px-4 py-3 text-right">Banda +2σ</th>
                    <th className="px-4 py-3 text-right">Imbalance</th>
                    <th className="px-4 py-3 text-right">Z-Score</th>
                    <th className="px-4 py-3">Regime</th>
                    <th className="px-4 py-3">Sinal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {Object.values(snapshot?.symbols || {}).map((s) => (
                    <tr key={s.symbol} className="hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-bold text-white">{s.symbol}</td>
                      <td className="px-4 py-3 text-right">{s.price.toFixed(5)}</td>
                      <td className="px-4 py-3 text-right text-amber-300">{s.vwap.toFixed(5)}</td>
                      <td className="px-4 py-3 text-right text-emerald-400">{s.lower_2.toFixed(5)}</td>
                      <td className="px-4 py-3 text-right text-rose-400">{s.upper_2.toFixed(5)}</td>
                      <td className={`px-4 py-3 text-right ${s.imbalance >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(s.imbalance * 100).toFixed(1)}%
                      </td>
                      <td className={`px-4 py-3 text-right font-semibold ${s.zscore >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {s.zscore.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-slate-300">{s.regime}</td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] text-slate-200">
                          {s.signal}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

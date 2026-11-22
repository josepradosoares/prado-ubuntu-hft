import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  WifiOff,
  Trash2,
  RefreshCw,
  Sun,
  Moon,
  Lock,
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
import { Sidebar, TabKey } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { MarketIndicatorsBar } from './components/MarketIndicatorsBar'
import { DerivDiagnosticsCard } from './components/DerivDiagnosticsCard'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './components/ui/Card'
import { ConfirmModal } from './components/ui/ConfirmModal'
import { DashboardSkeleton } from './components/ui/Skeleton'
import { useTheme } from './hooks/useTheme'
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatPrice,
  formatSignedNumber,
  formatSignedPercent,
  isFiniteNumber,
  sanitizeChartPoints,
} from './utils/formatters'

const PAGE_META: Record<TabKey, { title: string; description: string }> = {
  overview: {
    title: 'Visão geral',
    description: 'Resumo operacional da conta Deriv, indicadores de mercado e estado da frota HFT',
  },
  'running-bots': {
    title: 'Mesa de execução',
    description: 'Terminal gráfico ao vivo, frota de robôs matemáticos e contratos abertos na Deriv',
  },
  'my-bots': {
    title: 'Meus robôs',
    description: 'Gerenciamento completo, filtros, duplicação e controles operacionais dos robôs',
  },
  'create-bot': {
    title: 'Configurar robô matemático',
    description: 'Parametrização quantitativa de VWAP, Z-Score, Imbalance e multiplicadores Deriv',
  },
  backtest: {
    title: 'Backtest tick a tick',
    description: 'Simulação histórica tick a tick com métricas de acerto, lucro líquido e drawdown',
  },
  monitor: {
    title: 'Matriz VWAP e Z-Score',
    description: 'Leitura contínua de desvios ±2σ, Imbalance, regime de mercado e sinal quantitativo',
  },
  categories: {
    title: 'Categorias de ativos',
    description: 'Catálogo de símbolos Deriv e agrupamentos personalizados para monitoramento',
  },
  'deriv-config': {
    title: 'Configuração Deriv',
    description: 'Credenciais padrão, App ID, modo de execução e diagnóstico de conexão WebSocket',
  },
  'deriv-tokens': {
    title: 'Tokens e Contas',
    description: 'Cofre seguro de contas Demo (VRTC) e Real (CR) com alternância rápida',
  },
  history: {
    title: 'Histórico',
    description: 'Registro de operações executadas e diário do motor quantitativo',
  },
  settings: {
    title: 'Configurações',
    description: 'Preferências visuais, segurança administrativa, trava de risco e parâmetros do sistema',
  },
}

export default function App() {
  const { theme, setTheme, toggleTheme } = useTheme()

  const [authChecked, setAuthChecked] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [loginUser, setLoginUser] = useState('admin')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')

  const [activeTab, setActiveTab] = useState<TabKey>('running-bots')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [config, setConfig] = useState<ServerConfig | null>(null)
  const [templates, setTemplates] = useState<BotTemplate[]>([])
  const [symbols, setSymbols] = useState<BrokerSymbol[]>([])
  const [symbolMode, setSymbolMode] = useState<'PRINCIPAIS' | 'TODOS'>('PRINCIPAIS')
  const symbolModeRef = useRef<'PRINCIPAIS' | 'TODOS'>('PRINCIPAIS')
  const [chartSymbol, setChartSymbol] = useState('R_100')
  const [chartPoints, setChartPoints] = useState<ChartPoint[]>([])
  const [chartLoading, setChartLoading] = useState(false)
  const [chartError, setChartError] = useState<string | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null)

  const [confirmModal, setConfirmModal] = useState<{
    open: boolean
    title: string
    description: string
    confirmLabel: string
    variant: 'danger' | 'warning' | 'primary'
    onConfirm: () => void
  }>({
    open: false,
    title: '',
    description: '',
    confirmLabel: 'Confirmar',
    variant: 'danger',
    onConfirm: () => {},
  })

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
  const [botGridDir, setBotGridDir] = useState<'BUY_ONLY' | 'SELL_ONLY' | 'BOTH'>('BUY_ONLY')
  const [botGridStep, setBotGridStep] = useState(1.5)
  const [botGridTp, setBotGridTp] = useState(1.5)
  const [botGridMaxLevels, setBotGridMaxLevels] = useState(5)
  const [botFormDirty, setBotFormDirty] = useState(false)

  // Backtest form state
  const [btSymbol, setBtSymbol] = useState('R_100')
  const [btTemplateId, setBtTemplateId] = useState('WALL_STREET_HYBRID_BOTH')
  const [btTicks, setBtTicks] = useState(400)
  const [btCapital, setBtCapital] = useState(10000)
  const [btStake, setBtStake] = useState(10)
  const [btResult, setBtResult] = useState<BacktestReport | null>(null)
  const [btRunning, setBtRunning] = useState(false)

  // Category form state
  const [catName, setCatName] = useState('')
  const [catSymbols, setCatSymbols] = useState('')
  const [symbolSearch, setSymbolSearch] = useState('')

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
  const [useCustomCreds, setUseCustomCreds] = useState(false)
  const [syncingAccounts, setSyncingAccounts] = useState(false)

  // Settings password state
  const [newAdminPassword, setNewAdminPassword] = useState('')

  const showToast = useCallback((msg: string, err = false) => {
    setToast({ msg, err })
    setTimeout(() => setToast(null), 4500)
  }, [])

  const fetchChart = useCallback(async (sym: string) => {
    setChartLoading(true)
    try {
      const res = await fetch(`/api/chart?symbol=${encodeURIComponent(sym)}`)
      if (!res.ok) {
        setChartError(`Falha ao carregar gráfico (${res.status})`)
        return
      }
      const data = await res.json()
      if (data.ok && Array.isArray(data.points)) {
        setChartPoints(sanitizeChartPoints(data.points))
        setChartError(null)
      }
    } catch {
      setChartError('Não foi possível obter os pontos do gráfico da Deriv.')
    } finally {
      setChartLoading(false)
    }
  }, [])

  const loadAllInitial = useCallback(async () => {
    try {
      const [statusRes, cfgRes, tplRes, symRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/config'),
        fetch('/api/bot-templates'),
        fetch(`/api/symbols?mode=${symbolModeRef.current}`),
      ])

      if (statusRes.status === 401) {
        setAuthenticated(false)
        setAuthChecked(true)
        setInitialLoading(false)
        return
      }

      setAuthenticated(true)
      setAuthChecked(true)
      setConnectionError(null)

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
        if (c.accounts?.length) {
          setBotAccountId((prev) => prev || c.active_account_id || c.accounts[0].account_id)
        }
        if (c.active_symbols?.length) {
          setChartSymbol((prev) => (c.active_symbols.includes(prev) ? prev : c.active_symbols[0]))
        }
      }
      if (tplRes.ok) {
        const tData = await tplRes.json()
        setTemplates(Array.isArray(tData.templates) ? tData.templates : [])
      }
      if (symRes.ok) {
        const sData = await symRes.json()
        setSymbols(Array.isArray(sData.symbols) ? sData.symbols : [])
      }
    } catch {
      setAuthChecked(true)
      setConnectionError('Não foi possível conectar ao servidor backend Prado HFT.')
    } finally {
      setInitialLoading(false)
    }
  }, [])

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
          setConnectionError(null)
        } else {
          setConnectionError(`Erro ao atualizar dados (${res.status})`)
        }
        fetchChart(chartSymbol)
      } catch {
        setConnectionError('Sem comunicação com o backend. Tentando reconectar...')
      }
    }, 2000)
    return () => clearInterval(id)
  }, [authenticated, chartSymbol, fetchChart])

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    setLoginError('')
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setAuthenticated(true)
        setInitialLoading(true)
        await loadAllInitial()
      } else {
        setLoginError(data.error || 'Usuário ou senha inválidos.')
      }
    } catch {
      setLoginError('Erro de conexão ao autenticar.')
    }
  }

  async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' })
    setAuthenticated(false)
    setSnapshot(null)
  }

  async function refreshSymbols(mode: 'PRINCIPAIS' | 'TODOS') {
    setSymbolMode(mode)
    symbolModeRef.current = mode
    try {
      const res = await fetch(`/api/symbols?mode=${mode}`)
      if (res.ok) {
        const d = await res.json()
        setSymbols(Array.isArray(d.symbols) ? d.symbols : [])
      } else {
        showToast('Falha ao carregar catálogo de símbolos.', true)
      }
    } catch {
      showToast('Erro de rede ao carregar catálogo de símbolos.', true)
    }
  }

  async function handleBotAction(botId: string, action: string) {
    try {
      const res = await fetch('/api/bots/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: botId, action }),
      })
      const d = await res.json()
      if (d.ok) {
        showToast(d.message || `Comando ${action} executado.`)
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha no comando do robô.', true)
      }
    } catch {
      showToast('Erro de rede ao enviar comando ao robô.', true)
    }
  }

  async function handleDeleteAllBots() {
    try {
      const res = await fetch('/api/bots/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'DELETE_ALL' }),
      })
      if (res.ok) {
        showToast('Frota de robôs limpa.')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast('Falha ao limpar frota de robôs.', true)
      }
    } catch {
      showToast('Erro de rede ao limpar frota de robôs.', true)
    }
  }

  function resetBotForm() {
    setEditingBotId('')
    setBotName('')
    setBotAccountId(config?.active_account_id || config?.accounts?.[0]?.account_id || '')
    setBotTemplateId('WALL_STREET_HYBRID_BOTH')
    setBotSymbol('R_100')
    setBotStake(10)
    setBotMult(100)
    setBotWindow(120)
    setBotZscore(1.8)
    setBotImb(0.35)
    setBotRevertSigma(2.0)
    setBotGridDir('BUY_ONLY')
    setBotGridStep(1.5)
    setBotGridTp(1.5)
    setBotGridMaxLevels(5)
    setBotFormDirty(false)
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
    setBotGridDir((b.grid_direction as 'BUY_ONLY' | 'SELL_ONLY' | 'BOTH') || 'BUY_ONLY')
    setBotGridStep(b.grid_step_points ?? 1.5)
    setBotGridTp(b.grid_tp_points ?? 1.5)
    setBotGridMaxLevels(b.max_grid_levels ?? 5)
    setBotFormDirty(false)
    setActiveTab('create-bot')
  }

  async function duplicateBot(b: BotItem) {
    const payload = {
      name: `${b.name} (Cópia)`,
      account_id: b.account_id || config?.active_account_id || '',
      template_id: b.template_id,
      symbol: b.symbol,
      lot_size: Number(b.lot_size) || 10,
      multiplier: Number(b.multiplier) || 100,
      window_ticks: Number(b.window_ticks) || 120,
      zscore_threshold: Number(b.zscore_threshold) || 1.8,
      imbalance_threshold: Number(b.imbalance_threshold) || 0.35,
      revert_sigma: Number(b.revert_sigma) || 2.0,
      auto_start: false,
    }
    try {
      const res = await fetch('/api/bots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast(`Robô "${payload.name}" duplicado (pausado).`)
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao duplicar robô.', true)
      }
    } catch {
      showToast('Erro de rede ao duplicar robô.', true)
    }
  }

  async function saveBot(e: FormEvent) {
    e.preventDefault()
    if (!Number.isFinite(botStake) || botStake <= 0) {
      showToast('Stake deve ser maior que zero.', true)
      return
    }
    if (!Number.isFinite(botWindow) || botWindow < 10) {
      showToast('Janela de ticks deve ser no mínimo 10.', true)
      return
    }

    const payload: Record<string, unknown> = {
      name: botName.trim() || `Bot ${botSymbol}`,
      account_id: botAccountId || config?.active_account_id || '',
      bot_template_id: botTemplateId,
      template_id: botTemplateId,
      symbol: botSymbol,
      lot_size: Number(botStake),
      multiplier: Number(botMult),
      window_ticks: Number(botWindow),
      zscore_threshold: Number(botZscore),
      imbalance_threshold: Number(botImb),
      revert_sigma: Number(botRevertSigma),
      grid_direction: botGridDir,
      grid_step_points: Number(botGridStep),
      grid_tp_points: Number(botGridTp),
      max_grid_levels: Number(botGridMaxLevels),
      auto_start: true,
    }
    if (editingBotId) payload.bot_id = editingBotId

    try {
      const res = await fetch('/api/bots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        resetBotForm()
        showToast('Robô matemático salvo!')
        setActiveTab('running-bots')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Erro ao salvar robô.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar robô.', true)
    }
  }

  async function runBacktest(e: FormEvent) {
    e.preventDefault()
    setBtRunning(true)
    try {
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
      if (res.ok && d.ok) {
        setBtResult(d.report)
        if (config) setConfig({ ...config, backtest_history: d.history || [] })
        showToast('Backtest concluído!')
      } else {
        showToast(d.error || 'Falha no backtest.', true)
      }
    } catch {
      showToast('Erro de rede ao executar backtest.', true)
    } finally {
      setBtRunning(false)
    }
  }

  async function saveCategory(e: FormEvent) {
    e.preventDefault()
    const syms = catSymbols
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    try {
      const res = await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_name: catName.trim(), symbols: syms }),
      })
      const d = await res.json()
      if (res.ok && d.ok && config) {
        setConfig({ ...config, custom_categories: d.categories })
        setCatName('')
        setCatSymbols('')
        showToast('Categoria salva!')
      } else {
        showToast(d.error || 'Falha ao salvar categoria.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar categoria.', true)
    }
  }

  async function deleteCategory(categoryName: string) {
    try {
      const res = await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'DELETE', category_name: categoryName }),
      })
      const d = await res.json()
      if (res.ok && d.ok && config) {
        setConfig({ ...config, custom_categories: d.categories })
        showToast(`Categoria "${categoryName}" removida.`)
      } else {
        showToast(d.error || 'Falha ao remover categoria.', true)
      }
    } catch {
      showToast('Erro de rede ao remover categoria.', true)
    }
  }

  async function saveDerivConfig(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      deriv_app_id: cfgAppId.trim() || '1089',
      connection_mode: cfgConnMode,
    }
    if (cfgToken.trim()) payload.deriv_token = cfgToken.trim()

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setConfig(d.config)
        setCfgToken('')
        setAccAppId(d.config.deriv_app_id || '1089')
        setAccConnMode(d.config.connection_mode || 'DERIV_CLOUD')
        showToast('Configuração Deriv salva e contas sincronizadas!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao salvar configuração Deriv.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar configuração Deriv.', true)
    }
  }

  async function toggleRealTrading() {
    const next = !(config?.allow_real_trading ?? false)
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allow_real_trading: next }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setConfig(d.config)
        showToast(next ? 'Negociação em conta REAL liberada!' : 'Negociação em conta REAL bloqueada por segurança.')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao atualizar permissão REAL.', true)
      }
    } catch {
      showToast('Erro de rede ao atualizar permissão REAL.', true)
    }
  }

  async function syncDerivAccounts() {
    setSyncingAccounts(true)
    try {
      const res = await fetch('/api/accounts/sync', { method: 'POST' })
      const d = await res.json()
      if (res.ok && d.ok) {
        if (config) {
          setConfig({ ...config, accounts: d.accounts, active_account_id: d.active_account_id || config.active_account_id })
        }
        showToast(d.message || 'Contas sincronizadas da Deriv!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.message || d.error || 'Não foi possível sincronizar as contas.', true)
      }
    } catch {
      showToast('Erro de rede ao sincronizar contas da Deriv.', true)
    } finally {
      setSyncingAccounts(false)
    }
  }

  async function saveDerivAccount(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      account_type: accType,
      label: accLabel.trim(),
      deriv_token: useCustomCreds ? accToken.trim() : '',
      deriv_app_id: useCustomCreds ? accAppId.trim() || '1089' : '',
      default_stake_usd: Number(accStake),
      default_multiplier: Number(accMult),
      connection_mode: accConnMode,
    }
    if (editingAccId) payload.account_id = editingAccId

    try {
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setEditingAccId('')
        setAccLabel('')
        setAccToken('')
        if (config) {
          setConfig({ ...config, accounts: d.accounts, active_account_id: d.account.account_id })
        }
        showToast(d.message || 'Conta Deriv salva!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao salvar conta Deriv.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar conta Deriv.', true)
    }
  }

  async function selectAccount(accountId: string) {
    try {
      const res = await fetch('/api/accounts/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        if (config) setConfig({ ...config, active_account_id: accountId })
        showToast(d.message || 'Conta ativada.')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao ativar conta.', true)
      }
    } catch {
      showToast('Erro de rede ao ativar conta.', true)
    }
  }

  function requestDeleteAccount(account: DerivAccount) {
    setConfirmModal({
      open: true,
      title: 'Remover conta Deriv',
      description: `Deseja remover a conta "${account.label}" (${account.account_type}) do cofre?`,
      confirmLabel: 'Remover conta',
      variant: 'danger',
      onConfirm: async () => {
        setConfirmModal((m) => ({ ...m, open: false }))
        const res = await fetch('/api/accounts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'DELETE', account_id: account.account_id }),
        })
        const d = await res.json()
        if (d.ok && config) {
          setConfig({ ...config, accounts: d.accounts })
          showToast('Conta removida.')
        }
      },
    })
  }

  async function toggleAutoTrading() {
    const next = !(snapshot?.auto_trading_enabled ?? true)
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_trading_enabled: next }),
      })
      if (res.ok) {
        showToast(next ? 'Execução automática ativada.' : 'Execução automática pausada.')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast('Falha ao alternar execução automática.', true)
      }
    } catch {
      showToast('Erro de rede ao alternar execução automática.', true)
    }
  }

  function requestPanicFlatten(ticket?: string | number) {
    const isSingle = ticket !== undefined
    setConfirmModal({
      open: true,
      title: isSingle ? `Encerrar contrato #${ticket}` : 'Zerar todas as posições abertas',
      description: isSingle
        ? `Confirmar o encerramento imediato do contrato #${ticket} na Deriv?`
        : 'Confirmar o fechamento emergencial de todos os contratos abertos na conta ativa?',
      confirmLabel: isSingle ? 'Encerrar contrato' : 'Zerar tudo agora',
      variant: 'danger',
      onConfirm: async () => {
        setConfirmModal((m) => ({ ...m, open: false }))
        const res = await fetch('/api/flatten', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(isSingle ? { ticket } : {}),
        })
        const d = await res.json()
        if (d.ok) {
          showToast(d.message || 'Posições zeradas.')
          const stRes = await fetch('/api/status')
          if (stRes.ok) setSnapshot(await stRes.json())
        } else {
          showToast(d.message || 'Nenhuma posição fechada.', true)
        }
      },
    })
  }

  async function resetDailyRisk() {
    try {
      const res = await fetch('/api/risk/reset', { method: 'POST' })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast('Trava diária de risco redefinida.')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao redefinir trava diária.', true)
      }
    } catch {
      showToast('Erro de rede ao redefinir trava diária.', true)
    }
  }

  async function saveAdminPassword(e: FormEvent) {
    e.preventDefault()
    if (newAdminPassword.trim().length < 6) {
      showToast('A nova senha deve ter no mínimo 6 caracteres.', true)
      return
    }
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_admin_password: newAdminPassword.trim() }),
      })
      if (res.ok) {
        setNewAdminPassword('')
        showToast('Senha administrativa atualizada!')
      } else {
        showToast('Falha ao atualizar senha administrativa.', true)
      }
    } catch {
      showToast('Erro de rede ao atualizar senha administrativa.', true)
    }
  }

  const monitoredSymbols = useMemo(() => {
    const set = new Set<string>(['R_100', 'cryBTCUSD', 'frxEURUSD'])
    if (snapshot?.symbols) {
      Object.keys(snapshot.symbols).forEach((s) => {
        if (s) set.add(s)
      })
    }
    snapshot?.bots?.forEach((b) => {
      if (b?.symbol) set.add(b.symbol)
    })
    return Array.from(set)
  }, [snapshot])

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.template_id === botTemplateId),
    [templates, botTemplateId],
  )

  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500 dark:text-slate-400 text-sm font-mono">
        Inicializando terminal Prado Ubuntu HFT...
      </div>
    )
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-slate-100 dark:bg-[#0b0f17]">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-8 shadow-xl dark:shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-blue-600/10 border border-blue-600/25 flex items-center justify-center text-blue-600 dark:text-blue-400">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900 dark:text-white">Prado Ubuntu HFT</h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">Deriv Multipliers • Terminal 24/7</p>
              </div>
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Alternar tema"
              className="rounded-xl border border-slate-200 dark:border-slate-700 p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Usuário
              </label>
              <input
                type="text"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white focus:border-blue-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                Senha
              </label>
              <input
                type="password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-sm text-slate-900 dark:text-white focus:border-blue-500 focus:outline-none"
                required
              />
            </div>
            {loginError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
                {loginError}
              </div>
            )}
            <button
              type="submit"
              className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-sm font-semibold text-white transition shadow-lg shadow-blue-600/20"
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
  const pageInfo = PAGE_META[activeTab]

  const inputClass =
    'w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-blue-500 focus:outline-none transition'

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-xl border px-4 py-3 text-xs font-medium shadow-2xl ${
            toast.err
              ? 'border-rose-500/40 bg-rose-50 dark:bg-rose-950/95 text-rose-800 dark:text-rose-200'
              : 'border-emerald-500/40 bg-white dark:bg-slate-900/95 text-emerald-700 dark:text-emerald-200'
          }`}
        >
          {toast.err ? (
            <XCircle className="h-4 w-4 text-rose-500 shrink-0" />
          ) : (
            <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
          )}
          <span>{toast.msg}</span>
        </div>
      )}

      {/* Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        totalBots={totalBots}
      />

      {/* Right Shell */}
      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar
          pageTitle={pageInfo.title}
          chartSymbol={chartSymbol}
          availableSymbols={monitoredSymbols}
          onSelectSymbol={setChartSymbol}
          account={acc}
          accounts={config?.accounts || []}
          activeAccountId={config?.active_account_id || ''}
          onSelectAccount={selectAccount}
          autoTradingEnabled={snapshot?.auto_trading_enabled ?? true}
          onToggleAutoTrading={toggleAutoTrading}
          onPanicFlatten={() => requestPanicFlatten()}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          theme={theme}
          onToggleTheme={toggleTheme}
          logs={snapshot?.logs || []}
          onOpenSettings={() => setActiveTab('settings')}
          onLogout={handleLogout}
        />

        <main className="flex-1 px-4 sm:px-6 py-5 space-y-5 max-w-[1440px] w-full mx-auto">
          {/* Page Header */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                {pageInfo.title}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">{pageInfo.description}</p>
            </div>
            {snapshot?.timestamp && (
              <span className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] px-2.5 py-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                Ciclo: {snapshot.timestamp}
              </span>
            )}
          </div>

          {/* Connection Error Banner */}
          {connectionError && (
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-700 dark:text-rose-300">
              <div className="flex items-center gap-2">
                <WifiOff className="h-4 w-4 shrink-0" />
                <span>{connectionError}</span>
              </div>
              <button
                type="button"
                onClick={loadAllInitial}
                className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 px-2.5 py-1 font-semibold hover:bg-rose-500/15"
              >
                <RefreshCw className="h-3 w-3" />
                Tentar novamente
              </button>
            </div>
          )}

          {initialLoading && !snapshot ? (
            <DashboardSkeleton />
          ) : (
            <>
              {/* KPI Strip on Overview & Running Bots */}
              {(activeTab === 'overview' || activeTab === 'running-bots') && (
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                        <span>Conta Deriv conectada</span>
                        <span
                          className={`rounded-md px-2 py-0.5 text-[10px] font-semibold border ${
                            acc?.account_type === 'REAL'
                              ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30'
                              : 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30'
                          }`}
                        >
                          {acc?.account_type || 'DEMO'}
                        </span>
                      </div>
                      <div className="mt-2 text-lg font-bold font-mono text-slate-900 dark:text-white truncate">
                        {acc?.login || 'DESCONECTADO'}
                      </div>
                      <div
                        className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 truncate"
                        title={acc?.status_note || acc?.server}
                      >
                        {acc?.status_note || acc?.server || 'Aguardando token'}
                      </div>
                    </CardBody>
                  </Card>

                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="text-xs text-slate-500 dark:text-slate-400">Saldo / Equity</div>
                      <div className="mt-2 text-lg font-bold font-mono text-slate-900 dark:text-white">
                        {formatCurrency(acc?.equity, acc?.currency || 'USD')}
                      </div>
                      <div className="mt-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        Saldo base: {formatCurrency(acc?.balance, acc?.currency || 'USD')}
                      </div>
                    </CardBody>
                  </Card>

                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="text-xs text-slate-500 dark:text-slate-400">Robôs matemáticos ativos</div>
                      <div className="mt-2 text-lg font-bold font-mono text-blue-600 dark:text-blue-400">
                        {activeBots} ativos de {totalBots}
                      </div>
                      <div className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">
                        Motor HFT operacional
                      </div>
                    </CardBody>
                  </Card>

                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        Vetor de correlação da cesta
                      </div>
                      <div
                        className={`mt-2 text-lg font-bold font-mono ${
                          isFiniteNumber(snapshot?.basket_bias)
                            ? (snapshot?.basket_bias ?? 0) >= 0
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : 'text-rose-600 dark:text-rose-400'
                            : 'text-slate-500'
                        }`}
                      >
                        {formatSignedPercent(snapshot?.basket_bias, 1, true)}
                      </div>
                      <div className="mt-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        Realizado hoje: {formatCurrency(acc?.daily_realized, acc?.currency || 'USD')}
                      </div>
                    </CardBody>
                  </Card>
                </section>
              )}

              {/* OVERVIEW & RUNNING BOTS */}
              {(activeTab === 'overview' || activeTab === 'running-bots') && (
                <div className="space-y-6">
                  <MarketIndicatorsBar
                    symbol={chartSymbol}
                    symbolState={snapshot?.symbols?.[chartSymbol]}
                    connected={isConnected}
                  />
                  {activeTab === 'overview' && (
                    <DerivDiagnosticsCard account={snapshot?.account} />
                  )}

                  <LightweightChartPanel
                    symbol={chartSymbol}
                    availableSymbols={monitoredSymbols}
                    onSelectSymbol={setChartSymbol}
                    points={chartPoints}
                    symbolState={snapshot?.symbols?.[chartSymbol]}
                    theme={theme}
                    loading={chartLoading}
                    error={chartError}
                  />

                  <BotCardGrid
                    bots={snapshot?.bots || []}
                    symbols={snapshot?.symbols || {}}
                    lastUpdated={snapshot?.timestamp}
                    onAction={handleBotAction}
                    onEdit={startEditBot}
                    onDuplicate={duplicateBot}
                    onNewBot={() => {
                      resetBotForm()
                      setActiveTab('create-bot')
                    }}
                    onDeleteAll={handleDeleteAllBots}
                  />

                  {/* Open Positions */}
                  <Card className="overflow-hidden">
                    <CardHeader className="bg-slate-50/70 dark:bg-slate-900/40">
                      <CardTitle>Contratos abertos na Deriv</CardTitle>
                      <CardDescription>
                        Acompanhamento em tempo real com Stop Loss e Take Profit
                      </CardDescription>
                    </CardHeader>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950/40">
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
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                          {!snapshot?.positions?.length ? (
                            <tr>
                              <td
                                colSpan={8}
                                className="px-4 py-8 text-center text-slate-500 font-sans"
                              >
                                Nenhum contrato aberto no momento.
                              </td>
                            </tr>
                          ) : (
                            snapshot.positions.map((p) => {
                              if (!p || p.ticket === undefined) return null
                              const profitPositive = isFiniteNumber(p.profit) && p.profit >= 0
                              return (
                                <tr
                                  key={String(p.ticket)}
                                  className="hover:bg-slate-50 dark:hover:bg-slate-900/40"
                                >
                                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                                    #{p.ticket}
                                  </td>
                                  <td className="px-4 py-3 font-semibold text-slate-900 dark:text-white">
                                    {p.symbol}
                                  </td>
                                  <td className="px-4 py-3">
                                    <span
                                      className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                                        p.side === 'BUY'
                                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                          : 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                                      }`}
                                    >
                                      {p.side}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 text-right">
                                    ${formatNumber(p.volume, 2)}
                                  </td>
                                  <td className="px-4 py-3 text-right">
                                    {formatPrice(p.price_open, 4)}
                                  </td>
                                  <td className="px-4 py-3 text-right">
                                    {formatPrice(p.price_current, 4)}
                                  </td>
                                  <td
                                    className={`px-4 py-3 text-right font-semibold ${
                                      profitPositive
                                        ? 'text-emerald-600 dark:text-emerald-400'
                                        : 'text-rose-600 dark:text-rose-400'
                                    }`}
                                  >
                                    {formatSignedNumber(p.profit, 2)}
                                  </td>
                                  <td className="px-4 py-3 text-right">
                                    <button
                                      type="button"
                                      onClick={() => requestPanicFlatten(p.ticket)}
                                      className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[11px] text-rose-700 dark:text-rose-300 hover:bg-rose-500/20"
                                    >
                                      Encerrar
                                    </button>
                                  </td>
                                </tr>
                              )
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </div>
              )}

              {/* MY BOTS DEDICATED VIEW */}
              {activeTab === 'my-bots' && (
                <BotCardGrid
                  bots={snapshot?.bots || []}
                  symbols={snapshot?.symbols || {}}
                  lastUpdated={snapshot?.timestamp}
                  onAction={handleBotAction}
                  onEdit={startEditBot}
                  onDuplicate={duplicateBot}
                  onNewBot={() => {
                    setEditingBotId('')
                    setBotFormDirty(false)
                    setActiveTab('create-bot')
                  }}
                  onDeleteAll={handleDeleteAllBots}
                />
              )}

              {/* CREATE / EDIT BOT */}
              {activeTab === 'create-bot' && (
                <Card>
                  <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle>
                        {editingBotId ? 'Editar robô matemático' : 'Configurar novo robô matemático'}
                      </CardTitle>
                      <CardDescription>
                        Defina a conta Deriv, ativo, modelo quantitativo e gatilhos estatísticos
                      </CardDescription>
                    </div>
                    {botFormDirty && (
                      <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-700 dark:text-amber-300">
                        Alterações não salvas
                      </span>
                    )}
                  </CardHeader>
                  <CardBody>
                    <form
                      onSubmit={saveBot}
                      onChange={() => setBotFormDirty(true)}
                      className="space-y-6"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Nome do robô
                          </label>
                          <input
                            type="text"
                            value={botName}
                            onChange={(e) => setBotName(e.target.value)}
                            placeholder="Ex: Bot R_100 Reversão"
                            className={inputClass}
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Conta Deriv vinculada
                          </label>
                          <select
                            value={botAccountId}
                            onChange={(e) => setBotAccountId(e.target.value)}
                            className={inputClass}
                          >
                            {config?.accounts?.map((a) => (
                              <option key={a.account_id} value={a.account_id}>
                                [{a.account_type}] {a.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Ativo Deriv
                          </label>
                          <select
                            value={botSymbol}
                            onChange={(e) => setBotSymbol(e.target.value)}
                            className={`${inputClass} font-mono`}
                          >
                            {symbols.map((s) => (
                              <option key={s.name} value={s.name}>
                                {s.name} — {s.description}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="md:col-span-2 lg:col-span-3">
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Modelo matemático
                          </label>
                          <select
                            value={botTemplateId}
                            onChange={(e) => setBotTemplateId(e.target.value)}
                            className={inputClass}
                          >
                            {templates.map((t) => (
                              <option key={t.template_id} value={t.template_id}>
                                {t.name}
                              </option>
                            ))}
                          </select>
                          {selectedTemplate && (
                            <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                              {selectedTemplate.description} • Fórmula:{' '}
                              <code className="font-mono text-blue-600 dark:text-blue-400">
                                {selectedTemplate.formula}
                              </code>
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="border-t border-slate-100 dark:border-slate-800 pt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Stake (USD)
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            min="1"
                            value={botStake}
                            onChange={(e) => setBotStake(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Multiplicador
                          </label>
                          <select
                            value={botMult}
                            onChange={(e) => setBotMult(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          >
                            {[20, 50, 100, 200, 400].map((m) => (
                              <option key={m} value={m}>
                                {m}x
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Janela (ticks)
                          </label>
                          <input
                            type="number"
                            min="10"
                            value={botWindow}
                            onChange={(e) => setBotWindow(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Z-Score mínimo
                          </label>
                          <input
                            type="number"
                            step="0.1"
                            value={botZscore}
                            onChange={(e) => setBotZscore(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Imbalance mínimo
                          </label>
                          <input
                            type="number"
                            step="0.05"
                            value={botImb}
                            onChange={(e) => setBotImb(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Desvio Reversão (σ)
                          </label>
                          <input
                            type="number"
                            step="0.1"
                            value={botRevertSigma}
                            onChange={(e) => setBotRevertSigma(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                      </div>

                      {botTemplateId === 'GRID_LINEAR_HFT' && (
                        <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4 space-y-3">
                          <div className="text-xs font-semibold text-violet-600 dark:text-violet-300">
                            Parâmetros do Gradiente Linear (Grid HFT)
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                                Direção do Grid
                              </label>
                              <select
                                value={botGridDir}
                                onChange={(e) => setBotGridDir(e.target.value as 'BUY_ONLY' | 'SELL_ONLY' | 'BOTH')}
                                className={inputClass}
                              >
                                <option value="BUY_ONLY">Só Compra (na queda)</option>
                                <option value="SELL_ONLY">Só Venda (na alta)</option>
                                <option value="BOTH">Ambos (Compra e Venda)</option>
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                                Passo do Grid (pontos)
                              </label>
                              <input
                                type="number"
                                step="0.1"
                                min="0.01"
                                value={botGridStep}
                                onChange={(e) => setBotGridStep(Number(e.target.value))}
                                className={`${inputClass} font-mono`}
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                                Alvo por Nível (pontos)
                              </label>
                              <input
                                type="number"
                                step="0.1"
                                min="0.01"
                                value={botGridTp}
                                onChange={(e) => setBotGridTp(Number(e.target.value))}
                                className={`${inputClass} font-mono`}
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                                Máximo de Níveis
                              </label>
                              <input
                                type="number"
                                min="1"
                                max="20"
                                value={botGridMaxLevels}
                                onChange={(e) => setBotGridMaxLevels(Number(e.target.value))}
                                className={`${inputClass} font-mono`}
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2 pt-2">
                        <button
                          type="submit"
                          className="rounded-xl bg-blue-600 hover:bg-blue-500 px-5 py-2.5 text-xs font-semibold text-white transition"
                        >
                          {editingBotId ? 'Salvar alterações do robô' : 'Criar e ativar robô'}
                        </button>
                        {editingBotId && (
                          <button
                            type="button"
                            onClick={() => {
                              setEditingBotId('')
                              setBotFormDirty(false)
                            }}
                            className="rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-2.5 text-xs text-slate-700 dark:text-slate-300"
                          >
                            Cancelar
                          </button>
                        )}
                      </div>
                    </form>
                  </CardBody>
                </Card>
              )}

              {/* BACKTEST */}
              {activeTab === 'backtest' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Parâmetros do Backtest tick a tick</CardTitle>
                      <CardDescription>
                        Executa o motor matemático sobre ticks históricos sem alterar os cálculos originais
                      </CardDescription>
                    </CardHeader>
                    <CardBody className="space-y-6">
                      <form
                        onSubmit={runBacktest}
                        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4"
                      >
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Ativo
                          </label>
                          <select
                            value={btSymbol}
                            onChange={(e) => setBtSymbol(e.target.value)}
                            className={`${inputClass} font-mono`}
                          >
                            {symbols.map((s) => (
                              <option key={s.name} value={s.name}>
                                {s.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="lg:col-span-2">
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Modelo
                          </label>
                          <select
                            value={btTemplateId}
                            onChange={(e) => setBtTemplateId(e.target.value)}
                            className={inputClass}
                          >
                            {templates.map((t) => (
                              <option key={t.template_id} value={t.template_id}>
                                {t.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Ticks
                          </label>
                          <input
                            type="number"
                            value={btTicks}
                            onChange={(e) => setBtTicks(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Capital (USD)
                          </label>
                          <input
                            type="number"
                            value={btCapital}
                            onChange={(e) => setBtCapital(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div className="flex items-end">
                          <button
                            type="submit"
                            disabled={btRunning}
                            className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 py-2.5 text-xs font-semibold text-white"
                          >
                            {btRunning ? 'Executando...' : 'Executar Backtest'}
                          </button>
                        </div>
                      </form>

                      {btResult && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4 font-mono text-xs">
                          <div>
                            <span className="text-slate-500 dark:text-slate-400">Trades</span>
                            <div className="text-base font-bold text-slate-900 dark:text-white mt-1">
                              {btResult.total_trades ?? '--'}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400">Taxa de acerto</span>
                            <div className="text-base font-bold text-blue-600 dark:text-blue-400 mt-1">
                              {formatPercent(btResult.win_rate, 1, false)}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400">Lucro líquido</span>
                            <div
                              className={`text-base font-bold mt-1 ${
                                (btResult.net_profit ?? 0) >= 0
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : 'text-rose-600 dark:text-rose-400'
                              }`}
                            >
                              ${formatNumber(btResult.net_profit, 2)}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400">Drawdown máx.</span>
                            <div className="text-base font-bold text-rose-600 dark:text-rose-400 mt-1">
                              ${formatNumber(btResult.max_drawdown, 2)}
                            </div>
                          </div>
                        </div>
                      )}
                    </CardBody>
                  </Card>

                  {/* Backtest History Table */}
                  <Card className="overflow-hidden">
                    <CardHeader>
                      <CardTitle>Histórico de Backtests</CardTitle>
                    </CardHeader>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase text-slate-500 bg-slate-50 dark:bg-slate-950/40">
                          <tr>
                            <th className="px-4 py-3">Ativo</th>
                            <th className="px-4 py-3">Modelo</th>
                            <th className="px-4 py-3 text-right">Trades</th>
                            <th className="px-4 py-3 text-right">Acerto</th>
                            <th className="px-4 py-3 text-right">Lucro</th>
                            <th className="px-4 py-3 text-right">Drawdown</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                          {!config?.backtest_history?.length ? (
                            <tr>
                              <td colSpan={6} className="px-4 py-6 text-center text-slate-500 font-sans">
                                Nenhum backtest executado ainda.
                              </td>
                            </tr>
                          ) : (
                            config.backtest_history.map((h, i) => {
                              if (!h) return null
                              return (
                                <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                  <td className="px-4 py-2.5 font-semibold">{h.symbol || '--'}</td>
                                  <td className="px-4 py-2.5 font-sans text-slate-600 dark:text-slate-300">
                                    {h.template_name || '--'}
                                  </td>
                                  <td className="px-4 py-2.5 text-right">{h.total_trades ?? '--'}</td>
                                  <td className="px-4 py-2.5 text-right">
                                    {formatPercent(h.win_rate, 1, false)}
                                  </td>
                                  <td className="px-4 py-2.5 text-right">
                                    ${formatNumber(h.net_profit, 2)}
                                  </td>
                                  <td className="px-4 py-2.5 text-right text-rose-600 dark:text-rose-400">
                                    ${formatNumber(h.max_drawdown, 2)}
                                  </td>
                                </tr>
                              )
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </div>
              )}

              {/* CATEGORIES */}
              {activeTab === 'categories' && (
                <Card>
                  <CardHeader className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle>Categorias e Ativos Deriv</CardTitle>
                      <CardDescription>
                        Alterne entre Principais e Todos os pares carregados da Deriv
                      </CardDescription>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => refreshSymbols('PRINCIPAIS')}
                        className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${
                          symbolMode === 'PRINCIPAIS'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                        }`}
                      >
                        Principais
                      </button>
                      <button
                        type="button"
                        onClick={() => refreshSymbols('TODOS')}
                        className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${
                          symbolMode === 'TODOS'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                        }`}
                      >
                        Todos ({symbols.length})
                      </button>
                    </div>
                  </CardHeader>
                  <CardBody className="space-y-5">
                    <form onSubmit={saveCategory} className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <input
                        type="text"
                        value={catName}
                        onChange={(e) => setCatName(e.target.value)}
                        placeholder="Nome da categoria"
                        className={inputClass}
                        required
                      />
                      <input
                        type="text"
                        value={catSymbols}
                        onChange={(e) => setCatSymbols(e.target.value)}
                        placeholder="Ativos separados por vírgula (ex: R_100, cryBTCUSD)"
                        className={`${inputClass} font-mono`}
                        required
                      />
                      <button
                        type="submit"
                        className="rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-xs font-semibold text-white"
                      >
                        Salvar categoria
                      </button>
                    </form>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {Object.entries(config?.custom_categories || {}).map(([name, list]) => (
                        <div
                          key={name}
                          className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-sm font-semibold text-slate-900 dark:text-white">
                              {name}
                            </div>
                            <button
                              type="button"
                              onClick={() => deleteCategory(name)}
                              title="Excluir categoria"
                              className="rounded-lg p-1 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 transition"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {(Array.isArray(list) ? list : []).map((sym) => (
                              <span
                                key={sym}
                                className="rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2 py-0.5 text-[11px] font-mono text-slate-700 dark:text-slate-300"
                              >
                                {sym}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                            Catálogo ao vivo da Deriv ({symbols.length} ativos carregados)
                          </h4>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            Clique em qualquer ativo abaixo para adicioná-lo ao campo de nova categoria acima
                          </p>
                        </div>
                        <input
                          type="text"
                          value={symbolSearch}
                          onChange={(e) => setSymbolSearch(e.target.value)}
                          placeholder="Filtrar ativo (ex: R_100, EUR, BTC)..."
                          className={`${inputClass} max-w-xs text-xs`}
                        />
                      </div>
                      <div className="max-h-72 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {symbols
                          .filter((s) => {
                            const q = symbolSearch.trim().toLowerCase()
                            if (!q) return true
                            return (
                              s.name.toLowerCase().includes(q) ||
                              (s.description || '').toLowerCase().includes(q) ||
                              (s.category || '').toLowerCase().includes(q)
                            )
                          })
                          .map((s) => (
                            <button
                              key={s.name}
                              type="button"
                              onClick={() => {
                                const current = catSymbols
                                  .split(',')
                                  .map((x) => x.trim())
                                  .filter(Boolean)
                                if (!current.includes(s.name)) {
                                  setCatSymbols([...current, s.name].join(', '))
                                }
                              }}
                              className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950/60 hover:border-blue-500/50 px-3 py-2 text-left transition"
                            >
                              <div className="min-w-0">
                                <div className="text-xs font-mono font-semibold text-slate-900 dark:text-white truncate">
                                  {s.name}
                                </div>
                                <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                  {s.description || s.category}
                                </div>
                              </div>
                              <span className="shrink-0 rounded-md bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-400">
                                + Add
                              </span>
                            </button>
                          ))}
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )}

              {/* DERIV CONFIG */}
              {activeTab === 'deriv-config' && (
                <div className="space-y-6">
                  <DerivDiagnosticsCard account={snapshot?.account} />
                  <Card>
                  <CardHeader>
                    <CardTitle>Configuração Padrão Deriv (Token &amp; App ID)</CardTitle>
                    <CardDescription>
                      Salve seu token uma única vez aqui; ele nunca é exibido por completo no painel
                    </CardDescription>
                  </CardHeader>
                  <CardBody className="space-y-6">
                    <form
                      onSubmit={saveDerivConfig}
                      className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl"
                    >
                      <div className="md:col-span-2">
                        <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                          Deriv API Token padrão
                        </label>
                        <input
                          type="password"
                          value={cfgToken}
                          onChange={(e) => setCfgToken(e.target.value)}
                          placeholder={
                            config?.deriv_token_set
                              ? 'Token padrão já salvo (cole outro para substituir)'
                              : 'Cole seu token de app.deriv.com/account/api-token'
                          }
                          className={`${inputClass} font-mono`}
                        />
                        <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                          Tokens clássicos funcionam direto com App ID 1089. Tokens pat_... exigem App ID de developers.deriv.com.
                        </p>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                          Deriv App ID padrão
                        </label>
                        <input
                          type="text"
                          value={cfgAppId}
                          onChange={(e) => setCfgAppId(e.target.value)}
                          className={`${inputClass} font-mono`}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                          Modo de execução padrão
                        </label>
                        <select
                          value={cfgConnMode}
                          onChange={(e) => setCfgConnMode(e.target.value)}
                          className={inputClass}
                        >
                          <option value="DERIV_CLOUD">
                            Deriv WebSocket Live (Negociação Real/Demo)
                          </option>
                          <option value="SIMULATION">Simulador Quantitativo Interno</option>
                        </select>
                      </div>
                      <div className="md:col-span-2 pt-2">
                        <button
                          type="submit"
                          className="rounded-xl bg-blue-600 hover:bg-blue-500 px-5 py-2.5 text-xs font-semibold text-white"
                        >
                          Salvar configuração Deriv
                        </button>
                      </div>
                    </form>

                    {/* Diagnostics */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 p-4 text-xs font-mono grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <span className="text-slate-500">Estado:</span>{' '}
                        <strong className={isConnected ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                          {isConnected ? 'CONECTADO' : 'DESCONECTADO'}
                        </strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Backend:</span>{' '}
                        <strong>{acc?.backend || '--'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Servidor:</span>{' '}
                        <strong>{acc?.server || '--'}</strong>
                      </div>
                    </div>
                  </CardBody>
                  </Card>
                </div>
              )}

              {/* DERIV ACCOUNTS VAULT */}
              {activeTab === 'deriv-tokens' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader className="flex flex-wrap items-center justify-between gap-3">
                      <CardTitle>
                        {editingAccId
                          ? 'Editar conta Deriv'
                          : 'Cofre de Contas Deriv (Demo e Real)'}
                      </CardTitle>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={toggleRealTrading}
                          className={`rounded-xl border px-3.5 py-1.5 text-xs font-semibold transition ${
                            config?.allow_real_trading
                              ? 'border-amber-500/40 bg-amber-500/15 text-amber-600 dark:text-amber-300'
                              : 'border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                          }`}
                        >
                          {config?.allow_real_trading ? 'Conta REAL: Liberada' : 'Liberar negociação REAL'}
                        </button>
                        <button
                          type="button"
                          onClick={syncDerivAccounts}
                          disabled={syncingAccounts}
                          className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 px-3.5 py-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-300 disabled:opacity-50"
                        >
                          {syncingAccounts ? 'Sincronizando...' : 'Sincronizar contas da Deriv'}
                        </button>
                      </div>
                    </CardHeader>
                    <CardBody>
                      <form
                        onSubmit={saveDerivAccount}
                        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
                      >
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Ambiente
                          </label>
                          <select
                            value={accType}
                            onChange={(e) => setAccType(e.target.value as 'DEMO' | 'REAL')}
                            className={inputClass}
                          >
                            <option value="DEMO">Conta Demo Deriv (VRTC)</option>
                            <option value="REAL">Conta Real Deriv (CR)</option>
                          </select>
                        </div>
                        <div className="md:col-span-1 lg:col-span-2">
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Nome de identificação
                          </label>
                          <input
                            type="text"
                            value={accLabel}
                            onChange={(e) => setAccLabel(e.target.value)}
                            placeholder="Ex: Deriv Real Principal"
                            className={inputClass}
                            required
                          />
                        </div>

                        {config?.deriv_token_set && !useCustomCreds ? (
                          <div className="lg:col-span-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-4 py-2.5 text-xs">
                            <span className="text-emerald-700 dark:text-emerald-300">
                              Usando Token e App ID (<strong className="font-mono">{config.deriv_app_id}</strong>) salvos em <strong>Configuração Deriv</strong>.
                            </span>
                            <button
                              type="button"
                              onClick={() => setUseCustomCreds(true)}
                              className="text-slate-600 dark:text-slate-300 underline hover:text-blue-500"
                            >
                              Usar outro token / App ID
                            </button>
                          </div>
                        ) : (
                          <>
                            <div>
                              <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                                Deriv App ID
                              </label>
                              <input
                                type="text"
                                value={accAppId}
                                onChange={(e) => setAccAppId(e.target.value)}
                                className={`${inputClass} font-mono`}
                              />
                            </div>
                            <div className="lg:col-span-2">
                              <div className="flex items-center justify-between mb-1">
                                <label className="block text-xs text-slate-500 dark:text-slate-400">
                                  Deriv API Token
                                </label>
                                {config?.deriv_token_set && (
                                  <button
                                    type="button"
                                    onClick={() => setUseCustomCreds(false)}
                                    className="text-[11px] text-blue-500 underline"
                                  >
                                    Voltar a usar o token padrão
                                  </button>
                                )}
                              </div>
                              <input
                                type="password"
                                value={accToken}
                                onChange={(e) => setAccToken(e.target.value)}
                                placeholder={
                                  config?.deriv_token_set
                                    ? 'Token padrão carregado (deixe em branco para usar o salvo)'
                                    : 'Cole seu token da Deriv'
                                }
                                className={`${inputClass} font-mono`}
                              />
                            </div>
                          </>
                        )}
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Stake padrão (USD)
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            value={accStake}
                            onChange={(e) => setAccStake(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Multiplicador padrão
                          </label>
                          <select
                            value={accMult}
                            onChange={(e) => setAccMult(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          >
                            {[20, 50, 100, 200, 400].map((m) => (
                              <option key={m} value={m}>
                                {m}x
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Modo
                          </label>
                          <select
                            value={accConnMode}
                            onChange={(e) => setAccConnMode(e.target.value)}
                            className={inputClass}
                          >
                            <option value="DERIV_CLOUD">Deriv WebSocket Live</option>
                            <option value="SIMULATION">Simulador Quant</option>
                          </select>
                        </div>
                        <div className="lg:col-span-3 flex gap-2 pt-2">
                          <button
                            type="submit"
                            className="rounded-xl bg-blue-600 hover:bg-blue-500 px-5 py-2.5 text-xs font-semibold text-white"
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
                              className="rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-2.5 text-xs text-slate-700 dark:text-slate-300"
                            >
                              Cancelar
                            </button>
                          )}
                        </div>
                      </form>
                    </CardBody>
                  </Card>

                  <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {config?.accounts?.map((a: DerivAccount) => {
                      const isActive = a.account_id === config.active_account_id
                      return (
                        <Card
                          key={a.account_id}
                          className={isActive ? 'border-emerald-500/50' : ''}
                        >
                          <CardBody className="p-5">
                            <div className="flex items-center justify-between">
                              <span
                                className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                                  a.account_type === 'REAL'
                                    ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                                    : 'bg-sky-500/15 text-sky-700 dark:text-sky-300'
                                }`}
                              >
                                {a.account_type}
                              </span>
                              <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                                {a.loginid || '---'}
                              </span>
                            </div>
                            <h3 className="mt-2 text-sm font-bold text-slate-900 dark:text-white">
                              {a.label}
                            </h3>
                            <p className="mt-1 text-xs font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                              Saldo: {a.currency || 'USD'} {formatNumber(a.balance ?? 0, 2)}
                            </p>
                            <p className="mt-0.5 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                              App ID: {a.deriv_app_id} • Stake: ${formatNumber(a.default_stake_usd, 2)} •{' '}
                              {a.default_multiplier}x
                            </p>
                            <div className="mt-4 flex gap-2">
                              {!isActive ? (
                                <button
                                  type="button"
                                  onClick={() => selectAccount(a.account_id)}
                                  className="flex-1 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300"
                                >
                                  Ativar
                                </button>
                              ) : (
                                <span className="flex-1 rounded-xl bg-slate-100 dark:bg-slate-800 py-1.5 text-center text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
                                  Em operação
                                </span>
                              )}
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingAccId(a.account_id)
                                  setAccType((a.account_type as 'DEMO' | 'REAL') || 'DEMO')
                                  setAccLabel(a.label)
                                  setAccAppId(a.deriv_app_id || '1089')
                                  setAccStake(a.default_stake_usd || 10)
                                  setAccMult(a.default_multiplier || 100)
                                  setAccConnMode(a.connection_mode || 'DERIV_CLOUD')
                                }}
                                className="rounded-xl border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                              >
                                Editar
                              </button>
                              <button
                                type="button"
                                onClick={() => requestDeleteAccount(a)}
                                className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-700 dark:text-rose-300 hover:bg-rose-500/20"
                              >
                                Apagar
                              </button>
                            </div>
                          </CardBody>
                        </Card>
                      )
                    })}
                  </section>
                </div>
              )}

              {/* MATRIX VWAP & Z-SCORE */}
              {activeTab === 'monitor' && (
                <Card className="overflow-hidden">
                  <CardHeader>
                    <CardTitle>Matriz matemática — VWAP, Bandas (±2σ) e Z-Score</CardTitle>
                    <CardDescription>
                      Cálculo contínuo sobre os ativos monitorados na Deriv
                    </CardDescription>
                  </CardHeader>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950/40">
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
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                        {!Object.keys(snapshot?.symbols || {}).length ? (
                          <tr>
                            <td colSpan={9} className="px-4 py-8 text-center text-slate-500 font-sans">
                              Aguardando cotações da Deriv para preencher a matriz.
                            </td>
                          </tr>
                        ) : (
                          Object.values(snapshot?.symbols || {}).map((s) => {
                            if (!s || !s.symbol) return null
                            const imbPos = isFiniteNumber(s.imbalance) && s.imbalance >= 0
                            const zPos = isFiniteNumber(s.zscore) && s.zscore >= 0
                            return (
                              <tr
                                key={s.symbol}
                                className="hover:bg-slate-50 dark:hover:bg-slate-900/40"
                              >
                                <td className="px-4 py-3 font-bold text-slate-900 dark:text-white">
                                  {s.symbol}
                                </td>
                                <td className="px-4 py-3 text-right">
                                  {formatPrice(s.price, 5)}
                                </td>
                                <td className="px-4 py-3 text-right text-amber-600 dark:text-amber-300">
                                  {formatPrice(s.vwap, 5)}
                                </td>
                                <td className="px-4 py-3 text-right text-emerald-600 dark:text-emerald-400">
                                  {formatPrice(s.lower_2, 5)}
                                </td>
                                <td className="px-4 py-3 text-right text-rose-600 dark:text-rose-400">
                                  {formatPrice(s.upper_2, 5)}
                                </td>
                                <td
                                  className={`px-4 py-3 text-right ${
                                    imbPos
                                      ? 'text-emerald-600 dark:text-emerald-400'
                                      : 'text-rose-600 dark:text-rose-400'
                                  }`}
                                >
                                  {formatPercent(s.imbalance, 1, true)}
                                </td>
                                <td
                                  className={`px-4 py-3 text-right font-semibold ${
                                    zPos
                                      ? 'text-emerald-600 dark:text-emerald-400'
                                      : 'text-rose-600 dark:text-rose-400'
                                  }`}
                                >
                                  {formatNumber(s.zscore, 2)}
                                </td>
                                <td className="px-4 py-3 text-slate-600 dark:text-slate-300 font-sans">
                                  {s.regime || '--'}
                                </td>
                                <td className="px-4 py-3">
                                  <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[11px] text-slate-700 dark:text-slate-200">
                                    {s.signal || 'WAIT'}
                                  </span>
                                </td>
                              </tr>
                            )
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}

              {/* HISTORY & LOGS */}
              {activeTab === 'history' && (
                <div className="space-y-6">
                  <Card className="overflow-hidden">
                    <CardHeader>
                      <CardTitle>Histórico de Negociações</CardTitle>
                      <CardDescription>Operações encerradas registradas pelo motor</CardDescription>
                    </CardHeader>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase text-slate-500 bg-slate-50 dark:bg-slate-950/40">
                          <tr>
                            <th className="px-4 py-3">Horário</th>
                            <th className="px-4 py-3">Ativo</th>
                            <th className="px-4 py-3">Lado</th>
                            <th className="px-4 py-3 text-right">Stake</th>
                            <th className="px-4 py-3 text-right">Entrada</th>
                            <th className="px-4 py-3 text-right">Saída</th>
                            <th className="px-4 py-3 text-right">Resultado</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                          {!snapshot?.deals_history?.length ? (
                            <tr>
                              <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-sans">
                                Nenhuma operação encerrada registrada ainda.
                              </td>
                            </tr>
                          ) : (
                            snapshot.deals_history.map((d, idx) => {
                              if (!d) return null
                              return (
                                <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                  <td className="px-4 py-2.5 text-slate-500">{d.time_str || '--'}</td>
                                  <td className="px-4 py-2.5 font-semibold">{d.symbol || '--'}</td>
                                  <td className="px-4 py-2.5">{d.side || '--'}</td>
                                  <td className="px-4 py-2.5 text-right">${formatNumber(d.volume, 2)}</td>
                                  <td className="px-4 py-2.5 text-right">{formatPrice(d.price_open, 4)}</td>
                                  <td className="px-4 py-2.5 text-right">{formatPrice(d.price_close, 4)}</td>
                                  <td
                                    className={`px-4 py-2.5 text-right font-semibold ${
                                      isFiniteNumber(d.profit) && d.profit >= 0
                                        ? 'text-emerald-600 dark:text-emerald-400'
                                        : 'text-rose-600 dark:text-rose-400'
                                    }`}
                                  >
                                    {formatSignedNumber(d.profit, 2)}
                                  </td>
                                </tr>
                              )
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  </Card>

                  <Card className="overflow-hidden">
                    <CardHeader>
                      <CardTitle>Diário de execução do motor quantitativo</CardTitle>
                    </CardHeader>
                    <div className="max-h-80 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/50 text-xs font-mono">
                      {!snapshot?.logs?.length ? (
                        <div className="p-6 text-center text-slate-500 font-sans">
                          Sem registros no log.
                        </div>
                      ) : (
                        snapshot.logs.slice(0, 40).map((l, idx) => {
                          if (!l) return null
                          return (
                            <div key={idx} className="flex items-start gap-3 px-5 py-2.5">
                              <span className="shrink-0 text-slate-400">{l.time || '--'}</span>
                              <span className="shrink-0 rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] text-blue-600 dark:text-blue-300">
                                {l.module || '--'}
                              </span>
                              <span className="text-slate-700 dark:text-slate-300">{l.message || ''}</span>
                            </div>
                          )
                        })
                      )}
                    </div>
                  </Card>
                </div>
              )}

              {/* SETTINGS */}
              {activeTab === 'settings' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Aparência (Light / Dark Mode)</CardTitle>
                      <CardDescription>
                        A preferência é salva localmente sem afetar os robôs em execução
                      </CardDescription>
                    </CardHeader>
                    <CardBody className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setTheme('light')}
                        className={`flex-1 inline-flex items-center justify-center gap-2 rounded-xl border py-3 text-xs font-semibold transition ${
                          theme === 'light'
                            ? 'border-blue-600 bg-blue-600/10 text-blue-700'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300'
                        }`}
                      >
                        <Sun className="h-4 w-4" />
                        Modo Claro (Light)
                      </button>
                      <button
                        type="button"
                        onClick={() => setTheme('dark')}
                        className={`flex-1 inline-flex items-center justify-center gap-2 rounded-xl border py-3 text-xs font-semibold transition ${
                          theme === 'dark'
                            ? 'border-blue-500 bg-blue-500/15 text-blue-300'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300'
                        }`}
                      >
                        <Moon className="h-4 w-4" />
                        Modo Escuro (Dark)
                      </button>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Segurança e Risco Diário</CardTitle>
                      <CardDescription>
                        Redefinir trava de risco diário ou alterar senha do painel web
                      </CardDescription>
                    </CardHeader>
                    <CardBody className="space-y-4">
                      <button
                        type="button"
                        onClick={resetDailyRisk}
                        className="inline-flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 px-4 py-2 text-xs font-semibold text-amber-700 dark:text-amber-300 transition"
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                        Redefinir trava diária de risco
                      </button>

                      <form onSubmit={saveAdminPassword} className="flex gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                        <div className="relative flex-1">
                          <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                          <input
                            type="password"
                            value={newAdminPassword}
                            onChange={(e) => setNewAdminPassword(e.target.value)}
                            placeholder="Nova senha administrativa (mín. 6 chars)"
                            className={`${inputClass} pl-9`}
                          />
                        </div>
                        <button
                          type="submit"
                          className="rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-xs font-semibold text-white"
                        >
                          Alterar senha
                        </button>
                      </form>
                    </CardBody>
                  </Card>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      <ConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        description={confirmModal.description}
        confirmLabel={confirmModal.confirmLabel}
        variant={confirmModal.variant}
        onConfirm={confirmModal.onConfirm}
        onCancel={() => setConfirmModal((m) => ({ ...m, open: false }))}
      />
    </div>
  )
}

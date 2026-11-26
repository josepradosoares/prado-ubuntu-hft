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
  ExternalLink,
  KeyRound,
} from 'lucide-react'
import {
  BacktestReport,
  BotItem,
  BotTemplate,
  BrokerSymbol,
  ChartPoint,
  CTraderAccount,
  FeatureKey,
  IndicatorMeta,
  MeResponse,
  PositionItem,
  SaasPlan,
  ServerConfig,
  Snapshot,
  StrategyRecipe,
} from './types'
import { LightweightChartPanel } from './components/LightweightChartPanel'
import { BacktestEquityChart } from './components/BacktestEquityChart'
import { BotCardGrid } from './components/BotCardGrid'
import { ModelBuilderPanel } from './components/ModelBuilderPanel'
import { AdminPanel } from './components/AdminPanel'
import { NewsPanel } from './components/NewsPanel'
import { Sidebar, TabKey } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { MarketIndicatorsBar } from './components/MarketIndicatorsBar'
import { CTraderDiagnosticsCard } from './components/CTraderDiagnosticsCard'
import { VwapMatrixPanel } from './components/VwapMatrixPanel'
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
  formatSymbolDisplay,
  isFiniteNumber,
  sanitizeChartPoints,
} from './utils/formatters'
import {
  formatDataSource,
  formatExitReason,
  formatLogModule,
  formatPeriod,
  formatRegime,
  formatSignal,
  formatTimeframe,
  formatTradeSide,
} from './utils/labels'

const PAGE_META: Record<TabKey, { title: string; description: string }> = {
  overview: {
    title: 'Visão geral',
    description: 'Resumo operacional da sua conta, indicadores de mercado e robôs em operação',
  },
  'running-bots': {
    title: 'Painel ao Vivo',
    description: 'Gráfico em tempo real, robôs ativos e operações abertas',
  },
  'my-bots': {
    title: 'Meus robôs',
    description: 'Gerencie, pause, edite ou duplique seus robôs automatizados',
  },
  'create-bot': {
    title: 'Criar Robô',
    description: 'Escolha a conta, o ativo, a estratégia e o gerenciamento de risco do seu robô',
  },
  templates: {
    title: 'Estratégias',
    description: 'Use estratégias prontas ou crie as suas combinando indicadores técnicos e código Python',
  },
  backtest: {
    title: 'Simulador',
    description: 'Teste qualquer estratégia no histórico real com taxa de acerto, lucro e rebaixamento',
  },
  monitor: {
    title: 'Radar de Mercado',
    description: 'Acompanhe tendências, força de fluxo e sinais em tempo real nos ativos monitorados',
  },
  news: {
    title: 'Notícias',
    description: 'Monitoramento de notícias financeiras com filtro de impacto para seus robôs',
  },
  categories: {
    title: 'Mercados',
    description: 'Ativos disponíveis na corretora organizados por categoria',
  },
  'ctrader-config': {
    title: 'Conectar Corretora',
    description: 'Conecte sua corretora cTrader com segurança via autorização oficial OAuth 2.0',
  },
  'ctrader-accounts': {
    title: 'Minhas Contas',
    description: 'Gerencie suas contas Demo e Real e alterne rapidamente entre elas',
  },
  history: {
    title: 'Histórico',
    description: 'Registro de operações executadas e eventos da conta',
  },
  settings: {
    title: 'Configurações',
    description: 'Preferências visuais, segurança, limites diários e parâmetros gerais',
  },
  admin: {
    title: 'Painel Admin',
    description: 'Gerencie planos comerciais, dias de teste grátis, integrações Kiwify e assinaturas de clientes',
  },
}

function formatOpenDateTime(openMs?: number, fallbackStr?: string): string {
  if (openMs && openMs > 0) {
    const d = new Date(openMs)
    if (!Number.isNaN(d.getTime())) {
      const dd = String(d.getDate()).padStart(2, '0')
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const hh = String(d.getHours()).padStart(2, '0')
      const mi = String(d.getMinutes()).padStart(2, '0')
      const ss = String(d.getSeconds()).padStart(2, '0')
      return `${dd}/${mm} ${hh}:${mi}:${ss}`
    }
  }
  return fallbackStr || '--'
}

function formatElapsedDuration(openMs?: number): string {
  if (!openMs || openMs <= 0) return ''
  const diffSec = Math.max(0, Math.floor((Date.now() - openMs) / 1000))
  if (diffSec < 60) return `há ${diffSec}s`
  const mins = Math.floor(diffSec / 60)
  if (mins < 60) return `há ${mins}m`
  const hrs = Math.floor(mins / 60)
  const remMins = mins % 60
  if (hrs < 24) return `há ${hrs}h ${String(remMins).padStart(2, '0')}m`
  const days = Math.floor(hrs / 24)
  return `há ${days}d ${hrs % 24}h`
}

function computeSlTpProgress(p: PositionItem): { pct: number; towardTp: boolean } | null {
  if (!p.sl || !p.tp || p.sl <= 0 || p.tp <= 0 || p.price_open <= 0 || p.price_current <= 0) {
    return null
  }
  const isBuy = p.side === 'BUY'
  if (isBuy) {
    if (p.price_current >= p.price_open) {
      const span = Math.max(1e-9, p.tp - p.price_open)
      return { pct: Math.min(100, ((p.price_current - p.price_open) / span) * 100), towardTp: true }
    }
    const span = Math.max(1e-9, p.price_open - p.sl)
    return { pct: Math.min(100, ((p.price_open - p.price_current) / span) * 100), towardTp: false }
  }
  if (p.price_current <= p.price_open) {
    const span = Math.max(1e-9, p.price_open - p.tp)
    return { pct: Math.min(100, ((p.price_open - p.price_current) / span) * 100), towardTp: true }
  }
  const span = Math.max(1e-9, p.sl - p.price_open)
  return { pct: Math.min(100, ((p.price_current - p.price_open) / span) * 100), towardTp: false }
}

export default function App() {
  const { theme, setTheme, toggleTheme } = useTheme()

  const [authChecked, setAuthChecked] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [loginUser, setLoginUser] = useState('admin')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [supabaseEnabled, setSupabaseEnabled] = useState(false)
  const [authMode, setAuthMode] = useState<'LOGIN' | 'SIGNUP'>('LOGIN')
  const [loginInfo, setLoginInfo] = useState('')
  const [me, setMe] = useState<MeResponse | null>(null)
  const [publicPlans, setPublicPlans] = useState<SaasPlan[]>([])
  const [publicTrialDays, setPublicTrialDays] = useState<number>(7)
  const [signupPlanId, setSignupPlanId] = useState<string>('')

  const [activeTab, setActiveTab] = useState<TabKey>('running-bots')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [config, setConfig] = useState<ServerConfig | null>(null)
  const [templates, setTemplates] = useState<BotTemplate[]>([])
  const [indicatorsCatalog, setIndicatorsCatalog] = useState<IndicatorMeta[]>([])
  const [recipes, setRecipes] = useState<StrategyRecipe[]>([])
  const [defaultPythonCode, setDefaultPythonCode] = useState('')
  const [symbols, setSymbols] = useState<BrokerSymbol[]>([])
  const [symbolMode, setSymbolMode] = useState<'PRINCIPAIS' | 'TODOS'>('TODOS')
  const symbolModeRef = useRef<'PRINCIPAIS' | 'TODOS'>('TODOS')
  const [chartSymbol, setChartSymbol] = useState('EURUSD')
  const [chartTimeframe, setChartTimeframe] = useState('TICKS')
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
  const [botSymbol, setBotSymbol] = useState('EURUSD')
  const [botLotSize, setBotLotSize] = useState(0.01)
  const [botWindow, setBotWindow] = useState(120)
  const [botZscore, setBotZscore] = useState(1.8)
  const [botImb, setBotImb] = useState(0.35)
  const [botRevertSigma, setBotRevertSigma] = useState(2.0)
  const [botGridDir, setBotGridDir] = useState<'BUY_ONLY' | 'SELL_ONLY' | 'BOTH'>('BUY_ONLY')
  const [botGridStep, setBotGridStep] = useState(0.002)
  const [botGridTp, setBotGridTp] = useState(0.002)
  const [botGridMaxLevels, setBotGridMaxLevels] = useState(5)
  const [botLossGuardEnabled, setBotLossGuardEnabled] = useState(true)
  const [botMaxLossUsd, setBotMaxLossUsd] = useState(20)
  const [botNewsAssisted, setBotNewsAssisted] = useState(false)
  const [botTimeframe, setBotTimeframe] = useState('TICKS')
  const [botTpMode, setBotTpMode] = useState<'AUTO' | 'USD' | 'PCT' | 'PIPS' | 'TICKS'>('AUTO')
  const [botTpValue, setBotTpValue] = useState(10)
  const [botFormDirty, setBotFormDirty] = useState(false)

  // Backtest form state
  const [btSymbol, setBtSymbol] = useState('EURUSD')
  const [btTemplateId, setBtTemplateId] = useState('WALL_STREET_HYBRID_BOTH')
  const [btTimeframe, setBtTimeframe] = useState('TICKS')
  const [btPeriod, setBtPeriod] = useState('CUSTOM')
  const [btTicks, setBtTicks] = useState(400)
  const [btCapital, setBtCapital] = useState(10000)
  const [btLotSize, setBtLotSize] = useState(0.01)
  const [btResult, setBtResult] = useState<BacktestReport | null>(null)
  const [btRunning, setBtRunning] = useState(false)

  // Category form state
  const [catName, setCatName] = useState('')
  const [catSymbols, setCatSymbols] = useState('')
  const [symbolSearch, setSymbolSearch] = useState('')

  // Config cTrader state
  const [cfgClientId, setCfgClientId] = useState('')
  const [cfgClientSecret, setCfgClientSecret] = useState('')
  const [cfgRedirectUri, setCfgRedirectUri] = useState('')
  const [cfgAccessToken, setCfgAccessToken] = useState('')
  const [cfgRefreshToken, setCfgRefreshToken] = useState('')
  const [cfgConnMode, setCfgConnMode] = useState('CTRADER_CLOUD')

  // Account Vault form state
  const [editingAccId, setEditingAccId] = useState('')
  const [accType, setAccType] = useState<'DEMO' | 'REAL'>('DEMO')
  const [accLabel, setAccLabel] = useState('')
  const [accCtidAccountId, setAccCtidAccountId] = useState('')
  const [accToken, setAccToken] = useState('')
  const [accLotSize, setAccLotSize] = useState(0.01)
  const [accConnMode, setAccConnMode] = useState('CTRADER_CLOUD')
  const [useCustomCreds, setUseCustomCreds] = useState(false)
  const [syncingAccounts, setSyncingAccounts] = useState(false)
  const [newsScanning, setNewsScanning] = useState(false)
  const [calendarRefreshing, setCalendarRefreshing] = useState(false)

  // Settings password state
  const [newAdminPassword, setNewAdminPassword] = useState('')

  const showToast = useCallback((msg: string, err = false) => {
    setToast({ msg, err })
    setTimeout(() => setToast(null), 4500)
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauthState = params.get('ctrader_oauth')
    if (oauthState) {
      const oauthMsg = params.get('msg') || ''
      if (oauthState === 'ok') {
        showToast(oauthMsg || 'Conta cTrader autorizada via OAuth 2.0!')
      } else {
        showToast(oauthMsg || 'Falha na autorização OAuth cTrader.', true)
      }
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [showToast])

  const fetchChart = useCallback(async (sym: string, tf: string = 'TICKS') => {
    setChartLoading(true)
    try {
      const res = await fetch(`/api/chart?symbol=${encodeURIComponent(sym)}&timeframe=${encodeURIComponent(tf)}`)
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
      setChartError('Não foi possível obter os pontos do gráfico da cTrader.')
    } finally {
      setChartLoading(false)
    }
  }, [])

  const refreshMe = useCallback(async () => {
    try {
      const res = await fetch('/api/me')
      if (res.ok) {
        const d: MeResponse = await res.json()
        setMe(d)
      }
    } catch {
      // ignore
    }
  }, [])

  const loadAllInitial = useCallback(async () => {
    try {
      const [modeRes, pubRes] = await Promise.all([fetch('/api/auth/mode'), fetch('/api/plans/public')])
      if (modeRes.ok) {
        const mData = await modeRes.json()
        const sb = Boolean(mData.supabase_enabled)
        setSupabaseEnabled(sb)
        if (sb) {
          setLoginUser((prev) => (prev === 'admin' ? '' : prev))
        }
      }
      if (pubRes.ok) {
        const pData = await pubRes.json()
        const plist: SaasPlan[] = Array.isArray(pData.plans) ? pData.plans : []
        setPublicPlans(plist)
        if (typeof pData.trial_days === 'number') setPublicTrialDays(pData.trial_days)
        if (plist.length) setSignupPlanId((prev) => prev || plist[0].plan_id)
      }
      const [statusRes, cfgRes, tplRes, symRes, meRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/config'),
        fetch('/api/bot-templates'),
        fetch(`/api/symbols?mode=${symbolModeRef.current}`),
        fetch('/api/me'),
      ])

      if (statusRes.status === 401) {
        setAuthenticated(false)
        setMe(null)
        setAuthChecked(true)
        setInitialLoading(false)
        return
      }

      setAuthenticated(true)
      setAuthChecked(true)
      setConnectionError(null)
      if (window.location.pathname === '/login') {
        window.history.replaceState({}, document.title, '/')
      }

      if (meRes.ok) {
        const meData: MeResponse = await meRes.json()
        setMe(meData)
      }

      if (statusRes.ok) {
        const snap: Snapshot = await statusRes.json()
        setSnapshot(snap)
      }
      if (cfgRes.ok) {
        const cfgData = await cfgRes.json()
        const c: ServerConfig = cfgData.config
        setConfig(c)
        setCfgClientId(c.ctrader_client_id || '')
        setCfgRedirectUri(c.ctrader_redirect_uri || `${window.location.origin}/api/ctrader/oauth/callback`)
        setCfgConnMode(c.connection_mode || 'CTRADER_CLOUD')
        setAccConnMode(c.connection_mode || 'CTRADER_CLOUD')
        setAccLotSize(c.default_lot_size || 0.01)
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
        setIndicatorsCatalog(Array.isArray(tData.indicators) ? tData.indicators : [])
        setRecipes(Array.isArray(tData.recipes) ? tData.recipes : [])
        if (typeof tData.python_template === 'string') setDefaultPythonCode(tData.python_template)
      }
      if (symRes.ok) {
        const sData = await symRes.json()
        setSymbols(Array.isArray(sData.symbols) ? sData.symbols : [])
      }
    } catch {
      setAuthChecked(true)
      setConnectionError('Não foi possível conectar ao servidor backend Quantix.')
    } finally {
      setInitialLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAllInitial()
  }, [loadAllInitial])

  useEffect(() => {
    if (!authenticated) return
    fetchChart(chartSymbol, chartTimeframe)
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
        fetchChart(chartSymbol, chartTimeframe)
      } catch {
        setConnectionError('Sem comunicação com o backend. Tentando reconectar...')
      }
    }, 2000)
    return () => clearInterval(id)
  }, [authenticated, chartSymbol, chartTimeframe, fetchChart])

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    setLoginError('')
    setLoginInfo('')
    const endpoint = supabaseEnabled && authMode === 'SIGNUP' ? '/api/signup' : '/api/login'
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginUser,
          email: loginUser,
          password: loginPass,
          plan_id: authMode === 'SIGNUP' ? signupPlanId : undefined,
        }),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        if (data.confirmation_required) {
          setLoginInfo(data.message || 'Conta criada! Confirme seu e-mail e faça login.')
          setAuthMode('LOGIN')
          return
        }
        setAuthenticated(true)
        if (window.location.pathname === '/login') {
          window.history.replaceState({}, document.title, '/')
        }
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
    setMe(null)
  }

  async function selectTrialPlan(planId: string) {
    try {
      const res = await fetch('/api/subscription/select-trial-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: planId }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setMe((prev) => (prev ? { ...prev, entitlements: d.entitlements } : prev))
        showToast(`Plano de teste alterado para ${d.entitlements.plan_name}!`)
      } else {
        showToast(d.error || 'Não foi possível trocar o plano de teste.', true)
      }
    } catch {
      showToast('Erro de rede ao trocar plano de teste.', true)
    }
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
    setBotSymbol('EURUSD')
    setBotLotSize(config?.default_lot_size || 0.01)
    setBotWindow(120)
    setBotZscore(1.8)
    setBotImb(0.35)
    setBotRevertSigma(2.0)
    setBotGridDir('BUY_ONLY')
    setBotGridStep(0.002)
    setBotGridTp(0.002)
    setBotGridMaxLevels(5)
    setBotLossGuardEnabled(true)
    setBotMaxLossUsd(20)
    setBotNewsAssisted(false)
    setBotTimeframe('TICKS')
    setBotTpMode('AUTO')
    setBotTpValue(10)
    setBotFormDirty(false)
  }

  function startEditBot(b: BotItem) {
    setEditingBotId(b.bot_id)
    setBotName(b.name)
    setBotAccountId(b.account_id)
    setBotTemplateId(b.template_id)
    setBotSymbol(b.symbol)
    setBotLotSize(b.lot_size || 0.01)
    setBotWindow(b.window_ticks)
    setBotZscore(b.zscore_threshold)
    setBotImb(b.imbalance_threshold)
    setBotRevertSigma(b.revert_sigma)
    setBotGridDir((b.grid_direction as 'BUY_ONLY' | 'SELL_ONLY' | 'BOTH') || 'BUY_ONLY')
    setBotGridStep(b.grid_step_points ?? 0.002)
    setBotGridTp(b.grid_tp_points ?? 0.002)
    setBotGridMaxLevels(b.max_grid_levels ?? 5)
    setBotLossGuardEnabled(Boolean(b.loss_guard_enabled))
    setBotMaxLossUsd(b.max_loss_usd ?? 20)
    setBotNewsAssisted(Boolean(b.news_assisted))
    setBotTimeframe((b.timeframe || 'TICKS').toUpperCase())
    const loadedTpMode = String(b.tp_mode || 'AUTO').toUpperCase() as 'AUTO' | 'USD' | 'PCT' | 'PIPS' | 'TICKS'
    setBotTpMode(['AUTO', 'USD', 'PCT', 'PIPS', 'TICKS'].includes(loadedTpMode) ? loadedTpMode : 'AUTO')
    setBotTpValue(b.tp_value && b.tp_value > 0 ? b.tp_value : loadedTpMode === 'USD' ? 2.0 : loadedTpMode === 'PCT' ? 0.25 : 10)
    setBotFormDirty(false)
    setActiveTab('create-bot')
  }

  function openCreateBotForSymbol(sym: string) {
    resetBotForm()
    setBotSymbol(sym)
    setActiveTab('create-bot')
  }

  function handleCreateBotWithTemplate(tpl: BotTemplate) {
    resetBotForm()
    setBotTemplateId(tpl.template_id)
    setBotTimeframe(
      tpl.recommended_timeframe || (tpl.is_custom && tpl.custom_mode === 'INDICATORS' ? 'M5' : 'TICKS'),
    )
    setActiveTab('create-bot')
  }

  function handleTestInBacktest(tpl: BotTemplate) {
    setBtTemplateId(tpl.template_id)
    setBtTimeframe(
      tpl.recommended_timeframe || (tpl.is_custom && tpl.custom_mode === 'INDICATORS' ? 'M5' : 'TICKS'),
    )
    setActiveTab('backtest')
  }

  async function updateMonitoredSymbols(next: string[]) {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active_symbols: next.slice(0, 25) }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        if (d.config) setConfig(d.config)
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
        showToast('Lista de ativos monitorados atualizada!')
      } else {
        showToast(d.error || 'Falha ao atualizar ativos monitorados.', true)
      }
    } catch {
      showToast('Erro de rede ao atualizar ativos monitorados.', true)
    }
  }

  async function duplicateBot(b: BotItem) {
    const payload = {
      name: `${b.name} (Cópia)`,
      account_id: b.account_id || config?.active_account_id || '',
      template_id: b.template_id,
      symbol: b.symbol,
      lot_size: Number(b.lot_size) || 0.01,
      window_ticks: Number(b.window_ticks) || 120,
      zscore_threshold: Number(b.zscore_threshold) || 1.8,
      imbalance_threshold: Number(b.imbalance_threshold) || 0.35,
      revert_sigma: Number(b.revert_sigma) || 2.0,
      tp_mode: b.tp_mode || 'AUTO',
      tp_value: Number(b.tp_value) || 0,
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
    if (!Number.isFinite(botLotSize) || botLotSize < 0.01) {
      showToast('O volume mínimo é 0.01 lote.', true)
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
      lot_size: Number(botLotSize),
      window_ticks: Number(botWindow),
      zscore_threshold: Number(botZscore),
      imbalance_threshold: Number(botImb),
      revert_sigma: Number(botRevertSigma),
      grid_direction: botGridDir,
      grid_step_points: Number(botGridStep),
      grid_tp_points: Number(botGridTp),
      max_grid_levels: Number(botGridMaxLevels),
      loss_guard_enabled: Boolean(botLossGuardEnabled),
      max_loss_usd: Number(botMaxLossUsd),
      news_assisted: Boolean(botNewsAssisted),
      timeframe: botTimeframe,
      tp_mode: botTpMode,
      tp_value: botTpMode === 'AUTO' ? 0 : Number(botTpValue),
    }
    if (editingBotId) {
      payload.bot_id = editingBotId
    } else {
      payload.auto_start = true
    }

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
          timeframe: btTimeframe,
          period: btPeriod,
          tick_count: Number(btTicks),
          initial_capital: Number(btCapital),
          lot_size: Number(btLotSize),
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

  async function saveCTraderConfig(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      ctrader_client_id: cfgClientId.trim(),
      ctrader_redirect_uri: cfgRedirectUri.trim() || `${window.location.origin}/api/ctrader/oauth/callback`,
      connection_mode: cfgConnMode,
    }
    if (cfgClientSecret.trim()) payload.ctrader_client_secret = cfgClientSecret.trim()
    if (cfgAccessToken.trim()) payload.ctrader_access_token = cfgAccessToken.trim()
    if (cfgRefreshToken.trim()) payload.ctrader_refresh_token = cfgRefreshToken.trim()

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setConfig(d.config)
        setCfgClientSecret('')
        setCfgAccessToken('')
        setCfgRefreshToken('')
        showToast('Configuração cTrader salva!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao salvar configuração cTrader.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar configuração cTrader.', true)
    }
  }

  async function startCTraderOAuth() {
    try {
      const redirectUri = cfgRedirectUri.trim() || `${window.location.origin}/api/ctrader/oauth/callback`
      const res = await fetch(`/api/ctrader/oauth/start?redirect_uri=${encodeURIComponent(redirectUri)}`)
      const d = await res.json()
      if (res.ok && d.ok && d.auth_url) {
        window.location.href = d.auth_url
      } else {
        showToast(d.error || 'Salve Client ID e Client Secret antes de autorizar.', true)
      }
    } catch {
      showToast('Erro ao iniciar autorização OAuth cTrader.', true)
    }
  }

  async function scanNewsNow() {
    setNewsScanning(true)
    try {
      const res = await fetch('/api/news/scan', { method: 'POST' })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast(`Pesquisa concluída: ${(d.news?.items || []).length} notícia(s) analisada(s).`)
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao pesquisar notícias.', true)
      }
    } catch {
      showToast('Erro de rede ao pesquisar notícias.', true)
    } finally {
      setNewsScanning(false)
    }
  }

  async function updateNewsConfig(updates: Record<string, unknown>) {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setConfig(d.config)
        showToast('Configuração do Robô de Notícias atualizada!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao atualizar Robô de Notícias.', true)
      }
    } catch {
      showToast('Erro de rede ao atualizar Robô de Notícias.', true)
    }
  }

  async function refreshCalendarNow() {
    setCalendarRefreshing(true)
    try {
      const res = await fetch('/api/news/calendar', { method: 'POST' })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast(`Agenda econômica atualizada: ${(d.calendar?.events || []).length} evento(s).`)
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao atualizar calendário econômico.', true)
      }
    } catch {
      showToast('Erro de rede ao atualizar calendário econômico.', true)
    } finally {
      setCalendarRefreshing(false)
    }
  }

  async function saveNewsFeed(payload: {
    feed_id?: string
    source: string
    url: string
    default_symbol: string
  }): Promise<boolean> {
    if (!payload.url.trim()) {
      showToast('Informe a URL da fonte/RSS.', true)
      return false
    }
    try {
      const res = await fetch('/api/news/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'SAVE',
          feed_id: payload.feed_id || undefined,
          source: payload.source.trim() || 'Fonte Customizada',
          url: payload.url.trim(),
          default_symbol: payload.default_symbol || 'ALL',
        }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast('Fonte de notícias salva globalmente!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
        return true
      }
      showToast(d.error || 'Falha ao salvar fonte de notícias.', true)
      return false
    } catch {
      showToast('Erro de rede ao salvar fonte de notícias.', true)
      return false
    }
  }

  async function deleteNewsFeed(feedId: string) {
    try {
      const res = await fetch('/api/news/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'DELETE', feed_id: feedId }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast('Fonte de notícias removida.')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao remover URL.', true)
      }
    } catch {
      showToast('Erro de rede ao remover URL.', true)
    }
  }

  async function resetNewsFeeds() {
    try {
      const res = await fetch('/api/news/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'RESET_DEFAULT' }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        showToast('Fontes padrão restauradas!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao restaurar fontes padrão.', true)
      }
    } catch {
      showToast('Erro de rede ao restaurar fontes.', true)
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

  async function syncCTraderAccounts() {
    setSyncingAccounts(true)
    try {
      const res = await fetch('/api/accounts/sync', { method: 'POST' })
      const d = await res.json()
      if (res.ok && d.ok) {
        if (config) {
          setConfig({ ...config, accounts: d.accounts, active_account_id: d.active_account_id || config.active_account_id })
        }
        showToast(d.message || 'Contas sincronizadas da cTrader!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.message || d.error || 'Não foi possível sincronizar as contas.', true)
      }
    } catch {
      showToast('Erro de rede ao sincronizar contas da cTrader.', true)
    } finally {
      setSyncingAccounts(false)
    }
  }

  async function saveCTraderAccount(e: FormEvent) {
    e.preventDefault()
    const payload: Record<string, unknown> = {
      account_type: accType,
      label: accLabel.trim(),
      ctid_account_id: accCtidAccountId.trim(),
      access_token: useCustomCreds ? accToken.trim() : '',
      default_lot_size: Number(accLotSize),
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
        setAccCtidAccountId('')
        setAccToken('')
        if (config) {
          setConfig({
            ...config,
            accounts: d.accounts,
            active_account_id: d.account.account_id,
            active_account_type: d.account.account_type || config.active_account_type,
          })
        }
        showToast(d.message || 'Conta cTrader salva!')
        const stRes = await fetch('/api/status')
        if (stRes.ok) setSnapshot(await stRes.json())
      } else {
        showToast(d.error || 'Falha ao salvar conta cTrader.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar conta cTrader.', true)
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
        if (config) {
          setConfig({
            ...config,
            active_account_id: accountId,
            accounts: d.accounts || config.accounts,
          })
        }
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

  function requestDeleteAccount(account: CTraderAccount) {
    setConfirmModal({
      open: true,
      title: 'Remover conta cTrader',
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
      title: isSingle ? `Encerrar operação #${ticket}` : 'Encerrar todas as operações',
      description: isSingle
        ? `Confirmar o encerramento imediato da operação #${ticket} na corretora?`
        : 'Confirmar o encerramento imediato de todas as operações abertas na conta ativa?',
      confirmLabel: isSingle ? 'Encerrar operação' : 'Encerrar todas agora',
      variant: 'danger',
      onConfirm: async () => {
        setConfirmModal((m) => ({ ...m, open: false }))
        try {
          const res = await fetch('/api/flatten', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(isSingle ? { ticket } : {}),
          })
          const d = await res.json().catch(() => ({ ok: false, message: `Erro HTTP ${res.status}` }))
          if (res.ok && d.ok) {
            showToast(d.message || 'Posições zeradas.')
            const stRes = await fetch('/api/status')
            if (stRes.ok) setSnapshot(await stRes.json())
          } else {
            showToast(d.message || d.error || 'Nenhuma posição fechada.', true)
          }
        } catch {
          showToast('Erro de rede ao encerrar posição na cTrader.', true)
        }
      },
    })
  }

  function requestCloseProfitable(winnersCount: number, winnersTotal: number) {
    const cur = snapshot?.account?.currency || 'USD'
    setConfirmModal({
      open: true,
      title: `Realizar lucros de ${winnersCount} operação(ões)`,
      description: `Confirmar o encerramento imediato de ${winnersCount} operação(ões) no positivo (lucro atual somado: +${formatCurrency(winnersTotal, cur)})? Operações no negativo permanecerão abertas.`,
      confirmLabel: 'Realizar lucros agora',
      variant: 'primary',
      onConfirm: async () => {
        setConfirmModal((m) => ({ ...m, open: false }))
        try {
          const res = await fetch('/api/flatten', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profitable_only: true }),
          })
          const d = await res.json().catch(() => ({ ok: false, message: `Erro HTTP ${res.status}` }))
          if (res.ok && d.ok) {
            showToast(d.message || 'Posições lucrativas encerradas.')
            const stRes = await fetch('/api/status')
            if (stRes.ok) setSnapshot(await stRes.json())
          } else {
            showToast(d.message || d.error || 'Nenhuma posição lucrativa fechada.', true)
          }
        } catch {
          showToast('Erro de rede ao encerrar posições lucrativas na cTrader.', true)
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
    const set = new Set<string>(['EURUSD', 'BTCUSD', 'XAUUSD'])
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
        Inicializando terminal Quantix...
      </div>
    )
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-slate-100 dark:bg-[#1b191a]">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] p-8 shadow-xl dark:shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-blue-600/10 border border-blue-600/25 flex items-center justify-center text-blue-600 dark:text-blue-400">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-slate-900 dark:text-white">Quantix</h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">cTrader Open API • Terminal 24/7</p>
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
            {supabaseEnabled && (
              <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 dark:bg-slate-900 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('LOGIN')
                    setLoginError('')
                    setLoginInfo('')
                  }}
                  className={`rounded-lg py-1.5 text-xs font-semibold transition ${
                    authMode === 'LOGIN'
                      ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-500 dark:text-slate-400'
                  }`}
                >
                  Entrar
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('SIGNUP')
                    setLoginError('')
                    setLoginInfo('')
                  }}
                  className={`rounded-lg py-1.5 text-xs font-semibold transition ${
                    authMode === 'SIGNUP'
                      ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-500 dark:text-slate-400'
                  }`}
                >
                  Criar Conta
                </button>
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1.5">
                {supabaseEnabled ? 'E-mail (Supabase)' : 'Usuário'}
              </label>
              <input
                type={supabaseEnabled ? 'email' : 'text'}
                placeholder={supabaseEnabled ? 'seu@email.com' : 'admin'}
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
            {supabaseEnabled && authMode === 'SIGNUP' && (
              <div className="space-y-3 rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3">
                <div className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">
                  {publicTrialDays > 0
                    ? `Ganhe ${publicTrialDays} dias grátis para testar qualquer plano!`
                    : 'Escolha o plano da sua assinatura'}
                </div>
                {publicPlans.length > 0 && (
                  <select
                    value={signupPlanId}
                    onChange={(e) => setSignupPlanId(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-xs text-slate-900 dark:text-white"
                  >
                    {publicPlans.map((pl) => (
                      <option key={pl.plan_id} value={pl.plan_id}>
                        {pl.name} • R$ {pl.price_brl.toLocaleString('pt-BR', { minimumFractionDigits: 2 })} ({pl.max_bots} robôs)
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
            {loginInfo && (
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
                {loginInfo}
              </div>
            )}
            {loginError && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
                {loginError}
              </div>
            )}
            <button
              type="submit"
              className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-sm font-semibold text-white transition shadow-lg shadow-blue-600/20"
            >
              {supabaseEnabled && authMode === 'SIGNUP' ? 'Criar Conta no Supabase' : 'Entrar no Terminal'}
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
  const ent = me?.entitlements
  const isAdmin = Boolean(me?.is_admin)
  const hasFeature = (fk: FeatureKey) => {
    if (isAdmin || !ent) return true
    return Boolean(ent.has_access && ent.allowed_features.includes(fk))
  }
  const renderLockedFeatureCard = (featureKey: FeatureKey, title: string) => {
    const eligiblePlans = (me?.plans || []).filter((p) => p.allowed_features.includes(featureKey))
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-amber-500" />
            {title}
          </CardTitle>
          <CardDescription>
            {!ent?.has_access
              ? 'Seu período grátis ou assinatura encerrou. Assine um plano na Kiwify para liberar seu terminal.'
              : `Este módulo não faz parte do seu plano atual (${ent?.plan_name || 'Atual'}).`}
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(eligiblePlans.length > 0 ? eligiblePlans : me?.plans || []).map((pl) => (
              <div
                key={pl.plan_id}
                className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4 flex flex-col justify-between gap-3"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-slate-900 dark:text-white">{pl.name}</span>
                    <span className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400">
                      R$ {pl.price_brl.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{pl.description}</p>
                </div>
                <div className="flex flex-col gap-2">
                  {ent?.status === 'trial' && (
                    <button
                      type="button"
                      onClick={() => selectTrialPlan(pl.plan_id)}
                      className="w-full rounded-xl border border-sky-500/35 bg-sky-500/10 py-2 text-xs font-semibold text-sky-700 dark:text-sky-300"
                    >
                      Testar no período grátis
                    </button>
                  )}
                  {pl.kiwify_checkout_url ? (
                    <a
                      href={pl.kiwify_checkout_url}
                      target="_blank"
                      rel="noreferrer"
                      className="w-full text-center rounded-xl bg-blue-600 hover:bg-blue-500 py-2 text-xs font-semibold text-white"
                    >
                      Assinar na Kiwify
                    </a>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    )
  }

  const inputClass =
    'w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-blue-500 focus:outline-none transition'

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[#1b191a] text-slate-900 dark:text-slate-100">
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

      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        totalBots={totalBots}
        isAdmin={isAdmin}
        entitlements={ent}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar
          pageTitle={pageInfo.title}
          chartSymbol={chartSymbol}
          availableSymbols={monitoredSymbols}
          symbolCatalog={symbols}
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                {pageInfo.title}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">{pageInfo.description}</p>
            </div>
            {snapshot?.timestamp && (
              <span className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] px-2.5 py-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                Ciclo: {snapshot.timestamp}
              </span>
            )}
          </div>

          {!isAdmin && ent && ent.status === 'trial' && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-xs text-sky-800 dark:text-sky-200">
              <div>
                <strong>Período grátis ativo:</strong> faltam{' '}
                <strong>{ent.days_left ?? 0} dia(s)</strong> no plano <strong>{ent.plan_name}</strong> (até{' '}
                {ent.max_bots} robôs).
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {me?.plans && me.plans.length > 1 && (
                  <select
                    value={ent.plan_id}
                    onChange={(e) => selectTrialPlan(e.target.value)}
                    className="rounded-lg border border-sky-500/30 bg-white dark:bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-800 dark:text-slate-100"
                  >
                    {me.plans.map((pl) => (
                      <option key={pl.plan_id} value={pl.plan_id}>
                        Testar plano: {pl.name} ({pl.max_bots} robôs)
                      </option>
                    ))}
                  </select>
                )}
                {ent.kiwify_checkout_url && (
                  <a
                    href={ent.kiwify_checkout_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-lg bg-blue-600 hover:bg-blue-500 px-3 py-1.5 text-xs font-semibold text-white"
                  >
                    Assinar na Kiwify
                  </a>
                )}
              </div>
            </div>
          )}

          {!isAdmin && ent && !ent.has_access && (
            <div className="rounded-2xl border border-rose-500/35 bg-rose-500/10 p-4 space-y-3 text-xs text-rose-800 dark:text-rose-200">
              <div className="font-bold text-sm">
                Seu período grátis ou assinatura expirou — escolha um plano para continuar operando
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {(me?.plans || []).map((pl) => (
                  <div
                    key={pl.plan_id}
                    className="rounded-xl border border-rose-500/20 bg-white/80 dark:bg-slate-900/80 p-3 flex items-center justify-between gap-2 text-slate-900 dark:text-white"
                  >
                    <div>
                      <div className="font-bold">{pl.name}</div>
                      <div className="text-[11px] text-slate-500">
                        R$ {pl.price_brl.toLocaleString('pt-BR', { minimumFractionDigits: 2 })} • até {pl.max_bots} robôs
                      </div>
                    </div>
                    {pl.kiwify_checkout_url && (
                      <a
                        href={pl.kiwify_checkout_url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-lg bg-blue-600 hover:bg-blue-500 px-3 py-1.5 text-[11px] font-semibold text-white shrink-0"
                      >
                        Assinar
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

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
              {(activeTab === 'overview' || activeTab === 'running-bots') && (
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                  {/* Card 1: Conta cTrader */}
                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="flex items-center justify-between gap-1 text-xs text-slate-500 dark:text-slate-400">
                        <span className="truncate">Conta Conectada</span>
                        <div className="flex items-center gap-1 shrink-0">
                          <span className="rounded-md border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-slate-700 dark:text-slate-200">
                            {acc?.currency || 'USD'}
                          </span>
                          <span
                            className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold border ${
                              acc?.account_type === 'REAL'
                                ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30'
                                : 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30'
                            }`}
                          >
                            {acc?.account_type || 'DEMO'}
                          </span>
                        </div>
                      </div>
                      <div className="mt-2 text-lg font-bold font-mono text-slate-900 dark:text-white truncate">
                        {!acc?.login || acc.login === 'DESCONECTADO' ? 'Desconectado' : acc.login}
                      </div>
                      <div
                        className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 truncate"
                        title={acc?.broker_name || acc?.server}
                      >
                        {acc?.broker_name || acc?.server || 'Aguardando credenciais cTrader'}
                      </div>
                      {acc?.status_note && (
                        <div
                          className="mt-0.5 text-[10px] text-amber-600 dark:text-amber-300 truncate"
                          title={acc.status_note}
                        >
                          {acc.status_note}
                        </div>
                      )}
                    </CardBody>
                  </Card>

                  {/* Card 2: Patrimônio & Saldo */}
                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="text-xs text-slate-500 dark:text-slate-400">Patrimônio</div>
                      <div className="mt-2 text-lg font-bold font-mono text-slate-900 dark:text-white">
                        {formatCurrency(acc?.equity, acc?.currency || 'USD')}
                      </div>
                      <div className="mt-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        Saldo base: {formatCurrency(acc?.balance, acc?.currency || 'USD')}
                      </div>
                      <div
                        className={`mt-0.5 text-[11px] font-mono font-semibold ${
                          (acc?.profit ?? 0) >= 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-rose-600 dark:text-rose-400'
                        }`}
                      >
                        Flutuante: {(acc?.profit ?? 0) > 0 ? '+' : ''}
                        {formatCurrency(acc?.profit ?? 0, acc?.currency || 'USD')}
                      </div>
                    </CardBody>
                  </Card>

                  {/* Card 3: Resultado Hoje (Oficial cTrader + Barra de Meta/Trava) */}
                  {(() => {
                    const cur = acc?.currency || 'USD'
                    const dailyRealized = Number(acc?.daily_realized ?? 0)
                    const floatingPnl = Number(acc?.profit ?? 0)
                    const totalDay = dailyRealized + floatingPnl
                    const target = Number(acc?.daily_target_money ?? 0)
                    const maxLoss = Math.abs(Number(acc?.max_daily_loss_money ?? 0))
                    const tradesCount = acc?.daily_trades_count ?? 0
                    const winRate = acc?.daily_win_rate ?? 0
                    const src = acc?.daily_source
                    const srcLabel =
                      src === 'CTRADER_SERVER'
                        ? 'Servidor cTrader'
                        : src === 'SIMULATION'
                          ? 'Simulação'
                          : src === 'DISCONNECTED'
                            ? 'Desconectado'
                            : 'Sessão'
                    const srcClass =
                      src === 'CTRADER_SERVER'
                        ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                        : src === 'SIMULATION'
                          ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30'
                          : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-300 dark:border-slate-700'
                    const breakdownTitle =
                      acc?.daily_gross !== undefined
                        ? `Bruto: ${formatCurrency(acc.daily_gross, cur)} | Swap/Comissão: ${formatCurrency(acc.daily_commissions_swap ?? 0, cur)}`
                        : undefined
                    const showTargetBar = totalDay >= 0 && target > 0
                    const showLossBar = totalDay < 0 && maxLoss > 0
                    const pct = showTargetBar
                      ? Math.min(100, (totalDay / target) * 100)
                      : showLossBar
                        ? Math.min(100, (Math.abs(totalDay) / maxLoss) * 100)
                        : 0

                    return (
                      <Card hoverable>
                        <CardBody className="p-4">
                          <div className="flex items-center justify-between gap-1 text-xs text-slate-500 dark:text-slate-400">
                            <span className="truncate">Resultado Hoje</span>
                            <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-semibold shrink-0 ${srcClass}`}>
                              {srcLabel}
                            </span>
                          </div>
                          <div
                            title={breakdownTitle}
                            className={`mt-2 text-lg font-bold font-mono ${
                              dailyRealized > 0
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : dailyRealized < 0
                                  ? 'text-rose-600 dark:text-rose-400'
                                  : 'text-slate-900 dark:text-white'
                            }`}
                          >
                            {dailyRealized > 0 ? '+' : ''}
                            {formatCurrency(dailyRealized, cur)}
                          </div>
                          <div className="mt-1 text-[11px] font-mono text-slate-500 dark:text-slate-400 truncate">
                            Total c/ flutuante: {totalDay > 0 ? '+' : ''}
                            {formatCurrency(totalDay, cur)}
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                            {tradesCount} op{tradesCount === 1 ? '' : 's'} hoje • {winRate.toFixed(0)}% acerto
                          </div>
                          {(showTargetBar || showLossBar) && (
                            <div className="mt-2 space-y-1">
                              <div className="h-1.5 w-full rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    showTargetBar ? 'bg-emerald-500' : 'bg-rose-500'
                                  }`}
                                  style={{ width: `${pct.toFixed(1)}%` }}
                                />
                              </div>
                              <div className="flex justify-between text-[10px] font-mono text-slate-500 dark:text-slate-400">
                                <span>{showTargetBar ? 'Meta' : 'Trava'}</span>
                                <span>
                                  {pct.toFixed(0)}% de{' '}
                                  {showTargetBar
                                    ? formatCurrency(target, cur, 0)
                                    : formatCurrency(-maxLoss, cur, 0)}
                                </span>
                              </div>
                            </div>
                          )}
                        </CardBody>
                      </Card>
                    )
                  })()}

                  {/* Card 4: Robôs Matemáticos */}
                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="text-xs text-slate-500 dark:text-slate-400">Robôs Ativos</div>
                      <div className="mt-2 text-lg font-bold font-mono text-blue-600 dark:text-blue-400">
                        {activeBots} ativos de {totalBots}
                      </div>
                      <div
                        className={`mt-1 text-[11px] truncate ${
                          snapshot?.risk_locked
                            ? 'text-rose-600 dark:text-rose-400 font-semibold'
                            : 'text-emerald-600 dark:text-emerald-400'
                        }`}
                        title={snapshot?.risk_status}
                      >
                        {snapshot?.risk_locked
                          ? snapshot?.risk_status || 'Trava de risco ativa'
                          : 'Motor quantitativo operacional'}
                      </div>
                    </CardBody>
                  </Card>

                  {/* Card 5: Vetor de Correlação da Cesta */}
                  <Card hoverable>
                    <CardBody className="p-4">
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        Termômetro do Mercado
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
                      <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                        {(snapshot?.basket_bias ?? 0) > 0.05
                          ? 'Viés comprador da cesta'
                          : (snapshot?.basket_bias ?? 0) < -0.05
                            ? 'Viés vendedor da cesta'
                            : 'Cesta equilibrada'}
                      </div>
                    </CardBody>
                  </Card>
                </section>
              )}

              {(activeTab === 'overview' || activeTab === 'running-bots') && (
                <div className="space-y-6">
                  <MarketIndicatorsBar
                    symbol={chartSymbol}
                    symbolCatalog={symbols}
                    symbolState={snapshot?.symbols?.[chartSymbol]}
                    connected={isConnected}
                  />
                  {activeTab === 'overview' && (
                    <CTraderDiagnosticsCard account={snapshot?.account} />
                  )}

                  <LightweightChartPanel
                    symbol={chartSymbol}
                    availableSymbols={monitoredSymbols}
                    symbolCatalog={symbols}
                    timeframe={chartTimeframe}
                    onSelectTimeframe={setChartTimeframe}
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
                    symbolCatalog={symbols}
                    lastUpdated={snapshot?.timestamp}
                    autoTradingEnabled={snapshot?.auto_trading_enabled ?? true}
                    onAction={handleBotAction}
                    onEdit={startEditBot}
                    onDuplicate={duplicateBot}
                    onNewBot={() => {
                      resetBotForm()
                      setActiveTab('create-bot')
                    }}
                    onDeleteAll={handleDeleteAllBots}
                  />

                  {(() => {
                    const openPositions = (snapshot?.positions || []).filter((p) => p && p.ticket !== undefined)
                    const totalLots = openPositions.reduce((accSum, p) => accSum + Number(p.volume || 0), 0)
                    const totalFloat = openPositions.reduce((accSum, p) => accSum + Number(p.profit || 0), 0)
                    const winners = openPositions.filter((p) => Number(p.profit || 0) > 0)
                    const winnersTotal = winners.reduce((accSum, p) => accSum + Number(p.profit || 0), 0)
                    const cur = acc?.currency || 'USD'

                    return (
                      <Card className="overflow-hidden">
                        <CardHeader className="bg-slate-50/70 dark:bg-slate-900/40 flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <CardTitle>Operações Abertas</CardTitle>
                            <CardDescription>
                              Horário de abertura, duração, Stop Loss / Take Profit e lucro líquido na moeda da conta
                            </CardDescription>
                          </div>
                          {openPositions.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1 text-[11px] font-mono text-slate-700 dark:text-slate-200">
                                {openPositions.length} aberta{openPositions.length === 1 ? '' : 's'} • {formatNumber(totalLots, 2)} lotes
                              </span>
                              <span
                                className={`rounded-lg border px-2.5 py-1 text-[11px] font-mono font-semibold ${
                                  totalFloat >= 0
                                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                                    : 'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300'
                                }`}
                              >
                                Flutuante: {totalFloat > 0 ? '+' : ''}
                                {formatCurrency(totalFloat, cur)}
                              </span>
                              {winners.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => requestCloseProfitable(winners.length, winnersTotal)}
                                  className="rounded-lg border border-emerald-500/40 bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1 text-[11px] font-semibold text-white transition"
                                >
                                  Realizar Lucros ({winners.length})
                                </button>
                              )}
                            </div>
                          )}
                        </CardHeader>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <thead className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950/40">
                              <tr>
                                <th className="px-3 py-3">Posição</th>
                                <th className="px-3 py-3">Abertura</th>
                                <th className="px-3 py-3">Robô</th>
                                <th className="px-3 py-3">Ativo</th>
                                <th className="px-3 py-3">Lado</th>
                                <th className="px-3 py-3 text-right">Lotes</th>
                                <th className="px-3 py-3 text-right">Entrada / Atual</th>
                                <th className="px-3 py-3">SL / TP</th>
                                <th className="px-3 py-3 text-right">Lucro ({cur})</th>
                                <th className="px-3 py-3 text-right">Ação</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                              {!openPositions.length ? (
                                <tr>
                                  <td
                                    colSpan={10}
                                    className="px-4 py-8 text-center text-slate-500 font-sans"
                                  >
                                    Nenhuma posição aberta no momento.
                                  </td>
                                </tr>
                              ) : (
                                openPositions.map((p) => {
                                  const profitPositive = isFiniteNumber(p.profit) && p.profit >= 0
                                  const elapsed = formatElapsedDuration(p.open_timestamp_ms)
                                  const slTpProg = computeSlTpProgress(p)
                                  const costsTotal = Number(p.swap || 0) + Number(p.commission || 0)
                                  const priceDiff =
                                    p.price_open > 0 && p.price_current > 0
                                      ? (p.side === 'BUY' ? 1 : -1) * (p.price_current - p.price_open)
                                      : 0

                                  return (
                                    <tr
                                      key={String(p.ticket)}
                                      className="hover:bg-slate-50 dark:hover:bg-slate-900/40"
                                    >
                                      <td className="px-3 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                                        #{p.ticket}
                                      </td>
                                      <td className="px-3 py-3 whitespace-nowrap">
                                        <div className="text-slate-800 dark:text-slate-200">
                                          {formatOpenDateTime(p.open_timestamp_ms, p.open_time_str)}
                                        </div>
                                        {elapsed && (
                                          <div className="text-[10px] font-sans text-slate-500 dark:text-slate-400">
                                            {elapsed}
                                          </div>
                                        )}
                                      </td>
                                      <td className="px-3 py-3 font-sans font-semibold text-blue-600 dark:text-blue-400">
                                        {p.bot_name || p.comment || '--'}
                                      </td>
                                      <td className="px-3 py-3 font-sans font-semibold">
                                        <button
                                          type="button"
                                          title="Carregar ativo no gráfico acima"
                                          onClick={() => {
                                            setChartSymbol(p.symbol)
                                            showToast(`Gráfico atualizado para ${formatSymbolDisplay(p.symbol, symbols)}`)
                                            window.scrollTo({ top: 180, behavior: 'smooth' })
                                          }}
                                          className="text-left text-slate-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 underline decoration-dotted underline-offset-2"
                                        >
                                          {formatSymbolDisplay(p.symbol, symbols)}
                                        </button>
                                      </td>
                                      <td className="px-3 py-3">
                                        <span
                                          className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                                            p.side === 'BUY'
                                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                              : 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                                          }`}
                                        >
                                          {formatTradeSide(p.side)}
                                        </span>
                                      </td>
                                      <td className="px-3 py-3 text-right">
                                        {formatNumber(p.volume, 2)}
                                      </td>
                                      <td className="px-3 py-3 text-right whitespace-nowrap">
                                        <div className="text-slate-700 dark:text-slate-200">
                                          {formatPrice(p.price_open, 5)}
                                        </div>
                                        <div className="text-[11px] text-slate-500 dark:text-slate-400">
                                          {formatPrice(p.price_current, 5)}{' '}
                                          {priceDiff !== 0 && (
                                            <span className={priceDiff > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                                              ({priceDiff > 0 ? '+' : ''}{priceDiff.toFixed(5)})
                                            </span>
                                          )}
                                        </div>
                                      </td>
                                      <td className="px-3 py-3 min-w-[130px]">
                                        <div className="text-[11px] space-y-0.5">
                                          <div className="text-rose-600 dark:text-rose-400">
                                            SL: {p.sl > 0 ? formatPrice(p.sl, 5) : '--'}
                                          </div>
                                          <div className="text-emerald-600 dark:text-emerald-400">
                                            TP: {p.tp > 0 ? formatPrice(p.tp, 5) : '--'}
                                          </div>
                                        </div>
                                        {slTpProg && (
                                          <div className="mt-1 h-1 w-full rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                                            <div
                                              className={`h-full rounded-full ${
                                                slTpProg.towardTp ? 'bg-emerald-500' : 'bg-rose-500'
                                              }`}
                                              style={{ width: `${slTpProg.pct.toFixed(1)}%` }}
                                            />
                                          </div>
                                        )}
                                      </td>
                                      <td
                                        className={`px-3 py-3 text-right whitespace-nowrap ${
                                          profitPositive
                                            ? 'text-emerald-600 dark:text-emerald-400'
                                            : 'text-rose-600 dark:text-rose-400'
                                        }`}
                                      >
                                        <div className="font-semibold">
                                          {p.profit > 0 ? '+' : ''}
                                          {formatCurrency(p.profit, cur)}
                                        </div>
                                        {costsTotal !== 0 && (
                                          <div className="text-[10px] font-sans text-slate-500 dark:text-slate-400">
                                            Custos: {formatCurrency(costsTotal, cur)}
                                          </div>
                                        )}
                                      </td>
                                      <td className="px-3 py-3 text-right">
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
                    )
                  })()}
                </div>
              )}

              {activeTab === 'my-bots' && (
                <BotCardGrid
                  bots={snapshot?.bots || []}
                  symbols={snapshot?.symbols || {}}
                  symbolCatalog={symbols}
                  lastUpdated={snapshot?.timestamp}
                  autoTradingEnabled={snapshot?.auto_trading_enabled ?? true}
                  onAction={handleBotAction}
                  onEdit={startEditBot}
                  onDuplicate={duplicateBot}
                  onNewBot={() => {
                    resetBotForm()
                    setActiveTab('create-bot')
                  }}
                  onDeleteAll={handleDeleteAllBots}
                />
              )}

              {activeTab === 'create-bot' && (
                <Card>
                  <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle>
                        {editingBotId ? 'Editar robô matemático' : 'Configurar novo robô matemático'}
                      </CardTitle>
                      <CardDescription>
                        Defina a conta cTrader, ativo, modelo quantitativo, volume em Lotes e gatilhos estatísticos
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
                            placeholder="Ex: Bot EURUSD VWAP"
                            className={inputClass}
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Conta cTrader vinculada
                          </label>
                          <select
                            value={botAccountId}
                            onChange={(e) => setBotAccountId(e.target.value)}
                            className={inputClass}
                          >
                            {!config?.accounts?.length && <option value="default">Conta padrão ativa</option>}
                            {config?.accounts?.map((a) => (
                              <option key={a.account_id} value={a.account_id}>
                                [{a.account_type}] {a.label}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Ativo cTrader
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

                      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/40 p-3 flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                            Modo de Leitura / Tempo Gráfico
                          </div>
                          <div className="text-[11px] text-slate-500 dark:text-slate-400">
                            Em <strong>Tick a Tick</strong> mantém o comportamento HFT padrão; em <strong>M1–H1</strong> aplica o modelo matemático escolhido sobre velas desse período.
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {[
                            { id: 'TICKS', label: 'Tick a Tick (Padrão)' },
                            { id: 'M1', label: 'M1' },
                            { id: 'M5', label: 'M5' },
                            { id: 'M15', label: 'M15' },
                            { id: 'H1', label: 'H1' },
                          ].map((opt) => (
                            <button
                              key={opt.id}
                              type="button"
                              onClick={() => setBotTimeframe(opt.id)}
                              className={`rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
                                botTimeframe === opt.id
                                  ? 'border-blue-500 bg-blue-600 text-white'
                                  : 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                              }`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="border-t border-slate-100 dark:border-slate-800 pt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Volume Padrão (Lotes)
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            value={botLotSize}
                            onChange={(e) => setBotLotSize(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
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
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Alvo de Ganho (Take Profit)
                          </label>
                          <select
                            value={botTpMode}
                            onChange={(e) => {
                              const next = e.target.value as 'AUTO' | 'USD' | 'PCT' | 'PIPS' | 'TICKS'
                              setBotTpMode(next)
                              if (next === 'USD' && botTpValue <= 0) setBotTpValue(2.0)
                              else if (next === 'PCT' && botTpValue <= 0) setBotTpValue(0.25)
                              else if ((next === 'PIPS' || next === 'TICKS') && botTpValue <= 0) setBotTpValue(10)
                            }}
                            className={inputClass}
                          >
                            <option value="AUTO">Padrão Matemático (1.8σ VWAP)</option>
                            <option value="USD">Lucro alvo fixo (USD)</option>
                            <option value="PIPS">Distância em Pips</option>
                            <option value="PCT">% do Preço</option>
                            <option value="TICKS">Quantidade de Ticks</option>
                          </select>
                        </div>
                        {botTpMode !== 'AUTO' && (
                          <div>
                            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                              {botTpMode === 'USD'
                                ? 'Lucro alvo (USD)'
                                : botTpMode === 'PCT'
                                  ? 'Variação alvo (%)'
                                  : botTpMode === 'PIPS'
                                    ? 'Alvo em Pips'
                                    : 'Alvo em Ticks'}
                            </label>
                            <input
                              type="number"
                              step={botTpMode === 'USD' ? '0.5' : botTpMode === 'PCT' ? '0.05' : '1'}
                              min={botTpMode === 'USD' ? '0.1' : botTpMode === 'PCT' ? '0.01' : '1'}
                              value={botTpValue}
                              onChange={(e) => setBotTpValue(Number(e.target.value))}
                              className={`${inputClass} font-mono`}
                            />
                          </div>
                        )}
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
                                Passo do Grid (preço)
                              </label>
                              <input
                                type="number"
                                step="0.0005"
                                min="0.0001"
                                value={botGridStep}
                                onChange={(e) => setBotGridStep(Number(e.target.value))}
                                className={`${inputClass} font-mono`}
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                                Alvo por Nível (preço)
                              </label>
                              <input
                                type="number"
                                step="0.0005"
                                min="0.0001"
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

                      <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 flex flex-wrap items-center justify-between gap-4">
                        <label className="flex items-center gap-2.5 text-xs font-medium text-slate-700 dark:text-slate-200 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={botLossGuardEnabled}
                            onChange={(e) => setBotLossGuardEnabled(e.target.checked)}
                            className="h-4 w-4 rounded border-slate-400 text-amber-500 focus:ring-amber-500"
                          />
                          <span>
                            <strong>Trava de perda máxima:</strong> pausar este robô automaticamente se atingir perda limite
                          </span>
                        </label>
                        {botLossGuardEnabled && (
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-slate-500 dark:text-slate-400">Perda máxima (USD):</label>
                            <input
                              type="number"
                              step="0.5"
                              min="0.5"
                              value={botMaxLossUsd}
                              onChange={(e) => setBotMaxLossUsd(Number(e.target.value))}
                              className={`${inputClass} w-28 font-mono`}
                            />
                          </div>
                        )}
                      </div>

                      <div className="rounded-xl border border-blue-500/25 bg-blue-500/5 p-4 flex flex-wrap items-center justify-between gap-4">
                        <label className="flex items-center gap-2.5 text-xs font-medium text-slate-700 dark:text-slate-200 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={botNewsAssisted}
                            onChange={(e) => setBotNewsAssisted(e.target.checked)}
                            className="h-4 w-4 rounded border-slate-400 text-blue-500 focus:ring-blue-500"
                          />
                          <span>
                            <strong>Operar com Técnica + Notícias:</strong> este robô usa as informações das URLs monitoradas junto com VWAP/Z-Score para entrar a favor da notícia, segurar posição favorável até lucro maior ou sair se a notícia virar contra.
                          </span>
                        </label>
                      </div>

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

              {activeTab === 'backtest' && !hasFeature('backtest') && renderLockedFeatureCard('backtest', 'Simulador Histórico (Backtest)')}

              {activeTab === 'backtest' && hasFeature('backtest') && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Parâmetros do Backtest tick a tick</CardTitle>
                      <CardDescription>
                        Executa o motor matemático sobre séries históricas cTrader (ou simulador CFD por Lotes)
                      </CardDescription>
                    </CardHeader>
                    <CardBody className="space-y-6">
                      <form
                        onSubmit={runBacktest}
                        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-8 gap-4"
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
                            <option value="ALL">Todos os ativos</option>
                            {symbols.map((s) => (
                              <option key={s.name} value={s.name}>
                                {formatSymbolDisplay(s.name, symbols)}
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
                            Tempo Gráfico
                          </label>
                          <select
                            value={btTimeframe}
                            onChange={(e) => setBtTimeframe(e.target.value)}
                            className={`${inputClass} font-mono`}
                          >
                            <option value="TICKS">Tick a Tick</option>
                            <option value="M1">1 Minuto (M1)</option>
                            <option value="M5">5 Minutos (M5)</option>
                            <option value="M15">15 Minutos (M15)</option>
                            <option value="M30">30 Minutos (M30)</option>
                            <option value="H1">1 Hora (H1)</option>
                            <option value="H4">4 Horas (H4)</option>
                            <option value="D1">1 Dia (D1)</option>
                            <option value="MN1">1 Mês (MN1)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Período
                          </label>
                          <select
                            value={btPeriod}
                            onChange={(e) => setBtPeriod(e.target.value)}
                            className={`${inputClass} font-mono`}
                          >
                            <option value="CUSTOM">Manual (Ticks/Velas)</option>
                            <option value="1D">1 Dia</option>
                            <option value="1W">1 Semana</option>
                            <option value="1M">1 Mês</option>
                            <option value="1Y">1 Ano</option>
                            <option value="2Y">2 Anos</option>
                            <option value="ALL_TIME">Todo Período (5 Anos)</option>
                          </select>
                        </div>
                        {btPeriod === 'CUSTOM' && (
                          <div>
                            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                              {btTimeframe === 'TICKS' ? 'Ticks (120-5000)' : 'Velas (120-5000)'}
                            </label>
                            <input
                              type="number"
                              min={120}
                              max={5000}
                              value={btTicks}
                              onChange={(e) => setBtTicks(Number(e.target.value))}
                              className={`${inputClass} font-mono`}
                            />
                          </div>
                        )}
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Lotes
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            value={btLotSize}
                            onChange={(e) => setBtLotSize(Number(e.target.value))}
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
                        <div className="space-y-4">
                          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
                            <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-slate-700 dark:text-slate-200 font-semibold">
                              {btResult.symbol} • {formatTimeframe(btResult.timeframe)}
                            </span>
                            {btResult.period && (
                              <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-slate-600 dark:text-slate-300">
                                Período: {formatPeriod(btResult.period)}
                              </span>
                            )}
                            {btResult.lot_size !== undefined && (
                              <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-slate-600 dark:text-slate-300">
                                Lote: {formatNumber(btResult.lot_size, 2)}
                              </span>
                            )}
                            {btResult.ticks_processed !== undefined && (
                              <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-slate-600 dark:text-slate-300">
                                {btResult.ticks_processed.toLocaleString('pt-BR')} ticks
                              </span>
                            )}
                            <span
                              className={`rounded-md px-2 py-0.5 font-semibold ${
                                btResult.data_source === 'CTRADER_REAL'
                                  ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                  : 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                              }`}
                            >
                              {formatDataSource(btResult.data_source)}
                            </span>
                          </div>

                          {/* KPIs Principais */}
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4 font-mono text-xs">
                            <div>
                              <span className="text-slate-500 dark:text-slate-400">Operações</span>
                              <div className="text-base font-bold text-slate-900 dark:text-white mt-1">
                                {btResult.total_trades ?? '--'}
                              </div>
                              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                                {btResult.winning_trades ?? 0} ganhos / {btResult.losing_trades ?? 0} perdas
                              </div>
                            </div>
                            <div>
                              <span className="text-slate-500 dark:text-slate-400">Taxa de acerto</span>
                              <div className="text-base font-bold text-blue-600 dark:text-blue-400 mt-1">
                                {formatPercent(btResult.win_rate, 1, false)}
                              </div>
                              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                                Fator de lucro: {formatNumber(btResult.profit_factor ?? 1, 2)}
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
                                ${(btResult.net_profit ?? 0) >= 0 ? '+' : ''}
                                {formatNumber(btResult.net_profit, 2)}
                              </div>
                              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                                Retorno: {(btResult.return_pct ?? 0) >= 0 ? '+' : ''}
                                {formatPercent(btResult.return_pct ?? 0, 2, false)}
                              </div>
                            </div>
                            <div>
                              <span className="text-slate-500 dark:text-slate-400">Rebaixamento máx.</span>
                              <div className="text-base font-bold text-rose-600 dark:text-rose-400 mt-1">
                                ${formatNumber(btResult.max_drawdown, 2)}
                              </div>
                              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                                {formatPercent(btResult.max_drawdown_pct ?? 0, 2, false)} do pico
                              </div>
                            </div>
                          </div>

                          {/* Estatísticas Avançadas do Teste */}
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] p-3.5 font-mono text-xs">
                            <div>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400">Capital final</span>
                              <div className="font-semibold text-slate-900 dark:text-white mt-0.5">
                                ${formatNumber(btResult.final_equity ?? btResult.final_capital, 2)}
                              </div>
                            </div>
                            <div>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400">Expectativa por operação</span>
                              <div
                                className={`font-semibold mt-0.5 ${
                                  (btResult.expectancy ?? 0) >= 0
                                    ? 'text-emerald-600 dark:text-emerald-400'
                                    : 'text-rose-600 dark:text-rose-400'
                                }`}
                              >
                                ${(btResult.expectancy ?? 0) >= 0 ? '+' : ''}
                                {formatNumber(btResult.expectancy ?? 0, 2)}
                              </div>
                            </div>
                            <div>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400">Média Ganho / Perda</span>
                              <div className="font-semibold mt-0.5">
                                <span className="text-emerald-600 dark:text-emerald-400">
                                  +${formatNumber(btResult.avg_win ?? 0, 2)}
                                </span>
                                {' / '}
                                <span className="text-rose-600 dark:text-rose-400">
                                  ${formatNumber(btResult.avg_loss ?? 0, 2)}
                                </span>
                              </div>
                            </div>
                            <div>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400">Melhor / Pior operação</span>
                              <div className="font-semibold mt-0.5">
                                <span className="text-emerald-600 dark:text-emerald-400">
                                  +${formatNumber(btResult.best_trade ?? 0, 2)}
                                </span>
                                {' / '}
                                <span className="text-rose-600 dark:text-rose-400">
                                  ${formatNumber(btResult.worst_trade ?? 0, 2)}
                                </span>
                              </div>
                            </div>
                            <div>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400">Lucro / Perda bruta</span>
                              <div className="font-semibold mt-0.5">
                                <span className="text-emerald-600 dark:text-emerald-400">
                                  ${formatNumber(btResult.gross_profit ?? 0, 2)}
                                </span>
                                {' / '}
                                <span className="text-rose-600 dark:text-rose-400">
                                  ${formatNumber(btResult.gross_loss ?? 0, 2)}
                                </span>
                              </div>
                            </div>
                            <div>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400">Sequência máx. (G/P)</span>
                              <div className="font-semibold text-slate-900 dark:text-white mt-0.5">
                                {btResult.max_consecutive_wins ?? 0}G / {btResult.max_consecutive_losses ?? 0}P
                              </div>
                            </div>
                          </div>

                          {/* Gráfico de Evolução do Patrimônio */}
                          {btResult.equity_curve && btResult.equity_curve.length > 0 && (
                            <BacktestEquityChart
                              points={btResult.equity_curve}
                              initialCapital={btResult.initial_capital ?? btCapital}
                              theme={theme}
                            />
                          )}

                          {/* Tabela de Operações (Trades) */}
                          {btResult.trades && btResult.trades.length > 0 && (
                            <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
                              <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-950/40 px-3 py-2 border-b border-slate-200 dark:border-slate-800 text-xs">
                                <span className="font-semibold text-slate-700 dark:text-slate-200">
                                  Operações Executadas ({btResult.trades.length})
                                </span>
                                <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
                                  Últimas {btResult.trades.length} operações do teste
                                </span>
                              </div>
                              <div className="max-h-72 overflow-y-auto overflow-x-auto">
                                <table className="w-full text-left text-xs font-mono">
                                  <thead className="sticky top-0 bg-slate-50 dark:bg-slate-950/90 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                                    <tr>
                                      <th className="px-3 py-2">#</th>
                                      <th className="px-3 py-2">Tipo</th>
                                      <th className="px-3 py-2">Sinal</th>
                                      <th className="px-3 py-2">Motivo da Saída</th>
                                      <th className="px-3 py-2 text-right">Entrada</th>
                                      <th className="px-3 py-2 text-right">Fechamento</th>
                                      <th className="px-3 py-2 text-right">Resultado ($)</th>
                                      <th className="px-3 py-2 text-right">Patrimônio ($)</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                                    {btResult.trades.map((tr) => (
                                      <tr key={tr.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                                        <td className="px-3 py-1.5 text-slate-500">{tr.id}</td>
                                        <td className="px-3 py-1.5">
                                          <span
                                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                              tr.type === 'BUY'
                                                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                                : 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                                            }`}
                                          >
                                            {formatTradeSide(tr.type)}
                                          </span>
                                        </td>
                                        <td className="px-3 py-1.5 font-sans text-slate-600 dark:text-slate-300">
                                          {formatSignal(tr.signal)}
                                        </td>
                                        <td className="px-3 py-1.5 font-sans text-slate-500 dark:text-slate-400">
                                          {formatExitReason(tr.exit_reason || tr.result)}
                                        </td>
                                        <td className="px-3 py-1.5 text-right">{formatNumber(tr.entry, 5)}</td>
                                        <td className="px-3 py-1.5 text-right">{formatNumber(tr.exit, 5)}</td>
                                        <td
                                          className={`px-3 py-1.5 text-right font-semibold ${
                                            tr.pnl >= 0
                                              ? 'text-emerald-600 dark:text-emerald-400'
                                              : 'text-rose-600 dark:text-rose-400'
                                          }`}
                                        >
                                          {tr.pnl >= 0 ? '+' : ''}${formatNumber(tr.pnl, 2)}
                                        </td>
                                        <td className="px-3 py-1.5 text-right text-slate-700 dark:text-slate-200">
                                          ${formatNumber(tr.equity_after, 2)}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}

                          {btResult.per_symbol && btResult.per_symbol.length > 0 && (
                            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                              <table className="w-full text-left text-xs font-mono">
                                <thead className="bg-slate-50 dark:bg-slate-950/40 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                                  <tr>
                                    <th className="px-3 py-2">Ativo</th>
                                    <th className="px-3 py-2">Fonte</th>
                                    <th className="px-3 py-2 text-right">Operações</th>
                                    <th className="px-3 py-2 text-right">Acerto</th>
                                    <th className="px-3 py-2 text-right">Lucro</th>
                                    <th className="px-3 py-2 text-right">Rebaixamento</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                                  {btResult.per_symbol.map((ps, idx) => (
                                    <tr key={idx}>
                                      <td className="px-3 py-2 font-semibold">{ps.symbol}</td>
                                      <td className="px-3 py-2 font-sans">{formatDataSource(ps.data_source)}</td>
                                      <td className="px-3 py-2 text-right">{ps.total_trades}</td>
                                      <td className="px-3 py-2 text-right">{formatPercent(ps.win_rate, 1, false)}</td>
                                      <td className="px-3 py-2 text-right">${formatNumber(ps.net_profit, 2)}</td>
                                      <td className="px-3 py-2 text-right text-rose-600 dark:text-rose-400">${formatNumber(ps.max_drawdown, 2)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      )}
                    </CardBody>
                  </Card>

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
                            <th className="px-4 py-3 text-right">Operações</th>
                            <th className="px-4 py-3 text-right">Acerto</th>
                            <th className="px-4 py-3 text-right">Lucro</th>
                            <th className="px-4 py-3 text-right">Rebaixamento</th>
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

              {activeTab === 'categories' && (
                <Card>
                  <CardHeader className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle>Categorias e Ativos cTrader</CardTitle>
                      <CardDescription>
                        Alterne entre Principais e Todos os instrumentos carregados da corretora cTrader
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
                        placeholder="Ativos separados por vírgula (ex: EURUSD, XAUUSD, BTCUSD)"
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
                                className="rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2 py-0.5 text-[11px] text-slate-700 dark:text-slate-300"
                              >
                                {formatSymbolDisplay(sym, symbols)}
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
                            Catálogo cTrader ({symbols.length} ativos carregados)
                          </h4>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">
                            Clique em qualquer ativo abaixo para adicioná-lo ao campo de nova categoria acima
                          </p>
                        </div>
                        <input
                          type="text"
                          value={symbolSearch}
                          onChange={(e) => setSymbolSearch(e.target.value)}
                          placeholder="Filtrar ativo (ex: EURUSD, XAU, BTC)..."
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
                                <div className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                                  {formatSymbolDisplay(s.name, symbols)}
                                </div>
                                <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                  {s.category} • {s.name}
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

              {activeTab === 'ctrader-config' && (
                <div className="space-y-6">
                  <CTraderDiagnosticsCard account={snapshot?.account} />

                  {me?.server_oauth_configured && (
                    <Card className="border-emerald-500/35">
                      <CardHeader>
                        <CardTitle>Conectar sua corretora cTrader em 1 clique</CardTitle>
                        <CardDescription>
                          Autorize suas contas Demo e Real de qualquer corretora compatível com cTrader (IC Markets, Pepperstone, FP Markets, FTMO, FxPro e outras) direto no portal oficial cTrader ID
                        </CardDescription>
                      </CardHeader>
                      <CardBody className="space-y-4">
                        <div className="flex flex-wrap items-center gap-3">
                          <button
                            type="button"
                            onClick={startCTraderOAuth}
                            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-5 py-3 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20"
                          >
                            <KeyRound className="h-4 w-4" />
                            Conectar minha conta cTrader
                          </button>
                          <button
                            type="button"
                            onClick={syncCTraderAccounts}
                            disabled={syncingAccounts}
                            className="rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-3 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
                          >
                            {syncingAccounts ? 'Sincronizando...' : 'Atualizar minhas contas'}
                          </button>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Sua senha da corretora nunca é informada ao Quantix. O login ocorre com segurança no site oficial da cTrader e suas contas aparecerão automaticamente em <strong>Minhas Contas</strong>.
                        </p>
                      </CardBody>
                    </Card>
                  )}

                  {(!me?.server_oauth_configured || isAdmin) && (
                    <>
                      <Card>
                        <CardHeader>
                          <CardTitle>Como obter suas credenciais da cTrader Open API</CardTitle>
                      <CardDescription>
                        Siga estes 4 passos no portal oficial da Spotware para conectar qualquer corretora cTrader
                      </CardDescription>
                    </CardHeader>
                    <CardBody className="space-y-3 text-xs text-slate-600 dark:text-slate-300">
                      <ol className="list-decimal pl-5 space-y-1.5">
                        <li>
                          Acesse{' '}
                          <a
                            href="https://openapi.ctrader.com/apps"
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                          >
                            https://openapi.ctrader.com/apps
                            <ExternalLink className="h-3 w-3" />
                          </a>{' '}
                          e faça login com seu <strong>cTrader ID (cTID)</strong>.
                        </li>
                        <li>
                          Clique em <strong>Add new app</strong>, preencha nome/descrição e cadastre a Redirect URI:{' '}
                          <code className="rounded bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 font-mono text-[11px]">
                            {cfgRedirectUri || `${window.location.origin}/api/ctrader/oauth/callback`}
                          </code>
                        </li>
                        <li>
                          Após aprovação, copie o <strong>Client ID</strong> e o <strong>Client Secret</strong> e salve abaixo.
                        </li>
                        <li>
                          Clique em <strong>Autorizar com cTrader (OAuth 2.0)</strong> abaixo (ou cole o Access Token gerado no Playground do app).
                        </li>
                      </ol>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Credenciais cTrader Open API (OAuth 2.0 &amp; WebSocket 5036)</CardTitle>
                      <CardDescription>
                        Client Secret e tokens nunca são exibidos por completo após salvos
                      </CardDescription>
                    </CardHeader>
                    <CardBody className="space-y-6">
                      <form
                        onSubmit={saveCTraderConfig}
                        className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl"
                      >
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            cTrader Client ID
                          </label>
                          <input
                            type="text"
                            value={cfgClientId}
                            onChange={(e) => setCfgClientId(e.target.value)}
                            placeholder="Ex: 12345_abcde..."
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            cTrader Client Secret
                          </label>
                          <input
                            type="password"
                            value={cfgClientSecret}
                            onChange={(e) => setCfgClientSecret(e.target.value)}
                            placeholder={
                              config?.ctrader_client_secret_set
                                ? 'Client Secret salvo (cole outro para substituir)'
                                : 'Cole seu Client Secret de openapi.ctrader.com/apps'
                            }
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Redirect URI (OAuth Callback)
                          </label>
                          <input
                            type="text"
                            value={cfgRedirectUri}
                            onChange={(e) => setCfgRedirectUri(e.target.value)}
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
                            <option value="CTRADER_CLOUD">
                              cTrader Nuvem — Demo e Real (wss porta 5036)
                            </option>
                            <option value="SIMULATION">Simulador Quantitativo Interno (Lotes CFD)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Access Token (Opcional / Playground)
                          </label>
                          <input
                            type="password"
                            value={cfgAccessToken}
                            onChange={(e) => setCfgAccessToken(e.target.value)}
                            placeholder={
                              config?.ctrader_access_token_set
                                ? 'Access Token salvo (preenchido via OAuth ou manual)'
                                : 'Preenchido automaticamente pelo botão OAuth ou cole aqui'
                            }
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                            Refresh Token (Opcional)
                          </label>
                          <input
                            type="password"
                            value={cfgRefreshToken}
                            onChange={(e) => setCfgRefreshToken(e.target.value)}
                            placeholder={
                              config?.ctrader_refresh_token_set
                                ? 'Refresh Token salvo'
                                : 'Preenchido automaticamente pelo OAuth 2.0'
                            }
                            className={`${inputClass} font-mono`}
                          />
                        </div>
                        <div className="md:col-span-2 flex flex-wrap gap-3 pt-2">
                          <button
                            type="submit"
                            className="rounded-xl bg-blue-600 hover:bg-blue-500 px-5 py-2.5 text-xs font-semibold text-white"
                          >
                            Salvar configuração cTrader
                          </button>
                          <button
                            type="button"
                            onClick={startCTraderOAuth}
                            className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/35 bg-emerald-500/15 hover:bg-emerald-500/25 px-5 py-2.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300"
                          >
                            <KeyRound className="h-3.5 w-3.5" />
                            Autorizar com cTrader (OAuth 2.0)
                          </button>
                        </div>
                      </form>
                    </CardBody>
                  </Card>
                    </>
                  )}
                </div>
              )}

              {activeTab === 'ctrader-accounts' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <CardTitle>Cofre de Contas cTrader (Demo &amp; Real)</CardTitle>
                        <CardDescription>
                          Gerencie contas Demo e Real sincronizadas do seu cTrader ID (cTID) — conta REAL exige desbloqueio explícito
                        </CardDescription>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={toggleRealTrading}
                          className={`rounded-xl border px-3.5 py-1.5 text-xs font-semibold transition ${
                            config?.allow_real_trading
                              ? 'border-amber-500/50 bg-amber-500/15 text-amber-700 dark:text-amber-300'
                              : 'border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                          }`}
                        >
                          {config?.allow_real_trading ? 'Conta REAL: Liberada' : 'Liberar negociação REAL'}
                        </button>
                        <button
                          type="button"
                          onClick={syncCTraderAccounts}
                          disabled={syncingAccounts}
                          className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 px-3.5 py-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-300 disabled:opacity-50"
                        >
                          {syncingAccounts ? 'Sincronizando...' : 'Sincronizar contas cTrader'}
                        </button>
                      </div>
                    </CardHeader>
                    <CardBody>
                      <form
                        onSubmit={saveCTraderAccount}
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
                            <option value="DEMO">Conta Demo cTrader (demo.ctraderapi.com)</option>
                            <option value="REAL">Conta Real cTrader (live.ctraderapi.com)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Nome de identificação
                          </label>
                          <input
                            type="text"
                            value={accLabel}
                            onChange={(e) => setAccLabel(e.target.value)}
                            placeholder="Ex: IC Markets Demo"
                            className={inputClass}
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            cTID Trader Account ID (opcional)
                          </label>
                          <input
                            type="text"
                            value={accCtidAccountId}
                            onChange={(e) => setAccCtidAccountId(e.target.value)}
                            placeholder="Ex: 12345678 (auto se vazio)"
                            className={`${inputClass} font-mono`}
                          />
                        </div>

                        {config?.ctrader_access_token_set && !useCustomCreds ? (
                          <div className="lg:col-span-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-4 py-2.5 text-xs">
                            <span className="text-emerald-700 dark:text-emerald-300">
                              Usando Client ID (<strong className="font-mono">{config.ctrader_client_id || '--'}</strong>) e Access Token salvos em <strong>Configuração cTrader</strong>.
                            </span>
                            <button
                              type="button"
                              onClick={() => setUseCustomCreds(true)}
                              className="text-slate-600 dark:text-slate-300 underline hover:text-blue-500"
                            >
                              Usar outro Access Token
                            </button>
                          </div>
                        ) : (
                          <div className="lg:col-span-3">
                            <div className="flex items-center justify-between mb-1">
                              <label className="block text-xs text-slate-500 dark:text-slate-400">
                                Access Token cTrader
                              </label>
                              {config?.ctrader_access_token_set && (
                                <button
                                  type="button"
                                  onClick={() => setUseCustomCreds(false)}
                                  className="text-[11px] text-blue-500 underline"
                                >
                                  Voltar a usar token padrão
                                </button>
                              )}
                            </div>
                            <input
                              type="password"
                              value={accToken}
                              onChange={(e) => setAccToken(e.target.value)}
                              placeholder="Cole o Access Token OAuth da cTrader"
                              className={`${inputClass} font-mono`}
                            />
                          </div>
                        )}
                        <div>
                          <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">
                            Volume padrão (Lotes)
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            value={accLotSize}
                            onChange={(e) => setAccLotSize(Number(e.target.value))}
                            className={`${inputClass} font-mono`}
                          />
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
                            <option value="CTRADER_CLOUD">cTrader Nuvem (Demo / Real)</option>
                            <option value="SIMULATION">Simulador Quant (CFD Lotes)</option>
                          </select>
                        </div>
                        <div className="lg:col-span-3 flex gap-2 pt-2">
                          <button
                            type="submit"
                            className="rounded-xl bg-blue-600 hover:bg-blue-500 px-5 py-2.5 text-xs font-semibold text-white"
                          >
                            Salvar conta e conectar na cTrader
                          </button>
                          {editingAccId && (
                            <button
                              type="button"
                              onClick={() => {
                                setEditingAccId('')
                                setAccLabel('')
                                setAccCtidAccountId('')
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
                    {config?.accounts?.map((a: CTraderAccount) => {
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
                                {a.trader_login || a.ctid_account_id || '---'}
                              </span>
                            </div>
                            <h3 className="mt-2 text-sm font-bold text-slate-900 dark:text-white">
                              {a.label}
                            </h3>
                            <p className="mt-1 text-xs font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                              Saldo: {a.currency || 'USD'} {formatNumber(a.balance ?? 0, 2)}
                            </p>
                            <p className="mt-0.5 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                              {a.broker_name || 'cTrader'} • Lote padrão: {formatNumber(a.default_lot_size, 2)}
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
                                  setAccCtidAccountId(a.ctid_account_id || '')
                                  setAccLotSize(a.default_lot_size || 0.01)
                                  setAccConnMode(a.connection_mode || 'CTRADER_CLOUD')
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

              {activeTab === 'templates' && (
                <ModelBuilderPanel
                  templates={templates}
                  indicators={indicatorsCatalog}
                  recipes={recipes}
                  bots={snapshot?.bots || config?.bots || []}
                  defaultPythonCode={defaultPythonCode}
                  symbols={symbols}
                  inputClass={inputClass}
                  onTemplatesUpdated={setTemplates}
                  onCreateBotWithTemplate={handleCreateBotWithTemplate}
                  onTestInBacktest={handleTestInBacktest}
                  showToast={showToast}
                />
              )}

              {activeTab === 'news' && !hasFeature('news_bot') && renderLockedFeatureCard('news_bot', 'Monitor e Robô de Notícias')}

              {activeTab === 'news' && hasFeature('news_bot') && (
                <NewsPanel
                  news={snapshot?.news}
                  bots={snapshot?.bots || config?.bots || []}
                  symbols={symbols}
                  isAdmin={isAdmin}
                  newsScanning={newsScanning}
                  calendarRefreshing={calendarRefreshing}
                  inputClass={inputClass}
                  onScanNews={scanNewsNow}
                  onRefreshCalendar={refreshCalendarNow}
                  onUpdateNewsConfig={updateNewsConfig}
                  onSaveFeed={saveNewsFeed}
                  onDeleteFeed={deleteNewsFeed}
                  onResetFeeds={resetNewsFeeds}
                  onLoadAllSymbols={() => refreshSymbols('TODOS')}
                />
              )}

              {activeTab === 'monitor' && !hasFeature('market_radar') && renderLockedFeatureCard('market_radar', 'Radar de Mercado (VWAP / Z-Score)')}

              {activeTab === 'monitor' && hasFeature('market_radar') && (
                <VwapMatrixPanel
                  symbolsData={snapshot?.symbols || {}}
                  activeSymbols={config?.active_symbols || []}
                  symbolCatalog={symbols}
                  bots={snapshot?.bots || []}
                  basketBias={snapshot?.basket_bias}
                  customCategories={config?.custom_categories || {}}
                  onUpdateActiveSymbols={updateMonitoredSymbols}
                  onOpenChart={(sym) => {
                    setChartSymbol(sym)
                    setActiveTab('running-bots')
                  }}
                  onCreateBotForSymbol={openCreateBotForSymbol}
                />
              )}

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
                            <th className="px-4 py-3 text-right">Lotes</th>
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
                                  <td className="px-4 py-2.5 font-sans">{formatTradeSide(d.side)}</td>
                                  <td className="px-4 py-2.5 text-right">{formatNumber(d.volume, 2)}</td>
                                  <td className="px-4 py-2.5 text-right">{formatPrice(d.price_open, 5)}</td>
                                  <td className="px-4 py-2.5 text-right">{formatPrice(d.price_close, 5)}</td>
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
                              <span className="shrink-0 rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] font-sans text-blue-600 dark:text-blue-300">
                                {formatLogModule(l.module)}
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

              {activeTab === 'settings' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Aparência (Tema Claro / Escuro)</CardTitle>
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
              {activeTab === 'admin' && isAdmin && (
                <AdminPanel
                  inputClass={inputClass}
                  showToast={showToast}
                  onPlansChanged={refreshMe}
                />
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

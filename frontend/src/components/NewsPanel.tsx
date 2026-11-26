import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  CalendarClock,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
  Globe,
  PauseCircle,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  TrendingDown,
  TrendingUp,
  XCircle,
} from 'lucide-react'
import { AIProviderCatalogItem, AnalystCardItem, BotItem, BrokerSymbol, NewsFeed, NewsSnapshot } from '../types'
import { formatSymbolDisplay } from '../utils/formatters'
import { formatNewsImpact } from '../utils/labels'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

interface NewsPanelProps {
  news?: NewsSnapshot
  bots: BotItem[]
  symbols: BrokerSymbol[]
  isAdmin: boolean
  newsScanning: boolean
  calendarRefreshing: boolean
  inputClass: string
  onScanNews: () => void
  onRefreshCalendar: () => void
  onUpdateNewsConfig: (updates: Record<string, unknown>) => Promise<void>
  onTestNewsAi: (payload: {
    provider: string
    model: string
    api_key?: string
    base_url?: string
  }) => Promise<{ ok: boolean; bias?: string; impact?: string; reason?: string; latency_ms?: number; error?: string }>
  onFetchNewsAiModels: (payload: {
    provider: string
    api_key?: string
    base_url?: string
  }) => Promise<{ ok: boolean; models: string[]; error?: string }>
  onSaveFeed: (payload: { feed_id?: string; source: string; url: string; default_symbol: string }) => Promise<boolean>
  onDeleteFeed: (feedId: string) => Promise<void>
  onResetFeeds: () => Promise<void>
  onLoadAllSymbols: () => Promise<void>
}

const FALLBACK_AI_PROVIDERS: AIProviderCatalogItem[] = [
  {
    id: 'gemini',
    name: 'Google Gemini',
    default_model: 'gemini-3.5-flash-lite',
    models: [
      'gemini-3.5-flash-lite',
      'gemini-3.1-flash-lite',
      'gemini-3-flash-preview',
      'gemini-3.8-flash',
      'gemini-3.5-flash',
      'gemini-3.1-pro-preview',
    ],
    needs_base_url: false,
    key_placeholder: 'AIza...',
  },
  {
    id: 'openai',
    name: 'OpenAI (ChatGPT)',
    default_model: 'gpt-4o-mini',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1', 'o4-mini'],
    needs_base_url: false,
    key_placeholder: 'sk-...',
  },
  {
    id: 'claude',
    name: 'Anthropic Claude',
    default_model: 'claude-3-5-haiku-latest',
    models: ['claude-3-5-haiku-latest', 'claude-3-5-sonnet-latest', 'claude-3-7-sonnet-latest', 'claude-sonnet-4-20250514'],
    needs_base_url: false,
    key_placeholder: 'sk-ant-...',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter (Todos os modelos)',
    default_model: 'meta-llama/llama-3.3-70b-instruct:free',
    models: [
      'meta-llama/llama-3.3-70b-instruct:free',
      'google/gemini-2.0-flash-exp:free',
      'deepseek/deepseek-chat-v3-0324:free',
      'google/gemini-2.0-flash-001',
      'openai/gpt-4o-mini',
      'anthropic/claude-3.5-haiku',
      'deepseek/deepseek-chat-v3-0324',
      'meta-llama/llama-3.3-70b-instruct',
      'qwen/qwen-2.5-72b-instruct',
    ],
    needs_base_url: false,
    key_placeholder: 'sk-or-v1-...',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    default_model: 'deepseek-chat',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    needs_base_url: false,
    key_placeholder: 'sk-...',
  },
  {
    id: 'groq',
    name: 'Groq (Ultra-rápido)',
    default_model: 'llama-3.3-70b-versatile',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'deepseek-r1-distill-llama-70b'],
    needs_base_url: false,
    key_placeholder: 'gsk_...',
  },
  {
    id: 'xai',
    name: 'xAI (Grok)',
    default_model: 'grok-3-mini',
    models: ['grok-3-mini', 'grok-3', 'grok-2-latest'],
    needs_base_url: false,
    key_placeholder: 'xai-...',
  },
  {
    id: 'custom',
    name: 'Outro Provedor (Compatível OpenAI)',
    default_model: 'gpt-4o-mini',
    models: [],
    needs_base_url: true,
    key_placeholder: 'Cole sua API Key',
  },
]

function formatLastTime(ts?: number): string {
  if (!ts || ts <= 0) return 'Ainda não executado'
  const d = new Date(ts * 1000)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function NewsPanel({
  news,
  bots,
  symbols,
  isAdmin,
  newsScanning,
  calendarRefreshing,
  inputClass,
  onScanNews,
  onRefreshCalendar,
  onUpdateNewsConfig,
  onTestNewsAi,
  onFetchNewsAiModels,
  onSaveFeed,
  onDeleteFeed,
  onResetFeeds,
  onLoadAllSymbols,
}: NewsPanelProps) {
  // News headline filters
  const [searchTerm, setSearchTerm] = useState('')
  const [filterSymbol, setFilterSymbol] = useState('ALL')
  const [filterImpact, setFilterImpact] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL')
  const [filterBias, setFilterBias] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL'>('ALL')
  const [onlyMacroUsd, setOnlyMacroUsd] = useState(false)
  const [onlyAi, setOnlyAi] = useState(false)

  // Economic calendar filters
  const [calOnlyHigh, setCalOnlyHigh] = useState(false)
  const [calScope, setCalScope] = useState<'UPCOMING' | 'TODAY' | 'WEEK'>('UPCOMING')
  const [calCurrency, setCalCurrency] = useState('ALL')

  // Admin feed form
  const [showCustomForm, setShowCustomForm] = useState(false)
  const [feedEditingId, setFeedEditingId] = useState('')
  const [feedSource, setFeedSource] = useState('')
  const [feedUrl, setFeedUrl] = useState('')
  const [feedSymbol, setFeedSymbol] = useState('ALL')

  // Per-subscriber BYOK AI config state
  const aiProviders = useMemo(
    () => (news?.ai_providers && news.ai_providers.length > 0 ? news.ai_providers : FALLBACK_AI_PROVIDERS),
    [news?.ai_providers],
  )
  const aiDirtyRef = useRef(false)
  const [aiEnabled, setAiEnabled] = useState<boolean>(Boolean(news?.ai_enabled))
  const [aiProvider, setAiProvider] = useState<string>(news?.ai_provider || 'gemini')
  const [aiModel, setAiModel] = useState<string>(news?.ai_model || 'gemini-3.5-flash-lite')
  const [aiCustomModelMode, setAiCustomModelMode] = useState<boolean>(false)
  const [aiBaseUrl, setAiBaseUrl] = useState<string>(news?.ai_base_url || '')
  const [aiApiKey, setAiApiKey] = useState<string>('')
  const [aiSaving, setAiSaving] = useState(false)
  const [aiTesting, setAiTesting] = useState(false)
  const [aiLoadingModels, setAiLoadingModels] = useState(false)
  const [dynamicModels, setDynamicModels] = useState<string[]>([])
  const [aiModelsNote, setAiModelsNote] = useState<string>('')
  const [showAiConfig, setShowAiConfig] = useState(false)
  const [aiTestResult, setAiTestResult] = useState<{
    ok: boolean
    bias?: string
    impact?: string
    reason?: string
    latency_ms?: number
    error?: string
  } | null>(null)

  const selectedProviderMeta = useMemo(
    () => aiProviders.find((p) => p.id === aiProvider) || aiProviders[0],
    [aiProviders, aiProvider],
  )
  const availableModels = useMemo(() => {
    const merged = [...(selectedProviderMeta?.models || [])]
    for (const m of dynamicModels) {
      if (m && !merged.includes(m)) merged.push(m)
    }
    return merged
  }, [selectedProviderMeta, dynamicModels])

  useEffect(() => {
    if (aiDirtyRef.current || !news) return
    const nextProv = news.ai_provider || 'gemini'
    const nextModel = news.ai_model || 'gemini-3.5-flash-lite'
    const meta = aiProviders.find((p) => p.id === nextProv)
    const knownModels = meta?.models || []
    setAiEnabled(Boolean(news.ai_enabled))
    setAiProvider(nextProv)
    setAiModel(nextModel)
    setAiBaseUrl(news.ai_base_url || '')
    setAiCustomModelMode(knownModels.length === 0 || (Boolean(nextModel) && !knownModels.includes(nextModel)))
  }, [news, aiProviders])

  const connectedBots = useMemo(() => bots.filter((b) => Boolean(b.news_assisted)), [bots])
  const feeds = useMemo(() => news?.feeds || [], [news])
  const feedStatusMap = useMemo(() => {
    const map: Record<string, { ok: boolean; count: number; error: string }> = {}
    for (const st of news?.feed_status || []) {
      if (st.feed_id) map[st.feed_id] = st
    }
    return map
  }, [news])

  const aiAnalyzedCount = useMemo(
    () => (news?.items || []).filter((it) => Boolean(it.analysis_source && it.analysis_source.startsWith('AI_'))).length,
    [news],
  )
  const analystCards = useMemo<AnalystCardItem[]>(() => {
    if (news?.analyst_cards && news.analyst_cards.length > 0) return news.analyst_cards
    return Object.values(news?.summary_by_symbol || {})
      .filter((s) => s.symbol !== 'ALL')
      .map((s) => ({
        symbol: s.symbol,
        action: s.bias === 'BULLISH' ? 'BUY' : s.bias === 'BEARISH' ? 'SELL' : 'NEUTRAL',
        action_label: s.bias === 'BULLISH' ? 'Viés de Compra' : s.bias === 'BEARISH' ? 'Viés de Venda' : 'Neutro • Técnico',
        confluence_state: s.bias === 'BULLISH' ? 'MACRO_BUY' : s.bias === 'BEARISH' ? 'MACRO_SELL' : 'NEUTRAL',
        confluence_label: 'Análise Macro',
        conviction: s.confidence ?? Math.min(90, Math.round(Math.abs(s.avg_score) * 70 + 20)),
        news_bias: s.bias,
        news_score: s.avg_score,
        news_confidence: s.confidence ?? 0,
        tech_bias: 'NEUTRAL',
        tech_signal: 'WAIT',
        price: 0,
        vwap: 0,
        zscore: 0,
        count: s.count,
        high_impact: s.high_impact,
        ai_count: s.ai_count ?? 0,
        bullish_count: s.bullish_count ?? 0,
        bearish_count: s.bearish_count ?? 0,
        neutral_count: s.neutral_count ?? 0,
        top_reason: s.top_reason || s.top_headline || 'Sem manchetes diretas recentes — acompanhando o gráfico.',
        top_headline: s.top_headline || '',
        robot_effect: 'Acompanhe o alinhamento entre notícias e gráfico antes de entrar.',
        bots_count: connectedBots.filter((b) => b.symbol === s.symbol).length,
        shield_active: false,
        next_event: null,
      }))
  }, [news?.analyst_cards, news?.summary_by_symbol, connectedBots])
  const globalMacro = news?.summary_by_symbol?.ALL

  const filteredItems = useMemo(() => {
    const q = searchTerm.trim().toLowerCase()
    return (news?.items || []).filter((it) => {
      if (filterSymbol !== 'ALL' && it.symbol !== filterSymbol) return false
      if (filterImpact !== 'ALL' && it.impact !== filterImpact) return false
      if (filterBias !== 'ALL' && it.bias !== filterBias) return false
      if (onlyMacroUsd && !it.is_macro_usd) return false
      if (onlyAi && !(it.analysis_source && it.analysis_source.startsWith('AI_'))) return false
      if (q && !it.title.toLowerCase().includes(q) && !it.source.toLowerCase().includes(q)) return false
      return true
    })
  }, [news, searchTerm, filterSymbol, filterImpact, filterBias, onlyMacroUsd, onlyAi])

  const calendar = news?.calendar
  const calendarCurrencies = useMemo(() => {
    const s = new Set<string>(['USD', 'EUR', 'GBP', 'JPY'])
    for (const ev of calendar?.events || []) {
      if (ev.currency) s.add(ev.currency)
    }
    return Array.from(s)
  }, [calendar])

  const filteredCalendarEvents = useMemo(() => {
    const now = new Date()
    const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
    const endToday = startToday + 86400
    return (calendar?.events || []).filter((ev) => {
      if (calOnlyHigh && ev.impact !== 'HIGH') return false
      if (calScope === 'UPCOMING' && !ev.is_upcoming) return false
      if (calScope === 'TODAY' && (ev.timestamp < startToday || ev.timestamp >= endToday)) return false
      if (calCurrency !== 'ALL' && ev.currency !== calCurrency) return false
      return true
    })
  }, [calendar, calOnlyHigh, calScope, calCurrency])

  const availableNewsSymbols = useMemo(() => {
    const set = new Set<string>(Object.keys(news?.summary_by_symbol || {}))
    for (const it of news?.items || []) {
      if (it.symbol) set.add(it.symbol)
    }
    return Array.from(set).sort()
  }, [news])

  async function handleSubmitCustomFeed(e: FormEvent) {
    e.preventDefault()
    if (!feedUrl.trim()) return
    const ok = await onSaveFeed({
      feed_id: feedEditingId || undefined,
      source: feedSource.trim() || 'Fonte Personalizada',
      url: feedUrl.trim(),
      default_symbol: feedSymbol || 'ALL',
    })
    if (ok) {
      setFeedEditingId('')
      setFeedSource('')
      setFeedUrl('')
      setFeedSymbol('ALL')
      setShowCustomForm(false)
    }
  }

  function handleProviderChange(nextProv: string) {
    aiDirtyRef.current = true
    setAiTestResult(null)
    setAiModelsNote('')
    setDynamicModels([])
    setAiProvider(nextProv)
    const meta = aiProviders.find((p) => p.id === nextProv)
    const defModel = meta?.default_model || 'gpt-4o-mini'
    setAiModel(defModel)
    setAiCustomModelMode((meta?.models || []).length === 0)
  }

  async function handleSaveAiConfig(e: FormEvent) {
    e.preventDefault()
    setAiSaving(true)
    setAiTestResult(null)
    try {
      const payload: Record<string, unknown> = {
        news_ai_enabled: aiEnabled,
        news_ai_provider: aiProvider,
        news_ai_model: aiModel.trim() || selectedProviderMeta?.default_model || 'gemini-3.5-flash-lite',
        news_ai_base_url: aiBaseUrl.trim(),
      }
      if (aiApiKey.trim()) {
        payload.news_ai_api_key = aiApiKey.trim()
      }
      await onUpdateNewsConfig(payload)
      setAiApiKey('')
      aiDirtyRef.current = false
      if (aiEnabled) {
        onScanNews()
      }
    } finally {
      setAiSaving(false)
    }
  }

  async function handleClearAiKey() {
    setAiSaving(true)
    setAiTestResult(null)
    try {
      await onUpdateNewsConfig({ clear_news_ai_api_key: true, news_ai_enabled: false })
      setAiApiKey('')
      setAiEnabled(false)
      aiDirtyRef.current = false
    } finally {
      setAiSaving(false)
    }
  }

  async function handleTestAiConnection() {
    setAiTesting(true)
    setAiTestResult(null)
    try {
      const res = await onTestNewsAi({
        provider: aiProvider,
        model: aiModel.trim() || selectedProviderMeta?.default_model || 'gemini-3.5-flash-lite',
        api_key: aiApiKey.trim() || undefined,
        base_url: aiBaseUrl.trim() || undefined,
      })
      setAiTestResult(res)
    } finally {
      setAiTesting(false)
    }
  }

  async function handleLoadProviderModels() {
    setAiLoadingModels(true)
    setAiModelsNote('')
    setAiTestResult(null)
    try {
      const res = await onFetchNewsAiModels({
        provider: aiProvider,
        api_key: aiApiKey.trim() || undefined,
        base_url: aiBaseUrl.trim() || undefined,
      })
      if (res.ok && res.models.length > 0) {
        setDynamicModels(res.models)
        setAiModelsNote(`${res.models.length} modelo(s) carregado(s) da API.`)
      } else {
        setAiTestResult({
          ok: false,
          error: res.error || 'Nenhum modelo retornado pela API para esta chave.',
        })
      }
    } finally {
      setAiLoadingModels(false)
    }
  }

  function startEditFeed(f: NewsFeed) {
    setFeedEditingId(f.feed_id)
    setFeedSource(f.source)
    setFeedUrl(f.url)
    setFeedSymbol(f.default_symbol || 'ALL')
    setShowCustomForm(true)
  }

  return (
    <div className="space-y-6">
      {/* 1. MESA DO ANALISTA DE NOTÍCIAS IA (Cards de Confluência por Ativo + Config Recolhível) */}
      <Card className="overflow-hidden border-violet-500/30">
        <CardHeader className="bg-gradient-to-r from-violet-500/10 via-blue-500/5 to-transparent flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-violet-500/15 text-violet-500">
                <Sparkles className="h-4 w-4" />
              </span>
              Mesa do Analista de Notícias IA
            </CardTitle>
            <CardDescription>
              Confluência em tempo real: leitura semântica das notícias cruzada com o fluxo técnico (VWAP) e Calendário 3★ para orientar operador e robôs
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {aiAnalyzedCount > 0 && (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                {aiAnalyzedCount} de {news?.items?.length || 0} lidas por IA
              </span>
            )}
            <span
              className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
                news?.ai_active
                  ? 'border border-violet-500/30 bg-violet-500/15 text-violet-700 dark:text-violet-300'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
              }`}
            >
              {news?.ai_active
                ? `IA Ativa • ${(news?.ai_provider || 'gemini').toUpperCase()} (${news?.ai_model || ''})`
                : 'Regras Locais Gratuitas'}
            </span>
            <button
              type="button"
              onClick={() => setShowAiConfig((v) => !v)}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                showAiConfig
                  ? 'border-violet-500 bg-violet-600 text-white'
                  : 'border-violet-500/35 bg-violet-500/10 text-violet-700 dark:text-violet-300 hover:bg-violet-500/20'
              }`}
            >
              <Settings2 className="h-3.5 w-3.5" />
              {showAiConfig ? 'Fechar Config IA' : 'Configurar IA'}
            </button>
            <button
              type="button"
              onClick={onScanNews}
              disabled={newsScanning}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${newsScanning ? 'animate-spin' : ''}`} />
              {newsScanning ? 'Analisando...' : 'Atualizar Análise'}
            </button>
          </div>
        </CardHeader>

        <CardBody className="space-y-5">
          {!news?.ai_active && !showAiConfig && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-violet-500/25 bg-violet-500/5 px-4 py-2.5 text-xs">
              <span className="text-slate-700 dark:text-slate-300">
                Conecte sua própria API Key (<strong>Gemini, ChatGPT, Claude, OpenRouter, Groq</strong>…) para trocar as regras locais pela leitura inteligente de contexto por IA.
              </span>
              <button
                type="button"
                onClick={() => setShowAiConfig(true)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 px-3 py-1.5 text-[11px] font-semibold text-white shrink-0"
              >
                <Sparkles className="h-3 w-3" />
                Conectar minha IA
              </button>
            </div>
          )}

          {showAiConfig && (
            <form
              onSubmit={handleSaveAiConfig}
              className="space-y-4 rounded-2xl border border-violet-500/30 bg-slate-50/70 dark:bg-slate-950/50 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-900 dark:text-white">
                  Configuração da Sua API Key de IA
                </span>
                <button
                  type="button"
                  onClick={() => {
                    aiDirtyRef.current = true
                    setAiEnabled((v) => !v)
                  }}
                  className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold transition ${
                    aiEnabled
                      ? 'border-violet-500 bg-violet-600 text-white'
                      : 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300'
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${aiEnabled ? 'bg-emerald-300' : 'bg-slate-400'}`} />
                  {aiEnabled ? 'IA Ligada' : 'IA Desligada'}
                </button>
              </div>

              <div>
                <span className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                  1. Escolha o provedor de IA
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {aiProviders.map((p) => {
                    const selected = aiProvider === p.id
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => handleProviderChange(p.id)}
                        className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left text-xs font-semibold transition ${
                          selected
                            ? 'border-violet-500 bg-violet-500/15 text-violet-800 dark:text-violet-200 ring-1 ring-violet-500/40'
                            : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-700'
                        }`}
                      >
                        <span className="truncate">{p.name}</span>
                        {selected && <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-violet-500" />}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300">
                      2. Modelo
                    </label>
                    <button
                      type="button"
                      onClick={handleLoadProviderModels}
                      disabled={aiLoadingModels || (!aiApiKey.trim() && !news?.ai_api_key_set)}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-violet-600 dark:text-violet-300 hover:underline disabled:opacity-40"
                    >
                      <RefreshCw className={`h-3 w-3 ${aiLoadingModels ? 'animate-spin' : ''}`} />
                      {aiLoadingModels ? 'Buscando...' : 'Carregar modelos da minha API'}
                    </button>
                  </div>
                  {availableModels.length > 0 && (
                    <select
                      value={aiCustomModelMode ? '__CUSTOM__' : aiModel}
                      onChange={(e) => {
                        aiDirtyRef.current = true
                        const v = e.target.value
                        if (v === '__CUSTOM__') {
                          setAiCustomModelMode(true)
                        } else {
                          setAiCustomModelMode(false)
                          setAiModel(v)
                        }
                      }}
                      className={inputClass}
                    >
                      {availableModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                      <option value="__CUSTOM__">Outro modelo (digitar ID manualmente)</option>
                    </select>
                  )}
                  {(aiCustomModelMode || availableModels.length === 0) && (
                    <input
                      type="text"
                      value={aiModel}
                      onChange={(e) => {
                        aiDirtyRef.current = true
                        setAiModel(e.target.value)
                      }}
                      placeholder={selectedProviderMeta?.default_model || 'Ex: meta-llama/llama-3.3-70b-instruct:free'}
                      className={`${inputClass} font-mono ${availableModels.length > 0 ? 'mt-1.5' : ''}`}
                      required
                    />
                  )}
                  {aiModelsNote && (
                    <span className="mt-1 block text-[11px] text-emerald-600 dark:text-emerald-400">
                      {aiModelsNote}
                    </span>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300">
                      3. Sua API Key
                    </label>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          news?.ai_api_key_set
                            ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                            : 'bg-slate-200 dark:bg-slate-800 text-slate-500'
                        }`}
                      >
                        {news?.ai_api_key_set ? 'Chave salva' : 'Não configurada'}
                      </span>
                      {news?.ai_api_key_set && (
                        <button
                          type="button"
                          onClick={handleClearAiKey}
                          disabled={aiSaving}
                          className="inline-flex items-center gap-1 text-[11px] text-rose-600 dark:text-rose-400 hover:underline"
                        >
                          <Trash2 className="h-3 w-3" />
                          Remover
                        </button>
                      )}
                    </div>
                  </div>
                  <input
                    type="password"
                    value={aiApiKey}
                    onChange={(e) => {
                      aiDirtyRef.current = true
                      setAiApiKey(e.target.value)
                    }}
                    placeholder={
                      news?.ai_api_key_set
                        ? 'Chave salva e protegida (cole outra só para trocar)'
                        : selectedProviderMeta?.key_placeholder || 'Cole sua API Key aqui'
                    }
                    className={`${inputClass} font-mono`}
                  />
                </div>
              </div>

              {selectedProviderMeta?.needs_base_url && (
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1">
                    URL Base da API (Compatível com OpenAI /chat/completions)
                  </label>
                  <input
                    type="url"
                    value={aiBaseUrl}
                    onChange={(e) => {
                      aiDirtyRef.current = true
                      setAiBaseUrl(e.target.value)
                    }}
                    placeholder="https://api.mistral.ai/v1/chat/completions"
                    className={`${inputClass} font-mono`}
                    required
                  />
                </div>
              )}

              {aiTestResult && (
                <div
                  className={`rounded-xl border px-3.5 py-2.5 text-xs ${
                    aiTestResult.ok
                      ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                      : 'border-rose-500/35 bg-rose-500/10 text-rose-800 dark:text-rose-200'
                  }`}
                >
                  {aiTestResult.ok ? (
                    <div>
                      <strong>Conexão validada ({aiTestResult.latency_ms}ms)!</strong> Teste em manchete macro:{' '}
                      <span className="font-mono font-bold">{aiTestResult.bias}</span> ({aiTestResult.impact}) —{' '}
                      {aiTestResult.reason}
                    </div>
                  ) : (
                    <div>
                      <strong>Não foi possível conectar:</strong> {aiTestResult.error}
                    </div>
                  )}
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <span className="text-[11px] text-slate-500 dark:text-slate-400">
                  Sua chave fica salva exclusivamente na sua conta. Se o provedor oscilar, as regras locais assumem automaticamente.
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleTestAiConnection}
                    disabled={aiTesting || (!aiApiKey.trim() && !news?.ai_api_key_set)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-violet-500/35 bg-violet-500/10 hover:bg-violet-500/20 px-4 py-2 text-xs font-semibold text-violet-700 dark:text-violet-300 disabled:opacity-50"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {aiTesting ? 'Testando...' : 'Testar Conexão com IA'}
                  </button>
                  <button
                    type="submit"
                    disabled={aiSaving}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {aiSaving ? 'Salvando...' : 'Salvar e Aplicar IA'}
                  </button>
                </div>
              </div>
            </form>
          )}

          {globalMacro && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/50 px-4 py-2.5 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <Globe className="h-4 w-4 shrink-0 text-blue-500" />
                <span className="font-bold text-slate-800 dark:text-slate-100 shrink-0">Panorama Macro Global:</span>
                <span
                  className={`rounded-md px-2 py-0.5 text-[10px] font-bold shrink-0 ${
                    globalMacro.bias === 'BULLISH'
                      ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                      : globalMacro.bias === 'BEARISH'
                      ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                      : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                  }`}
                >
                  {globalMacro.bias === 'BULLISH' ? 'OTIMISTA (ALTA)' : globalMacro.bias === 'BEARISH' ? 'CAUTELA (BAIXA)' : 'NEUTRO'} •{' '}
                  {globalMacro.avg_score > 0 ? `+${globalMacro.avg_score.toFixed(2)}` : globalMacro.avg_score.toFixed(2)}
                </span>
                {globalMacro.top_reason && (
                  <span className="truncate text-slate-600 dark:text-slate-400">{globalMacro.top_reason}</span>
                )}
              </div>
              <span className="text-[11px] font-mono text-slate-500 shrink-0">
                {globalMacro.count} manchete(s) gerais
              </span>
            </div>
          )}

          {/* Cards das Moedas / Ativos — Decisão Clara para Operador e Robô */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {analystCards.map((card) => {
              const isBuy = card.action === 'STRONG_BUY' || card.action === 'BUY'
              const isSell = card.action === 'STRONG_SELL' || card.action === 'SELL'
              const isShield = card.action === 'PAUSE_SHIELD'
              const isConflict = card.action === 'WAIT_CONFLICT'
              const borderCls = isShield
                ? 'border-amber-500/45 bg-amber-500/[0.04]'
                : card.confluence_state === 'ALIGNED_BUY'
                ? 'border-emerald-500/45 bg-emerald-500/[0.04]'
                : card.confluence_state === 'ALIGNED_SELL'
                ? 'border-rose-500/45 bg-rose-500/[0.04]'
                : isConflict
                ? 'border-amber-500/35 bg-amber-500/[0.03]'
                : 'border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40'
              const badgeCls = isShield
                ? 'bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/35'
                : isBuy
                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30'
                : isSell
                ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30'
                : isConflict
                ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30'
                : 'bg-slate-200/80 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
              const barCls = isShield
                ? 'bg-amber-500'
                : isBuy
                ? 'bg-emerald-500'
                : isSell
                ? 'bg-rose-500'
                : isConflict
                ? 'bg-amber-500'
                : 'bg-slate-400'
              const isSelectedFilter = filterSymbol === card.symbol
              return (
                <div
                  key={card.symbol}
                  onClick={() => setFilterSymbol((prev) => (prev === card.symbol ? 'ALL' : card.symbol))}
                  className={`cursor-pointer rounded-2xl border p-4 transition space-y-3 ${borderCls} ${
                    isSelectedFilter ? 'ring-2 ring-blue-500' : 'hover:border-slate-400 dark:hover:border-slate-600'
                  }`}
                >
                  {/* Cabeçalho do Card: Ativo + Preço + Veredito */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-900 dark:text-white truncate">
                          {formatSymbolDisplay(card.symbol, symbols)}
                        </span>
                        {card.ai_count > 0 && (
                          <span className="rounded bg-violet-500/20 px-1.5 py-0.5 text-[10px] font-bold text-violet-700 dark:text-violet-300 shrink-0">
                            IA
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 flex items-center gap-2 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <span>{card.symbol}</span>
                        {card.price > 0 && <span>• {card.price}</span>}
                        {card.bots_count > 0 && (
                          <span className="rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] font-sans font-semibold text-blue-700 dark:text-blue-300">
                            {card.bots_count} robô(s)
                          </span>
                        )}
                      </div>
                    </div>
                    <span className={`inline-flex items-center gap-1 rounded-xl px-2.5 py-1 text-[11px] font-bold shrink-0 ${badgeCls}`}>
                      {isShield ? (
                        <PauseCircle className="h-3.5 w-3.5" />
                      ) : isBuy ? (
                        <TrendingUp className="h-3.5 w-3.5" />
                      ) : isSell ? (
                        <TrendingDown className="h-3.5 w-3.5" />
                      ) : (
                        <ShieldAlert className="h-3.5 w-3.5" />
                      )}
                      {card.action_label}
                    </span>
                  </div>

                  {/* Barra de Peso / Força para Decisão */}
                  <div>
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="font-medium text-slate-600 dark:text-slate-300">{card.confluence_label}</span>
                      <span className="font-mono font-bold text-slate-900 dark:text-white">
                        Peso {card.conviction}%
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${barCls}`}
                        style={{ width: `${Math.max(4, Math.min(100, card.conviction))}%` }}
                      />
                    </div>
                  </div>

                  {/* Comparação Lado a Lado: Notícias IA vs Fluxo Técnico */}
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white/60 dark:bg-slate-900/50 px-2.5 py-2">
                      <span className="block text-[10px] uppercase text-slate-400">Notícias / IA</span>
                      <div className="mt-0.5 flex items-center justify-between font-semibold">
                        <span
                          className={
                            card.news_bias === 'BULLISH'
                              ? 'text-emerald-600 dark:text-emerald-300'
                              : card.news_bias === 'BEARISH'
                              ? 'text-rose-600 dark:text-rose-300'
                              : 'text-slate-500'
                          }
                        >
                          {card.news_bias === 'BULLISH' ? 'ALTA' : card.news_bias === 'BEARISH' ? 'BAIXA' : 'NEUTRO'}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          {card.news_score > 0 ? `+${card.news_score.toFixed(2)}` : card.news_score.toFixed(2)}
                        </span>
                      </div>
                      <span className="block text-[10px] text-slate-400 mt-0.5">
                        {card.count} notícia(s) ({card.bullish_count}↑ / {card.bearish_count}↓)
                      </span>
                    </div>

                    <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white/60 dark:bg-slate-900/50 px-2.5 py-2">
                      <span className="block text-[10px] uppercase text-slate-400">Gráfico (VWAP)</span>
                      <div className="mt-0.5 flex items-center justify-between font-semibold">
                        <span
                          className={
                            card.tech_bias === 'BULLISH'
                              ? 'text-emerald-600 dark:text-emerald-300'
                              : card.tech_bias === 'BEARISH'
                              ? 'text-rose-600 dark:text-rose-300'
                              : 'text-slate-500'
                          }
                        >
                          {card.tech_bias === 'BULLISH' ? 'COMPRA' : card.tech_bias === 'BEARISH' ? 'VENDA' : 'NEUTRO'}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          Z {card.zscore >= 0 ? `+${card.zscore.toFixed(1)}` : card.zscore.toFixed(1)}
                        </span>
                      </div>
                      <span className="block text-[10px] font-mono text-slate-400 mt-0.5 truncate">
                        Sinal: {card.tech_signal}
                      </span>
                    </div>
                  </div>

                  {/* Tese resumida da IA */}
                  <p className="text-xs text-slate-700 dark:text-slate-200 leading-relaxed line-clamp-2">
                    “{card.top_reason}”
                  </p>

                  {/* Rodapé: Impacto direto no Robô + Próximo Evento 3★ */}
                  <div className="rounded-xl border border-slate-200/70 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 px-3 py-2 text-[11px] flex items-start gap-2">
                    <Bot className="h-3.5 w-3.5 shrink-0 mt-0.5 text-blue-500" />
                    <div className="min-w-0 flex-1">
                      <span className="block text-slate-700 dark:text-slate-200 font-medium">{card.robot_effect}</span>
                      {card.next_event && (
                        <span className="block text-[10px] text-amber-600 dark:text-amber-300 mt-0.5">
                          Próximo 3★: {card.next_event.currency} • {card.next_event.title} ({card.next_event.countdown})
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </CardBody>
      </Card>

      {/* 2. Controles do Motor de Notícias & Proteção Macro */}
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-blue-500" />
              Controles do Robô &amp; Proteção Macro
            </CardTitle>
            <CardDescription>
              Regras de segurança aplicadas automaticamente nos robôs que utilizam Técnica + Notícias
            </CardDescription>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 px-3 py-2 text-[11px] font-mono text-slate-500 dark:text-slate-400">
            <Clock className="h-3.5 w-3.5" />
            Última busca: {formatLastTime(news?.last_scan_at)}
          </span>
        </CardHeader>

        <CardBody className="space-y-4">
          {news?.last_error && (news?.items?.length || 0) === 0 && (
            <div className="flex items-start gap-2.5 rounded-xl border border-rose-500/35 bg-rose-500/10 px-4 py-3 text-xs text-rose-700 dark:text-rose-300">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <strong className="block">Não foi possível ler as fontes de notícias:</strong>
                <span className="font-mono text-[11px]">{news.last_error}</span>
              </div>
            </div>
          )}

          {(calendar?.active_shield_events?.length || 0) > 0 && (news?.calendar_shield_enabled ?? true) && (
            <div className="flex items-start gap-2.5 rounded-xl border border-amber-500/40 bg-amber-500/15 px-4 py-3 text-xs text-amber-800 dark:text-amber-200">
              <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <strong className="block">
                  Escudo do Calendário 3★ ATIVO AGORA — novas entradas pausadas nos pares afetados:
                </strong>
                <span>
                  {calendar?.active_shield_events?.map((ev) => `${ev.currency} (${ev.title})`).join(' • ')}
                </span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => onUpdateNewsConfig({ news_bot_enabled: !(news?.enabled ?? false) })}
              className={`rounded-xl border px-4 py-3 text-left transition ${
                news?.enabled
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 text-slate-600 dark:text-slate-300'
              }`}
            >
              <div className="text-xs font-bold flex items-center justify-between">
                <span>Monitoramento Automático</span>
                <span className="rounded px-1.5 py-0.5 text-[10px] font-mono bg-white/60 dark:bg-slate-900/60">
                  {news?.enabled ? 'ATIVO' : 'PAUSADO'}
                </span>
              </div>
              <div className="text-[11px] opacity-80 mt-1">
                Busca contínua nas fontes oficiais ({news?.ai_active ? `IA ${(news?.ai_provider || 'GEMINI').toUpperCase()} ativa` : 'Regras Locais PT/EN + Dólar Inverso'})
              </div>
            </button>

            <div
              className={`rounded-xl border px-4 py-3 flex flex-col justify-between gap-2 ${
                news?.calendar_shield_enabled ?? true
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 text-slate-600 dark:text-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() =>
                    onUpdateNewsConfig({ news_calendar_shield_enabled: !(news?.calendar_shield_enabled ?? true) })
                  }
                  className="text-xs font-bold inline-flex items-center gap-1.5 text-left"
                >
                  <ShieldAlert className="h-3.5 w-3.5" />
                  Escudo Calendário 3★: {(news?.calendar_shield_enabled ?? true) ? 'LIGADO' : 'DESLIGADO'}
                </button>
                <select
                  value={news?.calendar_pause_minutes ?? 15}
                  onChange={(e) => onUpdateNewsConfig({ news_calendar_pause_minutes: Number(e.target.value) || 15 })}
                  className="rounded-md border border-amber-500/30 bg-white dark:bg-slate-900 px-2 py-0.5 text-[11px] font-mono text-slate-800 dark:text-slate-100"
                >
                  <option value={10}>±10 min</option>
                  <option value={15}>±15 min</option>
                  <option value={30}>±30 min</option>
                </select>
              </div>
              <div className="text-[11px] opacity-85">
                Trava todos os robôs automaticamente antes e depois de eventos 3★ da moeda do ativo
              </div>
            </div>

            <button
              type="button"
              onClick={() => onUpdateNewsConfig({ news_filter_only: !(news?.news_filter_only ?? true) })}
              className={`rounded-xl border px-4 py-3 text-left transition ${
                news?.news_filter_only ?? true
                  ? 'border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-300'
                  : 'border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-300'
              }`}
            >
              <div className="text-xs font-bold flex items-center justify-between">
                <span>Modo: {(news?.news_filter_only ?? true) ? 'Filtro Puro (Seguro)' : 'Híbrido (Agressivo)'}</span>
                <span className="rounded px-1.5 py-0.5 text-[10px] font-mono bg-white/60 dark:bg-slate-900/60">
                  {(news?.news_filter_only ?? true) ? 'FILTRO' : 'HÍBRIDO'}
                </span>
              </div>
              <div className="text-[11px] opacity-80 mt-1">
                {(news?.news_filter_only ?? true)
                  ? 'Só entra com sinal técnico confirmado e bloqueia entradas contra a notícia'
                  : 'Permite abrir ordens extras a favor da manchete mesmo sem sinal técnico'}
              </div>
            </button>

            <button
              type="button"
              onClick={() =>
                onUpdateNewsConfig({ news_pause_grid_on_high_impact: !(news?.pause_grid_on_high_impact ?? false) })
              }
              className={`rounded-xl border px-4 py-3 text-left transition ${
                news?.pause_grid_on_high_impact
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300'
                  : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 text-slate-600 dark:text-slate-300'
              }`}
            >
              <div className="text-xs font-bold flex items-center justify-between">
                <span>Pausar Grid em Manchetes</span>
                <span className="rounded px-1.5 py-0.5 text-[10px] font-mono bg-white/60 dark:bg-slate-900/60">
                  {news?.pause_grid_on_high_impact ? 'LIGADO' : 'DESLIGADO'}
                </span>
              </div>
              <div className="text-[11px] opacity-80 mt-1">
                Pausa robôs de Grid quando surgir manchete de alto impacto
              </div>
            </button>

            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 px-4 py-3 flex flex-col justify-between">
              <label className="text-xs font-bold text-slate-800 dark:text-slate-200">
                Frequência de Atualização
              </label>
              <select
                value={news?.poll_interval_sec ?? 90}
                onChange={(e) => onUpdateNewsConfig({ news_poll_interval_sec: Number(e.target.value) || 90 })}
                className="mt-1.5 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs font-mono"
              >
                <option value={60}>A cada 60 segundos</option>
                <option value={90}>A cada 90 segundos (Padrão)</option>
                <option value={180}>A cada 3 minutos</option>
                <option value={300}>A cada 5 minutos</option>
              </select>
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 px-4 py-3 flex flex-col justify-between">
              <div className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                <Bot className="h-3.5 w-3.5 text-blue-500" />
                Robôs Usando Notícias ({connectedBots.length})
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 truncate">
                {connectedBots.length === 0
                  ? 'Nenhum robô com Técnica + Notícias ativo.'
                  : connectedBots.map((b) => `${b.name} (${b.symbol})`).join(', ')}
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* 2. Opção 3: Calendário Econômico da Semana */}
      <Card className="overflow-hidden">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-amber-500" />
              Calendário Econômico da Semana
            </CardTitle>
            <CardDescription>
              Agenda de eventos macroeconômicos (Payroll, FED, CPI, BCE, Juros) com contagem regressiva automática
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {calendar?.next_high_impact && (
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/35 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300">
                <ShieldAlert className="h-3.5 w-3.5" />
                Próximo 3★: {calendar.next_high_impact.currency} • {calendar.next_high_impact.title} ({calendar.next_high_impact.countdown})
              </span>
            )}
            <button
              type="button"
              onClick={onRefreshCalendar}
              disabled={calendarRefreshing}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${calendarRefreshing ? 'animate-spin' : ''}`} />
              {calendarRefreshing ? 'Atualizando...' : 'Atualizar Agenda'}
            </button>
          </div>
        </CardHeader>
        <CardBody className="space-y-3">
          {calendar?.last_error && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
              {calendar.last_error}
            </div>
          )}
          {!calendar?.last_error && calendar?.status_note && (
            <div className="rounded-xl border border-sky-500/25 bg-sky-500/10 px-3 py-2 text-xs text-sky-700 dark:text-sky-300">
              {calendar.status_note}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select
              value={calCurrency}
              onChange={(e) => setCalCurrency(e.target.value)}
              className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs font-mono"
            >
              <option value="ALL">Todas as moedas</option>
              {calendarCurrencies.map((cur) => (
                <option key={cur} value={cur}>
                  {cur}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setCalOnlyHigh((v) => !v)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                calOnlyHigh
                  ? 'border-amber-500/40 bg-amber-500/15 text-amber-700 dark:text-amber-300'
                  : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300'
              }`}
            >
              Só Alto Impacto (3★)
            </button>
            <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
              {(
                [
                  ['UPCOMING', 'Próximos'],
                  ['TODAY', 'Hoje'],
                  ['WEEK', 'Toda a semana'],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setCalScope(key)}
                  className={`px-3 py-1.5 text-xs font-semibold transition ${
                    calScope === key
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {calendar?.last_fetch_at ? (
              <span className="ml-auto text-[11px] font-mono text-slate-400">
                Sincronizado: {formatLastTime(calendar.last_fetch_at)}
              </span>
            ) : null}
          </div>

          <div className="overflow-x-auto max-h-72 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-950/90 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-3 py-2">Data / Hora</th>
                  <th className="px-3 py-2">Contagem</th>
                  <th className="px-3 py-2">Moeda</th>
                  <th className="px-3 py-2">Impacto</th>
                  <th className="px-3 py-2">Evento</th>
                  <th className="px-3 py-2 text-right">Previsão</th>
                  <th className="px-3 py-2 text-right">Anterior</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredCalendarEvents.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                      Nenhum evento encontrado com os filtros atuais. Clique em <strong>Atualizar Agenda</strong> para carregar os eventos da semana.
                    </td>
                  </tr>
                ) : (
                  filteredCalendarEvents.slice(0, 40).map((ev) => (
                    <tr key={ev.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                      <td className="px-3 py-2 font-mono text-slate-500 whitespace-nowrap">{ev.time_str || '--'}</td>
                      <td className="px-3 py-2 font-mono whitespace-nowrap">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                            ev.is_upcoming
                              ? 'bg-sky-500/15 text-sky-700 dark:text-sky-300'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                          }`}
                        >
                          {ev.countdown}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono font-bold">{ev.currency}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                            ev.impact === 'HIGH'
                              ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                              : ev.impact === 'MEDIUM'
                              ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                          }`}
                        >
                          {ev.impact === 'HIGH' ? 'Alto (3★)' : ev.impact === 'MEDIUM' ? 'Médio (2★)' : ev.impact === 'HOLIDAY' ? 'Feriado' : 'Baixo'}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-medium text-slate-900 dark:text-slate-100">{ev.title}</td>
                      <td className="px-3 py-2 text-right font-mono text-slate-600 dark:text-slate-300">{ev.forecast || '--'}</td>
                      <td className="px-3 py-2 text-right font-mono text-slate-500">{ev.previous || '--'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      {/* 3. Manchetes Financeiras com Filtros (Opção 1) */}
      <Card className="overflow-hidden">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>Manchetes Financeiras Monitoradas ({filteredItems.length} de {news?.items?.length || 0})</CardTitle>
            <CardDescription>
              Classificadas automaticamente em Português e Inglês por impacto, viés e evento macroeconômico dos EUA
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Buscar manchete..."
                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 pl-8 pr-2.5 py-1.5 text-xs"
              />
            </div>
            <select
              value={filterSymbol}
              onChange={(e) => setFilterSymbol(e.target.value)}
              className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs font-mono"
            >
              <option value="ALL">Todos ativos</option>
              {availableNewsSymbols.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
            <select
              value={filterImpact}
              onChange={(e) => setFilterImpact(e.target.value as 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW')}
              className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs"
            >
              <option value="ALL">Todos impactos</option>
              <option value="HIGH">Alto impacto</option>
              <option value="MEDIUM">Médio impacto</option>
              <option value="LOW">Baixo impacto</option>
            </select>
            <select
              value={filterBias}
              onChange={(e) => setFilterBias(e.target.value as 'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL')}
              className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs"
            >
              <option value="ALL">Todo viés</option>
              <option value="BULLISH">Alta</option>
              <option value="BEARISH">Baixa</option>
              <option value="NEUTRAL">Neutro</option>
            </select>
            <button
              type="button"
              onClick={() => setOnlyMacroUsd((v) => !v)}
              className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${
                onlyMacroUsd
                  ? 'border-amber-500/40 bg-amber-500/15 text-amber-700 dark:text-amber-300'
                  : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300'
              }`}
            >
              <Filter className="h-3 w-3" />
              Macro USD
            </button>
            <button
              type="button"
              onClick={() => setOnlyAi((v) => !v)}
              className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${
                onlyAi
                  ? 'border-violet-500/40 bg-violet-500/15 text-violet-700 dark:text-violet-300'
                  : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300'
              }`}
            >
              <Sparkles className="h-3 w-3" />
              Só IA ({aiAnalyzedCount})
            </button>
          </div>
        </CardHeader>
        <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
          {filteredItems.length === 0 ? (
            <div className="px-5 py-8 text-center text-xs text-slate-500">
              Nenhuma manchete encontrada para os filtros selecionados. Clique em <strong>Pesquisar Notícias Agora</strong> acima.
            </div>
          ) : (
            filteredItems.map((it) => (
              <div key={it.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-xs">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-800 dark:text-white">
                      {it.symbol}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                        it.impact === 'HIGH'
                          ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                      }`}
                    >
                      {formatNewsImpact(it.impact)}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                        it.bias === 'BULLISH'
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                          : it.bias === 'BEARISH'
                          ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                      }`}
                    >
                      {it.bias === 'BULLISH' ? 'ALTA' : it.bias === 'BEARISH' ? 'BAIXA' : 'NEUTRO'}
                    </span>
                    {it.is_macro_usd && (
                      <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-800 dark:text-amber-200">
                        MACRO USD
                      </span>
                    )}
                    {it.analysis_source && it.analysis_source.startsWith('AI_') && (
                      <span className="rounded bg-violet-500/20 px-2 py-0.5 text-[10px] font-bold text-violet-700 dark:text-violet-300">
                        IA {it.score > 0 ? `+${it.score.toFixed(2)}` : it.score.toFixed(2)}
                      </span>
                    )}
                    <span className="text-[11px] text-slate-400">
                      {it.source} • {it.published_at}
                    </span>
                  </div>
                  <div className="font-medium text-slate-900 dark:text-slate-100">{it.title}</div>
                  {it.ai_reason && (
                    <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                      Leitura: {it.ai_reason}
                    </div>
                  )}
                </div>
                {it.link && (
                  <a
                    href={it.link}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 shrink-0 text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Abrir
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            ))
          )}
        </div>
      </Card>

      {/* 4. Gerenciamento de Fontes de Notícias — EXCLUSIVO DO SUPER-ADMIN */}
      {isAdmin && (
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
                Fontes de Notícias Globais (Exclusivo Administrador)
              </CardTitle>
              <CardDescription>
                Somente você como administrador cadastra e altera fontes. Todas as fontes ativas aqui alimentam automaticamente os usuários com acesso ao módulo de Notícias.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setShowCustomForm((v) => !v)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/35 bg-blue-500/10 px-3 py-1.5 text-[11px] font-semibold text-blue-600 dark:text-blue-300"
              >
                <Plus className="h-3.5 w-3.5" />
                {showCustomForm ? 'Ocultar URL personalizada' : 'Adicionar URL RSS / Atom'}
              </button>
              <button
                type="button"
                onClick={onResetFeeds}
                className="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-1.5 text-[11px] font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800"
              >
                Restaurar padrões
              </button>
            </div>
          </CardHeader>

          <CardBody className="space-y-5">
            {/* Biblioteca de Fontes Prontas em 1 Clique */}
            {(news?.curated_catalog || []).length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  Catálogo de Fontes Prontas em 1 Clique (PT-BR e Inglês)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                  {(news?.curated_catalog || []).map((cat) => {
                    const alreadyAdded = feeds.some((f) => f.feed_id === cat.feed_id || f.url === cat.url)
                    return (
                      <div
                        key={cat.feed_id}
                        className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 flex flex-col justify-between gap-2"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-1 text-[10px] font-mono text-slate-500">
                            <span>{cat.language || 'GLOBAL'}</span>
                            <span>{cat.default_symbol}</span>
                          </div>
                          <div className="mt-1 text-xs font-semibold text-slate-900 dark:text-white leading-snug">
                            {cat.source}
                          </div>
                        </div>
                        <button
                          type="button"
                          disabled={alreadyAdded}
                          onClick={() =>
                            onSaveFeed({
                              feed_id: cat.feed_id,
                              source: cat.source,
                              url: cat.url,
                              default_symbol: cat.default_symbol,
                            })
                          }
                          className={`w-full rounded-lg py-1.5 text-[11px] font-semibold transition ${
                            alreadyAdded
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 cursor-default'
                              : 'bg-blue-600 hover:bg-blue-500 text-white'
                          }`}
                        >
                          {alreadyAdded ? 'Ativa no painel' : '+ Ativar fonte'}
                        </button>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Formulário Personalizado RSS / Atom */}
            {showCustomForm && (
              <form
                onSubmit={handleSubmitCustomFeed}
                className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4 grid grid-cols-1 md:grid-cols-12 gap-2 items-end"
              >
                <div className="md:col-span-3">
                  <label className="block text-[11px] text-slate-500 dark:text-slate-400 mb-1">Nome da fonte</label>
                  <input
                    type="text"
                    placeholder="Ex: Reuters / InfoMoney"
                    value={feedSource}
                    onChange={(e) => setFeedSource(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div className="md:col-span-5">
                  <label className="block text-[11px] text-slate-500 dark:text-slate-400 mb-1">URL do Feed (RSS ou Atom)</label>
                  <input
                    type="url"
                    required
                    placeholder="https://..."
                    value={feedUrl}
                    onChange={(e) => setFeedUrl(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div className="md:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-[11px] text-slate-500 dark:text-slate-400">Ativo padrão</label>
                    <button
                      type="button"
                      onClick={onLoadAllSymbols}
                      className="text-[10px] font-semibold text-blue-500 hover:text-blue-400"
                    >
                      Todos ({symbols.length})
                    </button>
                  </div>
                  <select
                    value={feedSymbol}
                    onChange={(e) => setFeedSymbol(e.target.value)}
                    className={inputClass}
                  >
                    <option value="ALL">TODOS</option>
                    {symbols.map((s) => (
                      <option key={s.name} value={s.name}>
                        {formatSymbolDisplay(s.name, symbols)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2 flex gap-1.5">
                  <button
                    type="submit"
                    className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 px-3 py-2 text-xs font-semibold text-white"
                  >
                    {feedEditingId ? 'Atualizar' : 'Salvar URL'}
                  </button>
                  {feedEditingId && (
                    <button
                      type="button"
                      onClick={() => {
                        setFeedEditingId('')
                        setFeedSource('')
                        setFeedUrl('')
                        setShowCustomForm(false)
                      }}
                      className="rounded-xl border border-slate-300 dark:border-slate-700 px-2.5 py-2 text-xs"
                    >
                      Cancelar
                    </button>
                  )}
                </div>
              </form>
            )}

            {/* Fontes Ativas com Status por Feed */}
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {feeds.map((f) => {
                const st = feedStatusMap[f.feed_id]
                return (
                  <div
                    key={f.feed_id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/70 px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white">{f.source}</span>
                        <span className="rounded bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-700 dark:text-slate-300">
                          {formatSymbolDisplay(f.default_symbol, symbols)}
                        </span>
                        {st && (
                          <span
                            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono ${
                              st.ok
                                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                : 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                            }`}
                          >
                            {st.ok ? (
                              <>
                                <CheckCircle2 className="h-3 w-3" />
                                OK • {st.count} manchetes
                              </>
                            ) : (
                              <>
                                <XCircle className="h-3 w-3" />
                                Erro: {st.error}
                              </>
                            )}
                          </span>
                        )}
                      </div>
                      <div className="truncate text-[11px] text-slate-500 dark:text-slate-400 font-mono">{f.url}</div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => startEditFeed(f)}
                        className="rounded-lg border border-slate-300 dark:border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteFeed(f.feed_id)}
                        className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[11px] font-medium text-rose-600 dark:text-rose-300 hover:bg-rose-500/20"
                      >
                        Apagar
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

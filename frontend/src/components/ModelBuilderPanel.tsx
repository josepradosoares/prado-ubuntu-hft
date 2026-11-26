import { ChangeEvent, FormEvent, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  Code2,
  Copy,
  FlaskConical,
  Play,
  Plus,
  Sliders,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react'
import {
  BotItem,
  BotTemplate,
  BrokerSymbol,
  CustomIndicatorItem,
  IndicatorMeta,
  StrategyRecipe,
} from '../types'
import { formatSymbolDisplay } from '../utils/formatters'
import { formatSignal } from '../utils/labels'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

interface ModelBuilderPanelProps {
  templates: BotTemplate[]
  indicators: IndicatorMeta[]
  recipes: StrategyRecipe[]
  bots: BotItem[]
  defaultPythonCode: string
  symbols: BrokerSymbol[]
  inputClass: string
  onTemplatesUpdated: (next: BotTemplate[]) => void
  onCreateBotWithTemplate: (template: BotTemplate) => void
  onTestInBacktest: (template: BotTemplate) => void
  showToast: (msg: string, err?: boolean) => void
}

interface SelectedIndicatorRow extends CustomIndicatorItem {
  uid: string
}

const PARAM_LABELS: Record<string, string> = {
  period: 'Período',
  fast: 'Média Rápida',
  slow: 'Média Lenta',
  signal: 'Sinal',
  d_period: 'Suavização %D',
  oversold: 'Sobrevenda',
  overbought: 'Sobrecompra',
  threshold: 'Limite',
  std_mult: 'Desvio (σ)',
  atr_mult: 'Mult. ATR',
  sigma_mult: 'Desvio (σ)',
  window: 'Janela',
  min_adx: 'ADX Mín.',
  step: 'Passo',
  max_step: 'Passo Máx.',
  crossover_only: 'Gatilho de Entrada',
  trend_mode: 'Modo de Leitura',
}

function formatTestDataSource(src?: string): string {
  if (src === 'CTRADER_LIVE') return 'cTrader (Corretora)'
  if (src === 'SIMULATION_FALLBACK') return 'Simulação Local (cTrader desconectada)'
  return 'Simulação Local'
}

interface TestResult {
  ok: boolean
  signal: string
  symbol?: string
  data_source?: string
  ticks_count?: number
  elapsed_ms?: number
  stdout?: string
  error?: string
  buy_votes?: number
  sell_votes?: number
  bars_scanned?: number
  buy_signals_count?: number
  sell_signals_count?: number
  last_signal?: string
  last_signal_bars_ago?: number | null
  details?: { id: string; vote: number; value: number }[]
}

export function ModelBuilderPanel({
  templates,
  indicators,
  recipes,
  bots,
  defaultPythonCode,
  symbols,
  inputClass,
  onTemplatesUpdated,
  onCreateBotWithTemplate,
  onTestInBacktest,
  showToast,
}: ModelBuilderPanelProps) {
  const uidCounter = useRef(1)
  const builderRef = useRef<HTMLDivElement>(null)

  function nextUid(): string {
    uidCounter.current += 1
    return `ind_${uidCounter.current}`
  }

  function toSelectedRows(items: CustomIndicatorItem[]): SelectedIndicatorRow[] {
    return items.map((item) => ({
      uid: nextUid(),
      id: item.id,
      params: { ...(item.params || {}) },
    }))
  }

  const [editingId, setEditingId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [customMode, setCustomMode] = useState<'INDICATORS' | 'PYTHON'>('INDICATORS')
  const [combineMode, setCombineMode] = useState<'MAJORITY' | 'ALL'>('MAJORITY')
  const [recommendedTimeframe, setRecommendedTimeframe] = useState('M5')
  const [selectedIndicators, setSelectedIndicators] = useState<SelectedIndicatorRow[]>((): SelectedIndicatorRow[] => [
    { uid: 'init_1', id: 'EMA', params: { fast: 9, slow: 21, crossover_only: 0 } },
    { uid: 'init_2', id: 'RSI', params: { period: 14, oversold: 30, overbought: 70, trend_mode: 0 } },
  ])
  const [pythonCode, setPythonCode] = useState(defaultPythonCode)
  const [testSymbol, setTestSymbol] = useState('EURUSD')
  const [testTimeframe, setTestTimeframe] = useState('M5')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [recipeStyleFilter, setRecipeStyleFilter] = useState('Todas')
  const [savingRecipeId, setSavingRecipeId] = useState('')

  const indicatorMetaById = useMemo(() => {
    const map: Record<string, IndicatorMeta> = {}
    for (const ind of indicators) {
      map[ind.id] = ind
    }
    return map
  }, [indicators])

  const groupedIndicators = useMemo(() => {
    const groups: Record<string, IndicatorMeta[]> = {}
    for (const ind of indicators) {
      const cat = ind.category || 'Outros'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(ind)
    }
    return groups
  }, [indicators])

  const selectedCountById = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const item of selectedIndicators) {
      counts[item.id] = (counts[item.id] || 0) + 1
    }
    return counts
  }, [selectedIndicators])

  const recipeStyles = useMemo(() => {
    const styles = Array.from(new Set(recipes.map((r) => r.style).filter(Boolean)))
    return ['Todas', ...styles]
  }, [recipes])

  const filteredRecipes = useMemo(() => {
    if (recipeStyleFilter === 'Todas') return recipes
    return recipes.filter((r) => r.style === recipeStyleFilter)
  }, [recipes, recipeStyleFilter])

  const botUsageByTemplateId = useMemo(() => {
    const map: Record<string, string[]> = {}
    for (const b of bots) {
      const tid = b.template_id
      if (!tid) continue
      if (!map[tid]) map[tid] = []
      map[tid].push(b.name || b.bot_id)
    }
    return map
  }, [bots])

  const hasCrossoverInTicksWarning = useMemo(
    () =>
      customMode === 'INDICATORS' &&
      testTimeframe === 'TICKS' &&
      selectedIndicators.some((item) => Number(item.params.crossover_only || 0) === 1),
    [customMode, testTimeframe, selectedIndicators],
  )

  function resetForm() {
    setEditingId('')
    setName('')
    setDescription('')
    setCustomMode('INDICATORS')
    setCombineMode('MAJORITY')
    setRecommendedTimeframe('M5')
    setSelectedIndicators(
      toSelectedRows([
        { id: 'EMA', params: { fast: 9, slow: 21, crossover_only: 0 } },
        { id: 'RSI', params: { period: 14, oversold: 30, overbought: 70, trend_mode: 0 } },
      ]),
    )
    setPythonCode(defaultPythonCode)
    setTestTimeframe('M5')
    setTestResult(null)
  }

  function addIndicator(ind: IndicatorMeta) {
    setSelectedIndicators((prev) => [
      ...prev,
      { uid: nextUid(), id: ind.id, params: { ...ind.default_params } },
    ])
  }

  function removeIndicatorRow(uid: string) {
    setSelectedIndicators((prev) => prev.filter((item) => item.uid !== uid))
  }

  function updateIndicatorParam(uid: string, key: string, value: number) {
    setSelectedIndicators((prev) =>
      prev.map((item) =>
        item.uid === uid ? { ...item, params: { ...item.params, [key]: value } } : item,
      ),
    )
  }

  function customizeRecipe(recipe: StrategyRecipe) {
    setEditingId('')
    setName(recipe.name)
    setDescription(recipe.description)
    setCustomMode('INDICATORS')
    setCombineMode(recipe.combine_mode || 'ALL')
    setSelectedIndicators(toSelectedRows(recipe.indicators))
    const recTf = recipe.recommended_timeframe || 'M5'
    setRecommendedTimeframe(recTf)
    setTestTimeframe(recTf)
    setTestResult(null)
    showToast(`Estratégia "${recipe.name}" carregada no editor para você ajustar ou testar!`)
    builderRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function saveRecipeDirectly(recipe: StrategyRecipe) {
    setSavingRecipeId(recipe.id)
    try {
      const res = await fetch('/api/bot-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'SAVE',
          name: recipe.name,
          description: recipe.description,
          custom_mode: 'INDICATORS',
          combine_mode: recipe.combine_mode,
          recommended_timeframe: recipe.recommended_timeframe || 'M5',
          indicators: recipe.indicators,
        }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        onTemplatesUpdated(d.templates || [])
        showToast(`Estratégia "${recipe.name}" adicionada! Já está disponível para criar robôs e simular.`)
      } else {
        showToast(d.error || 'Falha ao adicionar estratégia.', true)
      }
    } catch {
      showToast('Erro de rede ao adicionar estratégia.', true)
    } finally {
      setSavingRecipeId('')
    }
  }

  function handleFileUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const text = String(reader.result || '')
      setPythonCode(text)
      setCustomMode('PYTHON')
      if (!name.trim()) {
        setName(file.name.replace(/\.py$/i, ''))
      }
      showToast(`Arquivo "${file.name}" carregado no editor!`)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  function serializeIndicators(): CustomIndicatorItem[] {
    return selectedIndicators.map(({ id, params }) => ({ id, params }))
  }

  async function runTest() {
    if (customMode === 'INDICATORS' && selectedIndicators.length === 0) {
      showToast('Adicione pelo menos 1 indicador para testar.', true)
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch('/api/bot-templates/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          custom_mode: customMode,
          indicators: serializeIndicators(),
          combine_mode: combineMode,
          python_code: pythonCode,
          symbol: testSymbol,
          timeframe: testTimeframe,
        }),
      })
      const d: TestResult = await res.json()
      setTestResult(d)
      if (d.ok) {
        showToast(`Teste executado: sinal atual ${formatSignal(d.signal)}`)
      } else {
        showToast(d.error || 'Erro ao testar modelo.', true)
      }
    } catch {
      showToast('Erro de rede ao testar modelo.', true)
    } finally {
      setTesting(false)
    }
  }

  async function saveTemplate(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      showToast('Informe um nome para o modelo matemático.', true)
      return
    }
    if (customMode === 'INDICATORS' && selectedIndicators.length === 0) {
      showToast('Selecione pelo menos 1 indicador.', true)
      return
    }
    const effectiveTf =
      customMode === 'INDICATORS'
        ? testTimeframe !== 'TICKS'
          ? testTimeframe
          : recommendedTimeframe || 'M5'
        : 'TICKS'
    try {
      const res = await fetch('/api/bot-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'SAVE',
          template_id: editingId || undefined,
          name: name.trim(),
          description: description.trim() || 'Modelo matemático customizado',
          custom_mode: customMode,
          combine_mode: combineMode,
          recommended_timeframe: effectiveTf,
          indicators: serializeIndicators(),
          python_code: pythonCode,
        }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        onTemplatesUpdated(d.templates || [])
        resetForm()
        showToast('Modelo matemático salvo e disponível para os robôs!')
      } else {
        showToast(d.error || 'Falha ao salvar modelo.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar modelo.', true)
    }
  }

  async function deleteTemplate(tid: string) {
    const usedBy = botUsageByTemplateId[tid] || []
    if (usedBy.length > 0) {
      showToast(
        `Não é possível excluir: modelo em uso pelo(s) robô(s) ${usedBy.join(', ')}. Troque o modelo primeiro.`,
        true,
      )
      return
    }
    try {
      const res = await fetch('/api/bot-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'DELETE', template_id: tid }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        onTemplatesUpdated(d.templates || [])
        if (editingId === tid) resetForm()
        showToast('Modelo customizado removido.')
      } else {
        showToast(d.error || 'Falha ao remover modelo.', true)
      }
    } catch {
      showToast('Erro de rede ao remover modelo.', true)
    }
  }

  function startEdit(t: BotTemplate, asCopy = false) {
    setEditingId(asCopy ? '' : t.template_id)
    setName(asCopy ? `${t.name} (Cópia)` : t.name)
    setDescription(t.description || '')
    const mode = (t.custom_mode as 'INDICATORS' | 'PYTHON') || 'INDICATORS'
    setCustomMode(mode)
    setCombineMode((t.combine_mode as 'MAJORITY' | 'ALL') || 'MAJORITY')
    setSelectedIndicators(t.indicators?.length ? toSelectedRows(t.indicators) : [])
    setPythonCode(t.python_code || defaultPythonCode)
    const recTf = t.recommended_timeframe || (mode === 'INDICATORS' ? 'M5' : 'TICKS')
    setRecommendedTimeframe(recTf)
    setTestTimeframe(recTf)
    setTestResult(null)
    builderRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="space-y-6">
      {/* Bloco 1: Estratégias Prontas */}
      {recipes.length > 0 && (
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-emerald-500" />
                Estratégias Prontas ({recipes.length})
              </CardTitle>
              <CardDescription>
                Estratégias já configuradas por estilo de operação. Clique em <strong>Usar Estratégia</strong> para adicionar à sua lista ou em <strong>Personalizar</strong> para ajustar os parâmetros do seu jeito.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {recipeStyles.map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setRecipeStyleFilter(st)}
                  className={`rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition ${
                    recipeStyleFilter === st
                      ? 'border-blue-500 bg-blue-600 text-white'
                      : 'border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredRecipes.map((r) => (
                <div
                  key={r.id}
                  className="flex flex-col justify-between rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/40 p-3.5 space-y-2.5"
                >
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-bold text-slate-900 dark:text-white">{r.name}</span>
                      <div className="flex items-center gap-1.5">
                        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
                          {r.style}
                        </span>
                        <span className="rounded bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-700 dark:text-slate-300">
                          {r.recommended_timeframe}
                        </span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                      {r.description}
                    </p>
                    <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-slate-500 dark:text-slate-400">
                      <span className="font-semibold text-slate-600 dark:text-slate-300">Ativos sugeridos:</span>
                      <span>{r.markets}</span>
                      <span>•</span>
                      <span>
                        {r.combine_mode === 'ALL' ? 'Todos Concordam (E)' : 'Maioria'} ({r.indicators.map((i) => i.id).join(' + ')})
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => customizeRecipe(r)}
                      className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      Personalizar
                    </button>
                    <button
                      type="button"
                      onClick={() => saveRecipeDirectly(r)}
                      disabled={savingRecipeId === r.id}
                      className="inline-flex items-center gap-1 rounded-lg bg-blue-600 hover:bg-blue-500 px-2.5 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50"
                    >
                      <Plus className="h-3 w-3" />
                      {savingRecipeId === r.id ? 'Adicionando...' : 'Usar Estratégia'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Bloco 2: Criador de Estratégias */}
      <div ref={builderRef}>
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>{editingId ? 'Editar Estratégia' : 'Criar Estratégia Personalizada'}</CardTitle>
              <CardDescription>
                Combine múltiplos indicadores (inclusive o mesmo indicador com períodos diferentes, como EMA 50×200 + EMA 9×21) ou envie seu código Python.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCustomMode('INDICATORS')}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                  customMode === 'INDICATORS'
                    ? 'border-blue-500 bg-blue-600 text-white'
                    : 'border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300'
                }`}
              >
                <Sliders className="h-3.5 w-3.5" />
                Por Indicadores ({indicators.length || 21})
              </button>
              <button
                type="button"
                onClick={() => setCustomMode('PYTHON')}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                  customMode === 'PYTHON'
                    ? 'border-blue-500 bg-blue-600 text-white'
                    : 'border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300'
                }`}
              >
                <Code2 className="h-3.5 w-3.5" />
                Código Python / Upload .py
              </button>
            </div>
          </CardHeader>

          <CardBody>
            <form onSubmit={saveTemplate} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                    Nome do Modelo
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Ex: Meu Cruzamento EMA 9x21 + Filtro EMA 200"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                    Descrição curta
                  </label>
                  <input
                    type="text"
                    placeholder="Ex: Entra a favor da tendência macro com cruzamento curto"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>

              {customMode === 'INDICATORS' ? (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/40 p-3">
                    <div className="text-xs text-slate-700 dark:text-slate-300">
                      <strong>Regra de combinação:</strong> {selectedIndicators.length} indicador(es) na estratégia
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setCombineMode('MAJORITY')}
                        className={`rounded-lg border px-3 py-1 text-xs font-semibold ${
                          combineMode === 'MAJORITY'
                            ? 'border-emerald-500 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                            : 'border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        Maioria dos Indicadores
                      </button>
                      <button
                        type="button"
                        onClick={() => setCombineMode('ALL')}
                        className={`rounded-lg border px-3 py-1 text-xs font-semibold ${
                          combineMode === 'ALL'
                            ? 'border-emerald-500 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                            : 'border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        Todos Concordam (E)
                      </button>
                    </div>
                  </div>

                  {/* Subseção: Indicadores na sua estratégia (permite múltiplas instâncias) */}
                  <div className="space-y-2.5">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">
                      Indicadores na sua estratégia ({selectedIndicators.length})
                    </div>
                    {selectedIndicators.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-4 text-center text-xs text-slate-500 dark:text-slate-400">
                        Nenhum indicador adicionado ainda. Clique em <strong>+ Adicionar</strong> no catálogo abaixo ou escolha uma das Estratégias Prontas acima.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                        {selectedIndicators.map((item, idx) => {
                          const meta = indicatorMetaById[item.id]
                          return (
                            <div
                              key={item.uid}
                              className="rounded-xl border border-blue-500/40 bg-blue-500/5 p-3 space-y-2"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="text-xs font-bold text-slate-900 dark:text-white truncate">
                                    #{idx + 1} • {meta?.name || item.id}
                                  </div>
                                  {meta?.description && (
                                    <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5 leading-snug">
                                      {meta.description}
                                    </div>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={() => removeIndicatorRow(item.uid)}
                                  className="shrink-0 rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-600 dark:text-rose-300 hover:bg-rose-500/20"
                                >
                                  Remover
                                </button>
                              </div>

                              <div className="grid grid-cols-2 gap-2 pt-1">
                                {Object.entries(item.params).map(([k, val]) =>
                                  k === 'crossover_only' ? (
                                    <div key={k} className="col-span-2">
                                      <label className="block text-[10px] font-sans text-slate-500 dark:text-slate-400 mb-0.5">
                                        {PARAM_LABELS[k] || k}
                                      </label>
                                      <select
                                        value={Number(val) ? 1 : 0}
                                        onChange={(e) => updateIndicatorParam(item.uid, k, Number(e.target.value))}
                                        className={`${inputClass} py-1 text-xs`}
                                      >
                                        <option value={0}>Tendência (Posição Atual)</option>
                                        <option value={1}>Apenas Cruzamento</option>
                                      </select>
                                    </div>
                                  ) : k === 'trend_mode' ? (
                                    <div key={k} className="col-span-2">
                                      <label className="block text-[10px] font-sans text-slate-500 dark:text-slate-400 mb-0.5">
                                        {PARAM_LABELS[k] || k}
                                      </label>
                                      <select
                                        value={Number(val) || 0}
                                        onChange={(e) => updateIndicatorParam(item.uid, k, Number(e.target.value))}
                                        className={`${inputClass} py-1 text-xs`}
                                      >
                                        <option value={0}>Reversão (Sobrevenda / Sobrecompra)</option>
                                        <option value={1}>Tendência (Acima / Abaixo de 50)</option>
                                        <option value={2}>Cruzamento (Saindo de Sobrevenda / Sobrecompra)</option>
                                      </select>
                                    </div>
                                  ) : (
                                    <div key={k}>
                                      <label className="block text-[10px] font-sans text-slate-500 dark:text-slate-400 mb-0.5">
                                        {k === 'slow' && ['SMA', 'WMA', 'DEMA'].includes(item.id)
                                          ? 'Média Lenta (0 = Preço)'
                                          : PARAM_LABELS[k] || k}
                                      </label>
                                      <input
                                        type="number"
                                        step="any"
                                        value={val}
                                        onChange={(e) => updateIndicatorParam(item.uid, k, Number(e.target.value))}
                                        className={`${inputClass} py-1 text-xs font-mono`}
                                      />
                                    </div>
                                  ),
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Catálogo completo para adicionar indicadores (1 ou mais vezes cada) */}
                  <div className="space-y-3 pt-1">
                    <div className="text-xs font-bold text-slate-700 dark:text-slate-200">
                      Catálogo de Indicadores — clique em <strong>+ Adicionar</strong> para compor sua estratégia
                    </div>
                    {Object.entries(groupedIndicators).map(([category, list]) => (
                      <div key={category} className="space-y-2">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          {category} ({list.length})
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                          {list.map((ind) => {
                            const count = selectedCountById[ind.id] || 0
                            return (
                              <div
                                key={ind.id}
                                className="flex flex-col justify-between rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/40 p-2.5 gap-2"
                              >
                                <div>
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-100">
                                      {ind.name}
                                    </span>
                                    {count > 0 && (
                                      <span className="shrink-0 rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] font-bold text-blue-600 dark:text-blue-300">
                                        {count}x
                                      </span>
                                    )}
                                  </div>
                                  {ind.description && (
                                    <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
                                      {ind.description}
                                    </p>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  onClick={() => addIndicator(ind)}
                                  className="inline-flex w-fit items-center gap-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950/60 px-2.5 py-1 text-[11px] font-semibold text-slate-700 dark:text-slate-200 hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-300"
                                >
                                  <Plus className="h-3 w-3" />
                                  Adicionar
                                </button>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs text-slate-600 dark:text-slate-300">
                      Escreva ou importe um arquivo <code className="font-mono text-blue-500">.py</code> com{' '}
                      <code className="font-mono text-blue-500">def evaluate(prices, ticks, params):</code> retornando{' '}
                      <code className="font-mono">&quot;BUY&quot;</code>, <code className="font-mono">&quot;SELL&quot;</code> ou{' '}
                      <code className="font-mono">&quot;WAIT&quot;</code>.
                    </div>
                    <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800">
                      <Upload className="h-3.5 w-3.5" />
                      Importar arquivo .py
                      <input type="file" accept=".py" onChange={handleFileUpload} className="hidden" />
                    </label>
                  </div>
                  <textarea
                    rows={12}
                    value={pythonCode}
                    onChange={(e) => setPythonCode(e.target.value)}
                    spellCheck={false}
                    className={`${inputClass} font-mono text-xs leading-relaxed`}
                  />
                </div>
              )}

              {/* Aviso sobre Apenas Cruzamento em TICKS */}
              {hasCrossoverInTicksWarning && (
                <div className="flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-200">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-500" />
                  <div>
                    <strong>Atenção ao modo Tick a Tick:</strong> você ativou <strong>Apenas Cruzamento</strong>. Para não perder entradas entre ticks rápidos, recomendamos usar tempo gráfico em velas (<strong>M1</strong>, <strong>M5</strong>, <strong>M15</strong> ou <strong>H1</strong>) tanto no teste quanto no robô.
                  </div>
                </div>
              )}

              {/* Bloco 3: Barra de Teste Rápido com Resumo Histórico */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/60 p-3 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">Testar em:</span>
                    <select
                      value={testSymbol}
                      onChange={(e) => setTestSymbol(e.target.value)}
                      className={`${inputClass} w-auto py-1 text-xs font-mono`}
                    >
                      {symbols.map((s) => (
                        <option key={s.name} value={s.name}>
                          {formatSymbolDisplay(s.name, symbols)}
                        </option>
                      ))}
                    </select>
                    <select
                      value={testTimeframe}
                      onChange={(e) => {
                        const tf = e.target.value
                        setTestTimeframe(tf)
                        if (tf !== 'TICKS') setRecommendedTimeframe(tf)
                      }}
                      className={`${inputClass} w-auto py-1 text-xs font-mono`}
                    >
                      <option value="TICKS">Tick a Tick</option>
                      <option value="M1">M1 (Recomendado p/ scalping)</option>
                      <option value="M5">M5 (Recomendado p/ indicadores)</option>
                      <option value="M15">M15</option>
                      <option value="H1">H1</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={runTest}
                    disabled={testing}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    <Play className="h-3.5 w-3.5" />
                    {testing ? 'Executando...' : 'Executar Teste'}
                  </button>
                </div>

                {testResult && (
                  <div
                    className={`rounded-lg border px-3 py-2.5 text-xs font-mono ${
                      testResult.ok
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                        : 'border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200'
                    }`}
                  >
                    {testResult.ok ? (
                      <div className="space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            Sinal atual: <strong>{formatSignal(testResult.signal)}</strong> • {testResult.ticks_count} barras/ticks carregados em{' '}
                            {testResult.symbol} ({testResult.elapsed_ms} ms)
                          </div>
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-sans font-semibold ${
                              testResult.data_source === 'CTRADER_LIVE'
                                ? 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300'
                                : 'bg-amber-500/20 text-amber-800 dark:text-amber-300'
                            }`}
                          >
                            Fonte: {formatTestDataSource(testResult.data_source)}
                          </span>
                        </div>
                        {typeof testResult.bars_scanned === 'number' && (
                          <div className="text-[11px] font-sans">
                            {(testResult.buy_signals_count || 0) + (testResult.sell_signals_count || 0) > 0 ? (
                              <>
                                <strong>Janela analisada ({testResult.bars_scanned} pontos):</strong>{' '}
                                {testResult.buy_signals_count || 0} compra(s) • {testResult.sell_signals_count || 0} venda(s)
                                {testResult.last_signal && testResult.last_signal !== 'WAIT' && (
                                  <>
                                    {' '}• Último sinal: <strong>{formatSignal(testResult.last_signal)}</strong>{' '}
                                    {testResult.last_signal_bars_ago === 0
                                      ? '(nesta barra)'
                                      : `há ${testResult.last_signal_bars_ago} barra(s)`}
                                  </>
                                )}
                              </>
                            ) : (
                              <span className="text-amber-700 dark:text-amber-300">
                                Nenhum sinal disparado nas últimas {testResult.bars_scanned} barras — tente trocar o ativo/timeframe ou usar Maioria / Tendência.
                              </span>
                            )}
                          </div>
                        )}
                        {testResult.details && testResult.details.length > 0 && (
                          <div className="text-[11px] opacity-90">
                            Votos: {testResult.details.map((d) => `${d.id}=${d.vote > 0 ? '+1' : d.vote < 0 ? '-1' : '0'}(${d.value})`).join(' | ')}
                          </div>
                        )}
                        {testResult.stdout && <pre className="mt-1 whitespace-pre-wrap text-[11px]">{testResult.stdout}</pre>}
                      </div>
                    ) : (
                      <div>Erro: {testResult.error}</div>
                    )}
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-xs font-semibold text-white"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {editingId ? 'Atualizar Modelo' : 'Salvar Modelo Matemático'}
                </button>
                {editingId && (
                  <button
                    type="button"
                    onClick={resetForm}
                    className="rounded-xl border border-slate-300 dark:border-slate-700 px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300"
                  >
                    Cancelar edição
                  </button>
                )}
              </div>
            </form>
          </CardBody>
        </Card>
      </div>

      {/* Bloco 4: Minhas Estratégias e Modelos */}
      <Card>
        <CardHeader>
          <CardTitle>Minhas Estratégias e Modelos ({templates.length})</CardTitle>
          <CardDescription>
            Estratégias nativas (protegidas) e personalizadas prontas para simular no histórico ou criar um robô em 1 clique.
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-2.5">
          {templates.map((t) => {
            const usedBy = botUsageByTemplateId[t.template_id] || []
            return (
              <div
                key={t.template_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/40 px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-slate-900 dark:text-white">{t.name}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        t.is_custom
                          ? 'bg-blue-500/15 text-blue-600 dark:text-blue-300'
                          : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                      }`}
                    >
                      {t.is_custom ? (t.custom_mode === 'PYTHON' ? 'Python Personalizado' : 'Indicadores Personalizados') : 'Nativo'}
                    </span>
                    {usedBy.length > 0 && (
                      <span
                        title={usedBy.join(', ')}
                        className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300"
                      >
                        Em uso por {usedBy.length} robô{usedBy.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{t.description}</div>
                  <div className="text-[10px] font-mono text-blue-600 dark:text-blue-400 mt-0.5 truncate">{t.formula}</div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => onTestInBacktest(t)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-300 dark:border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    <FlaskConical className="h-3 w-3" />
                    Simular
                  </button>
                  <button
                    type="button"
                    onClick={() => onCreateBotWithTemplate(t)}
                    className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1 text-xs font-semibold text-white"
                  >
                    <Bot className="h-3 w-3" />
                    Criar Robô
                  </button>
                  {t.is_custom && (
                    <>
                      <button
                        type="button"
                        onClick={() => startEdit(t, true)}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 dark:border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <Copy className="h-3 w-3" />
                        Duplicar
                      </button>
                      <button
                        type="button"
                        onClick={() => startEdit(t, false)}
                        className="rounded-lg border border-slate-300 dark:border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteTemplate(t.template_id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-600 dark:text-rose-300 hover:bg-rose-500/20"
                      >
                        <Trash2 className="h-3 w-3" />
                        Excluir
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </CardBody>
      </Card>
    </div>
  )
}

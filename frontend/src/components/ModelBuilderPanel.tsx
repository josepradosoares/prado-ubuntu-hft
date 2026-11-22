import { ChangeEvent, FormEvent, useMemo, useState } from 'react'
import { Code2, Play, Plus, Sliders, Trash2, Upload } from 'lucide-react'
import { BotTemplate, BrokerSymbol, CustomIndicatorItem, IndicatorMeta } from '../types'
import { formatSymbolDisplay } from '../utils/formatters'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

interface ModelBuilderPanelProps {
  templates: BotTemplate[]
  indicators: IndicatorMeta[]
  defaultPythonCode: string
  symbols: BrokerSymbol[]
  inputClass: string
  onTemplatesUpdated: (next: BotTemplate[]) => void
  showToast: (msg: string, err?: boolean) => void
}

interface TestResult {
  ok: boolean
  signal: string
  symbol?: string
  ticks_count?: number
  elapsed_ms?: number
  stdout?: string
  error?: string
  buy_votes?: number
  sell_votes?: number
  details?: { id: string; vote: number; value: number }[]
}

export function ModelBuilderPanel({
  templates,
  indicators,
  defaultPythonCode,
  symbols,
  inputClass,
  onTemplatesUpdated,
  showToast,
}: ModelBuilderPanelProps) {
  const [editingId, setEditingId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [customMode, setCustomMode] = useState<'INDICATORS' | 'PYTHON'>('INDICATORS')
  const [combineMode, setCombineMode] = useState<'MAJORITY' | 'ALL'>('MAJORITY')
  const [selectedIndicators, setSelectedIndicators] = useState<CustomIndicatorItem[]>([
    { id: 'EMA', params: { fast: 9, slow: 21 } },
    { id: 'RSI', params: { period: 14, oversold: 30, overbought: 70 } },
  ])
  const [pythonCode, setPythonCode] = useState(defaultPythonCode)
  const [testSymbol, setTestSymbol] = useState('R_100')
  const [testTimeframe, setTestTimeframe] = useState('TICKS')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)

  const groupedIndicators = useMemo(() => {
    const groups: Record<string, IndicatorMeta[]> = {}
    for (const ind of indicators) {
      const cat = ind.category || 'Outros'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(ind)
    }
    return groups
  }, [indicators])

  function resetForm() {
    setEditingId('')
    setName('')
    setDescription('')
    setCustomMode('INDICATORS')
    setCombineMode('MAJORITY')
    setSelectedIndicators([
      { id: 'EMA', params: { fast: 9, slow: 21 } },
      { id: 'RSI', params: { period: 14, oversold: 30, overbought: 70 } },
    ])
    setPythonCode(defaultPythonCode)
    setTestResult(null)
  }

  function toggleIndicator(ind: IndicatorMeta) {
    setSelectedIndicators((prev) => {
      const exists = prev.some((i) => i.id === ind.id)
      if (exists) return prev.filter((i) => i.id !== ind.id)
      return [...prev, { id: ind.id, params: { ...ind.default_params } }]
    })
  }

  function updateIndicatorParam(indId: string, key: string, value: number) {
    setSelectedIndicators((prev) =>
      prev.map((item) =>
        item.id === indId ? { ...item, params: { ...item.params, [key]: value } } : item,
      ),
    )
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

  async function runTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch('/api/bot-templates/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          custom_mode: customMode,
          indicators: selectedIndicators,
          combine_mode: combineMode,
          python_code: pythonCode,
          symbol: testSymbol,
          timeframe: testTimeframe,
        }),
      })
      const d: TestResult = await res.json()
      setTestResult(d)
      if (d.ok) {
        showToast(`Teste executado: sinal ${d.signal}`)
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
          indicators: selectedIndicators,
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

  function startEdit(t: BotTemplate) {
    setEditingId(t.template_id)
    setName(t.name)
    setDescription(t.description || '')
    setCustomMode((t.custom_mode as 'INDICATORS' | 'PYTHON') || 'INDICATORS')
    setCombineMode((t.combine_mode as 'MAJORITY' | 'ALL') || 'MAJORITY')
    setSelectedIndicators(t.indicators?.length ? t.indicators : [])
    setPythonCode(t.python_code || defaultPythonCode)
    setTestResult(null)
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>{editingId ? 'Editar Modelo Matemático' : 'Criar Novo Modelo Matemático'}</CardTitle>
            <CardDescription>
              Monte uma estratégia escolhendo entre os {indicators.length || 21} indicadores principais ou envie/cole seu código Python e teste antes de salvar.
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
                  placeholder="Ex: Meu Cruzamento EMA + RSI"
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
                  placeholder="Ex: Entra a favor da tendência com filtro RSI"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            {customMode === 'INDICATORS' ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/40 p-3">
                  <div className="text-xs text-slate-700 dark:text-slate-300">
                    <strong>Regra de combinação:</strong> {selectedIndicators.length} indicador(es) selecionado(s)
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

                {Object.entries(groupedIndicators).map(([category, list]) => (
                  <div key={category} className="space-y-2">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      {category} ({list.length})
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                      {list.map((ind) => {
                        const active = selectedIndicators.find((s) => s.id === ind.id)
                        return (
                          <div
                            key={ind.id}
                            className={`rounded-xl border p-3 transition ${
                              active
                                ? 'border-blue-500/50 bg-blue-500/5'
                                : 'border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/40'
                            }`}
                          >
                            <label className="flex items-center gap-2 text-xs font-semibold text-slate-800 dark:text-slate-100 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={Boolean(active)}
                                onChange={() => toggleIndicator(ind)}
                                className="h-4 w-4 rounded border-slate-400 text-blue-600"
                              />
                              <span>{ind.name}</span>
                            </label>
                            {active && (
                              <div className="mt-2.5 grid grid-cols-2 gap-2">
                                {Object.entries(active.params).map(([k, val]) => (
                                  <div key={k}>
                                    <label className="block text-[10px] font-mono text-slate-500 dark:text-slate-400">
                                      {k}
                                    </label>
                                    <input
                                      type="number"
                                      step="any"
                                      value={val}
                                      onChange={(e) => updateIndicatorParam(ind.id, k, Number(e.target.value))}
                                      className={`${inputClass} py-1 text-xs font-mono`}
                                    />
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))}
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

            {/* Test Runner Bar */}
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
                    onChange={(e) => setTestTimeframe(e.target.value)}
                    className={`${inputClass} w-auto py-1 text-xs font-mono`}
                  >
                    <option value="TICKS">Tick a Tick</option>
                    <option value="M1">M1</option>
                    <option value="M5">M5</option>
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
                  className={`rounded-lg border px-3 py-2 text-xs font-mono ${
                    testResult.ok
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                      : 'border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200'
                  }`}
                >
                  {testResult.ok ? (
                    <div className="space-y-1">
                      <div>
                        Sinal gerado: <strong>{testResult.signal}</strong> • {testResult.ticks_count} pontos em{' '}
                        {testResult.symbol} ({testResult.elapsed_ms} ms)
                      </div>
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

      <Card>
        <CardHeader>
          <CardTitle>Modelos Disponíveis ({templates.length})</CardTitle>
          <CardDescription>
            Modelos nativos (protegidos) e seus modelos customizados prontos para usar nos robôs e no Backtest.
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-2.5">
          {templates.map((t) => (
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
                    {t.is_custom ? (t.custom_mode === 'PYTHON' ? 'Custom Python' : 'Custom Indicadores') : 'Nativo'}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{t.description}</div>
                <div className="text-[10px] font-mono text-blue-600 dark:text-blue-400 mt-0.5 truncate">{t.formula}</div>
              </div>
              {t.is_custom && (
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => startEdit(t)}
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
                </div>
              )}
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  )
}

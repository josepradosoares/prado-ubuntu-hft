import { useMemo, useState } from 'react'
import { Bot, LineChart, Plus, TrendingDown, TrendingUp, X } from 'lucide-react'
import { BotItem, BrokerSymbol, SymbolState } from '../types'
import { formatNumber, formatPercent, formatPrice, formatSignedPercent, formatSymbolDisplay, isFiniteNumber } from '../utils/formatters'
import { formatRegime, formatSignal } from '../utils/labels'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

type MatrixFilter = 'ALL' | 'TREND' | 'REVERT' | 'BOTS'

interface VwapMatrixPanelProps {
  symbolsData: Record<string, SymbolState>
  activeSymbols: string[]
  symbolCatalog: BrokerSymbol[]
  bots: BotItem[]
  basketBias?: number
  customCategories: Record<string, string[]>
  onUpdateActiveSymbols: (next: string[]) => Promise<void> | void
  onOpenChart: (sym: string) => void
  onCreateBotForSymbol: (sym: string) => void
}

const MAX_MONITORED_SYMBOLS = 25

function getRegimeRank(regime?: string): number {
  if (regime === 'INSTITUTIONAL_TREND_UP' || regime === 'INSTITUTIONAL_TREND_DOWN') return 0
  if (regime === 'HFT_MEAN_REVERSION') return 1
  return 2
}

export function VwapMatrixPanel({
  symbolsData,
  activeSymbols,
  symbolCatalog,
  bots,
  basketBias,
  customCategories,
  onUpdateActiveSymbols,
  onOpenChart,
  onCreateBotForSymbol,
}: VwapMatrixPanelProps) {
  const [filter, setFilter] = useState<MatrixFilter>('ALL')
  const [selectedToAdd, setSelectedToAdd] = useState('')
  const [saving, setSaving] = useState(false)

  const botCountsBySymbol = useMemo(() => {
    const counts: Record<string, { total: number; active: number }> = {}
    for (const b of bots) {
      if (!b?.symbol) continue
      if (!counts[b.symbol]) counts[b.symbol] = { total: 0, active: 0 }
      counts[b.symbol].total += 1
      if (b.active || b.status === 'RUNNING') counts[b.symbol].active += 1
    }
    return counts
  }, [bots])

  const rows = useMemo(() => {
    const allEntries = Object.values(symbolsData || {}).filter((s): s is SymbolState => Boolean(s && s.symbol))
    return [...allEntries].sort((a, b) => {
      const rankDiff = getRegimeRank(a.regime) - getRegimeRank(b.regime)
      if (rankDiff !== 0) return rankDiff
      const az = Math.abs(Number(a.zscore || 0))
      const bz = Math.abs(Number(b.zscore || 0))
      return bz - az
    })
  }, [symbolsData])

  const summary = useMemo(() => {
    let trends = 0
    let reverts = 0
    let neutrals = 0
    for (const s of rows) {
      if (s.regime === 'INSTITUTIONAL_TREND_UP' || s.regime === 'INSTITUTIONAL_TREND_DOWN') trends += 1
      else if (s.regime === 'HFT_MEAN_REVERSION') reverts += 1
      else neutrals += 1
    }
    return { trends, reverts, neutrals }
  }, [rows])

  const filteredRows = useMemo(() => {
    return rows.filter((s) => {
      if (filter === 'TREND') {
        return s.regime === 'INSTITUTIONAL_TREND_UP' || s.regime === 'INSTITUTIONAL_TREND_DOWN'
      }
      if (filter === 'REVERT') {
        return s.regime === 'HFT_MEAN_REVERSION'
      }
      if (filter === 'BOTS') {
        return Boolean(botCountsBySymbol[s.symbol]?.total)
      }
      return true
    })
  }, [rows, filter, botCountsBySymbol])

  const availableToAdd = useMemo(() => {
    const activeSet = new Set(activeSymbols)
    return symbolCatalog.filter((s) => s.name && !activeSet.has(s.name))
  }, [symbolCatalog, activeSymbols])

  async function applySymbols(next: string[]) {
    setSaving(true)
    try {
      await onUpdateActiveSymbols(next.slice(0, MAX_MONITORED_SYMBOLS))
    } finally {
      setSaving(false)
    }
  }

  async function handleAddSymbol() {
    if (!selectedToAdd || activeSymbols.length >= MAX_MONITORED_SYMBOLS) return
    if (activeSymbols.includes(selectedToAdd)) return
    await applySymbols([...activeSymbols, selectedToAdd])
    setSelectedToAdd('')
  }

  async function handleRemoveSymbol(sym: string) {
    const next = activeSymbols.filter((s) => s !== sym)
    await applySymbols(next)
  }

  async function applyPreset(presetKey: 'MAIN' | 'INDICES' | 'FOREX' | 'METALS' | 'CRYPTO' | 'BOTS_ONLY') {
    const botSyms = Array.from(new Set(bots.map((b) => b.symbol).filter(Boolean)))
    let list: string[] = []
    if (presetKey === 'MAIN') {
      list = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'US100', 'US500', 'BTCUSD', 'ETHUSD']
    } else if (presetKey === 'INDICES') {
      list = customCategories['Índices Globais'] || ['US100', 'US500', 'US30', 'DE40']
    } else if (presetKey === 'FOREX') {
      list = customCategories['Forex Principais'] || ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF']
    } else if (presetKey === 'METALS') {
      list = customCategories['Metais & Commodities'] || ['XAUUSD', 'XAGUSD']
    } else if (presetKey === 'CRYPTO') {
      list = customCategories['Criptomoedas (24/7)'] || ['BTCUSD', 'ETHUSD']
    } else {
      list = botSyms
    }
    const merged = presetKey === 'BOTS_ONLY' ? list : Array.from(new Set([...botSyms, ...list]))
    if (merged.length > 0) {
      await applySymbols(merged)
    }
  }

  const basketPositive = isFiniteNumber(basketBias) && basketBias > 0.02
  const basketNegative = isFiniteNumber(basketBias) && basketBias < -0.02

  return (
    <div className="space-y-5">
      {/* 4 Cards clicáveis de resumo */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <button
          type="button"
          onClick={() => setFilter((f) => (f === 'TREND' ? 'ALL' : 'TREND'))}
          className={`text-left rounded-2xl border p-4 transition shadow-sm ${
            filter === 'TREND'
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#252223] hover:border-blue-500/50'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Em Tendência</span>
            <TrendingUp className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono text-slate-900 dark:text-white">
            {summary.trends}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {filter === 'TREND' ? 'Filtro ativo (clique p/ limpar)' : 'Clique para filtrar tendências'}
          </div>
        </button>

        <button
          type="button"
          onClick={() => setFilter((f) => (f === 'REVERT' ? 'ALL' : 'REVERT'))}
          className={`text-left rounded-2xl border p-4 transition shadow-sm ${
            filter === 'REVERT'
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#252223] hover:border-blue-500/50'
          }`}
        >
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Reversão ±2σ</span>
            <TrendingDown className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-1.5 text-2xl font-bold font-mono text-slate-900 dark:text-white">
            {summary.reverts}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {filter === 'REVERT' ? 'Filtro ativo (clique p/ limpar)' : 'Clique para filtrar reversões'}
          </div>
        </button>

        <button
          type="button"
          onClick={() => setFilter('ALL')}
          className="text-left rounded-2xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#252223] p-4 transition shadow-sm hover:border-slate-400"
        >
          <div className="text-xs text-slate-500 dark:text-slate-400">Mercado Neutro</div>
          <div className="mt-1.5 text-2xl font-bold font-mono text-slate-900 dark:text-white">
            {summary.neutrals}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {rows.length} de {MAX_MONITORED_SYMBOLS} ativos monitorados
          </div>
        </button>

        <div className="rounded-2xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#252223] p-4 shadow-sm">
          <div className="text-xs text-slate-500 dark:text-slate-400">Viés da Cesta</div>
          <div
            className={`mt-1.5 text-2xl font-bold font-mono ${
              basketPositive
                ? 'text-emerald-600 dark:text-emerald-400'
                : basketNegative
                  ? 'text-rose-600 dark:text-rose-400'
                  : 'text-slate-700 dark:text-slate-300'
            }`}
          >
            {formatSignedPercent(basketBias, 1, true)}
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {basketPositive ? 'Viés Comprador' : basketNegative ? 'Viés Vendedor' : 'Equilíbrio Neutro'}
          </div>
        </div>
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Matriz matemática — VWAP, Bandas (±2σ) e Z-Score</CardTitle>
              <CardDescription>
                Ativos em tendência e reversão aparecem no topo. Limite seguro de {MAX_MONITORED_SYMBOLS} ativos simultâneos na API cTrader.
              </CardDescription>
            </div>

            {/* Filtros */}
            <div className="flex flex-wrap items-center gap-1.5">
              {(
                [
                  { id: 'ALL', label: `Todos (${rows.length})` },
                  { id: 'TREND', label: `Em Tendência (${summary.trends})` },
                  { id: 'REVERT', label: `Reversão (${summary.reverts})` },
                  { id: 'BOTS', label: 'Meus Robôs' },
                ] as const
              ).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setFilter(item.id)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition border ${
                    filter === item.id
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Gestão rápida de ativos monitorados + presets */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 dark:border-slate-800/80">
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              <span className="text-slate-500 dark:text-slate-400 font-medium mr-1">Carregar grupo:</span>
              <button
                type="button"
                disabled={saving}
                onClick={() => applyPreset('MAIN')}
                className="rounded-md border border-slate-200 dark:border-slate-700 px-2 py-1 font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Principais
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => applyPreset('INDICES')}
                className="rounded-md border border-slate-200 dark:border-slate-700 px-2 py-1 font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Índices (US100)
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => applyPreset('FOREX')}
                className="rounded-md border border-slate-200 dark:border-slate-700 px-2 py-1 font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Forex
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => applyPreset('METALS')}
                className="rounded-md border border-slate-200 dark:border-slate-700 px-2 py-1 font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Metais
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => applyPreset('CRYPTO')}
                className="rounded-md border border-slate-200 dark:border-slate-700 px-2 py-1 font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cripto
              </button>
              {bots.length > 0 && (
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => applyPreset('BOTS_ONLY')}
                  className="rounded-md border border-slate-200 dark:border-slate-700 px-2 py-1 font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Só Meus Robôs
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <select
                aria-label="Adicionar ativo para monitorar"
                value={selectedToAdd}
                onChange={(e) => setSelectedToAdd(e.target.value)}
                disabled={saving || activeSymbols.length >= MAX_MONITORED_SYMBOLS}
                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-2.5 py-1 text-xs font-mono text-slate-800 dark:text-slate-200 max-w-[200px]"
              >
                <option value="">
                  {activeSymbols.length >= MAX_MONITORED_SYMBOLS
                    ? `Limite ${MAX_MONITORED_SYMBOLS}/${MAX_MONITORED_SYMBOLS} atingido`
                    : '+ Adicionar ativo da cTrader'}
                </option>
                {availableToAdd.map((s) => (
                  <option key={s.name} value={s.name}>
                    {formatSymbolDisplay(s.name, symbolCatalog)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={saving || !selectedToAdd}
                onClick={handleAddSymbol}
                className="inline-flex items-center gap-1 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-2.5 py-1 text-xs font-semibold text-white"
              >
                <Plus className="h-3.5 w-3.5" />
                Incluir
              </button>
            </div>
          </div>
        </CardHeader>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950/40">
              <tr>
                <th className="px-4 py-3">Ativo</th>
                <th className="px-4 py-3 text-right">Preço</th>
                <th className="px-4 py-3 text-right">VWAP</th>
                <th className="px-4 py-3 text-right">Distância (σ)</th>
                <th className="px-4 py-3">Força (Z / Deseq.)</th>
                <th className="px-4 py-3">Regime</th>
                <th className="px-4 py-3">Sinal</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500 font-sans">
                    {rows.length === 0
                      ? 'Aguardando cotações da cTrader para preencher a matriz.'
                      : 'Nenhum ativo corresponde ao filtro selecionado.'}
                  </td>
                </tr>
              ) : (
                filteredRows.map((s) => {
                  const zVal = Number(s.zscore || 0)
                  const imbVal = Number(s.imbalance || 0)
                  const distSig = Number(s.sigma_distance || 0)
                  const zPos = isFiniteNumber(s.zscore) && zVal >= 0
                  const imbPos = isFiniteNumber(s.imbalance) && imbVal >= 0
                  const forcePct = Math.min(100, Math.round((Math.abs(zVal) / 2.5) * 100))
                  const botInfo = botCountsBySymbol[s.symbol]
                  const canRemove = activeSymbols.includes(s.symbol) && !botInfo?.total
                  const sigStr = String(s.signal || 'WAIT')
                  const isBuySig = sigStr.includes('BUY')
                  const isSellSig = sigStr.includes('SELL')

                  return (
                    <tr key={s.symbol} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-sans">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900 dark:text-white">
                            {formatSymbolDisplay(s.symbol, symbolCatalog)}
                          </span>
                          {botInfo && botInfo.total > 0 && (
                            <span
                              title={`${botInfo.active} ativo(s) de ${botInfo.total}`}
                              className="inline-flex items-center gap-1 rounded-md bg-blue-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 dark:text-blue-300"
                            >
                              <Bot className="h-3 w-3" />
                              {botInfo.active > 0 ? `${botInfo.active} ativo(s)` : `${botInfo.total}`}
                            </span>
                          )}
                          {canRemove && (
                            <button
                              type="button"
                              onClick={() => handleRemoveSymbol(s.symbol)}
                              title={`Remover ${s.symbol} da matriz`}
                              className="rounded p-0.5 text-slate-400 hover:bg-rose-500/10 hover:text-rose-500"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400">
                          -2σ: {formatPrice(s.lower_2, 4)} • +2σ: {formatPrice(s.upper_2, 4)}
                        </div>
                      </td>

                      <td className="px-4 py-3 text-right font-semibold text-slate-900 dark:text-white">
                        {formatPrice(s.price, 4)}
                      </td>

                      <td className="px-4 py-3 text-right text-amber-600 dark:text-amber-300">
                        {formatPrice(s.vwap, 4)}
                      </td>

                      <td className="px-4 py-3 text-right">
                        <span
                          className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                            Math.abs(distSig) >= 2.0
                              ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                              : distSig >= 0
                                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                                : 'bg-rose-500/10 text-rose-700 dark:text-rose-300'
                          }`}
                        >
                          {distSig >= 0 ? '+' : ''}
                          {formatNumber(distSig, 2)}σ
                        </span>
                      </td>

                      <td className="px-4 py-3 min-w-[140px]">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className={zPos ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : 'text-rose-600 dark:text-rose-400 font-semibold'}>
                            Z {zVal >= 0 ? '+' : ''}{formatNumber(zVal, 2)}
                          </span>
                          <span className={imbPos ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                            {formatPercent(s.imbalance, 0, true)}
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 w-full rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              Math.abs(zVal) >= 1.8
                                ? zPos
                                  ? 'bg-emerald-500'
                                  : 'bg-rose-500'
                                : 'bg-slate-400 dark:bg-slate-500'
                            }`}
                            style={{ width: `${forcePct}%` }}
                          />
                        </div>
                      </td>

                      <td className="px-4 py-3 font-sans">
                        <span
                          className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium ${
                            s.regime === 'INSTITUTIONAL_TREND_UP'
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                              : s.regime === 'INSTITUTIONAL_TREND_DOWN'
                                ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                                : s.regime === 'HFT_MEAN_REVERSION'
                                  ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                          }`}
                        >
                          {formatRegime(s.regime)}
                        </span>
                      </td>

                      <td className="px-4 py-3 font-sans">
                        <span
                          className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                            isBuySig
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                              : isSellSig
                                ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200'
                          }`}
                        >
                          {formatSignal(s.signal)}
                        </span>
                      </td>

                      <td className="px-4 py-3 text-right font-sans">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => onOpenChart(s.symbol)}
                            title={`Abrir gráfico de ${s.symbol}`}
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 px-2 py-1 text-[11px] font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            <LineChart className="h-3 w-3" />
                            Gráfico
                          </button>
                          <button
                            type="button"
                            onClick={() => onCreateBotForSymbol(s.symbol)}
                            title={`Criar robô para ${s.symbol}`}
                            className="inline-flex items-center gap-1 rounded-lg bg-blue-600 hover:bg-blue-500 px-2 py-1 text-[11px] font-semibold text-white"
                          >
                            <Plus className="h-3 w-3" />
                            Robô
                          </button>
                        </div>
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
  )
}

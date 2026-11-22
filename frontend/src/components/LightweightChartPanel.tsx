import { useEffect, useMemo, useRef } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, LineStyle, Time } from 'lightweight-charts'
import { Activity, AlertCircle } from 'lucide-react'
import { BrokerSymbol, ChartPoint, SymbolState } from '../types'
import { ThemeMode } from '../hooks/useTheme'
import { formatNumber, formatPrice, formatSymbolDisplay, isFiniteNumber, sanitizeChartPoints } from '../utils/formatters'

interface Props {
  symbol: string
  availableSymbols: string[]
  symbolCatalog?: BrokerSymbol[]
  timeframe?: string
  onSelectTimeframe?: (tf: string) => void
  onSelectSymbol: (sym: string) => void
  points: ChartPoint[]
  symbolState?: SymbolState
  theme: ThemeMode
  loading?: boolean
  error?: string | null
}

function getChartThemeOptions(theme: ThemeMode) {
  if (theme === 'light') {
    return {
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#475569',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(226, 232, 240, 0.8)' },
        horzLines: { color: 'rgba(226, 232, 240, 0.8)' },
      },
      rightPriceScale: {
        borderColor: '#e2e8f0',
      },
      timeScale: {
        borderColor: '#e2e8f0',
        timeVisible: true,
        secondsVisible: true,
      },
      crosshair: {
        vertLine: { color: 'rgba(37, 99, 235, 0.35)', labelBackgroundColor: '#1e293b' },
        horzLine: { color: 'rgba(37, 99, 235, 0.35)', labelBackgroundColor: '#1e293b' },
      },
    }
  }

  return {
    layout: {
      background: { type: ColorType.Solid, color: '#111827' },
      textColor: '#94a3b8',
      fontFamily: 'JetBrains Mono, monospace',
    },
    grid: {
      vertLines: { color: 'rgba(30, 41, 59, 0.55)' },
      horzLines: { color: 'rgba(30, 41, 59, 0.55)' },
    },
    rightPriceScale: {
      borderColor: '#1e293b',
    },
    timeScale: {
      borderColor: '#1e293b',
      timeVisible: true,
      secondsVisible: true,
    },
    crosshair: {
      vertLine: { color: 'rgba(59, 130, 246, 0.45)', labelBackgroundColor: '#1e293b' },
      horzLine: { color: 'rgba(59, 130, 246, 0.45)', labelBackgroundColor: '#1e293b' },
    },
  }
}

export function LightweightChartPanel({
  symbol,
  availableSymbols,
  symbolCatalog,
  timeframe = 'TICKS',
  onSelectTimeframe,
  onSelectSymbol,
  points,
  symbolState,
  theme,
  loading = false,
  error = null,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const priceSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const upperSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const lowerSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  const cleanPoints = useMemo(() => sanitizeChartPoints(points), [points])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      ...getChartThemeOptions(theme),
      height: 320,
    })

    const priceSeries = chart.addAreaSeries({
      lineColor: '#38bdf8',
      topColor: 'rgba(56, 189, 248, 0.25)',
      bottomColor: 'rgba(56, 189, 248, 0.01)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    })
    const vwapSeries = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    })
    const upperSeries = chart.addLineSeries({
      color: '#f43f5e',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    })
    const lowerSeries = chart.addLineSeries({
      color: '#10b981',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    })

    chartRef.current = chart
    priceSeriesRef.current = priceSeries
    vwapSeriesRef.current = vwapSeries
    upperSeriesRef.current = upperSeries
    lowerSeriesRef.current = lowerSeries

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions(getChartThemeOptions(theme))
    }
  }, [theme])

  useEffect(() => {
    if (
      !priceSeriesRef.current ||
      !vwapSeriesRef.current ||
      !upperSeriesRef.current ||
      !lowerSeriesRef.current
    ) {
      return
    }
    priceSeriesRef.current.setData(cleanPoints.map((p) => ({ time: p.time as Time, value: p.price })))
    vwapSeriesRef.current.setData(cleanPoints.map((p) => ({ time: p.time as Time, value: p.vwap })))
    upperSeriesRef.current.setData(cleanPoints.map((p) => ({ time: p.time as Time, value: p.upper_2 })))
    lowerSeriesRef.current.setData(cleanPoints.map((p) => ({ time: p.time as Time, value: p.lower_2 })))
    if (cleanPoints.length > 0) {
      chartRef.current?.timeScale().fitContent()
    }
  }, [cleanPoints])

  const zVal = symbolState?.zscore
  const zColor = isFiniteNumber(zVal)
    ? zVal >= 0
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-rose-600 dark:text-rose-400'
    : 'text-slate-500 dark:text-slate-400'

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#111827] shadow-sm dark:shadow-xl dark:shadow-black/30 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800/80 px-5 py-3.5 bg-slate-50/70 dark:bg-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                Terminal Gráfico ao Vivo • {symbol}
              </h2>
              <span className="rounded-md bg-amber-500/10 border border-amber-500/25 px-2 py-0.5 text-[11px] font-mono text-amber-700 dark:text-amber-300">
                VWAP + Bandas ±2σ
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Cotações em tempo real da Deriv com VWAP ponderada por volume e bandas de desvio padrão
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="hidden md:flex items-center gap-3 text-xs font-mono">
            <span className="text-slate-500 dark:text-slate-400">
              P: <strong className="text-sky-600 dark:text-sky-300">{formatPrice(symbolState?.price, 4)}</strong>
            </span>
            <span className="text-slate-500 dark:text-slate-400">
              VWAP: <strong className="text-amber-600 dark:text-amber-300">{formatPrice(symbolState?.vwap, 4)}</strong>
            </span>
            <span className="text-slate-500 dark:text-slate-400">
              Z: <strong className={zColor}>{formatNumber(symbolState?.zscore, 2)}</strong>
            </span>
            <span className="rounded-md bg-slate-100 dark:bg-slate-800 px-2 py-1 text-[11px] text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700">
              {symbolState?.signal || 'WAIT'}
            </span>
          </div>

          <select
            aria-label="Selecionar ativo do gráfico"
            value={symbol}
            onChange={(e) => onSelectSymbol(e.target.value)}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-mono text-slate-900 dark:text-white focus:border-blue-500 focus:outline-none"
          >
            {availableSymbols.map((s) => (
              <option key={s} value={s}>
                {formatSymbolDisplay(s, symbolCatalog)}
              </option>
            ))}
          </select>

          {onSelectTimeframe && (
            <div className="flex items-center gap-1 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-0.5">
              {(['TICKS', 'M1', 'M5', 'M15', 'H1'] as const).map((tf) => (
                <button
                  key={tf}
                  type="button"
                  onClick={() => onSelectTimeframe(tf)}
                  className={`rounded-lg px-2 py-1 text-[11px] font-mono font-semibold transition ${
                    timeframe === tf
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-800'
                  }`}
                >
                  {tf === 'TICKS' ? 'Tick' : tf}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="relative px-2 py-2">
        {error && (
          <div className="mx-3 my-2 flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {loading && cleanPoints.length === 0 && (
          <div className="h-[320px] flex items-center justify-center text-xs font-mono text-slate-400">
            Carregando série de ticks da Deriv...
          </div>
        )}
        <div
          ref={containerRef}
          className={`w-full ${loading && cleanPoints.length === 0 ? 'hidden' : 'block'}`}
        />
        {!loading && cleanPoints.length === 0 && !error && (
          <div className="h-[120px] flex items-center justify-center text-xs text-slate-500 dark:text-slate-400">
            Aguardando ticks de {symbol} para plotar VWAP e Bandas ±2σ.
          </div>
        )}
        <div className="flex flex-wrap items-center gap-4 px-3 pt-2 pb-1 text-[11px] text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-sky-400" /> Preço Deriv
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-amber-400" /> VWAP
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-rose-500" /> Banda +2σ
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500" /> Banda -2σ
          </span>
        </div>
      </div>
    </section>
  )
}

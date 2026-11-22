import { useEffect, useRef } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, LineStyle, Time } from 'lightweight-charts'
import { Activity } from 'lucide-react'
import { ChartPoint, SymbolState } from '../types'

interface Props {
  symbol: string
  availableSymbols: string[]
  onSelectSymbol: (sym: string) => void
  points: ChartPoint[]
  symbolState?: SymbolState
}

export function LightweightChartPanel({
  symbol,
  availableSymbols,
  onSelectSymbol,
  points,
  symbolState,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const priceSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const upperSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const lowerSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#0b111e' },
        textColor: '#94a3b8',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.45)' },
        horzLines: { color: 'rgba(30, 41, 59, 0.45)' },
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
        vertLine: { color: 'rgba(245, 158, 11, 0.4)', labelBackgroundColor: '#1e293b' },
        horzLine: { color: 'rgba(245, 158, 11, 0.4)', labelBackgroundColor: '#1e293b' },
      },
      height: 310,
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
    if (!points.length || !priceSeriesRef.current || !vwapSeriesRef.current || !upperSeriesRef.current || !lowerSeriesRef.current) {
      return
    }
    priceSeriesRef.current.setData(points.map((p) => ({ time: p.time as Time, value: p.price })))
    vwapSeriesRef.current.setData(points.map((p) => ({ time: p.time as Time, value: p.vwap })))
    upperSeriesRef.current.setData(points.map((p) => ({ time: p.time as Time, value: p.upper_2 })))
    lowerSeriesRef.current.setData(points.map((p) => ({ time: p.time as Time, value: p.lower_2 })))
    chartRef.current?.timeScale().fitContent()
  }, [points])

  return (
    <section className="rounded-2xl border border-slate-800/80 bg-[#0b111e]/95 shadow-xl shadow-black/40 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 px-5 py-3.5 bg-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-white">Terminal Gráfico ao Vivo • Lightweight Charts</h2>
              <span className="rounded-md bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 text-[11px] font-mono text-amber-300">
                VWAP + Bandas ±2σ
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Cotações em tempo real da Deriv com VWAP ponderada por volume e bandas de desvio padrão
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {symbolState && (
            <div className="hidden sm:flex items-center gap-3 text-xs font-mono">
              <span className="text-slate-400">
                P: <strong className="text-sky-300">{symbolState.price.toFixed(4)}</strong>
              </span>
              <span className="text-slate-400">
                VWAP: <strong className="text-amber-300">{symbolState.vwap.toFixed(4)}</strong>
              </span>
              <span className="text-slate-400">
                Z: <strong className={symbolState.zscore >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{symbolState.zscore.toFixed(2)}</strong>
              </span>
              <span className="rounded-md bg-slate-800 px-2 py-1 text-[11px] text-slate-200">
                {symbolState.signal}
              </span>
            </div>
          )}

          <select
            value={symbol}
            onChange={(e) => onSelectSymbol(e.target.value)}
            className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-mono text-white focus:border-amber-500 focus:outline-none"
          >
            {availableSymbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="relative px-2 py-2">
        <div ref={containerRef} className="w-full" />
        <div className="flex flex-wrap items-center gap-4 px-3 pt-2 pb-1 text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sky-400" /> Preço Deriv</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-400" /> VWAP</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-rose-500" /> Banda +2σ</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Banda -2σ</span>
        </div>
      </div>
    </section>
  )
}

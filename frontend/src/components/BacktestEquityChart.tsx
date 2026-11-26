import { useEffect, useRef } from 'react'
import { ColorType, createChart, IChartApi, LineStyle, Time } from 'lightweight-charts'
import { BacktestEquityPoint } from '../types'
import { ThemeMode } from '../hooks/useTheme'

interface Props {
  points: BacktestEquityPoint[]
  initialCapital: number
  theme: ThemeMode
}

export function BacktestEquityChart({ points, initialCapital, theme }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el || !points.length) return

    const isLight = theme === 'light'
    const chart = createChart(el, {
      height: 240,
      layout: {
        background: { type: ColorType.Solid, color: isLight ? '#ffffff' : '#252223' },
        textColor: isLight ? '#595355' : '#b5b0b2',
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: isLight ? 'rgba(226, 224, 225, 0.8)' : 'rgba(59, 54, 56, 0.6)' },
        horzLines: { color: isLight ? 'rgba(226, 224, 225, 0.8)' : 'rgba(59, 54, 56, 0.6)' },
      },
      rightPriceScale: {
        borderColor: isLight ? '#e2e0e1' : '#3b3638',
      },
      timeScale: {
        borderColor: isLight ? '#e2e0e1' : '#3b3638',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: 'rgba(135, 194, 69, 0.5)', labelBackgroundColor: '#252223' },
        horzLine: { color: 'rgba(135, 194, 69, 0.5)', labelBackgroundColor: '#252223' },
      },
    })

    const lastEq = points[points.length - 1]?.equity ?? initialCapital
    const isProfit = lastEq >= initialCapital
    const lineColor = isProfit ? '#87c245' : '#f43f5e'

    const areaSeries = chart.addAreaSeries({
      lineColor,
      topColor: isProfit ? 'rgba(135, 194, 69, 0.30)' : 'rgba(244, 63, 94, 0.25)',
      bottomColor: isProfit ? 'rgba(135, 194, 69, 0.02)' : 'rgba(244, 63, 94, 0.02)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    })

    const baselineSeries = chart.addLineSeries({
      color: isLight ? '#9e999b' : '#767072',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
    })

    const sorted = [...points].sort((a, b) => a.time - b.time)
    const deduped: { time: Time; value: number }[] = []
    let prevT = -1
    for (const p of sorted) {
      const t = p.time <= prevT ? prevT + 1 : p.time
      prevT = t
      deduped.push({ time: t as Time, value: Number(p.equity) })
    }

    areaSeries.setData(deduped)
    baselineSeries.setData(deduped.map((d) => ({ time: d.time, value: initialCapital })))
    chart.timeScale().fitContent()
    chartRef.current = chart

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [points, initialCapital, theme])

  if (!points.length) {
    return (
      <div className="flex h-[240px] items-center justify-center rounded-xl border border-dashed border-slate-300 dark:border-slate-700 text-xs text-slate-500">
        Sem pontos suficientes para desenhar a curva de evolução.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] p-3">
      <div className="mb-2 flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400">
        <span className="font-sans font-semibold text-xs text-slate-700 dark:text-slate-200">
          Curva de Evolução do Patrimônio
        </span>
        <span>
          Capital inicial: ${initialCapital.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  )
}

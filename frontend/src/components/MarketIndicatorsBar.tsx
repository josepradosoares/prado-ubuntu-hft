import { Activity, Wifi, WifiOff } from 'lucide-react'
import { BrokerSymbol, SymbolState } from '../types'
import { formatNumber, formatPercent, formatPrice, formatSymbolDisplay, isFiniteNumber } from '../utils/formatters'

interface MarketIndicatorsBarProps {
  symbol: string
  symbolCatalog?: BrokerSymbol[]
  symbolState?: SymbolState
  connected: boolean
}

export function MarketIndicatorsBar({ symbol, symbolCatalog, symbolState, connected }: MarketIndicatorsBarProps) {
  const zVal = symbolState?.zscore
  const imbVal = symbolState?.imbalance

  const zColor = isFiniteNumber(zVal)
    ? zVal >= 0
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-rose-600 dark:text-rose-400'
    : 'text-slate-500 dark:text-slate-400'

  const imbColor = isFiniteNumber(imbVal)
    ? imbVal >= 0
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-rose-600 dark:text-rose-400'
    : 'text-slate-500 dark:text-slate-400'

  const items = [
    {
      label: 'Ativo Selecionado',
      value: formatSymbolDisplay(symbol, symbolCatalog),
      valueClass: 'text-slate-900 dark:text-white font-sans',
    },
    {
      label: 'Preço Atual',
      value: formatPrice(symbolState?.price, 4),
      valueClass: 'text-sky-600 dark:text-sky-300 font-mono',
    },
    {
      label: 'VWAP',
      value: formatPrice(symbolState?.vwap, 4),
      valueClass: 'text-amber-600 dark:text-amber-300 font-mono',
    },
    {
      label: 'Z-Score',
      value: formatNumber(zVal, 2),
      valueClass: `${zColor} font-mono`,
    },
    {
      label: 'Imbalance',
      value: formatPercent(imbVal, 1, true),
      valueClass: `${imbColor} font-mono`,
    },
    {
      label: 'Regime de Mercado',
      value: symbolState?.regime || '--',
      valueClass: 'text-slate-800 dark:text-slate-200 text-xs font-medium truncate',
    },
  ]

  return (
    <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-2xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#111827] px-4 py-3 shadow-sm"
        >
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            {item.label}
          </div>
          <div className={`mt-1 text-sm font-bold ${item.valueClass}`} title={item.value}>
            {item.value}
          </div>
        </div>
      ))}

      <div className="rounded-2xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#111827] px-4 py-3 shadow-sm">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Status Conexão
        </div>
        <div className="mt-1 flex items-center gap-1.5 text-xs font-semibold">
          {connected ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
              <span className="text-emerald-600 dark:text-emerald-400">Online</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-rose-500 shrink-0" />
              <span className="text-rose-600 dark:text-rose-400">Offline</span>
            </>
          )}
          <Activity className="h-3 w-3 text-slate-400 ml-auto shrink-0" />
        </div>
      </div>
    </section>
  )
}

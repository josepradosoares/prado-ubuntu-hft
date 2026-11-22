import type { ChartPoint, SymbolState } from '../types'

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function formatNumber(
  value: number | null | undefined,
  decimals = 2,
  fallback = '--',
): string {
  if (!isFiniteNumber(value)) {
    return fallback
  }
  return value.toFixed(decimals)
}

export function formatPrice(
  value: number | null | undefined,
  decimals = 4,
  fallback = '--',
): string {
  return formatNumber(value, decimals, fallback)
}

export function formatSignedNumber(
  value: number | null | undefined,
  decimals = 2,
  fallback = '--',
): string {
  if (!isFiniteNumber(value)) {
    return fallback
  }
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}`
}

export function formatPercent(
  value: number | null | undefined,
  decimals = 1,
  isRatio = true,
  fallback = '--',
): string {
  if (!isFiniteNumber(value)) {
    return fallback
  }
  const scaled = isRatio ? value * 100 : value
  if (!Number.isFinite(scaled)) {
    return fallback
  }
  return `${scaled.toFixed(decimals)}%`
}

export function formatSignedPercent(
  value: number | null | undefined,
  decimals = 1,
  isRatio = true,
  fallback = '--',
): string {
  if (!isFiniteNumber(value)) {
    return fallback
  }
  const scaled = isRatio ? value * 100 : value
  if (!Number.isFinite(scaled)) {
    return fallback
  }
  const sign = scaled > 0 ? '+' : ''
  return `${sign}${scaled.toFixed(decimals)}%`
}

export function formatCurrency(
  value: number | null | undefined,
  currency = 'USD',
  decimals = 2,
  fallback = '--',
): string {
  if (!isFiniteNumber(value)) {
    return fallback
  }
  return `${currency} ${value.toLocaleString('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

export function sanitizeChartPoints(raw: unknown): ChartPoint[] {
  if (!Array.isArray(raw)) {
    return []
  }
  const byTime = new Map<number, ChartPoint>()
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const p = item as Partial<ChartPoint>
    if (
      isFiniteNumber(p.time) &&
      isFiniteNumber(p.price) &&
      isFiniteNumber(p.vwap) &&
      isFiniteNumber(p.upper_2) &&
      isFiniteNumber(p.lower_2)
    ) {
      byTime.set(p.time, {
        time: p.time,
        price: p.price,
        vwap: p.vwap,
        upper_2: p.upper_2,
        lower_2: p.lower_2,
      })
    }
  }
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time)
}

export function hasValidSymbolMetrics(state?: Partial<SymbolState> | null): boolean {
  if (!state) return false
  return isFiniteNumber(state.price) || isFiniteNumber(state.vwap)
}

const FRIENDLY_SYMBOL_NAMES: Record<string, string> = {
  R_10: 'Volatility 10 Index',
  R_25: 'Volatility 25 Index',
  R_50: 'Volatility 50 Index',
  R_75: 'Volatility 75 Index',
  R_100: 'Volatility 100 Index',
  '1HZ10V': 'Volatility 10 (1s) Index',
  '1HZ25V': 'Volatility 25 (1s) Index',
  '1HZ50V': 'Volatility 50 (1s) Index',
  '1HZ75V': 'Volatility 75 (1s) Index',
  '1HZ100V': 'Volatility 100 (1s) Index',
  stpRNG: 'Step Index',
  BOOM500: 'Boom 500 Index',
  BOOM1000: 'Boom 1000 Index',
  CRASH500: 'Crash 500 Index',
  CRASH1000: 'Crash 1000 Index',
  frxXAUUSD: 'Gold/USD',
  frxXAGUSD: 'Silver/USD',
  cryBTCUSD: 'BTC/USD',
  cryETHUSD: 'ETH/USD',
  OTC_SP500: 'US 500',
  OTC_NDX: 'US Tech 100',
  OTC_DJI: 'Wall Street 30',
  OTC_HSI: 'Hong Kong 50',
  OTC_AS51: 'Australia 200',
  OTC_N225: 'Japan 225',
  OTC_GDAXI: 'Germany 40',
  OTC_FTSE: 'UK 100',
  OTC_FCHI: 'France 40',
  OTC_SX5E: 'Euro 50',
}

export function formatSymbolDisplay(
  symbol: string,
  catalog?: Array<{ name: string; description?: string }>,
): string {
  if (!symbol) return '--'
  if (symbol === 'ALL') return 'TODOS OS ATIVOS'
  const found = catalog?.find((item) => item.name === symbol)
  const desc = found?.description?.trim()
  if (desc && desc.toLowerCase() !== symbol.toLowerCase() && !desc.startsWith('Ativo ')) {
    return desc
  }
  if (FRIENDLY_SYMBOL_NAMES[symbol]) {
    return FRIENDLY_SYMBOL_NAMES[symbol]
  }
  if ((symbol.startsWith('frx') || symbol.startsWith('cry')) && symbol.length === 9) {
    return `${symbol.slice(3, 6)}/${symbol.slice(6, 9)}`
  }
  return symbol
}

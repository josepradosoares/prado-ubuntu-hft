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
  decimals = 5,
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
  EURUSD: 'EUR/USD',
  GBPUSD: 'GBP/USD',
  USDJPY: 'USD/JPY',
  AUDUSD: 'AUD/USD',
  USDCAD: 'USD/CAD',
  USDCHF: 'USD/CHF',
  NZDUSD: 'NZD/USD',
  EURJPY: 'EUR/JPY',
  GBPJPY: 'GBP/JPY',
  XAUUSD: 'Gold/USD (XAUUSD)',
  XAGUSD: 'Silver/USD (XAGUSD)',
  BTCUSD: 'BTC/USD',
  ETHUSD: 'ETH/USD',
  US500: 'S&P 500 (US500)',
  SPX500: 'S&P 500 (SPX500)',
  US100: 'Nasdaq 100 (US100)',
  USTEC: 'Nasdaq 100 (USTEC)',
  NAS100: 'Nasdaq 100 (NAS100)',
  'US100.cash': 'Nasdaq 100 (US100)',
  US30: 'Dow Jones 30 (US30)',
  DJ30: 'Dow Jones 30 (DJ30)',
  DE40: 'DAX 40 (DE40)',
  GER40: 'DAX 40 (GER40)',
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
  return symbol
}

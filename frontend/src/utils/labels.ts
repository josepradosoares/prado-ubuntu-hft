const REGIME_LABELS: Record<string, string> = {
  HFT_MEAN_REVERSION: 'Reversão à Média',
  INSTITUTIONAL_TREND_UP: 'Tendência de Alta',
  INSTITUTIONAL_TREND_DOWN: 'Tendência de Baixa',
  NEUTRAL: 'Mercado Neutro',
  AGUARDANDO: 'Aguardando dados',
}

const SIGNAL_LABELS: Record<string, string> = {
  BUY_FLOW: 'Fluxo Comprador',
  SELL_FLOW: 'Fluxo Vendedor',
  BUY_REVERT_VWAP: 'Compra (Reversão VWAP)',
  SELL_REVERT_VWAP: 'Venda (Reversão VWAP)',
  BUY_NEWS: 'Compra (Notícias)',
  BUY_NEWS_HYBRID: 'Compra (Notícias)',
  SELL_NEWS: 'Venda (Notícias)',
  SELL_NEWS_HYBRID: 'Venda (Notícias)',
  BUY: 'Compra',
  SELL: 'Venda',
  WAIT: 'Aguardando',
  WAIT_CORRELATION_BLOCK: 'Bloqueado por Correlação',
  AUTO_PAUSED: 'Automático Pausado',
  PAUSED_MANUAL: 'Pausado Manualmente',
  PAUSED_MAX_LOSS: 'Pausado (Limite de Perda)',
  PAUSED_NEWS: 'Pausado por Notícia',
  RESUMED_NEWS: 'Retomado após Notícia',
  STOPPED: 'Parado',
  STOPPED_MANUAL: 'Parado',
  RISK_LOCKED: 'Trava de Risco Diária',
  RATE_LIMITED: 'Limite da Corretora',
  ACCOUNT_MISMATCH: 'Conta Incompatível',
  UNAVAILABLE: 'Ativo Indisponível',
  NEWS_TECH_EXIT: 'Saída por Notícia',
  HOLD_NEWS_PROFIT: 'Mantendo Posição',
}

const TRADE_SIDE_LABELS: Record<string, string> = {
  BUY: 'Compra',
  SELL: 'Venda',
}

const EXIT_REASON_LABELS: Record<string, string> = {
  TP: 'Alvo (TP)',
  SL: 'Stop Loss',
  EOD: 'Fim do Período',
  WIN: 'Ganho',
  LOSS: 'Perda',
}

const OPERATION_MODE_LABELS: Record<string, string> = {
  BOTH: 'Tendência e Reversão',
  TREND_ONLY: 'Somente Tendência',
  REVERT_ONLY: 'Somente Reversão',
  GRID_LINEAR: 'Grade Linear',
  CUSTOM: 'Personalizado',
}

const DATA_SOURCE_LABELS: Record<string, string> = {
  CTRADER_REAL: 'Dados Reais cTrader',
  SIMULATION: 'Simulação',
  SIMULATION_FALLBACK: 'Simulação',
  MISTO: 'Misto (Real + Simulação)',
}

const BACKEND_NAME_LABELS: Record<string, string> = {
  CTRADER_CLOUD: 'cTrader Nuvem',
  CTRADER_LIVE_API: 'cTrader Nuvem (Porta 5036)',
  CTRADER_LIVE: 'cTrader Nuvem',
  CTRADER_DEMO: 'cTrader Nuvem',
  CTRADER_DISCONNECTED: 'Desconectado',
  SIMULATION: 'Simulador Local',
  SIMULATION_FEED: 'Simulador Local',
}

const LOG_MODULE_LABELS: Record<string, string> = {
  CTRADER_WS: 'Conexão cTrader',
  CTRADER_CONFIG: 'Configuração',
  CTRADER_VAULT: 'Contas cTrader',
  BOT_FLEET: 'Frota de Robôs',
  BOT_EXEC: 'Execução',
  BOT_NEWS_EXEC: 'Execução Notícias',
  BOT_NEWS_EXIT: 'Saída Notícias',
  BOT_RISK_GUARD: 'Proteção de Risco',
  RISK_GUARD: 'Proteção de Risco',
  BOT_RATE_LIMIT: 'Limite da API',
  BOT_SYMBOL_UNAVAILABLE: 'Ativo Indisponível',
  BOT_ERROR: 'Erro no Robô',
  NEWS_SCOUT: 'Notícias',
  NEWS_GUARD: 'Notícias',
  NEWS_FEED: 'Notícias',
  BACKTEST: 'Backtest',
  CONFIG: 'Sistema',
  TEMPLATE: 'Modelos',
  POSITION_CLOSE: 'Fechamento',
  SUPABASE_SYNC: 'Sincronização',
}

const PERIOD_LABELS: Record<string, string> = {
  CUSTOM: 'Manual',
  '1D': '1 Dia',
  '1W': '1 Semana',
  '1M': '1 Mês',
  '1Y': '1 Ano',
  '2Y': '2 Anos',
  ALL_TIME: '5 Anos',
}

const TIMEFRAME_LABELS: Record<string, string> = {
  TICKS: 'Tick a Tick',
  M1: '1 min',
  M5: '5 min',
  M15: '15 min',
  M30: '30 min',
  H1: '1 hora',
  H4: '4 horas',
  D1: '1 dia',
  MN1: '1 mês',
}

const NEWS_IMPACT_LABELS: Record<string, string> = {
  HIGH: 'Alto Impacto',
  MEDIUM: 'Médio Impacto',
  LOW: 'Baixo Impacto',
}

function humanizeFallback(raw: string): string {
  const clean = raw.trim()
  if (!clean) return '--'
  if (!/^[A-Z0-9_]+$/.test(clean)) return clean
  return clean
    .toLowerCase()
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function lookupLabel(
  code: string | null | undefined,
  map: Record<string, string>,
  emptyFallback = '--',
): string {
  const normalized = String(code || '').trim().toUpperCase()
  if (!normalized) return emptyFallback
  if (map[normalized]) return map[normalized]
  return humanizeFallback(String(code || ''))
}

export function formatRegime(code: string | null | undefined): string {
  return lookupLabel(code, REGIME_LABELS, 'Aguardando dados')
}

export function formatSignal(code: string | null | undefined): string {
  return lookupLabel(code, SIGNAL_LABELS, 'Aguardando')
}

export function formatTradeSide(code: string | null | undefined): string {
  return lookupLabel(code, TRADE_SIDE_LABELS)
}

export function formatExitReason(code: string | null | undefined): string {
  return lookupLabel(code, EXIT_REASON_LABELS)
}

export function formatOperationMode(code: string | null | undefined): string {
  return lookupLabel(code, OPERATION_MODE_LABELS)
}

export function formatDataSource(code: string | null | undefined): string {
  return lookupLabel(code, DATA_SOURCE_LABELS, 'Simulação')
}

export function formatBackendName(code: string | null | undefined): string {
  return lookupLabel(code, BACKEND_NAME_LABELS, 'Desconectado')
}

export function formatLogModule(code: string | null | undefined): string {
  return lookupLabel(code, LOG_MODULE_LABELS)
}

export function formatPeriod(code: string | null | undefined): string {
  return lookupLabel(code, PERIOD_LABELS, 'Manual')
}

export function formatTimeframe(code: string | null | undefined): string {
  return lookupLabel(code, TIMEFRAME_LABELS, 'Tick a Tick')
}

export function formatNewsImpact(code: string | null | undefined): string {
  return lookupLabel(code, NEWS_IMPACT_LABELS)
}

export interface RateLimitStatus {
  state: string
  cooldown_seconds: number
  ws_per_sec?: number
  historical_per_sec?: number
  last_error?: string
}

export interface AccountSummary {
  backend: string
  connected: boolean
  account_type: string
  account_mode?: string
  connection_state?: string
  auth_state?: string
  data_state?: string
  trading_state?: string
  rate_limit?: RateLimitStatus
  masked_client_id?: string
  broker_name?: string
  leverage?: number
  last_tick_at?: number
  active_account_id: string
  login: string
  server: string
  name: string
  currency: string
  balance: number
  equity: number
  profit: number
  daily_realized: number
  daily_gross?: number
  daily_commissions_swap?: number
  daily_trades_count?: number
  daily_win_rate?: number
  daily_source?: 'CTRADER_SERVER' | 'SESSION_MEMORY' | 'SIMULATION' | 'DISCONNECTED' | string
  max_daily_loss_money?: number
  daily_target_money?: number
  margin_free: number
  status_note?: string
}

export interface SymbolState {
  symbol: string
  price: number
  vwap: number
  upper_1: number
  lower_1: number
  upper_2: number
  lower_2: number
  std_dev: number
  sigma_distance: number
  zscore: number
  imbalance: number
  regime: string
  signal: string
}

export interface BotItem {
  bot_id: string
  name: string
  account_id: string
  account_label?: string
  account_type?: string
  symbol: string
  template_id: string
  template_name?: string
  operation_mode: string
  lot_size: number
  window_ticks: number
  zscore_threshold: number
  imbalance_threshold: number
  revert_sigma: number
  sl_sigma_mult: number
  tp_sigma_mult: number
  tp_mode?: 'AUTO' | 'USD' | 'PCT' | 'PIPS' | 'TICKS' | string
  tp_value?: number
  active: boolean
  status?: 'STOPPED' | 'STARTING' | 'RUNNING' | 'PAUSED' | 'ERROR' | 'STOPPING'
  last_error?: string
  trades_executed: number
  last_signal?: string
  last_regime?: string
  grid_direction?: string
  grid_step_points?: number
  grid_tp_points?: number
  max_grid_levels?: number
  loss_guard_enabled?: boolean
  max_loss_usd?: number
  news_assisted?: boolean
  timeframe?: string
  realized_pnl?: number
  floating_pnl?: number
  total_pnl?: number
}

export interface PositionItem {
  ticket: string | number
  symbol: string
  side: string
  volume: number
  price_open: number
  price_current: number
  sl: number
  tp: number
  profit: number
  swap?: number
  commission?: number
  used_margin?: number
  open_timestamp_ms?: number
  open_time_str?: string
  bot_name?: string
  comment?: string
}

export interface DealItem {
  time_str: string
  symbol: string
  side: string
  volume: number
  price_open: number
  price_close: number
  profit: number
  reason?: string
  bot_name?: string
}

export interface LogEvent {
  time: string
  module: string
  message: string
}

export interface NewsFeed {
  feed_id: string
  source: string
  url: string
  default_symbol: string
}

export interface NewsFeedStatus {
  feed_id: string
  source: string
  ok: boolean
  count: number
  error: string
  checked_at: number
}

export interface CuratedNewsSource {
  feed_id: string
  source: string
  url: string
  default_symbol: string
  language?: string
  category?: string
}

export interface EconomicCalendarEvent {
  id: string
  title: string
  currency: string
  impact: 'HIGH' | 'MEDIUM' | 'LOW' | 'HOLIDAY' | string
  timestamp: number
  time_str: string
  forecast: string
  previous: string
  is_upcoming: boolean
  countdown: string
}

export interface EconomicCalendarSnapshot {
  events: EconomicCalendarEvent[]
  last_fetch_at: number
  last_error: string
  status_note?: string
  next_high_impact: EconomicCalendarEvent | null
}

export interface NewsItem {
  id: string
  title: string
  source: string
  link: string
  published_at: string
  symbol: string
  impact: 'HIGH' | 'MEDIUM' | 'LOW'
  bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  score: number
  is_macro_usd?: boolean
}

export interface NewsSnapshot {
  enabled: boolean
  pause_grid_on_high_impact: boolean
  auto_trade_enabled: boolean
  lot_size: number
  poll_interval_sec?: number
  last_scan_at: number
  last_error?: string
  feeds?: NewsFeed[]
  feed_status?: NewsFeedStatus[]
  curated_catalog?: CuratedNewsSource[]
  items: NewsItem[]
  summary_by_symbol: Record<string, { symbol: string; count: number; high_impact: number; avg_score: number; bias: string }>
  calendar?: EconomicCalendarSnapshot
}

export interface Snapshot {
  timestamp: string
  auto_trading_enabled: boolean
  basket_bias: number
  risk_locked?: boolean
  risk_status?: string
  account: AccountSummary
  symbols: Record<string, SymbolState>
  bots: BotItem[]
  positions: PositionItem[]
  deals_history: DealItem[]
  logs: LogEvent[]
  news?: NewsSnapshot
}

export interface CTraderAccount {
  account_id: string
  ctid_account_id?: string
  trader_login?: string
  account_type: string
  is_live?: boolean
  broker_name?: string
  label: string
  access_token?: string
  refresh_token?: string
  default_lot_size: number
  connection_mode: string
  balance?: number
  currency?: string
}

export interface ServerConfig {
  admin_username: string
  connection_mode: string
  allow_real_trading?: boolean
  active_account_id: string
  active_account_type: string
  ctrader_client_id: string
  ctrader_client_secret_set?: boolean
  ctrader_access_token_set?: boolean
  ctrader_refresh_token_set?: boolean
  ctrader_redirect_uri?: string
  default_lot_size: number
  accounts: CTraderAccount[]
  custom_categories: Record<string, string[]>
  bots: BotItem[]
  backtest_history: BacktestReport[]
  auto_trading_enabled: boolean
  active_symbols: string[]
  correlated_basket: string[]
}

export interface IndicatorMeta {
  id: string
  name: string
  category: string
  description?: string
  default_params: Record<string, number>
}

export interface CustomIndicatorItem {
  id: string
  params: Record<string, number>
}

export interface StrategyRecipe {
  id: string
  name: string
  style: string
  markets: string
  recommended_timeframe: string
  description: string
  combine_mode: 'MAJORITY' | 'ALL'
  indicators: CustomIndicatorItem[]
}

export interface BotTemplate {
  template_id: string
  name: string
  operation_mode: string
  formula: string
  description: string
  recommended_timeframe?: string
  window_ticks: number
  zscore_threshold: number
  imbalance_threshold: number
  revert_sigma: number
  grid_direction?: string
  grid_step_points?: number
  grid_tp_points?: number
  max_grid_levels?: number
  loss_guard_enabled?: boolean
  max_loss_usd?: number
  news_assisted?: boolean
  timeframe?: string
  is_custom?: boolean
  custom_mode?: 'INDICATORS' | 'PYTHON'
  combine_mode?: 'MAJORITY' | 'ALL'
  indicators?: CustomIndicatorItem[]
  python_code?: string
  realized_pnl?: number
  floating_pnl?: number
  total_pnl?: number
}

export interface BrokerSymbol {
  name: string
  category: string
  description: string
}

export interface BacktestTradeItem {
  id: number
  type: 'BUY' | 'SELL' | string
  signal: string
  exit_reason?: string
  entry: number
  exit: number
  pnl: number
  result: 'WIN' | 'LOSS' | string
  equity_after: number
}

export interface BacktestEquityPoint {
  trade: number
  time: number
  equity: number
  drawdown: number
}

export interface BacktestReport {
  symbol: string
  timeframe?: string
  period?: string
  lot_size?: number
  data_source?: string
  template_name?: string
  formula?: string
  ticks_processed?: number
  initial_capital?: number
  final_equity?: number
  final_capital: number
  total_trades: number
  winning_trades?: number
  losing_trades?: number
  win_rate: number
  net_profit: number
  return_pct?: number
  gross_profit?: number
  gross_loss?: number
  profit_factor?: number
  avg_win?: number
  avg_loss?: number
  expectancy?: number
  best_trade?: number
  worst_trade?: number
  max_consecutive_wins?: number
  max_consecutive_losses?: number
  max_drawdown: number
  max_drawdown_pct?: number
  equity_curve?: BacktestEquityPoint[]
  trades?: BacktestTradeItem[]
  timestamp?: string
  per_symbol?: BacktestReport[]
}

export interface ChartPoint {
  time: number
  price: number
  vwap: number
  upper_2: number
  lower_2: number
}

export type FeatureKey =
  | 'backtest'
  | 'custom_strategies'
  | 'python_code'
  | 'market_radar'
  | 'news_bot'
  | 'multi_accounts'
  | 'real_trading'

export interface FeatureCatalogItem {
  key: FeatureKey
  label: string
  description: string
}

export interface SaasPlan {
  plan_id: string
  name: string
  description: string
  price_brl: number
  billing_cycle: 'monthly' | 'yearly' | 'lifetime' | string
  kiwify_product_id: string
  kiwify_checkout_url: string
  max_bots: number
  allow_real_trading: boolean
  allowed_features: FeatureKey[]
  active: boolean
  sort_order?: number
}

export interface PlatformSettings {
  trial_days: number
  trial_allow_real_trading: boolean
  default_trial_plan_id: string
  kiwify_webhook_secret: string
}

export interface UserEntitlements {
  is_admin: boolean
  has_access: boolean
  status: 'admin' | 'trial' | 'active' | 'expired' | 'canceled' | 'blocked' | string
  plan_id: string
  plan_name: string
  max_bots: number
  allow_real_trading: boolean
  allowed_features: FeatureKey[]
  days_left: number | null
  trial_ends_at?: number | null
  current_period_end?: number | null
  kiwify_checkout_url?: string
}

export interface MeResponse {
  ok: boolean
  user_id: string
  email: string
  is_admin: boolean
  server_oauth_configured: boolean
  entitlements: UserEntitlements
  plans: SaasPlan[]
  trial_days: number
  feature_catalog: FeatureCatalogItem[]
}

export interface SaasSubscriptionRecord {
  email: string
  user_id: string
  plan_id: string
  plan_name?: string
  status: string
  effective_status?: string
  days_left?: number
  trial_ends_at: number
  current_period_end: number
  kiwify_customer_name?: string
  last_event?: string
  updated_at?: number
}

export interface WebhookLogItem {
  time: string
  event: string
  email: string
  plan_id: string
  status: string
}

export interface AdminOverviewResponse {
  ok: boolean
  settings: PlatformSettings
  plans: SaasPlan[]
  subscriptions: SaasSubscriptionRecord[]
  webhook_logs: WebhookLogItem[]
  webhook_url: string
  feature_catalog: FeatureCatalogItem[]
}

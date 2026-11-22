export interface RateLimitStatus {
  state: string;
  cooldown_seconds: number;
  ws_per_min?: Record<string, number>;
  rest_per_min?: number;
  last_error?: string;
}

export interface AccountSummary {
  backend: string;
  connected: boolean;
  account_type: string;
  account_mode?: string;
  connection_state?: string;
  auth_state?: string;
  data_state?: string;
  trading_state?: string;
  rate_limit?: RateLimitStatus;
  masked_app_id?: string;
  last_tick_at?: number;
  active_account_id: string;
  login: string;
  server: string;
  name: string;
  currency: string;
  balance: number;
  equity: number;
  profit: number;
  daily_realized: number;
  margin_free: number;
  status_note?: string;
}

export interface SymbolState {
  symbol: string;
  price: number;
  vwap: number;
  upper_1: number;
  lower_1: number;
  upper_2: number;
  lower_2: number;
  std_dev: number;
  sigma_distance: number;
  zscore: number;
  imbalance: number;
  regime: string;
  signal: string;
}

export interface BotItem {
  bot_id: string;
  name: string;
  account_id: string;
  account_label?: string;
  account_type?: string;
  symbol: string;
  template_id: string;
  template_name?: string;
  operation_mode: string;
  lot_size: number;
  multiplier: number;
  window_ticks: number;
  zscore_threshold: number;
  imbalance_threshold: number;
  revert_sigma: number;
  sl_sigma_mult: number;
  tp_sigma_mult: number;
  active: boolean;
  status?: 'STOPPED' | 'STARTING' | 'RUNNING' | 'PAUSED' | 'ERROR' | 'STOPPING';
  last_error?: string;
  trades_executed: number;
  last_signal?: string;
  last_regime?: string;
  grid_direction?: string;
  grid_step_points?: number;
  grid_tp_points?: number;
  max_grid_levels?: number;
  loss_guard_enabled?: boolean;
  max_loss_usd?: number;
  news_assisted?: boolean;
  timeframe?: string;
  realized_pnl?: number;
  floating_pnl?: number;
  total_pnl?: number;
}

export interface PositionItem {
  ticket: string | number;
  symbol: string;
  side: string;
  volume: number;
  price_open: number;
  price_current: number;
  sl: number;
  tp: number;
  profit: number;
  bot_name?: string;
  comment?: string;
}

export interface DealItem {
  time_str: string;
  symbol: string;
  side: string;
  volume: number;
  price_open: number;
  price_close: number;
  profit: number;
  reason?: string;
  bot_name?: string;
}

export interface LogEvent {
  time: string;
  module: string;
  message: string;
}

export interface NewsFeed {
  feed_id: string;
  source: string;
  url: string;
  default_symbol: string;
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  link: string;
  published_at: string;
  symbol: string;
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  score: number;
  is_macro_usd?: boolean;
}

export interface NewsSnapshot {
  enabled: boolean;
  pause_grid_on_high_impact: boolean;
  auto_trade_enabled: boolean;
  stake_usd: number;
  multiplier: number;
  last_scan_at: number;
  last_error?: string;
  feeds?: NewsFeed[];
  items: NewsItem[];
  summary_by_symbol: Record<string, { symbol: string; count: number; high_impact: number; avg_score: number; bias: string }>;
}

export interface Snapshot {
  timestamp: string;
  auto_trading_enabled: boolean;
  basket_bias: number;
  account: AccountSummary;
  symbols: Record<string, SymbolState>;
  bots: BotItem[];
  positions: PositionItem[];
  deals_history: DealItem[];
  logs: LogEvent[];
  news?: NewsSnapshot;
}

export interface DerivAccount {
  account_id: string;
  account_type: string;
  label: string;
  deriv_token: string;
  deriv_app_id: string;
  default_stake_usd: number;
  default_multiplier: number;
  connection_mode: string;
  loginid: string;
  balance?: number;
  currency?: string;
}

export interface ServerConfig {
  admin_username: string;
  connection_mode: string;
  allow_real_trading?: boolean;
  active_account_id: string;
  active_account_type: string;
  deriv_token_set?: boolean;
  deriv_app_id: string;
  default_stake_usd: number;
  default_multiplier: number;
  accounts: DerivAccount[];
  custom_categories: Record<string, string[]>;
  bots: BotItem[];
  backtest_history: BacktestReport[];
  auto_trading_enabled: boolean;
  active_symbols: string[];
  correlated_basket: string[];
}

export interface BotTemplate {
  template_id: string;
  name: string;
  operation_mode: string;
  formula: string;
  description: string;
  window_ticks: number;
  zscore_threshold: number;
  imbalance_threshold: number;
  revert_sigma: number;
  grid_direction?: string;
  grid_step_points?: number;
  grid_tp_points?: number;
  max_grid_levels?: number;
  loss_guard_enabled?: boolean;
  max_loss_usd?: number;
  news_assisted?: boolean;
  timeframe?: string;
  realized_pnl?: number;
  floating_pnl?: number;
  total_pnl?: number;
}

export interface BrokerSymbol {
  name: string;
  category: string;
  description: string;
}

export interface BacktestReport {
  symbol: string;
  template_name?: string;
  total_trades: number;
  win_rate: number;
  net_profit: number;
  max_drawdown: number;
  final_capital: number;
  timestamp?: string;
}

export interface ChartPoint {
  time: number;
  price: number;
  vwap: number;
  upper_2: number;
  lower_2: number;
}

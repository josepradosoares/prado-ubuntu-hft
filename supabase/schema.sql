-- Prado Ubuntu HFT: Multi-user Supabase schema with RLS (applied via Supabase MCP)

create table if not exists public.prado_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null default '',
  role text not null default 'user',
  connection_mode text not null default 'DERIV_CLOUD',
  allow_real_trading boolean not null default false,
  auto_trading_enabled boolean not null default true,
  active_account_id text not null default '',
  active_account_type text not null default 'DEMO',
  deriv_app_id text not null default '1089',
  default_stake_usd double precision not null default 10.0,
  default_multiplier integer not null default 100,
  active_symbols jsonb not null default '["R_100","R_75","1HZ100V","frxEURUSD","cryBTCUSD"]'::jsonb,
  correlated_basket jsonb not null default '["R_50","R_25"]'::jsonb,
  custom_categories jsonb not null default '{}'::jsonb,
  risk_config jsonb not null default '{}'::jsonb,
  news_config jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.prado_deriv_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id text not null,
  account_type text not null default 'DEMO',
  label text not null default 'Deriv',
  deriv_token text not null default '',
  deriv_app_id text not null default '1089',
  default_stake_usd double precision not null default 10.0,
  default_multiplier integer not null default 100,
  connection_mode text not null default 'DERIV_CLOUD',
  loginid text not null default '',
  created_at timestamptz not null default now(),
  unique (user_id, account_id)
);
create index if not exists idx_prado_deriv_accounts_user on public.prado_deriv_accounts(user_id);

create table if not exists public.prado_bots (
  bot_id text not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  account_id text not null default '',
  symbol text not null,
  template_id text not null,
  operation_mode text not null default 'BOTH',
  timeframe text not null default 'TICKS',
  news_assisted boolean not null default false,
  loss_guard_enabled boolean not null default false,
  max_loss_usd double precision not null default 20.0,
  status text not null default 'STOPPED',
  lot_size double precision not null default 10.0,
  multiplier integer not null default 100,
  realized_pnl double precision not null default 0.0,
  floating_pnl double precision not null default 0.0,
  total_pnl double precision not null default 0.0,
  trades_executed integer not null default 0,
  config_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, bot_id)
);
create index if not exists idx_prado_bots_user on public.prado_bots(user_id);

create table if not exists public.prado_custom_templates (
  template_id text not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text not null default '',
  custom_mode text not null default 'INDICATORS',
  combine_mode text not null default 'MAJORITY',
  formula text not null default '',
  indicators jsonb not null default '[]'::jsonb,
  python_code text not null default '',
  config_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, template_id)
);
create index if not exists idx_prado_custom_templates_user on public.prado_custom_templates(user_id);

create table if not exists public.prado_news_feeds (
  feed_id text not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  source text not null,
  url text not null,
  default_symbol text not null default 'ALL',
  created_at timestamptz not null default now(),
  primary key (user_id, feed_id)
);
create index if not exists idx_prado_news_feeds_user on public.prado_news_feeds(user_id);

create table if not exists public.prado_deals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  bot_id text not null default '',
  bot_name text not null default '',
  ticket text not null default '',
  symbol text not null,
  side text not null,
  volume double precision not null default 0.0,
  price_open double precision not null default 0.0,
  price_close double precision not null default 0.0,
  profit double precision not null default 0.0,
  reason text not null default '',
  closed_at timestamptz not null default now()
);
create index if not exists idx_prado_deals_user_closed on public.prado_deals(user_id, closed_at desc);

create table if not exists public.prado_backtests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  symbol text not null,
  template_name text not null default '',
  total_trades integer not null default 0,
  win_rate double precision not null default 0.0,
  net_profit double precision not null default 0.0,
  max_drawdown double precision not null default 0.0,
  final_capital double precision not null default 10000.0,
  report_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_prado_backtests_user_created on public.prado_backtests(user_id, created_at desc);

create table if not exists public.prado_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  module text not null default 'SYSTEM',
  message text not null,
  created_at timestamptz not null default now()
);
create index if not exists idx_prado_logs_user_created on public.prado_logs(user_id, created_at desc);

alter table public.prado_settings enable row level security;
alter table public.prado_deriv_accounts enable row level security;
alter table public.prado_bots enable row level security;
alter table public.prado_custom_templates enable row level security;
alter table public.prado_news_feeds enable row level security;
alter table public.prado_deals enable row level security;
alter table public.prado_backtests enable row level security;
alter table public.prado_logs enable row level security;

create policy "prado_settings_owner" on public.prado_settings
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_deriv_accounts_owner" on public.prado_deriv_accounts
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_bots_owner" on public.prado_bots
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_custom_templates_owner" on public.prado_custom_templates
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_news_feeds_owner" on public.prado_news_feeds
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_deals_owner" on public.prado_deals
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_backtests_owner" on public.prado_backtests
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_logs_owner" on public.prado_logs
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

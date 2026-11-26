-- Prado Ubuntu HFT: Multi-user Supabase schema with RLS (cTrader Open API)

create table if not exists public.prado_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null default '',
  role text not null default 'user',
  connection_mode text not null default 'CTRADER_CLOUD',
  allow_real_trading boolean not null default false,
  auto_trading_enabled boolean not null default true,
  active_account_id text not null default '',
  active_account_type text not null default 'DEMO',
  ctrader_client_id text not null default '',
  ctrader_redirect_uri text not null default '',
  default_lot_size double precision not null default 0.01,
  active_symbols jsonb not null default '["EURUSD","GBPUSD","XAUUSD","US100","BTCUSD"]'::jsonb,
  correlated_basket jsonb not null default '["EURUSD","GBPUSD"]'::jsonb,
  custom_categories jsonb not null default '{}'::jsonb,
  risk_config jsonb not null default '{}'::jsonb,
  news_config jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.prado_ctrader_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id text not null,
  ctid_account_id text not null default '',
  trader_login text not null default '',
  account_type text not null default 'DEMO',
  is_live boolean not null default false,
  broker_name text not null default 'cTrader',
  label text not null default 'cTrader',
  access_token text not null default '',
  refresh_token text not null default '',
  token_expires_at double precision not null default 0.0,
  default_lot_size double precision not null default 0.01,
  connection_mode text not null default 'CTRADER_CLOUD',
  balance double precision not null default 0.0,
  currency text not null default 'USD',
  created_at timestamptz not null default now(),
  unique (user_id, account_id)
);
create index if not exists idx_prado_ctrader_accounts_user on public.prado_ctrader_accounts(user_id);

create table if not exists public.prado_bots (
  bot_id text not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  account_id text not null default '',
  symbol text not null default 'EURUSD',
  template_id text not null,
  operation_mode text not null default 'BOTH',
  timeframe text not null default 'TICKS',
  news_assisted boolean not null default false,
  loss_guard_enabled boolean not null default false,
  max_loss_usd double precision not null default 20.0,
  status text not null default 'STOPPED',
  lot_size double precision not null default 0.01,
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
alter table public.prado_ctrader_accounts enable row level security;
alter table public.prado_bots enable row level security;
alter table public.prado_custom_templates enable row level security;
alter table public.prado_news_feeds enable row level security;
alter table public.prado_deals enable row level security;
alter table public.prado_backtests enable row level security;
alter table public.prado_logs enable row level security;

create policy "prado_settings_owner" on public.prado_settings
  for all using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "prado_ctrader_accounts_owner" on public.prado_ctrader_accounts
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

-- SaaS Commercial Platform Settings, Plans & Kiwify Subscriptions
create table if not exists public.prado_platform_settings (
  id text primary key default 'default',
  trial_days integer not null default 7,
  trial_allow_real_trading boolean not null default false,
  default_trial_plan_id text not null default 'pro',
  kiwify_webhook_secret text not null default '',
  news_feeds jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.prado_plans (
  plan_id text primary key,
  name text not null,
  description text not null default '',
  price_brl double precision not null default 0,
  billing_cycle text not null default 'monthly',
  kiwify_product_id text not null default '',
  kiwify_checkout_url text not null default '',
  max_bots integer not null default 2,
  allow_real_trading boolean not null default false,
  allowed_features jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  sort_order integer not null default 0,
  updated_at timestamptz not null default now()
);

create table if not exists public.prado_subscriptions (
  email text primary key,
  user_id text not null default '',
  plan_id text not null default 'starter',
  status text not null default 'trial',
  trial_ends_at double precision not null default 0,
  current_period_end double precision not null default 0,
  kiwify_order_id text not null default '',
  kiwify_subscription_id text not null default '',
  kiwify_customer_name text not null default '',
  last_event text not null default '',
  updated_at timestamptz not null default now()
);

create index if not exists idx_prado_subscriptions_user on public.prado_subscriptions(user_id);

alter table public.prado_platform_settings enable row level security;
alter table public.prado_plans enable row level security;
alter table public.prado_subscriptions enable row level security;

drop policy if exists "prado_platform_settings_admin" on public.prado_platform_settings;
create policy "prado_platform_settings_admin" on public.prado_platform_settings
  for all to authenticated
  using (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'))
  with check (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));

drop policy if exists "prado_plans_read_active" on public.prado_plans;
drop policy if exists "prado_plans_admin_all" on public.prado_plans;
create policy "prado_plans_select" on public.prado_plans
  for select to authenticated
  using (active = true or exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));
create policy "prado_plans_admin_insert" on public.prado_plans
  for insert to authenticated
  with check (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));
create policy "prado_plans_admin_update" on public.prado_plans
  for update to authenticated
  using (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'))
  with check (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));
create policy "prado_plans_admin_delete" on public.prado_plans
  for delete to authenticated
  using (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));

drop policy if exists "prado_subscriptions_read_own" on public.prado_subscriptions;
drop policy if exists "prado_subscriptions_admin_all" on public.prado_subscriptions;
create policy "prado_subscriptions_select" on public.prado_subscriptions
  for select to authenticated
  using ((select auth.uid())::text = user_id or exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));
create policy "prado_subscriptions_admin_insert" on public.prado_subscriptions
  for insert to authenticated
  with check (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));
create policy "prado_subscriptions_admin_update" on public.prado_subscriptions
  for update to authenticated
  using (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'))
  with check (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));
create policy "prado_subscriptions_admin_delete" on public.prado_subscriptions
  for delete to authenticated
  using (exists (select 1 from public.prado_settings s where s.user_id = (select auth.uid()) and s.role = 'admin'));

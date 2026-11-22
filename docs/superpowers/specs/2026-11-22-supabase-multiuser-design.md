# Design: Migração Completa para Supabase (Multi-Usuário + Persistência em Nuvem)

## 1. Intenção e Objetivo
Migrar toda a persistência do painel **Prado Ubuntu HFT — Deriv Multipliers** do arquivo único `data/prado_server_config.json` para o **Supabase (PostgreSQL + Supabase Auth)**, separando os dados por usuário (`user_id` + Row Level Security) para suportar múltiplos usuários simultâneos sem perder robôs, modelos, URLs ou histórico de lucros ao reiniciar ou trocar de VPS.

---

## 2. Abordagem Escolhida
- **Abordagem 2 (Multi-Usuário com Motor HFT Híbrido):**
  - **Login e Sessão:** **Supabase Auth** (`email` + `senha`) no frontend e validação de JWT no backend (`web_app.py`), mantendo compatibilidade com `SIMULATION` / testes locais quando `SUPABASE_URL` não estiver configurado.
  - **Camada de Persistência (`prado_linux/supabase_store.py`):** cliente REST/PostgREST em Python puro (`urllib.request` com `SUPABASE_URL`, `SUPABASE_ANON_KEY` e `SUPABASE_SERVICE_ROLE_KEY` via `.env`), evitando dependências pesadas no Ubuntu.
  - **Motor HFT em Memória por Usuário:** o loop de mercado (`step_once`) continua rodando em memória com baixa latência para cada usuário ativo (`services_by_user[user_id]`), sincronizando alterações de robôs, modelos, configurações e ordens fechadas (`deals`) para o Supabase.

---

## 3. Estrutura do Banco de Dados (`supabase/schema.sql`)
Todas as tabelas possuem `user_id uuid not null references auth.users(id) on delete cascade`, índices por `user_id` e **RLS (`auth.uid() = user_id`)** habilitado:

1. **`prado_settings`** (`user_id` PK): `connection_mode`, `allow_real_trading` (default `false`), `auto_trading_enabled`, `active_account_id`, `deriv_app_id`, `default_stake_usd`, `default_multiplier`, `active_symbols` (jsonb), `correlated_basket` (jsonb), `custom_categories` (jsonb), parâmetros globais de risco e notícias.
2. **`prado_deriv_accounts`** (`id`, `user_id`, `account_id`, `account_type`, `label`, `deriv_token`, `deriv_app_id`, `default_stake_usd`, `default_multiplier`, `connection_mode`, `loginid`).
3. **`prado_bots`** (`bot_id` PK, `user_id`, `name`, `account_id`, `symbol`, `template_id`, `operation_mode`, `timeframe`, `news_assisted`, `loss_guard_enabled`, `max_loss_usd`, `status`, `lot_size`, `multiplier`, `grid_*`, `realized_pnl`, `floating_pnl`, `total_pnl`, `trades_executed`, `config_json` jsonb).
4. **`prado_custom_templates`** (`template_id` PK, `user_id`, `name`, `description`, `custom_mode`, `combine_mode`, `indicators` jsonb, `python_code`, `formula`).
5. **`prado_news_feeds`** (`feed_id` PK, `user_id`, `source`, `url`, `default_symbol`).
6. **`prado_deals`** (`id` PK, `user_id`, `bot_id`, `bot_name`, `ticket`, `symbol`, `side`, `volume`, `price_open`, `price_close`, `profit`, `reason`, `closed_at`).
7. **`prado_backtests`** (`id` PK, `user_id`, `symbol`, `template_name`, `total_trades`, `win_rate`, `net_profit`, `max_drawdown`, `final_capital`, `created_at`).
8. **`prado_logs`** (`id` PK, `user_id`, `module`, `message`, `created_at`).

---

## 4. Segurança e Restrições
- Credenciais (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) ficam apenas no `.env` do servidor (nunca commitadas no GitHub).
- `allow_real_trading` inicia sempre `false` para novos usuários.
- Testes automatizados rodam com store mockado / modo `SIMULATION`, sem chamadas reais ao Supabase nem ordens reais na Deriv.
- A criação das tabelas no Supabase pode ser executada diretamente via **Supabase MCP** (quando configurado) ou colando `supabase/schema.sql` no SQL Editor do Supabase.

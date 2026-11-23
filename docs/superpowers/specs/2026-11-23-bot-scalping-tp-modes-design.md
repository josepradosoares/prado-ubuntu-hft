# Design: Modos de Take Profit para Scalping em Robôs (`USD`, `%`, `Ticks`)

**Data:** 2026-11-23  
**Escopo:** Mudança pequena (Engine + Supabase Store + Frontend + Testes)

## Intenção e Motivação
Hoje, ao abrir ordens na Deriv (`MULTUP`/`MULTDOWN`), `place_order` em `prado_linux/engine.py` ignora configurações de alvo e trava o Take Profit em `max(1.5, stake * 0.9)` USD (90% do Stake, mínimo $1.50). Isso impede que um robô faça scalping rápido para pegar poucos ticks. O usuário quer poder escolher, por robô, entre **Valor fixo em USD**, **% do Stake** ou **Quantidade de Ticks**.

## Objetivos, Não-Objetivos e Anti-Objetivos
- **Objetivos:**
  - Adicionar `tp_mode` (`"AUTO"` | `"USD"` | `"PCT"` | `"TICKS"`) e `tp_value` (`float`) na configuração de cada robô, com persistência local e no Supabase.
  - Expor o seletor no painel (`ModelBuilderPanel.tsx` + build em `prado_linux/static`).
  - Executar `USD` e `PCT` nativamente via `limit_order.take_profit` na Deriv; executar `TICKS` via monitoramento no loop do motor com `close_single_position`.
- **Não-objetivos:** Alterar a lógica atual de `grid_tp_points` do robô Grid Linear ou reestruturar Stop Loss.
- **Anti-objetivos:** Quebrar robôs existentes sem `tp_mode`/`tp_value` (devem continuar funcionando em `"AUTO"` = 90% do Stake) ou enviar `take_profit <= 0` para a Deriv.

## Restrições
- A API de Multipliers da Deriv (`limit_order.take_profit`) aceita apenas valor financeiro (USD), não quantidade de ticks.
- O monitoramento de ticks no motor depende do ciclo `poll_interval_sec` (mínimo `0.5s`).

## Abordagens Consideradas
1. **Opção 1 — Híbrida (Escolhida):** `USD` e `PCT` enviam o valor calculado direto no `limit_order.take_profit` da Deriv (execução instantânea na corretora). `TICKS` monitora a posição aberta no loop do motor e fecha via `close_single_position` quando o preço anda `>= tp_value` ticks a favor (usando o menor incremento não-nulo dos ticks recentes como tamanho do tick) com lucro positivo, mantendo um TP de segurança na Deriv.
2. **Opção 2 — Tudo Nativo por Conversão:** Converter `TICKS` para USD na entrada. Rejeitada porque spread/comissão na Deriv tornam o alvo em ticks impreciso.
3. **Opção 3 — Fechamento 100% no Python:** Remover `take_profit` da Deriv para todos os modos. Rejeitada por adicionar latência de polling e risco em reinício do serviço.

## Desenho da Solução
- **Backend (`engine.py` & `supabase_store.py`):**
  - Novos campos no bot: `tp_mode` (default `"AUTO"`), `tp_value` (default `0.0`).
  - `place_order` aceita `tp_mode` e `tp_value`:
    - `"USD"`: `tp_usd = round(max(0.05, tp_value), 2)`
    - `"PCT"`: `tp_usd = round(max(0.05, stake * (tp_value / 100.0)), 2)`
    - `"TICKS"` ou `"AUTO"`: envia `tp_usd` padrão (`max(1.5, stake * tp_usd_mult)`) como trava de segurança na Deriv.
  - No loop do motor (`_run_cycle`), para robôs não-Grid com `tp_mode == "TICKS"` e `tp_value > 0`: calcula `tick_step` a partir dos ticks recentes do símbolo e, se a posição aberta do robô avançou `>= tp_value * tick_step` a favor do `price_open` (e está com `profit > 0`), chama `close_single_position(ticket)`.
- **Frontend (`ModelBuilderPanel.tsx`):**
  - Seletor **Alvo de Ganho (Take Profit)** com opções `Padrão (90% Stake)`, `Valor fixo (USD)`, `% do Stake` e `Ticks`, acompanhado de campo numérico `Valor do alvo`.

## Em aberto para o implementador
- Ajustar a validação de mínimo aceito pela Deriv caso a corretora exija piso por contrato, e cobrir os 3 modos + compatibilidade retroativa com testes em `tests/`.

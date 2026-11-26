# Design: Backtest Tick a Tick Real + Métricas Completas + Gráfico de Evolução

**Tamanho:** Pequena alteração (backend `engine.py` + componente de gráfico + aba de Backtest em `App.tsx` + testes).

## 1. Intenção e Objetivo
Tornar a aba **Backtest tick a tick** do painel **Quantix** fiel à execução histórica tick a tick e realmente auditável, exibindo métricas completas de desempenho, um gráfico de evolução do patrimônio (*equity curve*) e a lista detalhada das operações executadas.

## 2. Escopo (Goals & Non-Goals)
- **Goals:**
  - Avaliar 100% dos ticks para detecção de Stop Loss / Take Profit sem pular ticks (`step_stride` removido da checagem de SL/TP).
  - Calcular e retornar métricas completas no relatório: `win_rate`, `net_profit`, `return_pct`, `max_drawdown`, `max_drawdown_pct`, `profit_factor` (inclusive no modo `ALL`), `gross_profit`, `gross_loss`, `avg_win`, `avg_loss`, `expectancy`, `best_trade`, `worst_trade`, `max_consecutive_wins`, `max_consecutive_losses`, `ticks_processed`, `period`, `lot_size`, `equity_curve` e `trades`.
  - Exibir na aba Backtest um **Gráfico de Evolução do Patrimônio** (`BacktestEquityChart.tsx` com `lightweight-charts`, seguindo a paleta **Quantix** `#87C245` / `#252223` / `#F2F2F2`).
  - Exibir o resumo detalhado de métricas e a **Tabela de Trades** executados.
- **Non-Goals:**
  - Replay animado barra-a-barra (play/pause/velocidade).
  - Otimização genética / grid search de parâmetros.
  - Múltiplas posições simultâneas no mesmo ativo no backtest.

## 3. Abordagens Consideradas
1. **Apenas Backend Tick-a-Tick:** corrige o motor, mantém os 4 cards atuais. Descartada por não oferecer visibilidade de evolução nem detalhes das operações.
2. **Motor Tick-a-Tick Real + Métricas Completas + Gráfico de Evolução + Tabela de Trades (Escolhida):** entrega precisão no motor e auditoria visual completa usando `lightweight-charts` já presente no projeto.
3. **Replay Interativo estilo MT5:** complexo demais para validação rápida de modelos.

## 4. Arquitetura da Solução
- **Backend ([prado_linux/engine.py](file:///C:/Projeto/Prado/prado-ubuntu-hft/prado_linux/engine.py)):**
  - Em `_run_single_backtest_locked`: iterar **todos os ticks** (`range(40, len(ticks))`) para checar SL/TP e encerramento no último tick; para entrada, manter avaliação tick a tick em modelos nativos (e usar passo leve apenas se modelo Python customizado exceder 1000 ticks, evitando timeout).
  - Construir `equity_curve` com ponto inicial (`initial_capital`) + um ponto por trade fechado (`{ time, equity, drawdown, trade_id }`).
  - Calcular `max_drawdown_pct`, `avg_win`, `avg_loss`, `expectancy`, `best_trade`, `worst_trade`, `max_consecutive_wins`, `max_consecutive_losses`, `period`, `lot_size`.
  - Corrigir `profit_factor` no resumo do modo `ALL` (`gross_profit / gross_loss`).
  - Manter `trades` (últimos 100 trades) no relatório retornado à UI (sem salvar `trades` / `equity_curve` no `config.json` para não inflar `backtest_history`).
- **Frontend ([frontend/src/types.ts](file:///C:/Projeto/Prado/prado-ubuntu-hft/frontend/src/types.ts), [frontend/src/components/BacktestEquityChart.tsx](file:///C:/Projeto/Prado/prado-ubuntu-hft/frontend/src/components/BacktestEquityChart.tsx), [frontend/src/App.tsx](file:///C:/Projeto/Prado/prado-ubuntu-hft/frontend/src/App.tsx)):**
  - Atualizar `BacktestReport` com os novos campos opcionais.
  - Criar `BacktestEquityChart` usando `lightweight-charts` (`AreaSeries` `#87C245`, linha tracejada de capital inicial, responsivo e compatível com temas claro/escuro Quantix).
  - Expandir a seção de resultado em `App.tsx`:
    - Cabeçalho com badges (`Ativo • Timeframe • Período • Lote • Ticks • Fonte de dados`).
    - Grade de KPIs principais (Trades + W/L, Acerto %, Lucro líquido `$`/`%`, Drawdown máx. `$`/`%`) + grade de estatísticas avançadas (Fator de Lucro, Expectativa, Média Ganho/Perda, Melhor/Pior Trade, Sequências W/L, Capital Final).
    - Gráfico de Evolução do Patrimônio (`BacktestEquityChart`).
    - Tabela de Operações (Trades) com rolagem e cores semânticas.
- **Testes ([tests/test_backtest_tick_by_tick.py](file:///C:/Projeto/Prado/prado-ubuntu-hft/tests/test_backtest_tick_by_tick.py)):**
  - Verificar que SL/TP é detectado em tick intermediário (provando que não pula ticks), que `equity_curve` e novas métricas são calculadas corretamente, e que o modo `ALL` calcula `profit_factor` real.

## 5. Ledger de Suposições
### Confirmed
- **C1.** Seguir a Abordagem 2 (motor tick a tick real + mais informações do teste + gráfico de evolução) — confirmado pelo usuário: *"2 implemente e tem como incluir mais infomrações do teste e ter um grafico de evolução."*

### Assumptions (unconfirmed)
- **A1.** Manter o fallback sintético (`SIMULATION_FALLBACK`) quando desconectado da cTrader, destacando claramente o badge de fonte na tela — *source: agent-proposed*.
- **A2.** Manter 1 posição aberta por vez por ativo no backtest — *source: agent-proposed*.
- **A3.** Retornar até os últimos 100 trades na tabela de operações e não persistir `trades`/`equity_curve` no `config.json` (apenas o resumo no histórico) — *source: agent-proposed*.

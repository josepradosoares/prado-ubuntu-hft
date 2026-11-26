# Design: Matriz VWAP & Z-Score, Adaptação US100/Índices cTrader e Gatilho de Cruzamento de Médias

**Tamanho:** Pequena alteração (backend `ctrader_client.py`, `indicators.py`, `config.py`, `engine.py` + frontend `VwapMatrixPanel.tsx`, `ModelBuilderPanel.tsx`, `formatters.ts`, `App.tsx` + testes).

## 1. Intenção e Objetivo
1. **Matriz VWAP e Z-Score (Abordagem 2):** transformar a tabela passiva em um radar quantitativo completo, destacando ativos em tendência no topo, com cards clicáveis, termômetro de distância `±σ` e força Z-Score/Desequilíbrio, gestão rápida de até 25 ativos monitorados e atalhos para abrir o gráfico ou criar robô.
2. **Adaptação do US100 e Índices para a cTrader Open API:** resolver automaticamente apelidos de corretora (`USTEC`, `NAS100`, `US100.cash`, `SPX500`, `DJ30`, `GER40`), compartilhar buffer de ticks ao vivo por `symbolId`/apelido, respeitar distância mínima `slDistance`/`tpDistance`, ampliar fallback de histórico para 24h e corrigir migração legada de `US100Cash#`.
3. **Médias Móveis com Modo Selecionável:** permitir escolher em `EMA`, `SMA`, `WMA` e `DEMA` entre **Tendência (Posição Atual)** (`crossover_only = 0`, padrão) e **Apenas Cruzamento** (`crossover_only = 1`).

## 2. Suposições Confirmadas
- **C1.** Matriz limitada a até **25 ativos simultâneos** em `active_symbols` para respeitar o limite de 5 req/s de histórico da cTrader Open API.
- **C2.** Resolução automática de apelidos aplicada para `US100` e também para `US500`, `US30` e `DE40`.
- **C3.** Parâmetro `crossover_only` com padrão `0` para manter 100% de compatibilidade com modelos e testes existentes.

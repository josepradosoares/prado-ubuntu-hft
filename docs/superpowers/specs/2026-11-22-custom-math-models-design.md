# Design: Menu de Modelos Matemáticos Customizados (21 Indicadores + Editor/Upload Python)

## 1. Intenção e Objetivo
Permitir que o usuário crie, edite, teste e exclua seus próprios **Modelos Matemáticos** diretamente pelo painel web, escolhendo entre:
1. **Construtor Visual por Indicadores:** seleção e parametrização dentre **21 indicadores técnicos e institucionais principais** (sem escrever código).
2. **Estratégia em Python Customizado:** upload de arquivo `.py` **ou** edição/colagem direta em editor na tela, com botão **Testar Código** para validar execução, logs e sinal gerado (`BUY`, `SELL`, `WAIT`) antes de colocar em produção.

Todos os modelos salvos passam a aparecer automaticamente em `/api/bot-templates`, no formulário **Configurar robô matemático** e no **Backtest**.

---

## 2. Abordagens Consideradas
- **Abordagem 1 (Escolhida):** Menu dedicado **Modelos Matemáticos** com dois modos de criação (`Indicadores` + `Código Python com Upload/Editor e Teste`), persistidos no servidor e integrados ao motor (`engine.py`) e ao backtest.
- **Abordagem 2 (Descartada):** Apenas upload/editor Python sem construtor visual de indicadores.

---

## 3. Escopo e Arquitetura

### 3.1 Catálogo dos 21 Indicadores (Python Puro)
Novo módulo `prado_linux/indicators.py` calculando os 21 indicadores em Python puro sobre a série de preços/ticks/velas:
1. **Tendência (7):** `SMA`, `EMA`, `WMA`, `DEMA`, `MACD`, `ADX` (`+DI`/`-DI`), `PARABOLIC_SAR`.
2. **Osciladores / Momento (7):** `RSI`, `STOCHASTIC` (`%K`/`%D`), `CCI`, `WILLIAMS_R`, `ROC`, `MOMENTUM`, `MFI`.
3. **Volatilidade / Canais (4):** `BOLLINGER`, `ATR`, `KELTNER`, `DONCHIAN`.
4. **Institucional / Fluxo (3):** `VWAP`, `ZSCORE`, `IMBALANCE`.

Cada indicador possui:
- Parâmetros editáveis (ex.: período, desvios, níveis de sobrecompra/sobrevenda).
- Avaliação padronizada retornando um voto direcional (`+1` BUY, `-1` SELL, `0` NEUTRAL) e leitura numérica atual.
- Regra de combinação do modelo: `ALL` (todos os indicadores selecionados devem concordar) ou `MAJORITY` (maioria / pontuação mínima configurável).

### 3.2 Modo Código Python (Upload `.py` + Editor + Teste)
- Contrato simples e explícito para o usuário:
  ```python
  def evaluate(prices, ticks, params):
      # Retorna "BUY", "SELL" ou "WAIT"
      return "WAIT"
  ```
- Na tela:
  - Botão **Importar `.py`** (lê o arquivo local para o editor) e editor de código com template inicial pronto.
  - Botão **Testar Código**: envia o script para `POST /api/bot-templates/test`, que valida sintaxe (`ast.parse`), executa `evaluate(...)` com timeout/isolamento contra dados reais ou simulados do ativo escolhido e retorna `{ ok, signal, elapsed_ms, stdout, error }`.

### 3.3 Persistência e Motor
- `PradoServerConfig` (`config.py`) ganha `custom_templates: list[dict[str, Any]]`.
- `PradoTradingService` (`engine.py`):
  - `get_all_templates()` retorna `MATH_BOT_TEMPLATES` (6 nativos) + `self.cfg.custom_templates`.
  - `save_custom_template()`, `delete_custom_template()`, `test_custom_template()`.
  - Em `step_once()` e `run_backtest()`, quando `template_id` pertencer a um modelo customizado (`CUSTOM_INDICATORS` ou `CUSTOM_PYTHON`), o motor executa os indicadores configurados ou a função `evaluate(...)` do script salvo.
- Rotas em `web_app.py`:
  - `GET /api/bot-templates` (nativos + customizados + metadados dos 21 indicadores)
  - `POST /api/bot-templates` (salvar/atualizar/excluir modelo customizado)
  - `POST /api/bot-templates/test` (testar indicadores ou código Python antes de salvar)

### 3.4 Interface Web (`frontend`)
- Novo item no menu lateral (`Sidebar.tsx`): **Modelos Matemáticos** (`templates`).
- Tela dividida em:
  - **Lista de Modelos Criados** (editar, testar, duplicar/excluir) + modelos nativos (somente leitura).
  - **Criador de Modelo** com seletor de modo:
    - **Por Indicadores (21 disponíveis):** checkboxes/cartões por família, edição dos parâmetros de cada indicador ativo e escolha da regra (`Todos confirmam` / `Maioria`).
    - **Código Python:** botão de upload `.py`, área de código com exemplo pronto, seletor de ativo para teste e botão **Testar Código** exibindo o resultado em tempo real.

---

## 4. Restrições e Não-Objetivos
- Não instalar bibliotecas pesadas em C (`TA-Lib`, `pandas-ta`) que possam quebrar no deploy Ubuntu; tudo em Python padrão (`math`, `statistics`, `ast`).
- Não permitir que um erro em código Python customizado derrube o loop principal do servidor (`try/except` + validação prévia + proteção de timeout).
- Modelos nativos (1 a 6) permanecem intactos e protegidos contra exclusão.

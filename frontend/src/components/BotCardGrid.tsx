import { Play, Pause, Pencil, Trash2, TrendingUp, TrendingDown, Cpu, Plus } from 'lucide-react'
import { BotItem, SymbolState } from '../types'

interface Props {
  bots: BotItem[]
  symbols: Record<string, SymbolState>
  onAction: (botId: string, action: string) => void
  onEdit: (bot: BotItem) => void
  onNewBot: () => void
  onDeleteAll: () => void
}

export function BotCardGrid({ bots, symbols, onAction, onEdit, onNewBot, onDeleteAll }: Props) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Cpu className="h-4 w-4 text-amber-400" />
            Frota de Robôs Matemáticos (Deriv Multipliers)
          </h2>
          <p className="text-xs text-slate-400">
            Cards independentes em tempo real com disparo manual, pausa e edição rápida
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onNewBot}
            className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 px-3.5 py-2 text-xs font-semibold text-slate-950 shadow-lg shadow-amber-500/20 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            Novo robô matemático
          </button>
          {bots.length > 0 && (
            <button
              onClick={onDeleteAll}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900/70 hover:bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 transition"
            >
              Limpar frota
            </button>
          )}
        </div>
      </div>

      {bots.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-10 text-center">
          <p className="text-sm text-slate-400">
            Nenhum robô configurado ainda. Clique em <strong className="text-amber-400">Novo robô matemático</strong> para criar seu primeiro robô.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {bots.map((b) => {
            const st = symbols[b.symbol]
            const isReal = b.account_type === 'REAL'
            const z = st?.zscore ?? 0
            const imb = (st?.imbalance ?? 0) * 100
            const signal = st?.signal || b.last_signal || 'WAIT'
            const isBuySig = signal.includes('BUY')
            const isSellSig = signal.includes('SELL')

            return (
              <div
                key={b.bot_id}
                className={`group relative flex flex-col justify-between rounded-2xl border p-5 transition-all duration-200 bg-gradient-to-b from-slate-900/90 to-[#0a101d] shadow-lg shadow-black/30 hover:shadow-amber-500/5 ${
                  b.active
                    ? 'border-emerald-500/30 hover:border-emerald-400/50'
                    : 'border-slate-800 hover:border-slate-700 opacity-85'
                }`}
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2 w-2 rounded-full ${
                            b.active ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-slate-500'
                          }`}
                        />
                        <h3 className="truncate text-sm font-bold text-white">{b.name}</h3>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-400">
                        {b.template_name || b.template_id}
                      </p>
                    </div>

                    <span
                      className={`shrink-0 rounded-lg px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide border ${
                        b.active
                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {b.active ? 'Ativo' : 'Pausado'}
                    </span>
                  </div>

                  {/* Badges Row */}
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
                    <span
                      className={`rounded-md px-2 py-0.5 font-semibold border ${
                        isReal
                          ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                          : 'bg-sky-500/10 text-sky-300 border-sky-500/30'
                      }`}
                    >
                      {isReal ? 'Real' : 'Demo'} • {b.account_label || 'Deriv'}
                    </span>
                    <span className="rounded-md bg-slate-800/90 border border-slate-700 px-2 py-0.5 font-mono text-white">
                      {b.symbol}
                    </span>
                    <span className="rounded-md bg-slate-800/60 border border-slate-700/70 px-2 py-0.5 font-mono text-slate-300">
                      ${b.lot_size} • {b.multiplier}x
                    </span>
                    <span className="rounded-md bg-slate-800/60 border border-slate-700/70 px-2 py-0.5 font-mono text-slate-400">
                      {b.trades_executed || 0} ordens
                    </span>
                  </div>

                  {/* Live Quant Metrics */}
                  <div className="mt-4 grid grid-cols-2 gap-2.5 rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 font-mono text-xs">
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Preço Atual</div>
                      <div className="mt-0.5 font-semibold text-white">
                        {st ? st.price.toFixed(4) : '---'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">VWAP</div>
                      <div className="mt-0.5 font-semibold text-amber-300">
                        {st ? st.vwap.toFixed(4) : '---'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Z-Score</div>
                      <div className={`mt-0.5 font-semibold ${z >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {st ? z.toFixed(2) : '0.00'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Imbalance</div>
                      <div className={`mt-0.5 font-semibold ${imb >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {st ? `${imb.toFixed(1)}%` : '0.0%'}
                      </div>
                    </div>
                  </div>

                  {/* Regime & Signal */}
                  <div className="mt-3 flex items-center justify-between gap-2 text-[11px]">
                    <span className="truncate rounded-lg bg-slate-800/80 px-2.5 py-1 text-slate-300 border border-slate-700/60">
                      {st?.regime || 'NEUTRAL'}
                    </span>
                    <span
                      className={`shrink-0 rounded-lg px-2.5 py-1 font-mono font-semibold border ${
                        isBuySig
                          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                          : isSellSig
                          ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                          : 'bg-slate-800/80 text-slate-400 border-slate-700/60'
                      }`}
                    >
                      {signal}
                    </span>
                  </div>
                </div>

                {/* Action Controls */}
                <div className="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-5 gap-1.5">
                  <button
                    onClick={() => onAction(b.bot_id, 'FIRE_BUY')}
                    title="Comprar Multiplier"
                    className="inline-flex items-center justify-center gap-1 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 py-2 text-[11px] font-semibold text-emerald-300 transition"
                  >
                    <TrendingUp className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Buy</span>
                  </button>
                  <button
                    onClick={() => onAction(b.bot_id, 'FIRE_SELL')}
                    title="Vender Multiplier"
                    className="inline-flex items-center justify-center gap-1 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 py-2 text-[11px] font-semibold text-rose-300 transition"
                  >
                    <TrendingDown className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Sell</span>
                  </button>
                  <button
                    onClick={() => onAction(b.bot_id, b.active ? 'STOP' : 'START')}
                    title={b.active ? 'Pausar robô' : 'Iniciar robô'}
                    className="inline-flex items-center justify-center rounded-xl border border-slate-700 bg-slate-800/70 hover:bg-slate-700 py-2 text-slate-200 transition"
                  >
                    {b.active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 text-emerald-400" />}
                  </button>
                  <button
                    onClick={() => onEdit(b)}
                    title="Editar robô"
                    className="inline-flex items-center justify-center rounded-xl border border-slate-700 bg-slate-800/70 hover:bg-slate-700 py-2 text-slate-200 transition"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => onAction(b.bot_id, 'DELETE')}
                    title="Apagar robô"
                    className="inline-flex items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/10 hover:bg-rose-500/20 py-2 text-rose-300 transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

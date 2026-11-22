import { useMemo, useState } from 'react'
import {
  Play,
  Pause,
  Square,
  Pencil,
  Trash2,
  TrendingUp,
  TrendingDown,
  Cpu,
  Plus,
  Search,
  Copy,
  Eye,
  X,
} from 'lucide-react'
import { BotItem, SymbolState } from '../types'
import { formatNumber, formatPercent, formatPrice, isFiniteNumber } from '../utils/formatters'
import { ConfirmModal } from './ui/ConfirmModal'

interface Props {
  bots: BotItem[]
  symbols: Record<string, SymbolState>
  lastUpdated?: string
  onAction: (botId: string, action: string) => void
  onEdit: (bot: BotItem) => void
  onDuplicate: (bot: BotItem) => void
  onNewBot: () => void
  onDeleteAll: () => void
}

export function BotCardGrid({
  bots,
  symbols,
  lastUpdated,
  onAction,
  onEdit,
  onDuplicate,
  onNewBot,
  onDeleteAll,
}: Props) {
  const [search, setSearch] = useState('')
  const [assetFilter, setAssetFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'PAUSED'>('ALL')
  const [detailBot, setDetailBot] = useState<BotItem | null>(null)
  const [confirmState, setConfirmState] = useState<{
    open: boolean
    title: string
    description: string
    confirmLabel: string
    variant: 'danger' | 'warning' | 'primary'
    onConfirm: () => void
  }>({
    open: false,
    title: '',
    description: '',
    confirmLabel: 'Confirmar',
    variant: 'danger',
    onConfirm: () => {},
  })

  const uniqueAssets = useMemo(() => {
    const set = new Set<string>()
    bots.forEach((b) => {
      if (b?.symbol) set.add(b.symbol)
    })
    return Array.from(set).sort()
  }, [bots])

  const filteredBots = useMemo(() => {
    const q = search.trim().toLowerCase()
    return bots.filter((b) => {
      if (!b || !b.bot_id) return false
      if (statusFilter === 'ACTIVE' && !b.active) return false
      if (statusFilter === 'PAUSED' && b.active) return false
      if (assetFilter !== 'ALL' && b.symbol !== assetFilter) return false
      if (q) {
        const hay = `${b.name || ''} ${b.symbol || ''} ${b.template_name || ''} ${b.template_id || ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [bots, search, assetFilter, statusFilter])

  function requestOrder(b: BotItem, side: 'FIRE_BUY' | 'FIRE_SELL') {
    const isReal = b.account_type === 'REAL'
    const label = side === 'FIRE_BUY' ? 'COMPRA (BUY)' : 'VENDA (SELL)'
    if (isReal) {
      setConfirmState({
        open: true,
        title: `Confirmar ${label} em Conta REAL`,
        description: `Você está prestes a enviar uma ordem real de ${label} no ativo ${b.symbol} pelo robô "${b.name}" (Stake: $${formatNumber(b.lot_size, 2)} • ${b.multiplier || '--'}x). Deseja continuar?`,
        confirmLabel: `Enviar ${side === 'FIRE_BUY' ? 'Buy' : 'Sell'} Real`,
        variant: 'warning',
        onConfirm: () => {
          setConfirmState((s) => ({ ...s, open: false }))
          onAction(b.bot_id, side)
        },
      })
      return
    }
    onAction(b.bot_id, side)
  }

  function requestDeleteBot(b: BotItem) {
    setConfirmState({
      open: true,
      title: 'Excluir robô matemático',
      description: `Tem certeza que deseja excluir o robô "${b.name}" (${b.symbol})? Esta ação não pode ser desfeita.`,
      confirmLabel: 'Excluir robô',
      variant: 'danger',
      onConfirm: () => {
        setConfirmState((s) => ({ ...s, open: false }))
        onAction(b.bot_id, 'DELETE')
      },
    })
  }

  function requestDeleteAll() {
    setConfirmState({
      open: true,
      title: 'Limpar toda a frota de robôs',
      description: `Todos os ${bots.length} robôs configurados serão removidos permanentemente. Deseja prosseguir?`,
      confirmLabel: 'Limpar frota',
      variant: 'danger',
      onConfirm: () => {
        setConfirmState((s) => ({ ...s, open: false }))
        onDeleteAll()
      },
    })
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <Cpu className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            Frota de Robôs Matemáticos (Deriv Multipliers)
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Cards independentes em tempo real com disparo manual, duplicação, pausa e edição rápida
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onNewBot}
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 px-3.5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-600/20 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            Novo robô matemático
          </button>
          {bots.length > 0 && (
            <button
              type="button"
              onClick={requestDeleteAll}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 transition"
            >
              Limpar frota
            </button>
          )}
        </div>
      </div>

      {/* Filters Bar */}
      {bots.length > 0 && (
        <div className="flex flex-wrap items-center gap-2.5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] p-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar robô por nome, ativo ou modelo..."
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/70 pl-9 pr-3 py-1.5 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <select
            aria-label="Filtrar por ativo"
            value={assetFilter}
            onChange={(e) => setAssetFilter(e.target.value)}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/70 px-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200 focus:border-blue-500 focus:outline-none"
          >
            <option value="ALL">Todos os ativos</option>
            {uniqueAssets.map((sym) => (
              <option key={sym} value={sym}>
                {sym}
              </option>
            ))}
          </select>
          <select
            aria-label="Filtrar por status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'ALL' | 'ACTIVE' | 'PAUSED')}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/70 px-3 py-1.5 text-xs text-slate-800 dark:text-slate-200 focus:border-blue-500 focus:outline-none"
          >
            <option value="ALL">Todos os status</option>
            <option value="ACTIVE">Ativos</option>
            <option value="PAUSED">Pausados</option>
          </select>
        </div>
      )}

      {bots.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-[#111827]/60 p-10 text-center">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Nenhum robô configurado ainda. Clique em{' '}
            <strong className="text-blue-600 dark:text-blue-400">Novo robô matemático</strong> para cadastrar seu primeiro robô.
          </p>
        </div>
      ) : filteredBots.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-[#111827]/60 p-8 text-center">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Nenhum robô corresponde aos filtros aplicados.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredBots.map((b) => {
            const st = symbols?.[b.symbol]
            const isReal = b.account_type === 'REAL'
            const zVal = st?.zscore
            const imbVal = st?.imbalance
            const signal = st?.signal || b.last_signal || 'WAIT'
            const isBuySig = signal.includes('BUY')
            const isSellSig = signal.includes('SELL')

            const zColor = isFiniteNumber(zVal)
              ? zVal >= 0
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-rose-600 dark:text-rose-400'
              : 'text-slate-500 dark:text-slate-400'

            const imbColor = isFiniteNumber(imbVal)
              ? imbVal >= 0
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-rose-600 dark:text-rose-400'
              : 'text-slate-500 dark:text-slate-400'

            return (
              <div
                key={b.bot_id}
                className={`group relative flex flex-col justify-between rounded-2xl border p-5 transition-all duration-200 bg-white dark:bg-[#111827] shadow-sm dark:shadow-lg dark:shadow-black/30 ${
                  b.active
                    ? 'border-emerald-500/40 dark:border-emerald-500/30 hover:border-emerald-500/70'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 opacity-90'
                }`}
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                            b.active
                              ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]'
                              : 'bg-slate-400 dark:bg-slate-600'
                          }`}
                        />
                        <h3 className="truncate text-sm font-bold text-slate-900 dark:text-white">
                          {b.name || 'Robô sem nome'}
                        </h3>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
                        {b.template_name || b.template_id || 'Modelo matemático'}
                      </p>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => setDetailBot(b)}
                        title="Detalhes do robô"
                        className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition"
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDuplicate(b)}
                        title="Duplicar robô"
                        className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                      <span
                        className={`rounded-lg px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide border ${
                          b.status === 'ERROR'
                            ? 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30'
                            : b.status === 'PAUSED'
                              ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30'
                              : b.active || b.status === 'RUNNING'
                                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                        }`}
                      >
                        {b.status === 'ERROR'
                          ? 'Erro'
                          : b.status === 'PAUSED'
                            ? 'Pausado'
                            : b.active || b.status === 'RUNNING'
                              ? 'Ativo'
                              : 'Parado'}
                      </span>
                    </div>
                  </div>

                  {/* Badges Row */}
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
                    <span
                      className={`rounded-md px-2 py-0.5 font-semibold border ${
                        isReal
                          ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30'
                          : 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30'
                      }`}
                    >
                      {isReal ? 'Real' : 'Demo'} • {b.account_label || 'Deriv'}
                    </span>
                    <span className="rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2 py-0.5 font-mono text-slate-800 dark:text-white">
                      {b.symbol}
                    </span>
                    <span className="rounded-md bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/70 px-2 py-0.5 font-mono text-slate-600 dark:text-slate-300">
                      ${formatNumber(b.lot_size, 2)} • {b.multiplier ?? '--'}x
                    </span>
                    <span className="rounded-md bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/70 px-2 py-0.5 font-mono text-slate-500 dark:text-slate-400">
                      {b.trades_executed ?? 0} ordens
                    </span>
                  </div>

                  {/* Live Quant Metrics */}
                  <div className="mt-4 grid grid-cols-2 gap-2.5 rounded-xl border border-slate-200/80 dark:border-slate-800/80 bg-slate-50 dark:bg-slate-950/60 p-3 font-mono text-xs">
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Preço Atual</div>
                      <div className="mt-0.5 font-semibold text-slate-900 dark:text-white">
                        {formatPrice(st?.price, 4)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">VWAP</div>
                      <div className="mt-0.5 font-semibold text-amber-600 dark:text-amber-300">
                        {formatPrice(st?.vwap, 4)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Z-Score</div>
                      <div className={`mt-0.5 font-semibold ${zColor}`}>
                        {formatNumber(zVal, 2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500">Imbalance</div>
                      <div className={`mt-0.5 font-semibold ${imbColor}`}>
                        {formatPercent(imbVal, 1, true)}
                      </div>
                    </div>
                  </div>

                  {/* Regime, Signal & Last Update */}
                  <div className="mt-3 flex items-center justify-between gap-2 text-[11px]">
                    <span className="truncate rounded-lg bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/60">
                      {st?.regime || 'AGUARDANDO'}
                    </span>
                    <span
                      className={`shrink-0 rounded-lg px-2.5 py-1 font-mono font-semibold border ${
                        isBuySig
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                          : isSellSig
                          ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30'
                          : 'bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700/60'
                      }`}
                    >
                      {signal}
                    </span>
                  </div>
                  {b.last_error ? (
                    <div className="mt-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-[10px] font-mono text-rose-700 dark:text-rose-300 break-words">
                      Erro isolado: {b.last_error}
                    </div>
                  ) : null}
                  {lastUpdated && (
                    <div className="mt-2 text-[10px] font-mono text-slate-400 dark:text-slate-500">
                      Atualização: {lastUpdated}
                    </div>
                  )}
                </div>

                {/* Action Controls */}
                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 grid grid-cols-6 gap-1.5">
                  <button
                    type="button"
                    onClick={() => requestOrder(b, 'FIRE_BUY')}
                    title="Comprar Multiplier"
                    className="inline-flex items-center justify-center gap-1 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 py-2 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 transition"
                  >
                    <TrendingUp className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Buy</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => requestOrder(b, 'FIRE_SELL')}
                    title="Vender Multiplier"
                    className="inline-flex items-center justify-center gap-1 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 py-2 text-[11px] font-semibold text-rose-700 dark:text-rose-300 transition"
                  >
                    <TrendingDown className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Sell</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      onAction(
                        b.bot_id,
                        b.active || b.status === 'RUNNING'
                          ? 'PAUSE'
                          : b.status === 'PAUSED'
                            ? 'RESUME'
                            : 'START',
                      )
                    }
                    title={
                      b.active || b.status === 'RUNNING'
                        ? 'Pausar robô'
                        : b.status === 'PAUSED'
                          ? 'Retomar robô'
                          : 'Iniciar robô'
                    }
                    className="inline-flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/70 hover:bg-slate-100 dark:hover:bg-slate-700 py-2 text-slate-700 dark:text-slate-200 transition"
                  >
                    {b.active || b.status === 'RUNNING' ? (
                      <Pause className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                    ) : (
                      <Play className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => onAction(b.bot_id, 'STOP')}
                    title="Parar robô com segurança"
                    className="inline-flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/70 hover:bg-slate-100 dark:hover:bg-slate-700 py-2 text-slate-700 dark:text-slate-200 transition"
                  >
                    <Square className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onEdit(b)}
                    title="Editar robô"
                    className="inline-flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/70 hover:bg-slate-100 dark:hover:bg-slate-700 py-2 text-slate-700 dark:text-slate-200 transition"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => requestDeleteBot(b)}
                    title="Apagar robô"
                    className="inline-flex items-center justify-center rounded-xl border border-rose-500/25 bg-rose-500/10 hover:bg-rose-500/20 py-2 text-rose-600 dark:text-rose-300 transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Bot Detail Modal */}
      {detailBot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">{detailBot.name}</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {detailBot.template_name || detailBot.template_id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDetailBot(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-5 grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 p-3 border border-slate-200/70 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Ativo / Modo</div>
                <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {detailBot.symbol} • {detailBot.operation_mode || 'BOTH'}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 p-3 border border-slate-200/70 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Stake / Mult</div>
                <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                  ${formatNumber(detailBot.lot_size, 2)} • {detailBot.multiplier ?? '--'}x
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 p-3 border border-slate-200/70 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Janela (ticks)</div>
                <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {detailBot.window_ticks ?? '--'}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 p-3 border border-slate-200/70 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Z-Score Mín.</div>
                <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {formatNumber(detailBot.zscore_threshold, 2)}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 p-3 border border-slate-200/70 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Imbalance Mín.</div>
                <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {formatNumber(detailBot.imbalance_threshold, 2)}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 dark:bg-slate-900/70 p-3 border border-slate-200/70 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Desvio Reversão (σ)</div>
                <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {formatNumber(detailBot.revert_sigma, 2)}
                </div>
              </div>
            </div>
            <div className="px-5 py-3.5 bg-slate-50 dark:bg-slate-900/50 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  const b = detailBot
                  setDetailBot(null)
                  onEdit(b)
                }}
                className="rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-xs font-semibold text-white"
              >
                Editar parâmetros
              </button>
              <button
                type="button"
                onClick={() => setDetailBot(null)}
                className="rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-300"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        description={confirmState.description}
        confirmLabel={confirmState.confirmLabel}
        variant={confirmState.variant}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((s) => ({ ...s, open: false }))}
      />
    </section>
  )
}

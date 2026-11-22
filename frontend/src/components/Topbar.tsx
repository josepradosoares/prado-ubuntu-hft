import { useState } from 'react'
import {
  Menu,
  Sun,
  Moon,
  Bell,
  Power,
  AlertTriangle,
  LogOut,
  Settings,
} from 'lucide-react'
import { AccountSummary, DerivAccount, LogEvent } from '../types'
import { ThemeMode } from '../hooks/useTheme'

interface TopbarProps {
  pageTitle: string
  chartSymbol: string
  availableSymbols: string[]
  onSelectSymbol: (sym: string) => void
  account?: AccountSummary
  accounts: DerivAccount[]
  activeAccountId: string
  onSelectAccount: (id: string) => void
  autoTradingEnabled: boolean
  onToggleAutoTrading: () => void
  onPanicFlatten: () => void
  onOpenMobileMenu: () => void
  theme: ThemeMode
  onToggleTheme: () => void
  logs: LogEvent[]
  onOpenSettings: () => void
  onLogout: () => void
}

export function Topbar({
  pageTitle,
  chartSymbol,
  availableSymbols,
  onSelectSymbol,
  account,
  accounts,
  activeAccountId,
  onSelectAccount,
  autoTradingEnabled,
  onToggleAutoTrading,
  onPanicFlatten,
  onOpenMobileMenu,
  theme,
  onToggleTheme,
  logs,
  onOpenSettings,
  onLogout,
}: TopbarProps) {
  const [notifOpen, setNotifOpen] = useState(false)
  const connState = account?.connection_state || (account?.connected ? 'CONNECTED' : 'DISCONNECTED')
  const isConnected = Boolean(account?.connected) && account?.backend !== 'DERIV_DISCONNECTED' && connState === 'CONNECTED'
  const isReal = (account?.account_mode || account?.account_type) === 'REAL'
  const authLabel =
    account?.auth_state === 'AUTHENTICATED'
      ? 'VALIDADA'
      : account?.auth_state === 'APP_ID_MISMATCH'
        ? 'ERRO APP ID'
        : account?.auth_state === 'INSUFFICIENT_SCOPE'
          ? 'ESCOPO INSUFICIENTE'
          : account?.auth_state === 'TOKEN_INVALID' || account?.auth_state === 'TOKEN_EXPIRED'
            ? 'TOKEN INVÁLIDO'
            : 'NÃO AUTENTICADA'

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 dark:border-slate-800/80 bg-white/90 dark:bg-[#0b0f17]/90 backdrop-blur-md">
      <div className="px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
        {/* Left: Mobile Menu + Current Page + Connection Status */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onOpenMobileMenu}
            aria-label="Abrir menu"
            className="lg:hidden rounded-xl border border-slate-200 dark:border-slate-700 p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <Menu className="h-4 w-4" />
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                  isConnected
                    ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]'
                    : 'bg-rose-500'
                }`}
              />
              <h1 className="truncate text-sm font-bold text-slate-900 dark:text-white">
                {pageTitle}
              </h1>
              <span
                className={`hidden sm:inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold border ${
                  isReal
                    ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30'
                    : 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30'
                }`}
              >
                {account?.account_type || 'DEMO'}
              </span>
            </div>
            <div className="hidden sm:block text-[11px] font-mono text-slate-500 dark:text-slate-400 truncate">
              {isConnected ? 'CONEXÃO: CONECTADA' : 'CONEXÃO: DESCONECTADA'} • AUTH: {authLabel} • {account?.login || '--'}
            </div>
          </div>
        </div>

        {/* Right Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Asset Selector */}
          <select
            aria-label="Ativo principal"
            value={chartSymbol}
            onChange={(e) => onSelectSymbol(e.target.value)}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-2.5 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200 focus:border-blue-500 focus:outline-none"
          >
            {availableSymbols.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {/* Account Selector */}
          <select
            aria-label="Conta Deriv ativa"
            value={activeAccountId}
            onChange={(e) => onSelectAccount(e.target.value)}
            className="hidden md:block max-w-[210px] rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-2.5 py-1.5 text-xs text-slate-800 dark:text-slate-200 focus:border-blue-500 focus:outline-none"
          >
            {!accounts.length && <option value="">Sem token salvo</option>}
            {accounts.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                [{a.account_type}] {a.label} ({a.loginid || 'Deriv'})
              </option>
            ))}
          </select>

          {/* Auto Trading Toggle */}
          <button
            type="button"
            onClick={onToggleAutoTrading}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition ${
              autoTradingEnabled
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20'
                : 'border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
            }`}
          >
            <Power className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{autoTradingEnabled ? 'Auto: Ativo' : 'Auto: Pausado'}</span>
          </button>

          {/* Panic Flatten */}
          <button
            type="button"
            onClick={onPanicFlatten}
            className="inline-flex items-center gap-1.5 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:text-rose-300 transition"
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Zerar tudo</span>
          </button>

          {/* Notifications */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setNotifOpen((v) => !v)}
              aria-label="Notificações"
              className="relative rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              <Bell className="h-3.5 w-3.5" />
              {logs.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-blue-500" />
              )}
            </button>
            {notifOpen && (
              <div className="absolute right-0 mt-2 w-80 max-w-[90vw] rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] shadow-2xl z-50 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-900 dark:text-white">
                    Eventos recentes
                  </span>
                  <button
                    type="button"
                    onClick={() => setNotifOpen(false)}
                    className="text-[11px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    Fechar
                  </button>
                </div>
                <div className="max-h-64 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/60 text-xs">
                  {logs.length === 0 ? (
                    <div className="p-4 text-center text-slate-400">Sem eventos registrados.</div>
                  ) : (
                    logs.slice(0, 8).map((l, i) => {
                      if (!l) return null
                      return (
                        <div key={i} className="px-4 py-2.5">
                          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                            <span>{l.module || '--'}</span>
                            <span>{l.time || '--'}</span>
                          </div>
                          <p className="mt-0.5 text-slate-700 dark:text-slate-300 line-clamp-2">
                            {l.message || ''}
                          </p>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Theme Toggle */}
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
            title={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            {theme === 'dark' ? <Sun className="h-3.5 w-3.5 text-amber-400" /> : <Moon className="h-3.5 w-3.5 text-slate-700" />}
          </button>

          {/* Settings Shortcut */}
          <button
            type="button"
            onClick={onOpenSettings}
            aria-label="Configurações"
            title="Configurações"
            className="hidden sm:inline-flex rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            <Settings className="h-3.5 w-3.5" />
          </button>

          {/* Logout */}
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 transition"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Sair</span>
          </button>
        </div>
      </div>
    </header>
  )
}

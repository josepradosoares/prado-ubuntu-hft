import { AccountSummary } from '../types'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

interface DerivDiagnosticsCardProps {
  account?: AccountSummary
}

function formatTickTime(ts?: number): string {
  if (!ts || !Number.isFinite(ts) || ts <= 0) return '--'
  try {
    return new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour12: false })
  } catch {
    return '--'
  }
}

export function DerivDiagnosticsCard({ account }: DerivDiagnosticsCardProps) {
  const mode = account?.account_mode || account?.account_type || 'DEMO'
  const connState = account?.connection_state || (account?.connected ? 'CONNECTED' : 'DISCONNECTED')
  const authState = account?.auth_state || 'UNAUTHENTICATED'
  const dataState = account?.data_state || 'NO_DATA'
  const tradingState = account?.trading_state || 'BLOCKED'
  const rlState = account?.rate_limit?.state || 'NORMAL'

  const connLabel =
    connState === 'CONNECTED'
      ? 'CONECTADA'
      : connState === 'CONNECTING'
        ? 'CONECTANDO'
        : connState === 'RECONNECTING'
          ? 'RECONECTANDO'
          : connState === 'ERROR'
            ? 'ERRO'
            : 'DESCONECTADA'

  const authLabel =
    authState === 'AUTHENTICATED'
      ? 'VALIDADA'
      : authState === 'APP_ID_MISMATCH'
        ? 'ERRO DE APP ID'
        : authState === 'INSUFFICIENT_SCOPE'
          ? 'ESCOPO INSUFICIENTE'
          : authState === 'TOKEN_EXPIRED'
            ? 'TOKEN EXPIRADO'
            : authState === 'TOKEN_INVALID'
              ? 'TOKEN INVÁLIDO'
              : 'NÃO AUTENTICADA'

  const dataLabel =
    dataState === 'LIVE'
      ? 'TEMPO REAL'
      : dataState === 'STALE'
        ? 'DESATUALIZADO'
        : dataState === 'DATA_ERROR'
          ? 'ERRO DE DADOS'
          : 'INDISPONÍVEL'

  const tradingLabel =
    tradingState === 'READY'
      ? 'DISPONÍVEL'
      : tradingState === 'EXECUTING'
        ? 'EXECUTANDO'
        : tradingState === 'ERROR'
          ? 'ERRO'
          : 'BLOQUEADA'

  const rows = [
    { label: 'CONTA', value: mode, ok: true },
    { label: 'CONEXÃO', value: connLabel, ok: connState === 'CONNECTED' },
    { label: 'AUTENTICAÇÃO', value: authLabel, ok: authState === 'AUTHENTICATED' },
    { label: 'APP ID', value: account?.masked_app_id || '--', ok: authState !== 'APP_ID_MISMATCH' },
    { label: 'MERCADO', value: dataLabel, ok: dataState === 'LIVE' },
    { label: 'ÚLTIMO TICK', value: formatTickTime(account?.last_tick_at), ok: Boolean(account?.last_tick_at) },
    { label: 'RATELIMIT', value: rlState === 'BLOCKED' ? 'BLOQUEADO' : 'NORMAL', ok: rlState !== 'BLOCKED' },
    { label: 'BACKEND', value: account?.backend || 'DERIV_DISCONNECTED', ok: account?.backend !== 'DERIV_DISCONNECTED' },
    { label: 'NEGOCIAÇÃO', value: tradingLabel, ok: tradingState === 'READY' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Diagnóstico Deriv API</CardTitle>
        <CardDescription>
          Estados separados de conta, autenticação REST/OTP, WebSocket, mercado, RateLimit e proteção de ordens
        </CardDescription>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 text-xs">
          {rows.map((r) => (
            <div
              key={r.label}
              className="flex items-center justify-between rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/50 px-3 py-2"
            >
              <span className="font-semibold text-slate-500 dark:text-slate-400">{r.label}</span>
              <span
                className={`font-mono font-semibold ${
                  r.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                }`}
              >
                {r.value}
              </span>
            </div>
          ))}
        </div>
        {account?.status_note ? (
          <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300 font-mono break-words">
            {account.status_note}
          </div>
        ) : null}
      </CardBody>
    </Card>
  )
}

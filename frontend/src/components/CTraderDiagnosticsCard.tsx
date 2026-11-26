import { AccountSummary } from '../types'
import { formatBackendName } from '../utils/labels'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

interface CTraderDiagnosticsCardProps {
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

export function CTraderDiagnosticsCard({ account }: CTraderDiagnosticsCardProps) {
  const mode = account?.account_mode || account?.account_type || 'DEMO'
  const connState = account?.connection_state || (account?.connected ? 'CONNECTED' : 'DISCONNECTED')
  const authState = account?.auth_state || 'UNAUTHENTICATED'
  const dataState = account?.data_state || 'NO_DATA'
  const tradingState = account?.trading_state || 'BLOCKED'
  const rlState = account?.rate_limit?.state || 'NORMAL'

  const connLabel =
    connState === 'CONNECTED'
      ? 'Conectada (porta 5036)'
      : connState === 'CONNECTING'
        ? 'Conectando'
        : connState === 'RECONNECTING'
          ? 'Reconectando'
          : connState === 'ERROR'
            ? 'Erro'
            : 'Desconectada'

  const authLabel =
    authState === 'AUTHENTICATED'
      ? 'Validada (OAuth 2.0)'
      : authState === 'APP_CREDENTIALS_INVALID'
        ? 'Client ID/Secret inválido'
        : authState === 'INSUFFICIENT_SCOPE'
          ? 'Escopo insuficiente'
          : authState === 'TOKEN_EXPIRED'
            ? 'Token expirado'
            : authState === 'TOKEN_INVALID'
              ? 'Token inválido'
              : authState === 'NO_DEMO_ACCOUNT'
                ? 'Sem conta Demo'
                : 'Não autenticada'

  const dataLabel =
    dataState === 'LIVE'
      ? 'Tempo real'
      : dataState === 'STALE'
        ? 'Desatualizado'
        : dataState === 'DATA_ERROR'
          ? 'Erro de dados'
          : 'Indisponível'

  const tradingLabel =
    tradingState === 'READY'
      ? 'Disponível'
      : tradingState === 'EXECUTING'
        ? 'Executando'
        : tradingState === 'ERROR'
          ? 'Erro'
          : 'Bloqueada'

  const brokerText = account?.broker_name
    ? `${account.broker_name}${account.leverage ? ` (1:${account.leverage})` : ''}`
    : 'cTrader'

  const rows = [
    { label: 'Ambiente', value: `${mode} • ${brokerText}`, ok: true },
    { label: 'Conexão WebSocket', value: connLabel, ok: connState === 'CONNECTED' },
    { label: 'Autenticação', value: authLabel, ok: authState === 'AUTHENTICATED' },
    { label: 'Client ID', value: account?.masked_client_id || '--', ok: authState !== 'APP_CREDENTIALS_INVALID' },
    { label: 'Cotações', value: dataLabel, ok: dataState === 'LIVE' },
    { label: 'Último Tick', value: formatTickTime(account?.last_tick_at), ok: Boolean(account?.last_tick_at) },
    { label: 'Limite de Requisições', value: rlState === 'BLOCKED' ? 'Bloqueado' : 'Normal (50 req/s)', ok: rlState !== 'BLOCKED' },
    { label: 'Motor', value: formatBackendName(account?.backend), ok: account?.backend !== 'CTRADER_DISCONNECTED' },
    { label: 'Negociação', value: tradingLabel, ok: tradingState === 'READY' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Diagnóstico cTrader Open API</CardTitle>
        <CardDescription>
          Estados separados de conta cTID, autenticação OAuth 2.0, WebSocket JSON (porta 5036), cotações e limite da API
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
                className={`font-mono font-semibold truncate max-w-[180px] ${
                  r.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                }`}
                title={r.value}
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

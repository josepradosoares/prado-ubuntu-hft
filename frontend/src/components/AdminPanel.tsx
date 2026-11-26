import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Copy, Crown, Edit3, Plus, RefreshCw, Save, ShieldAlert, Trash2, Users } from 'lucide-react'
import {
  AdminOverviewResponse,
  FeatureCatalogItem,
  FeatureKey,
  PlatformSettings,
  SaasPlan,
  SaasSubscriptionRecord,
  WebhookLogItem,
} from '../types'
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from './ui/Card'

interface AdminPanelProps {
  inputClass: string
  showToast: (msg: string, err?: boolean) => void
  onPlansChanged: () => Promise<void>
}

const EMPTY_PLAN_FORM = {
  plan_id: '',
  name: '',
  description: '',
  price_brl: 197,
  billing_cycle: 'monthly',
  kiwify_product_id: '',
  kiwify_checkout_url: '',
  max_bots: 5,
  allow_real_trading: true,
  allowed_features: ['real_trading', 'backtest'] as FeatureKey[],
  active: true,
  sort_order: 10,
}

export function AdminPanel({ inputClass, showToast, onPlansChanged }: AdminPanelProps) {
  const [loading, setLoading] = useState(true)
  const [settings, setSettings] = useState<PlatformSettings>({
    trial_days: 7,
    trial_allow_real_trading: false,
    default_trial_plan_id: 'pro',
    kiwify_webhook_secret: '',
  })
  const [plans, setPlans] = useState<SaasPlan[]>([])
  const [subs, setSubs] = useState<SaasSubscriptionRecord[]>([])
  const [webhookLogs, setWebhookLogs] = useState<WebhookLogItem[]>([])
  const [webhookUrl, setWebhookUrl] = useState('')
  const [featureCatalog, setFeatureCatalog] = useState<FeatureCatalogItem[]>([])

  const [planForm, setPlanForm] = useState({ ...EMPTY_PLAN_FORM })
  const [clientEmail, setClientEmail] = useState('')
  const [clientPlanId, setClientPlanId] = useState('pro')
  const [clientStatus, setClientStatus] = useState('active')
  const [clientDays, setClientDays] = useState(30)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/admin/overview')
      if (!res.ok) {
        showToast('Sem permissão ou falha ao carregar Painel Admin.', true)
        return
      }
      const d: AdminOverviewResponse = await res.json()
      setSettings(d.settings)
      setPlans(d.plans || [])
      setSubs(d.subscriptions || [])
      setWebhookLogs(d.webhook_logs || [])
      setWebhookUrl(d.webhook_url || '')
      setFeatureCatalog(d.feature_catalog || [])
    } catch {
      showToast('Erro de rede ao carregar Painel Admin.', true)
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  async function saveGlobalSettings(e: FormEvent) {
    e.preventDefault()
    try {
      const res = await fetch('/api/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setSettings(d.settings)
        await Promise.all([loadOverview(), onPlansChanged()])
        showToast(`Configurações salvas! Teste grátis: ${d.settings.trial_days} dia(s) em todos os planos.`)
      } else {
        showToast(d.error || 'Erro ao salvar configurações.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar configurações.', true)
    }
  }

  async function submitPlan(e: FormEvent) {
    e.preventDefault()
    try {
      const res = await fetch('/api/admin/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...planForm, action: 'SAVE' }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setPlans(d.plans || [])
        setPlanForm({ ...EMPTY_PLAN_FORM })
        await onPlansChanged()
        showToast('Plano salvo com sucesso!')
      } else {
        showToast(d.error || 'Erro ao salvar plano.', true)
      }
    } catch {
      showToast('Erro de rede ao salvar plano.', true)
    }
  }

  async function removePlan(planId: string) {
    try {
      const res = await fetch('/api/admin/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'DELETE', plan_id: planId }),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setPlans(d.plans || [])
        await onPlansChanged()
        showToast('Plano removido.')
      } else {
        showToast(d.error || 'Não foi possível excluir o plano.', true)
      }
    } catch {
      showToast('Erro de rede ao excluir plano.', true)
    }
  }

  async function upsertSubscription(payload: Record<string, unknown>, okMsg: string) {
    try {
      const res = await fetch('/api/admin/subscriptions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await res.json()
      if (res.ok && d.ok) {
        setSubs(d.subscriptions || [])
        showToast(okMsg)
      } else {
        showToast(d.error || 'Erro ao atualizar assinatura.', true)
      }
    } catch {
      showToast('Erro de rede ao atualizar assinatura.', true)
    }
  }

  function togglePlanFeature(key: FeatureKey) {
    setPlanForm((prev) => {
      const exists = prev.allowed_features.includes(key)
      const nextFeatures = exists
        ? prev.allowed_features.filter((f) => f !== key)
        : [...prev.allowed_features, key]
      return {
        ...prev,
        allowed_features: nextFeatures,
        allow_real_trading: nextFeatures.includes('real_trading'),
      }
    })
  }

  if (loading && plans.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] p-8 text-center text-xs text-slate-500">
        Carregando painel administrativo...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 1. Configurações Globais: Trial Grátis + Kiwify Webhook */}
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Crown className="h-4 w-4 text-amber-500" />
              Administração Global • Dias Grátis &amp; Integração Kiwify
            </CardTitle>
            <CardDescription>
              Defina quantos dias grátis novos usuários recebem em todos os planos e configure o webhook automático da Kiwify
            </CardDescription>
          </div>
          <button
            type="button"
            onClick={loadOverview}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Atualizar
          </button>
        </CardHeader>
        <CardBody>
          <form onSubmit={saveGlobalSettings} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                Dias grátis (todos os planos)
              </label>
              <input
                type="number"
                min={0}
                max={365}
                value={settings.trial_days}
                onChange={(e) => setSettings((s) => ({ ...s, trial_days: Math.max(0, Number(e.target.value) || 0) }))}
                className={`${inputClass} font-mono`}
              />
              <span className="mt-1 block text-[11px] text-slate-500">
                Padrão 7 dias. Coloque 0 para exigir assinatura imediata.
              </span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                Plano inicial do teste grátis
              </label>
              <select
                value={settings.default_trial_plan_id}
                onChange={(e) => setSettings((s) => ({ ...s, default_trial_plan_id: e.target.value }))}
                className={inputClass}
              >
                {plans.filter((p) => p.active).map((p) => (
                  <option key={p.plan_id} value={p.plan_id}>
                    {p.name} ({p.max_bots} robôs)
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[11px] text-slate-500">
                Durante o teste, o cliente também pode testar qualquer plano ativo.
              </span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                Token secreto do Webhook Kiwify
              </label>
              <input
                type="text"
                value={settings.kiwify_webhook_secret}
                onChange={(e) => setSettings((s) => ({ ...s, kiwify_webhook_secret: e.target.value }))}
                placeholder="Ex: meu_segredo_kiwify_2026"
                className={`${inputClass} font-mono`}
              />
              <span className="mt-1 block text-[11px] text-slate-500">
                Cole o mesmo token na Kiwify ou na URL ?token=
              </span>
            </div>

            <div className="flex flex-col justify-between gap-2">
              <label className="flex items-start gap-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.trial_allow_real_trading}
                  onChange={(e) => setSettings((s) => ({ ...s, trial_allow_real_trading: e.target.checked }))}
                  className="mt-0.5 rounded"
                />
                <span>
                  <strong className="block text-slate-900 dark:text-white">Conta Real no teste grátis</strong>
                  <span className="text-[11px] text-slate-500">
                    Desmarcado = teste grátis roda só em Conta Demo
                  </span>
                </span>
              </label>
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white"
              >
                <Save className="h-3.5 w-3.5" />
                Salvar configurações
              </button>
            </div>

            <div className="md:col-span-2 lg:col-span-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 p-3 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="min-w-0 flex-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 block">
                  URL para cadastrar na Kiwify (Webhooks)
                </span>
                <code className="font-mono text-xs text-emerald-700 dark:text-emerald-300 break-all">
                  {webhookUrl}
                </code>
              </div>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard?.writeText(webhookUrl)
                  showToast('URL do Webhook Kiwify copiada!')
                }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-white dark:hover:bg-slate-800"
              >
                <Copy className="h-3.5 w-3.5" />
                Copiar URL
              </button>
            </div>
          </form>
        </CardBody>
      </Card>

      {/* 2. Planos Comerciais (Criar / Editar / Excluir) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <Card className="lg:col-span-5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-4 w-4 text-blue-500" />
              {planForm.plan_id ? `Editar plano: ${planForm.name}` : 'Criar novo plano'}
            </CardTitle>
            <CardDescription>
              Defina preço, limite de robôs, ID da Kiwify e exatamente quais módulos o cliente poderá acessar
            </CardDescription>
          </CardHeader>
          <CardBody>
            <form onSubmit={submitPlan} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Nome do plano</label>
                  <input
                    type="text"
                    value={planForm.name}
                    onChange={(e) => setPlanForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ex: Profissional"
                    className={inputClass}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Máx. de robôs</label>
                  <input
                    type="number"
                    min={1}
                    max={500}
                    value={planForm.max_bots}
                    onChange={(e) => setPlanForm((f) => ({ ...f, max_bots: Math.max(1, Number(e.target.value) || 1) }))}
                    className={`${inputClass} font-mono`}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Descrição</label>
                <input
                  type="text"
                  value={planForm.description}
                  onChange={(e) => setPlanForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Resumo dos benefícios exibido ao cliente"
                  className={inputClass}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Preço (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    min={0}
                    value={planForm.price_brl}
                    onChange={(e) => setPlanForm((f) => ({ ...f, price_brl: Number(e.target.value) || 0 }))}
                    className={`${inputClass} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Ciclo</label>
                  <select
                    value={planForm.billing_cycle}
                    onChange={(e) => setPlanForm((f) => ({ ...f, billing_cycle: e.target.value }))}
                    className={inputClass}
                  >
                    <option value="monthly">Mensal</option>
                    <option value="yearly">Anual</option>
                    <option value="lifetime">Vitalício</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">ID do Produto Kiwify</label>
                  <input
                    type="text"
                    value={planForm.kiwify_product_id}
                    onChange={(e) => setPlanForm((f) => ({ ...f, kiwify_product_id: e.target.value }))}
                    placeholder="Ex: a1b2c3d4"
                    className={`${inputClass} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">Link Checkout Kiwify</label>
                  <input
                    type="url"
                    value={planForm.kiwify_checkout_url}
                    onChange={(e) => setPlanForm((f) => ({ ...f, kiwify_checkout_url: e.target.value }))}
                    placeholder="https://pay.kiwify.com.br/..."
                    className={inputClass}
                  />
                </div>
              </div>

              <div>
                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">
                  Recursos liberados neste plano
                </div>
                <div className="grid grid-cols-1 gap-1.5">
                  {featureCatalog.map((feat) => (
                    <label
                      key={feat.key}
                      className="flex items-start gap-2 rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900/50"
                    >
                      <input
                        type="checkbox"
                        checked={planForm.allowed_features.includes(feat.key)}
                        onChange={() => togglePlanFeature(feat.key)}
                        className="mt-0.5 rounded"
                      />
                      <span>
                        <strong className="block text-slate-900 dark:text-white">{feat.label}</strong>
                        <span className="text-[11px] text-slate-500">{feat.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <label className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 pt-1">
                <input
                  type="checkbox"
                  checked={planForm.active}
                  onChange={(e) => setPlanForm((f) => ({ ...f, active: e.target.checked }))}
                  className="rounded"
                />
                Plano ativo e disponível para novos clientes
              </label>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-xs font-semibold text-white"
                >
                  {planForm.plan_id ? 'Salvar alterações' : 'Criar plano'}
                </button>
                {planForm.plan_id && (
                  <button
                    type="button"
                    onClick={() => setPlanForm({ ...EMPTY_PLAN_FORM })}
                    className="rounded-xl border border-slate-300 dark:border-slate-700 px-4 py-2.5 text-xs"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>
          </CardBody>
        </Card>

        <div className="lg:col-span-7 space-y-4">
          {plans.map((p) => (
            <Card key={p.plan_id} className={!p.active ? 'opacity-65' : ''}>
              <CardBody className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-slate-900 dark:text-white">{p.name}</h3>
                      <span
                        className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                          p.active
                            ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                            : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        {p.active ? 'Ativo' : 'Inativo'}
                      </span>
                      <span className="rounded-md bg-blue-500/10 px-2 py-0.5 text-[10px] font-mono font-semibold text-blue-600 dark:text-blue-400">
                        Até {p.max_bots} robô(s)
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{p.description || 'Sem descrição'}</p>
                  </div>
                  <div className="text-right font-mono">
                    <div className="text-lg font-bold text-slate-900 dark:text-white">
                      R$ {p.price_brl.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {p.billing_cycle === 'yearly' ? 'por ano' : p.billing_cycle === 'lifetime' ? 'pagamento único' : 'por mês'}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {p.allowed_features.length === 0 ? (
                    <span className="text-[11px] text-slate-400">Apenas Conta Demo + Estratégias Prontas</span>
                  ) : (
                    p.allowed_features.map((fk) => {
                      const meta = featureCatalog.find((f) => f.key === fk)
                      return (
                        <span
                          key={fk}
                          className="rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-2 py-0.5 text-[11px] text-slate-700 dark:text-slate-300"
                        >
                          {meta ? meta.label : fk}
                        </span>
                      )
                    })
                  )}
                </div>

                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
                  <div className="font-mono text-[11px] text-slate-500">
                    Kiwify ID: <strong className="text-slate-700 dark:text-slate-300">{p.kiwify_product_id || 'não vinculado'}</strong>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setPlanForm({
                          plan_id: p.plan_id,
                          name: p.name,
                          description: p.description,
                          price_brl: p.price_brl,
                          billing_cycle: p.billing_cycle,
                          kiwify_product_id: p.kiwify_product_id,
                          kiwify_checkout_url: p.kiwify_checkout_url,
                          max_bots: p.max_bots,
                          allow_real_trading: p.allow_real_trading,
                          allowed_features: [...p.allowed_features],
                          active: p.active,
                          sort_order: p.sort_order || 10,
                        })
                      }
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={() => removePlan(p.plan_id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-700 dark:text-rose-300 hover:bg-rose-500/20"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Excluir
                    </button>
                  </div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      </div>

      {/* 3. Clientes e Assinaturas */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4 text-emerald-500" />
            Clientes &amp; Assinaturas ({subs.length})
          </CardTitle>
          <CardDescription>
            Libere acessos manuais, estenda dias grátis ou bloqueie clientes em caso de chargeback
          </CardDescription>
        </CardHeader>
        <CardBody className="space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              upsertSubscription(
                { email: clientEmail, plan_id: clientPlanId, status: clientStatus, duration_days: clientDays },
                `Acesso salvo para ${clientEmail}`,
              ).then(() => setClientEmail(''))
            }}
            className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
          >
            <div className="md:col-span-4">
              <label className="block text-[11px] text-slate-500 mb-1">E-mail do cliente</label>
              <input
                type="email"
                value={clientEmail}
                onChange={(e) => setClientEmail(e.target.value)}
                placeholder="cliente@email.com"
                className={inputClass}
                required
              />
            </div>
            <div className="md:col-span-3">
              <label className="block text-[11px] text-slate-500 mb-1">Plano</label>
              <select value={clientPlanId} onChange={(e) => setClientPlanId(e.target.value)} className={inputClass}>
                {plans.map((p) => (
                  <option key={p.plan_id} value={p.plan_id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-[11px] text-slate-500 mb-1">Status</label>
              <select value={clientStatus} onChange={(e) => setClientStatus(e.target.value)} className={inputClass}>
                <option value="active">Ativo (Pago)</option>
                <option value="trial">Teste Grátis</option>
                <option value="expired">Expirado</option>
                <option value="blocked">Bloqueado</option>
              </select>
            </div>
            <div className="md:col-span-1">
              <label className="block text-[11px] text-slate-500 mb-1">Dias</label>
              <input
                type="number"
                min={0}
                value={clientDays}
                onChange={(e) => setClientDays(Number(e.target.value) || 0)}
                className={`${inputClass} font-mono`}
              />
            </div>
            <div className="md:col-span-2">
              <button
                type="submit"
                className="w-full rounded-xl bg-emerald-600 hover:bg-emerald-500 py-2.5 text-xs font-semibold text-white"
              >
                Salvar cliente
              </button>
            </div>
          </form>

          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-950/40 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-2.5">Cliente</th>
                  <th className="px-4 py-2.5">Plano</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5 text-right">Restante</th>
                  <th className="px-4 py-2.5 text-right">Ações rápidas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {subs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                      Nenhum cliente registrado ainda.
                    </td>
                  </tr>
                ) : (
                  subs.map((s) => (
                    <tr key={s.email} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                      <td className="px-4 py-2.5 font-medium">{s.email}</td>
                      <td className="px-4 py-2.5">
                        <select
                          value={s.plan_id}
                          onChange={(e) =>
                            upsertSubscription(
                              { email: s.email, plan_id: e.target.value, status: s.status },
                              `Plano de ${s.email} atualizado.`,
                            )
                          }
                          className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1 text-xs"
                        >
                          {plans.map((p) => (
                            <option key={p.plan_id} value={p.plan_id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${
                            s.effective_status === 'active'
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                              : s.effective_status === 'trial'
                              ? 'bg-sky-500/15 text-sky-700 dark:text-sky-300'
                              : 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
                          }`}
                        >
                          {s.effective_status === 'active'
                            ? 'Ativo'
                            : s.effective_status === 'trial'
                            ? 'Teste Grátis'
                            : s.effective_status === 'canceled'
                            ? 'Cancelado'
                            : s.effective_status === 'blocked'
                            ? 'Bloqueado'
                            : 'Expirado'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono">{s.days_left ?? 0}d</td>
                      <td className="px-4 py-2.5 text-right space-x-1.5">
                        <button
                          type="button"
                          onClick={() =>
                            upsertSubscription(
                              { email: s.email, plan_id: s.plan_id, add_trial_days: 7 },
                              `+7 dias grátis adicionados para ${s.email}`,
                            )
                          }
                          className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[11px] font-medium text-sky-700 dark:text-sky-300"
                        >
                          +7d grátis
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            upsertSubscription(
                              { email: s.email, plan_id: s.plan_id, status: 'active', duration_days: 30 },
                              `Plano ativado por 30 dias para ${s.email}`,
                            )
                          }
                          className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300"
                        >
                          Ativar 30d
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            upsertSubscription(
                              { email: s.email, plan_id: s.plan_id, status: 'blocked' },
                              `${s.email} bloqueado e robôs pausados.`,
                            )
                          }
                          className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-[11px] font-medium text-rose-700 dark:text-rose-300"
                        >
                          Bloquear
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      {/* 4. Auditoria de Webhooks Kiwify */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-blue-500" />
            Eventos Recebidos da Kiwify ({webhookLogs.length})
          </CardTitle>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950/40 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-2.5">Horário</th>
                <th className="px-4 py-2.5">Evento</th>
                <th className="px-4 py-2.5">E-mail</th>
                <th className="px-4 py-2.5">Plano</th>
                <th className="px-4 py-2.5">Status resultante</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {webhookLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-5 text-center font-sans text-slate-500">
                    Nenhum webhook recebido da Kiwify ainda.
                  </td>
                </tr>
              ) : (
                webhookLogs.map((w, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-2 text-slate-500">{w.time}</td>
                    <td className="px-4 py-2 font-semibold">{w.event}</td>
                    <td className="px-4 py-2 font-sans">{w.email}</td>
                    <td className="px-4 py-2">{w.plan_id}</td>
                    <td className="px-4 py-2">{w.status}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

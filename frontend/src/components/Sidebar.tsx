import {
  LayoutDashboard,
  Activity,
  Bot,
  Sliders,
  FlaskConical,
  BarChart3,
  Layers,
  Settings,
  KeyRound,
  History,
  Wrench,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  ShieldCheck,
  Newspaper,
  Code2,
} from 'lucide-react'

export type TabKey =
  | 'overview'
  | 'running-bots'
  | 'my-bots'
  | 'create-bot'
  | 'templates'
  | 'backtest'
  | 'monitor'
  | 'news'
  | 'categories'
  | 'deriv-config'
  | 'deriv-tokens'
  | 'history'
  | 'settings'

interface NavGroup {
  title: string
  items: {
    key: TabKey
    label: string
    icon: JSX.Element
    badge?: number
  }[]
}

interface SidebarProps {
  activeTab: TabKey
  onSelectTab: (tab: TabKey) => void
  collapsed: boolean
  onToggleCollapse: () => void
  mobileOpen: boolean
  onCloseMobile: () => void
  totalBots: number
}

export function Sidebar({
  activeTab,
  onSelectTab,
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  totalBots,
}: SidebarProps) {
  const groups: NavGroup[] = [
    {
      title: 'Operações',
      items: [
        { key: 'overview', label: 'Visão geral', icon: <LayoutDashboard className="h-4 w-4 shrink-0" /> },
        { key: 'running-bots', label: 'Mesa de execução', icon: <Activity className="h-4 w-4 shrink-0" /> },
        { key: 'my-bots', label: 'Meus robôs', icon: <Bot className="h-4 w-4 shrink-0" />, badge: totalBots },
      ],
    },
    {
      title: 'Quant & Estratégia',
      items: [
        { key: 'create-bot', label: 'Configurar robô matemático', icon: <Sliders className="h-4 w-4 shrink-0" /> },
        { key: 'templates', label: 'Modelos Matemáticos', icon: <Code2 className="h-4 w-4 shrink-0" /> },
        { key: 'backtest', label: 'Backtest tick a tick', icon: <FlaskConical className="h-4 w-4 shrink-0" /> },
        { key: 'monitor', label: 'Matriz VWAP e Z-Score', icon: <BarChart3 className="h-4 w-4 shrink-0" /> },
        { key: 'news', label: 'Pesquisa & Notícias', icon: <Newspaper className="h-4 w-4 shrink-0" /> },
      ],
    },
    {
      title: 'Mercado & Deriv',
      items: [
        { key: 'categories', label: 'Categorias de ativos', icon: <Layers className="h-4 w-4 shrink-0" /> },
        { key: 'deriv-config', label: 'Configuração Deriv', icon: <Settings className="h-4 w-4 shrink-0" /> },
        { key: 'deriv-tokens', label: 'Tokens e Contas', icon: <KeyRound className="h-4 w-4 shrink-0" /> },
      ],
    },
    {
      title: 'Sistema',
      items: [
        { key: 'history', label: 'Histórico', icon: <History className="h-4 w-4 shrink-0" /> },
        { key: 'settings', label: 'Configurações', icon: <Wrench className="h-4 w-4 shrink-0" /> },
      ],
    },
  ]

  const sidebarContent = (isMobile: boolean) => (
    <div className="flex h-full flex-col bg-white dark:bg-[#0f1624] border-r border-slate-200 dark:border-slate-800/90">
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between gap-2 px-4 border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600/10 dark:bg-blue-500/15 border border-blue-600/20 dark:border-blue-500/30 text-blue-600 dark:text-blue-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
          {(!collapsed || isMobile) && (
            <div className="min-w-0">
              <div className="truncate text-sm font-bold tracking-tight text-slate-900 dark:text-white">
                Prado Ubuntu HFT
              </div>
              <div className="truncate text-[10px] font-mono text-slate-500 dark:text-slate-400">
                Deriv Multipliers
              </div>
            </div>
          )}
        </div>

        {isMobile ? (
          <button
            type="button"
            onClick={onCloseMobile}
            aria-label="Fechar menu"
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onToggleCollapse}
            title={collapsed ? 'Expandir menu' : 'Recolher menu'}
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition"
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        )}
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {groups.map((group) => (
          <div key={group.title}>
            {(!collapsed || isMobile) && (
              <div className="px-2.5 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                {group.title}
              </div>
            )}
            <div className="space-y-1">
              {group.items.map((item) => {
                const active = activeTab === item.key
                return (
                  <button
                    key={item.key}
                    type="button"
                    title={collapsed && !isMobile ? item.label : undefined}
                    onClick={() => {
                      onSelectTab(item.key)
                      if (isMobile) onCloseMobile()
                    }}
                    className={`w-full flex items-center justify-between gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium transition-all ${
                      active
                        ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/25'
                        : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/70 hover:text-slate-900 dark:hover:text-white'
                    } ${collapsed && !isMobile ? 'justify-center px-0' : ''}`}
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      {item.icon}
                      {(!collapsed || isMobile) && (
                        <span className="truncate">{item.label}</span>
                      )}
                    </span>
                    {(!collapsed || isMobile) && item.badge !== undefined && (
                      <span
                        className={`rounded-md px-1.5 py-0.5 text-[10px] font-mono ${
                          active
                            ? 'bg-white/20 text-white'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer Version */}
      <div className="border-t border-slate-100 dark:border-slate-800/80 px-4 py-3 text-[11px] font-mono text-slate-400 dark:text-slate-500">
        {collapsed && !isMobile ? (
          <div className="text-center">v2.0</div>
        ) : (
          <div className="flex items-center justify-between">
            <span>Prado HFT</span>
            <span>v2.0 • Ubuntu</span>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Fixed Sidebar */}
      <aside
        className={`hidden lg:block shrink-0 transition-all duration-200 ${
          collapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        <div className="sticky top-0 h-screen">{sidebarContent(false)}</div>
      </aside>

      {/* Mobile Drawer Sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <div className="relative z-10 w-72 max-w-[85vw] h-full shadow-2xl">
            {sidebarContent(true)}
          </div>
        </div>
      )}
    </>
  )
}

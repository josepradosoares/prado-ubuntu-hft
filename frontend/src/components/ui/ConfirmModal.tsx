import { AlertTriangle, X } from 'lucide-react'

interface ConfirmModalProps {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'primary'
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  variant = 'danger',
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!open) return null

  const btnStyle =
    variant === 'danger'
      ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/20'
      : variant === 'warning'
      ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20'
      : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/20'

  const iconStyle =
    variant === 'danger'
      ? 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30'
      : variant === 'warning'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30'
      : 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] shadow-2xl overflow-hidden"
      >
        <div className="flex items-start justify-between gap-3 p-5 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${iconStyle}`}>
              <AlertTriangle className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-600 dark:hover:text-slate-200 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">
          <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">{description}</p>
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 bg-slate-50 dark:bg-slate-900/50 border-t border-slate-100 dark:border-slate-800">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-200 transition"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-xl px-4 py-2 text-xs font-semibold shadow-lg transition ${btnStyle}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

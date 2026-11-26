import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  hoverable?: boolean
}

export function Card({ children, className = '', hoverable = false }: CardProps) {
  return (
    <div
      className={`rounded-2xl border border-slate-200 dark:border-slate-800/90 bg-white dark:bg-[#252223] shadow-sm dark:shadow-lg dark:shadow-black/25 transition-all duration-200 ${
        hoverable ? 'hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md' : ''
      } ${className}`}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  children: ReactNode
  className?: string
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
  return (
    <div
      className={`border-b border-slate-100 dark:border-slate-800/80 px-5 py-4 ${className}`}
    >
      {children}
    </div>
  )
}

interface CardTitleProps {
  children: ReactNode
  className?: string
}

export function CardTitle({ children, className = '' }: CardTitleProps) {
  return (
    <h3 className={`text-sm font-semibold text-slate-900 dark:text-slate-100 ${className}`}>
      {children}
    </h3>
  )
}

interface CardDescriptionProps {
  children: ReactNode
  className?: string
}

export function CardDescription({ children, className = '' }: CardDescriptionProps) {
  return (
    <p className={`mt-0.5 text-xs text-slate-500 dark:text-slate-400 ${className}`}>
      {children}
    </p>
  )
}

interface CardBodyProps {
  children: ReactNode
  className?: string
}

export function CardBody({ children, className = '' }: CardBodyProps) {
  return <div className={`p-5 ${className}`}>{children}</div>
}

interface CardFooterProps {
  children: ReactNode
  className?: string
}

export function CardFooter({ children, className = '' }: CardFooterProps) {
  return (
    <div
      className={`border-t border-slate-100 dark:border-slate-800/80 px-5 py-3.5 bg-slate-50/70 dark:bg-slate-900/40 rounded-b-2xl ${className}`}
    >
      {children}
    </div>
  )
}

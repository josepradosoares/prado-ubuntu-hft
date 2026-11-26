export function SkeletonLine({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800 ${className}`}
    />
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] p-4 space-y-3"
          >
            <SkeletonLine className="h-3 w-24" />
            <SkeletonLine className="h-6 w-36" />
            <SkeletonLine className="h-3 w-28" />
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#252223] p-5 space-y-4">
        <SkeletonLine className="h-5 w-64" />
        <SkeletonLine className="h-[280px] w-full" />
      </div>
    </div>
  )
}

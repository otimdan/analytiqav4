"use client"
import type { UsageSummary } from "@/lib/types"

export function UsageMeter({ usage }: { usage: UsageSummary | null }) {
  if (!usage) return null

  const pct = usage.limit > 0 ? Math.min(100, Math.round((usage.used / usage.limit) * 100)) : 0
  const low = usage.remaining <= Math.max(1, Math.ceil(usage.limit * 0.1))
  const out = usage.remaining <= 0

  return (
    <div
      className="flex items-center gap-2"
      title={`${usage.used} of ${usage.limit} analyses used this month · ${usage.plan} plan`}
    >
      <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-gray-200 sm:block">
        <div
          className={`h-full rounded-full ${out ? "bg-red-500" : low ? "bg-amber-500" : "bg-indigo-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs tabular-nums ${out ? "text-red-600" : low ? "text-amber-600" : "text-gray-500"}`}>
        {usage.used}/{usage.limit}
      </span>
    </div>
  )
}

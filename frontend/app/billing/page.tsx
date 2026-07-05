"use client"
import { useEffect, useState, useCallback } from "react"
import Link from "next/link"
import { ArrowLeft, Check, Sparkles } from "lucide-react"
import type { Plan, UsageSummary } from "@/lib/types"
import { getPlans, getUsage, createCheckout, createPortalSession } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { AccountMenu } from "@/components/auth/AccountMenu"

export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [p, u] = await Promise.all([getPlans(), getUsage().catch(() => null)])
      setPlans(p)
      setUsage(u)
    } catch {
      setError("Couldn't load billing information.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const currentPlan = plans.find((p) => p.current)
  const onPaidPlan = !!currentPlan?.is_paid

  async function upgrade(planId: string) {
    setBusy(planId)
    setError(null)
    try {
      const { checkout_url } = await createCheckout(planId)
      window.location.href = checkout_url
    } catch {
      setBusy(null)
      setError("Couldn't start checkout. Billing may not be fully set up yet — please try again shortly.")
    }
  }

  async function manage() {
    setBusy("manage")
    setError(null)
    try {
      const { portal_url } = await createPortalSession()
      window.location.href = portal_url
    } catch {
      setBusy(null)
      setError("Couldn't open the subscription portal.")
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b border-gray-100 bg-white">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-6">
          <Link href="/app" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800">
            <ArrowLeft className="size-4" /> Back to app
          </Link>
          <AccountMenu />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-2xl font-bold tracking-tight">Plan &amp; billing</h1>

        {/* Current plan + usage */}
        <div className="mt-4 rounded-2xl border border-gray-200 bg-white p-5">
          {loading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : (
            <>
              <p className="text-sm text-gray-600">
                You&apos;re on the{" "}
                <span className="font-semibold text-gray-900">{currentPlan?.name ?? "Free"}</span> plan.
              </p>
              {usage && (
                <div className="mt-3">
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Analyses this month</span>
                    <span className="tabular-nums">{usage.used} / {usage.limit}</span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={`h-full rounded-full ${usage.remaining <= 0 ? "bg-red-500" : "bg-indigo-500"}`}
                      style={{ width: `${usage.limit > 0 ? Math.min(100, (usage.used / usage.limit) * 100) : 0}%` }}
                    />
                  </div>
                </div>
              )}
              {onPaidPlan && (
                <Button variant="outline" size="sm" className="mt-4" onClick={manage} disabled={busy === "manage"}>
                  {busy === "manage" ? "Opening…" : "Manage subscription"}
                </Button>
              )}
            </>
          )}
        </div>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        {/* Plan catalog (rendered from the backend — new plans appear automatically) */}
        {!loading && (
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`relative rounded-2xl border bg-white p-5 ${plan.current ? "border-indigo-300 ring-1 ring-indigo-100" : "border-gray-200"}`}
              >
                {plan.current && (
                  <span className="absolute right-4 top-4 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                    Current
                  </span>
                )}
                <h2 className="text-lg font-semibold">{plan.name}</h2>
                <div className="mt-1 flex items-baseline gap-1">
                  <span className="text-3xl font-bold tracking-tight">${plan.price_usd}</span>
                  <span className="text-sm text-gray-500">{plan.price_usd > 0 ? "/ month" : "forever"}</span>
                </div>
                <p className="mt-3 flex items-center gap-2 text-sm text-gray-600">
                  <Check className="size-4 shrink-0 text-indigo-600" />
                  {plan.monthly_analyses} analyses / month
                </p>

                <div className="mt-5">
                  {plan.current ? (
                    <Button variant="outline" className="w-full" disabled>Current plan</Button>
                  ) : plan.is_paid ? (
                    <Button className="w-full" onClick={() => upgrade(plan.id)} disabled={busy === plan.id}>
                      <Sparkles className="size-4" />
                      {busy === plan.id ? "Starting…" : `Upgrade to ${plan.name}`}
                    </Button>
                  ) : (
                    <Button variant="outline" className="w-full" disabled>Free plan</Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

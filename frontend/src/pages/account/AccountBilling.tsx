/**
 * AccountBilling -- plan + upgrade surface.
 *
 * Reads GET /billing/plans for the tenant's current plan, the purchasable
 * tiers, and whether Stripe billing is live. Selecting a tier starts a
 * Stripe-hosted Checkout (POST /billing/checkout) and hands off to the
 * returned URL; card data never touches Daena. When billing is off the view
 * degrades to a "contact us" message instead of a dead button.
 *
 * This is the surface the entitlement gates' 402 (upgrade_required) redirect
 * lands on, so every gated 402 reaches somewhere a user can actually upgrade.
 */
import { useCallback, useEffect, useState } from 'react'
import { Sparkles, Check, ExternalLink, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

interface PlansResponse {
  billing_enabled: boolean
  current_plan: string
  plans: string[]
}

// Ordinal rank mirrors app/core/entitlements.PLAN_RANK so the UI can tell which
// tiers a tenant already has (at or below their current plan) without a second
// API call. Display-only; the backend stays the source of truth for access.
const PLAN_RANK: Record<string, number> = {
  FREE: 0,
  PRO: 10,
  MAX: 20,
  ENTERPRISE: 30,
  FOUNDER: 100,
}

// Honest one-line value per tier, mirroring FEATURE_MIN_PLAN exactly (no
// aspirational perks). Unknown plans fall back to a generic label.
const PLAN_BLURB: Record<string, string> = {
  PRO: 'Council multi-model routing',
  MAX: 'Quintessence expert-lens routing, plus Council',
  ENTERPRISE: 'Team and org management, plus all routing modes',
}

function planRank(plan: string | undefined | null): number {
  if (!plan) return 0
  return PLAN_RANK[plan.toUpperCase()] ?? 0
}

function extractDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  const message = (detail as { message?: string } | undefined)?.message
  return typeof message === 'string' ? message : fallback
}

export function AccountBilling() {
  const [data, setData] = useState<PlansResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [checkoutPlan, setCheckoutPlan] = useState<string | null>(null)

  // Post-checkout feedback from Stripe's success/cancel redirect.
  const status = new URLSearchParams(window.location.search).get('status')

  // Returns the fetched plan rank (-1 on error) so the post-checkout poll below
  // can tell when the webhook has provisioned the new tier. `quiet` skips the
  // skeleton toggle so a background poll does not flash the loading state.
  const load = useCallback(async (opts?: { quiet?: boolean }): Promise<number> => {
    if (!opts?.quiet) setLoading(true)
    setError(null)
    try {
      const res = await api.get<PlansResponse>('/billing/plans')
      setData(res.data)
      return planRank(res.data.current_plan)
    } catch (err) {
      setError(extractDetail(err, 'Could not load billing plans'))
      return -1
    } finally {
      if (!opts?.quiet) setLoading(false)
    }
  }, [])

  // Initial load. On a Stripe success redirect the poll effect below owns the
  // load sequence (baseline + retries), so skip the duplicate fetch here.
  useEffect(() => {
    if (status !== 'success') load()
  }, [load, status])

  // After a successful Stripe redirect the subscription is provisioned by the
  // webhook (checkout.session.completed -> handle_event), which is ASYNC to this
  // browser redirect -- so the first read can still show the OLD plan. Poll a
  // bounded number of times until the tier rises, so the new plan appears
  // without forcing the user to refresh after paying.
  useEffect(() => {
    if (status !== 'success') return
    let cancelled = false
    void (async () => {
      const baseline = await load()
      for (let attempt = 0; attempt < 5 && !cancelled; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 2000))
        if (cancelled) break
        const rank = await load({ quiet: true })
        if (rank > baseline) break
      }
    })()
    return () => {
      cancelled = true
    }
  }, [load, status])

  // Deep-link scroll when navigated to /account/billing#billing (e.g. from a
  // gated 402 redirect).
  useEffect(() => {
    if (window.location.hash === '#billing') {
      const el = document.getElementById('billing')
      if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    }
  }, [])

  const startCheckout = useCallback(async (plan: string) => {
    setCheckoutPlan(plan)
    setError(null)
    try {
      const res = await api.post<{ checkout_url: string }>('/billing/checkout', { plan })
      const url = res.data?.checkout_url
      if (!url) {
        throw new Error('No checkout URL returned')
      }
      // Hand off to Stripe-hosted Checkout. Daena never sees card data.
      window.location.href = url
    } catch (err) {
      const message = extractDetail(err, 'Could not start checkout')
      setError(message)
      toast.error(message)
      setCheckoutPlan(null)
    }
  }, [])

  if (loading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-20 rounded-lg bg-midnight-300/30 animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Post-checkout status banner */}
      {status === 'success' && (
        <div className="flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2.5 text-sm text-emerald-200">
          <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
          <span>Payment received. Your plan updates within a moment of Stripe confirming the subscription.</span>
        </div>
      )}
      {status === 'cancelled' && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-200">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>Checkout was cancelled. No charge was made.</span>
        </div>
      )}

      {/* Inline error (Rule 17: surfaced in-component, not toast-only) */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Current plan */}
      {data && (
        <p className="text-sm text-starlight-300">
          You are on the{' '}
          <span className="font-display font-semibold text-starlight-100">
            {(data.current_plan || 'FREE').toUpperCase()}
          </span>{' '}
          plan.
        </p>
      )}

      {/* Billing disabled -> contact us instead of a dead button */}
      {data && !data.billing_enabled && (
        <div className="rounded-lg border border-white/10 bg-midnight-400/50 px-4 py-4">
          <p className="text-sm text-starlight-200">
            Self-serve billing is not enabled yet.
          </p>
          <p className="mt-1 text-xs text-starlight-400">
            Contact your account team to change or upgrade your plan.
          </p>
        </div>
      )}

      {/* Purchasable plans */}
      {data && data.billing_enabled && data.plans.length === 0 && (
        <p className="text-sm text-starlight-400">No upgrade plans are available right now.</p>
      )}

      {data && data.billing_enabled && data.plans.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.plans.map((plan) => {
            const key = plan.toUpperCase()
            const isCurrent = planRank(data.current_plan) === planRank(key) && data.current_plan?.toUpperCase() === key
            const owned = planRank(data.current_plan) >= planRank(key)
            const busy = checkoutPlan === plan
            return (
              <div
                key={plan}
                className={`flex flex-col rounded-xl border bg-midnight-400/50 p-4 ${
                  isCurrent ? 'border-primary-500/40' : 'border-white/10'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Sparkles size={15} className="text-primary-500" />
                  <h3 className="font-display font-semibold text-starlight-100">{key}</h3>
                </div>
                <p className="mt-2 flex-1 text-xs text-starlight-400">
                  {PLAN_BLURB[key] ?? 'Higher plan tier'}
                </p>
                <div className="mt-4">
                  {isCurrent ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary-500">
                      <Check size={13} /> Current plan
                    </span>
                  ) : owned ? (
                    <span className="inline-flex items-center gap-1.5 text-xs text-starlight-400">
                      <Check size={13} /> Included
                    </span>
                  ) : (
                    <button
                      onClick={() => startCheckout(plan)}
                      disabled={busy || checkoutPlan !== null}
                      className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {busy ? (
                        <>
                          <Loader2 size={13} className="animate-spin" /> Starting checkout...
                        </>
                      ) : (
                        <>
                          Upgrade to {key} <ExternalLink size={12} />
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default AccountBilling

/**
 * OrgBilling -- Organization-level billing and credits.
 * Wired to GET /api/v1/org/billing with spend breakdown.
 */
import { useCallback, useEffect, useState } from 'react'
import { CreditCard, TrendingUp, Users, DollarSign } from 'lucide-react'
import { api } from '@/lib/api'

interface MemberSpend {
  name: string
  email: string
  spend_usd: number
}

interface BillingData {
  total_spend_usd: number
  total_tokens: number
  active_members: number
  spend_by_member: MemberSpend[]
}

function formatCurrency(n: number): string {
  return n < 0.01 && n > 0 ? '<$0.01' : `$${n.toFixed(2)}`
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function OrgBilling() {
  const [data, setData] = useState<BillingData | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchBilling = useCallback(async () => {
    try {
      const res = await api.get('/org/billing')
      setData(res.data)
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchBilling() }, [fetchBilling])

  const maxSpend = data?.spend_by_member?.reduce((max, m) => Math.max(max, m.spend_usd), 0) || 1

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Organization credits</h1>
        <p className="text-sm text-starlight-400 mt-1">Monitor usage and billing across your organization</p>
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-4 max-w-2xl">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-xl bg-midnight-300/30 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-3 gap-4 max-w-2xl">
            {[
              {
                label: 'Total spend',
                value: formatCurrency(data?.total_spend_usd || 0),
                sub: 'All time',
                icon: CreditCard,
                color: 'text-accent-amber',
                bgFrom: 'from-accent-amber/5',
                bgTo: 'to-accent-amber/10',
              },
              {
                label: 'Token usage',
                value: formatTokens(data?.total_tokens || 0),
                sub: 'All time',
                icon: TrendingUp,
                color: 'text-accent-cyan',
                bgFrom: 'from-accent-cyan/5',
                bgTo: 'to-accent-cyan/10',
              },
              {
                label: 'Active members',
                value: String(data?.active_members || 0),
                sub: 'Total',
                icon: Users,
                color: 'text-accent-purple',
                bgFrom: 'from-accent-purple/5',
                bgTo: 'to-accent-purple/10',
              },
            ].map((stat) => (
              <div key={stat.label} className={`p-4 rounded-xl bg-gradient-to-br ${stat.bgFrom} ${stat.bgTo} border border-white/5`}>
                <stat.icon size={16} className={`${stat.color} mb-2`} />
                <p className="text-lg font-semibold text-starlight-100">{stat.value}</p>
                <p className="text-[10px] text-starlight-500">{stat.label}</p>
                <p className="text-[10px] text-starlight-600">{stat.sub}</p>
              </div>
            ))}
          </div>

          {/* Usage by member -- horizontal bar chart */}
          <div className="rounded-lg border border-white/5 overflow-hidden max-w-2xl">
            <div className="px-4 py-3 bg-midnight-300/20 border-b border-white/5 flex items-center gap-2">
              <DollarSign size={14} className="text-accent-amber" />
              <p className="text-xs font-medium text-starlight-300">Usage by member</p>
            </div>

            {!data?.spend_by_member?.length || data.spend_by_member.every(m => m.spend_usd === 0) ? (
              <div className="px-6 py-8 text-center">
                <p className="text-sm text-starlight-400">No usage data yet</p>
                <p className="text-xs text-starlight-500 mt-1">Usage appears after API calls are made through Daena</p>
              </div>
            ) : (
              <div className="p-4 space-y-3">
                {data.spend_by_member.map((m) => {
                  const pct = maxSpend > 0 ? (m.spend_usd / maxSpend) * 100 : 0
                  return (
                    <div key={m.email} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-starlight-200">{m.name}</span>
                        <span className="text-xs font-mono text-starlight-400">{formatCurrency(m.spend_usd)}</span>
                      </div>
                      <div className="h-2 rounded-full bg-midnight-400/50 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-accent-amber/60 to-accent-amber"
                          style={{ width: `${Math.max(pct, 2)}%`, transition: 'width 0.5s ease' }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Plan upgrade CTA */}
          <div className="p-4 rounded-xl bg-gradient-to-br from-primary-500/5 to-accent-purple/5 border border-primary-500/10 max-w-2xl">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-starlight-100">Need more capacity?</p>
                <p className="text-xs text-starlight-400 mt-0.5">
                  Upgrade to Enterprise for higher limits, priority support, and SSO
                </p>
              </div>
              <button className="px-4 py-2 rounded-lg bg-primary-500/20 text-primary-400 text-xs font-medium hover:bg-primary-500/30 transition-colors cursor-pointer">
                View plans
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default OrgBilling

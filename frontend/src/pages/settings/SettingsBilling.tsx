/**
 * Billing & Usage settings -- cost overview from real backend data.
 * Fetches from GET /billing/overview and /billing/by-provider.
 * No mock data. Shows actual usage or zeros.
 */
import { useEffect, useState, useCallback } from 'react'
import { Card, Badge } from '@/components/common'
import { DollarSign, BarChart3, Bell, TrendingUp, Layers, Calendar, CheckCircle, Gauge, Users } from 'lucide-react'
import { api } from '@/lib/api'
import { persistUiPref } from '@/stores/uiStore'

interface BillingOverview {
  session_cost: number
  daily_cost: number
  monthly_cost: number
  total_entries: number
}

interface ProviderCost {
  provider: string
  cost_usd: number
  total_tokens: number
  call_count: number
}

interface TaskTypeCost {
  task_type: string
  cost_usd: number
  count: number
}

interface DayHistoryEntry {
  date: string
  cost_usd: number
}

const PROVIDER_DISPLAY: Record<string, string> = {
  ollama: 'Ollama (Local)',
  anthropic: 'Anthropic (Claude)',
  openai: 'OpenAI',
  google: 'Google (Gemini)',
  groq: 'Groq',
  openrouter: 'OpenRouter',
  together: 'Together.ai',
  perplexity: 'Perplexity',
}

const OVER_BUDGET_OPTIONS = [
  { value: 'warn', label: 'Warn only' },
  { value: 'fallback', label: 'Fallback to cheapest model' },
  { value: 'block', label: 'Block all cloud requests' },
]

export function SettingsBilling() {
  const [monthlyBudget, setMonthlyBudget] = useState(25)
  const [alertThreshold, setAlertThreshold] = useState(80)
  const [overBudgetAction, setOverBudgetAction] = useState('fallback')
  const [overview, setOverview] = useState<BillingOverview>({
    session_cost: 0, daily_cost: 0, monthly_cost: 0, total_entries: 0,
  })
  const [providers, setProviders] = useState<ProviderCost[]>([])
  const [taskTypes, setTaskTypes] = useState<TaskTypeCost[]>([])
  const [history, setHistory] = useState<DayHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [quota, setQuota] = useState<{
    monthly_credit_usd: number
    spend_this_month_usd: number
    remaining_monthly_usd: number
    daily_credit_usd: number | null
    spend_today_usd: number
    remaining_daily_usd: number | null
    overage_action: string
    is_over_quota: boolean
  } | null>(null)
  const [userQuotas, setUserQuotas] = useState<Array<{
    user_id: string; email: string; display_name: string | null;
    plan_tier: string; monthly_credit_usd: number; spend_this_month_usd: number;
    daily_credit_usd: number | null; spend_today_usd: number;
    overage_action: string; max_tenant_share_pct: number; admin_override: boolean;
  }>>([])
  const [showAdmin, setShowAdmin] = useState(false)

  const fetchBilling = useCallback(async () => {
    try {
      const [ovRes, pvRes, ttRes, hRes] = await Promise.allSettled([
        api.get('/billing/overview'),
        api.get('/billing/by-provider'),
        api.get('/billing/by-task-type'),
        api.get('/billing/history?days=14'),
      ])
      if (ovRes.status === 'fulfilled') {
        const payload = ovRes.value.data?.data ?? ovRes.value.data
        if (payload) {
          setOverview(payload)
        }
      }
      if (pvRes.status === 'fulfilled') {
        const raw = pvRes.value.data?.data ?? pvRes.value.data
        if (raw) {
          const arr: ProviderCost[] = Object.entries(raw).map(([provider, data]) => ({
            provider,
            ...(data as Record<string, number>),
          } as ProviderCost))
          setProviders(arr)
        }
      }
      if (ttRes.status === 'fulfilled') {
        const raw = ttRes.value.data?.data ?? ttRes.value.data
        if (raw && typeof raw === 'object') {
          const arr: TaskTypeCost[] = Object.entries(raw).map(([task_type, data]) => ({
            task_type,
            ...(data as Record<string, number>),
          } as TaskTypeCost))
          setTaskTypes(arr)
        }
      }
      if (hRes.status === 'fulfilled') {
        const raw = hRes.value.data?.data ?? hRes.value.data
        if (Array.isArray(raw)) {
          setHistory(raw as DayHistoryEntry[])
        }
      }
    } catch { /* graceful */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void fetchBilling() }, [fetchBilling])

  // Hydrate alert threshold preference from backend user settings
  useEffect(() => {
    api.get('/settings/user').then((res) => {
      const settings = res.data?.data
      const threshold = settings?.budget_alert_threshold
      if (typeof threshold === 'number') {
        setAlertThreshold(Math.max(0, Math.min(100, threshold)))
      }
      const budget = settings?.monthly_budget
      if (typeof budget === 'number' && budget >= 0) {
        setMonthlyBudget(budget)
      }
      const action = settings?.over_budget_action
      if (action === 'warn' || action === 'fallback' || action === 'block') {
        setOverBudgetAction(action)
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    api.get('/billing/my-quota')
      .then(res => {
        const d = res.data?.data ?? res.data
        if (d) setQuota(d)
      })
      .catch(() => {})
  }, [])

  // Check if user is admin and fetch quotas
  useEffect(() => {
    api.get('/billing/user-quotas')
      .then(res => {
        const d = res.data?.data ?? res.data
        if (Array.isArray(d)) {
          setUserQuotas(d)
          setShowAdmin(true)
        }
      })
      .catch(() => {}) // Non-admin gets 403, ignore
  }, [])

  const monthlyPct = monthlyBudget > 0 ? Math.round((overview.monthly_cost / monthlyBudget) * 100) : 0
  const totalTokens = providers.reduce((sum, p) => sum + (p.total_tokens || 0), 0)

  return (
    <div className="space-y-6">
      {/* My Quota */}
      {quota && (
        <Card variant="glass" padding="lg">
          <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
            <Gauge size={14} /> My Quota
          </h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="px-3 py-3 rounded-lg bg-midnight-800/40 border border-white/5">
              <p className="text-lg font-display font-bold text-starlight-100">
                ${quota.remaining_monthly_usd.toFixed(2)}
              </p>
              <p className="text-[10px] text-starlight-500">Monthly remaining</p>
              <p className="text-[10px] text-starlight-400 mt-0.5">
                ${quota.spend_this_month_usd.toFixed(2)} of ${quota.monthly_credit_usd.toFixed(2)} used
              </p>
            </div>
            {quota.daily_credit_usd != null && (
              <div className="px-3 py-3 rounded-lg bg-midnight-800/40 border border-white/5">
                <p className="text-lg font-display font-bold text-starlight-100">
                  ${(quota.remaining_daily_usd ?? 0).toFixed(2)}
                </p>
                <p className="text-[10px] text-starlight-500">Daily remaining</p>
                <p className="text-[10px] text-starlight-400 mt-0.5">
                  ${quota.spend_today_usd.toFixed(2)} of ${quota.daily_credit_usd.toFixed(2)} today
                </p>
              </div>
            )}
          </div>
          {/* Monthly progress bar */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-starlight-400">Monthly quota</span>
              <span className="text-xs text-starlight-300 font-medium">
                {quota.monthly_credit_usd > 0 ? Math.round((quota.spend_this_month_usd / quota.monthly_credit_usd) * 100) : 0}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-midnight-400/50 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  quota.is_over_quota ? 'bg-status-error' :
                  quota.spend_this_month_usd / quota.monthly_credit_usd > 0.8 ? 'bg-accent-amber' :
                  'bg-status-success'
                }`}
                style={{ width: `${Math.min(100, quota.monthly_credit_usd > 0 ? (quota.spend_this_month_usd / quota.monthly_credit_usd) * 100 : 0)}%` }}
              />
            </div>
          </div>
          {/* Overage action label */}
          <p className="text-[10px] text-starlight-500 mt-2 flex items-center gap-1">
            {quota.overage_action === 'fallback_free' && 'When limit reached: switches to free local models'}
            {quota.overage_action === 'block' && 'When limit reached: requests are paused'}
            {quota.overage_action === 'warn' && 'When limit reached: you will be warned but can continue'}
            {quota.overage_action === 'allow_overage' && 'Overage allowed against team budget'}
          </p>
          {quota.is_over_quota && (
            <div className="mt-3 px-3 py-2 rounded-lg bg-accent-amber/10 border border-accent-amber/20">
              <p className="text-[10px] text-accent-amber font-medium">
                Quota reached. {quota.overage_action === 'fallback_free' ? 'Queries are routed to free local models.' : 'Contact your admin for more credits.'}
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Cost Overview */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <DollarSign size={14} /> Cost Overview
        </h3>
        <div className="grid grid-cols-3 gap-4 mb-5">
          {[
            { label: 'This Session', value: `$${overview.session_cost.toFixed(2)}`, sub: `${overview.total_entries} API calls` },
            { label: 'Today', value: `$${overview.daily_cost.toFixed(2)}`, sub: `~${Math.round(totalTokens / 1000)}K tokens` },
            { label: 'This Month', value: `$${overview.monthly_cost.toFixed(2)}`, sub: `of $${monthlyBudget} budget` },
          ].map((item) => (
            <div key={item.label} className="px-3 py-3 rounded-lg bg-midnight-800/40 border border-white/5">
              <p className="text-lg font-display font-bold text-starlight-100">{item.value}</p>
              <p className="text-[10px] text-starlight-500">{item.label}</p>
              <p className="text-[10px] text-starlight-400 mt-0.5">{item.sub}</p>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-status-success mt-2 flex items-center gap-1">
          <CheckCircle size={10} /> Local Ollama queries are always free
        </p>
        {/* Monthly budget progress bar */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-starlight-400">Monthly usage</span>
            <span className="text-xs text-starlight-300 font-medium">{monthlyPct}%</span>
          </div>
          <div className="h-2 rounded-full bg-midnight-400/50 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                monthlyPct > 90 ? 'bg-status-error' : monthlyPct > 70 ? 'bg-accent-amber' : 'bg-status-success'
              }`}
              style={{ width: `${Math.min(monthlyPct, 100)}%` }}
            />
          </div>
        </div>
      </Card>

      {/* Per-Provider Breakdown */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <BarChart3 size={14} /> Cost by Provider
        </h3>
        {providers.length === 0 ? (
          <p className="text-xs text-starlight-500 italic">No API usage recorded yet. Send chat messages to see billing data.</p>
        ) : (
          <div className="space-y-2">
            {providers.map((p) => {
              const tokens = p.total_tokens || 0
              return (
                <div key={p.provider} className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-midnight-800/30 border border-white/5">
                  <div>
                    <p className="text-sm text-starlight-200">{PROVIDER_DISPLAY[p.provider.toLowerCase()] || p.provider}</p>
                    <p className="text-[10px] text-starlight-500">{tokens.toLocaleString()} tokens</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-starlight-100">${(p.cost_usd || 0).toFixed(2)}</p>
                    {p.cost_usd === 0 && <Badge variant="success" size="sm">Free</Badge>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* Cost by Task Type */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Layers size={14} /> Cost by Task Type
        </h3>
        {taskTypes.length === 0 ? (
          <p className="text-xs text-starlight-500 italic">No task type data yet.</p>
        ) : (
          <div className="space-y-2">
            {taskTypes.map((t) => (
              <div key={t.task_type} className="flex items-center justify-between px-3 py-2 rounded-lg bg-midnight-800/30 border border-white/5">
                <div>
                  <p className="text-sm text-starlight-200 capitalize">{t.task_type.replace(/_/g, ' ')}</p>
                  <p className="text-[10px] text-starlight-500">{t.count || 0} calls</p>
                </div>
                <p className="text-sm font-medium text-starlight-100">${(t.cost_usd || 0).toFixed(4)}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 14-Day Cost History */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Calendar size={14} /> 14-Day Cost History
        </h3>
        {history.length === 0 ? (
          <p className="text-xs text-starlight-500 italic">No history data available yet.</p>
        ) : (
          <div className="space-y-1">
            {/* Simple bar chart */}
            {(() => {
              const maxCost = Math.max(...history.map(h => h.cost_usd || 0), 0.01)
              return history.map((h) => {
                const pct = Math.round(((h.cost_usd || 0) / maxCost) * 100)
                const dateStr = new Date(h.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                return (
                  <div key={h.date} className="flex items-center gap-3">
                    <span className="text-[10px] text-starlight-500 w-14 shrink-0 text-right font-mono">{dateStr}</span>
                    <div className="flex-1 h-4 rounded bg-midnight-400/30 overflow-hidden">
                      <div
                        className="h-full rounded bg-primary-500/40"
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-starlight-400 w-14 shrink-0 font-mono">${(h.cost_usd || 0).toFixed(3)}</span>
                  </div>
                )
              })
            })()}
          </div>
        )}
      </Card>

      {/* Budget Settings */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Bell size={14} /> Budget Settings
        </h3>
        {/* DECISION-003 (2026-06-01): these three controls are now wired
            into real per-user enforcement. On save, monthly_budget +
            over_budget_action sync into the user's UserQuota row, which
            CostGuard.preflight_check enforces on every chat. The alert
            threshold drives an early-warning notification. */}
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-status-success/20 bg-status-success/5 px-3 py-2">
          <Badge variant="success" size="sm">Enforced</Badge>
          <p className="text-[10px] text-starlight-400 leading-relaxed">
            These preferences drive real per-user budget enforcement.
            <code>Monthly Budget</code> and <code>Over-budget action</code> sync into your
            personal usage quota on save, which the cost guard checks before every
            request. <code>Alert at %</code> triggers an early-warning notification.
          </p>
        </div>
        <div className="space-y-4 max-w-md">
          <div
            title="Saved to your personal usage quota (UserQuota.monthly_credit_usd). CostGuard enforces this cap on every chat request."
          >
            <label className="block text-xs text-starlight-400 mb-1">Monthly Budget (USD)</label>
            <input
              type="number"
              value={monthlyBudget}
              onChange={(e) => {
                const v = Math.max(0, parseInt(e.target.value) || 0)
                setMonthlyBudget(v)
                persistUiPref('monthly_budget', v)
              }}
              className="glass-input w-32 px-3 py-2 rounded-lg text-sm text-starlight-200 text-center"
            />
          </div>
          <div
            title="When your monthly spend crosses this percentage of your budget, Daena emits an 'approaching budget' notification (deduped to once per hour)."
          >
            <label className="block text-xs text-starlight-400 mb-1">Alert at (%)</label>
            <input
              type="range"
              min="50"
              max="100"
              value={alertThreshold}
              onChange={(e) => {
                const next = parseInt(e.target.value, 10)
                setAlertThreshold(next)
                persistUiPref('budget_alert_threshold', next)
              }}
              className="w-full accent-primary-500"
            />
            <p className="text-[10px] text-starlight-500 mt-0.5">Alert when usage reaches {alertThreshold}% of budget</p>
          </div>
          <div
            title="Saved to your personal usage quota (UserQuota.overage_action). warn = notify only; fallback = route to a free model; block = refuse the request."
          >
            <label className="block text-xs text-starlight-400 mb-1">Over-budget action</label>
            <select
              value={overBudgetAction}
              onChange={(e) => {
                const next = e.target.value
                setOverBudgetAction(next)
                persistUiPref('over_budget_action', next)
              }}
              className="glass-input w-full px-3 py-2 rounded-lg text-sm text-starlight-200 bg-midnight-400/60 border border-white/5 cursor-pointer"
            >
              {OVER_BUDGET_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Admin: Per-User Quotas */}
      {showAdmin && (
        <Card variant="glass" padding="lg">
          <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
            <Users size={14} /> Per-User Quotas
          </h3>
          {userQuotas.length === 0 ? (
            <p className="text-xs text-starlight-500 italic">No user quotas provisioned yet. Users get quotas on their first chat message.</p>
          ) : (
            <div className="space-y-2">
              {userQuotas.map((uq) => {
                const pct = uq.monthly_credit_usd > 0
                  ? Math.round((uq.spend_this_month_usd / uq.monthly_credit_usd) * 100)
                  : 0
                return (
                  <div key={uq.user_id} className="flex items-center gap-4 px-3 py-2.5 rounded-lg bg-midnight-800/30 border border-white/5">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-starlight-200 truncate">
                        {uq.display_name || uq.email}
                      </p>
                      <div className="flex items-center gap-3 text-[10px] text-starlight-500 mt-0.5">
                        <span>{uq.plan_tier}</span>
                        <span>${uq.spend_this_month_usd.toFixed(2)} / ${uq.monthly_credit_usd.toFixed(2)}</span>
                        {uq.daily_credit_usd != null && (
                          <span>Today: ${uq.spend_today_usd.toFixed(2)} / ${uq.daily_credit_usd.toFixed(2)}</span>
                        )}
                        <span className="capitalize">{uq.overage_action.replace('_', ' ')}</span>
                        {uq.admin_override && <span className="text-accent-amber">Custom</span>}
                      </div>
                    </div>
                    <div className="w-24">
                      <div className="h-1.5 rounded-full bg-midnight-400/50 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${pct > 90 ? 'bg-status-error' : pct > 70 ? 'bg-accent-amber' : 'bg-status-success'}`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                      <p className="text-[9px] text-starlight-500 text-right mt-0.5">{pct}%</p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

export default SettingsBilling

/**
 * Billing & Usage settings -- cost overview from real backend data.
 * Fetches from GET /billing/overview and /billing/by-provider.
 * No mock data. Shows actual usage or zeros.
 */
import { useEffect, useState, useCallback } from 'react'
import { Card, Badge } from '@/components/common'
import { DollarSign, BarChart3, Bell, TrendingUp, Layers, Calendar } from 'lucide-react'
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

  const monthlyPct = monthlyBudget > 0 ? Math.round((overview.monthly_cost / monthlyBudget) * 100) : 0
  const totalTokens = providers.reduce((sum, p) => sum + (p.total_tokens || 0), 0)

  return (
    <div className="space-y-6">
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
                    <p className="text-sm text-starlight-200">{p.provider}</p>
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
        <div className="space-y-4 max-w-md">
          <div>
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
          <div>
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
          <div>
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
    </div>
  )
}

export default SettingsBilling

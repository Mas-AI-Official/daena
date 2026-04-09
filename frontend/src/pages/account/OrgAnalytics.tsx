/**
 * OrgAnalytics -- Organization analytics dashboard.
 * Equivalent to Perplexity's /account/org/analytics
 */
import { BarChart3, TrendingUp, Users, Zap } from 'lucide-react'

export function OrgAnalytics() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Analytics</h1>
        <p className="text-sm text-starlight-400 mt-1">Usage analytics across your organization</p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-3xl">
        {[
          { label: 'Messages today', value: '0', icon: BarChart3, color: 'text-primary-400' },
          { label: 'Tokens used', value: '0', icon: TrendingUp, color: 'text-accent-cyan' },
          { label: 'Active users', value: '1', icon: Users, color: 'text-accent-purple' },
          { label: 'Skills invoked', value: '0', icon: Zap, color: 'text-accent-amber' },
        ].map((stat) => (
          <div key={stat.label} className="p-4 rounded-xl bg-midnight-300/30 border border-white/5">
            <stat.icon size={16} className={`${stat.color} mb-2`} />
            <p className="text-lg font-semibold text-starlight-100">{stat.value}</p>
            <p className="text-[10px] text-starlight-500">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Chart placeholder */}
      <div className="rounded-xl border border-white/5 p-6 max-w-3xl">
        <h3 className="text-sm font-medium text-starlight-200 mb-4">Usage over time</h3>
        <div className="h-48 flex items-center justify-center">
          <p className="text-sm text-starlight-500">Chart will render with usage data</p>
        </div>
      </div>

      {/* Department breakdown */}
      <div className="rounded-xl border border-white/5 p-6 max-w-3xl">
        <h3 className="text-sm font-medium text-starlight-200 mb-4">Activity by department</h3>
        <div className="space-y-2">
          {['Engineering', 'Product', 'Research', 'Marketing'].map((dept) => (
            <div key={dept} className="flex items-center gap-3">
              <span className="text-xs text-starlight-400 w-24">{dept}</span>
              <div className="flex-1 h-2 rounded-full bg-midnight-400 overflow-hidden">
                <div className="h-full rounded-full bg-primary-500/40" style={{ width: '0%' }} />
              </div>
              <span className="text-[10px] text-starlight-500 w-8 text-right">0</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default OrgAnalytics

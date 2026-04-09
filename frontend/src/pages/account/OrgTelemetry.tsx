/**
 * OrgTelemetry -- Heartbeat telemetry and monitoring dashboard.
 * Equivalent to Perplexity's /account/org/comet-telemetry
 */
import { Activity, Heart, Clock, CheckCircle2 } from 'lucide-react'

export function OrgTelemetry() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Heartbeat telemetry</h1>
        <p className="text-sm text-starlight-400 mt-1">Monitor Daena Heartbeat deployment and usage across your organization</p>
      </div>

      {/* Telemetry stats */}
      <div className="grid grid-cols-3 gap-4 max-w-2xl">
        {[
          { label: 'Heartbeat cycles', value: '0', icon: Heart, color: 'text-status-error' },
          { label: 'Avg cycle time', value: '--', icon: Clock, color: 'text-accent-cyan' },
          { label: 'Tasks completed', value: '0', icon: CheckCircle2, color: 'text-status-success' },
        ].map((stat) => (
          <div key={stat.label} className="p-4 rounded-xl bg-midnight-300/30 border border-white/5">
            <stat.icon size={16} className={`${stat.color} mb-2`} />
            <p className="text-lg font-semibold text-starlight-100">{stat.value}</p>
            <p className="text-[10px] text-starlight-500">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Telemetry log */}
      <div className="rounded-lg border border-white/5 overflow-hidden max-w-2xl">
        <div className="px-4 py-3 bg-midnight-300/20 border-b border-white/5 flex items-center gap-2">
          <Activity size={14} className="text-starlight-400" />
          <p className="text-xs font-medium text-starlight-300">Recent telemetry</p>
        </div>
        <div className="px-6 py-8 text-center">
          <p className="text-sm text-starlight-400">No Results</p>
          <p className="text-xs text-starlight-500 mt-1">
            Changes in usage can take up to 24 hours to appear.
          </p>
        </div>
      </div>
    </div>
  )
}

export default OrgTelemetry

/**
 * Governance settings -- mode selector, slider, tier info, shield laws.
 */
import { Card, Badge } from '@/components/common'
import { persistUiPref } from '@/stores/uiStore'
import { useUiStore } from '@/stores/uiStore'
import { Shield, Lock, AlertTriangle, Zap, Scale, Building2 } from 'lucide-react'
import type { GovernanceMode } from '@/types/api'

const GOVERNANCE_MODES: { value: GovernanceMode; label: string; icon: typeof Zap; desc: string; color: string }[] = [
  {
    value: 'UNLEASHED',
    label: 'Unleashed',
    icon: Zap,
    desc: 'No governance pipeline. Shield only. Raw power. Daena finds a way.',
    color: 'bg-status-error/20 text-status-error border-status-error/30',
  },
  {
    value: 'BALANCED',
    label: 'Balanced',
    icon: Scale,
    desc: 'Light governance. Auto-proceed most actions. Approval for dangerous ops only.',
    color: 'bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30',
  },
  {
    value: 'GOVERNED',
    label: 'Governed',
    icon: Building2,
    desc: 'Full 10-stage pipeline. All Hard Laws enforced. Enterprise mode.',
    color: 'bg-starlight-400/20 text-starlight-300 border-starlight-400/30',
  },
]

const SHIELD_LAWS = [
  'Audit logging runs in ALL modes (tamper-evident chain)',
  'Never exfiltrate client or founder data without consent',
  'Tenant isolation enforced at database level (never cross-tenant)',
  'Audit trail integrity (append-only, hash-chained)',
]

const SOFT_LAWS = [
  'No self-modification of governance laws',
  'No unbounded execution (timeout + resource limits)',
  'Founder override (logged but never blocked)',
  'No permanent deletion (archive pattern)',
  'Governance mode toggled by Founder only',
]

export function SettingsGovernance() {
  const { governanceMode, setGovernanceMode } = useUiStore()

  const handleModeChange = (mode: GovernanceMode) => {
    setGovernanceMode(mode)
    persistUiPref('default_governance_mode', mode)
  }

  return (
    <div className="space-y-6">
      {/* Governance Mode Selector */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Zap size={14} /> Governance Mode
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {GOVERNANCE_MODES.map(({ value, label, icon: Icon, desc, color }) => (
            <button
              key={value}
              onClick={() => handleModeChange(value)}
              className={`p-4 rounded-xl border text-left transition-all cursor-pointer ${
                governanceMode === value
                  ? `${color} border shadow-lg`
                  : 'bg-midnight-800/40 border-white/5 hover:border-white/15 text-starlight-400'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon size={16} />
                <span className="font-display font-semibold text-sm">{label}</span>
              </div>
              <p className="text-xs opacity-80 leading-relaxed">{desc}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Tier Breakdown */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <AlertTriangle size={14} /> Tier Breakdown
        </h3>
        <div className="space-y-2">
          {[
            { tier: 0, label: 'SILENT', desc: 'No logging, no checks', pct: '~40%' },
            { tier: 1, label: 'LOG', desc: 'Audit trail only', pct: '~30%' },
            { tier: 2, label: 'NOTIFY', desc: 'User notified', pct: '~15%' },
            { tier: 3, label: 'APPROVE', desc: 'Requires human approval', pct: '~10%' },
            { tier: 4, label: 'COUNCIL+APPROVE', desc: 'Multi-model council + human', pct: '~5%' },
          ].map((t) => (
            <div key={t.tier} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5">
              <Badge variant={t.tier <= 1 ? 'success' : t.tier <= 2 ? 'warning' : 'danger'} size="sm">
                T{t.tier}
              </Badge>
              <span className="text-xs text-starlight-200 flex-1">{t.label}</span>
              <span className="text-xs text-starlight-400">{t.desc}</span>
              <span className="text-[10px] text-starlight-500 w-10 text-right">{t.pct}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Shield Laws (always active) */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Shield size={14} className="text-accent-gold" /> Shield Laws (Always Active)
        </h3>
        <div className="space-y-2">
          {SHIELD_LAWS.map((law, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-accent-gold font-bold mt-0.5">{i + 1}.</span>
              <span className="text-starlight-300">{law}</span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-starlight-500 mt-3">
          Shield laws are enforced in ALL modes including Unleashed. They protect your data and IP.
        </p>
      </Card>

      {/* Soft Laws (GOVERNED only) */}
      <Card variant="glass" padding="lg" className={governanceMode !== 'GOVERNED' ? 'opacity-40' : ''}>
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Lock size={14} /> Governance Laws (Governed Mode Only)
        </h3>
        <div className="space-y-2">
          {SOFT_LAWS.map((law, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-accent-red font-bold mt-0.5">{i + 5}.</span>
              <span className="text-starlight-300">{law}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

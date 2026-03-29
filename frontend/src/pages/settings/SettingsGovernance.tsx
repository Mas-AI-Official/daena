/**
 * Governance settings — default slider, tier overrides, hard laws.
 */
import { Card, Badge } from '@/components/common'
import { GovernanceSlider } from '@/components/common'
import { persistUiPref } from '@/stores/uiStore'
import { useUiStore } from '@/stores/uiStore'
import { Shield, Lock, AlertTriangle } from 'lucide-react'

const HARD_LAWS = [
  'Never bypass human approval for Tier 3+ actions',
  'Never expose credentials or secrets in outputs',
  'Never modify governance rules without FOUNDER role',
  'Never delete data without explicit user consent',
  'Never impersonate a human identity',
  'Never execute recursive self-modification',
  'Never bypass DaenaBot governance layer',
  'Never share user data between tenants',
  'Never override hard-coded safety limits',
]

export function SettingsGovernance() {
  const { governanceSlider, setGovernanceSlider } = useUiStore()
  const handleSliderChange = (value: typeof governanceSlider) => {
    setGovernanceSlider(value)
    persistUiPref('default_governance_slider', value)
  }

  return (
    <div className="space-y-6">
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Shield size={14} /> Default Governance Level
        </h3>
        <div className="max-w-md">
          <GovernanceSlider value={governanceSlider} onChange={handleSliderChange} />
          <p className="text-xs text-starlight-500 mt-3">
            This sets the default for new sessions. Users can adjust per-session.
          </p>
        </div>
      </Card>

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

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Lock size={14} /> 9 Immutable Hard Laws
        </h3>
        <div className="space-y-2">
          {HARD_LAWS.map((law, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-accent-red font-bold mt-0.5">{i + 1}.</span>
              <span className="text-starlight-300">{law}</span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-starlight-500 mt-3">
          These laws are hard-coded and cannot be modified from the UI.
        </p>
      </Card>
    </div>
  )
}

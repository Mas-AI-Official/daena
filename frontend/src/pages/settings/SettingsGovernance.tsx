/**
 * Governance settings -- mode selector, slider, tier info, shield laws.
 *
 * PR-GOV-01: governance mode picker is gated to the FOUNDER role,
 * mirroring the backend field-level guard at
 * backend/app/api/v1/settings.py SENSITIVE_PREF_FIELDS. Non-Founders
 * see the current mode but cannot change it (the buttons are disabled
 * with a tooltip pointing back to Hard Law 8).
 */
import { Card, Badge } from '@/components/common'
import { persistUiPref } from '@/stores/uiStore'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { Shield, Lock, AlertTriangle, Zap, Scale, Building2, Info } from 'lucide-react'
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

const FOUNDER_ONLY_TOOLTIP =
  'Hard Law 8: governance mode is Founder-controlled. Ask a Founder ' +
  'to change the mode for this tenant.'

export function SettingsGovernance() {
  const { governanceMode, setGovernanceMode } = useUiStore()
  const userRole = useAuthStore((s) => s.user?.role)
  const isFounder = userRole === 'FOUNDER'

  const handleModeChange = (mode: GovernanceMode) => {
    if (!isFounder) return
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
        {!isFounder && (
          <div
            className="mb-3 flex items-start gap-2 px-3 py-2 rounded-lg bg-midnight-800/60 border border-accent-gold/20 text-xs text-starlight-300"
            role="status"
          >
            <Info size={14} className="text-accent-gold mt-0.5 shrink-0" />
            <span>
              Read-only. Governance mode for this tenant is set by the Founder
              (Hard Law 8). The current mode is shown highlighted.
            </span>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {GOVERNANCE_MODES.map(({ value, label, icon: Icon, desc, color }) => {
            const isCurrent = governanceMode === value
            return (
              <button
                key={value}
                type="button"
                onClick={() => handleModeChange(value)}
                disabled={!isFounder}
                title={!isFounder ? FOUNDER_ONLY_TOOLTIP : undefined}
                aria-disabled={!isFounder}
                className={`p-4 rounded-xl border text-left transition-all ${
                  isCurrent
                    ? `${color} border shadow-lg`
                    : 'bg-midnight-800/40 border-white/5 text-starlight-400'
                } ${
                  isFounder
                    ? 'cursor-pointer hover:border-white/15'
                    : 'cursor-not-allowed opacity-70'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={16} />
                  <span className="font-display font-semibold text-sm">{label}</span>
                  {isCurrent && !isFounder && (
                    <Badge variant="warning" size="sm">
                      Current
                    </Badge>
                  )}
                </div>
                <p className="text-xs opacity-80 leading-relaxed">{desc}</p>
              </button>
            )
          })}
        </div>
      </Card>

      {/* Internal tiers kept under debug disclosure only. Founder-facing control is the 3-mode selector above. */}
      <Card variant="glass" padding="lg">
        <details>
          <summary className="cursor-pointer text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
            <AlertTriangle size={14} /> Advanced internal tiers
          </summary>
          <p className="mt-2 text-xs text-starlight-500">
            Debug view only. The product control is Unleashed, Balanced, Governed.
          </p>
          <div className="mt-4 space-y-2">
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
        </details>
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

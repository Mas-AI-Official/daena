/**
 * GovernanceTrustPage -- Sprint-18 PR-2 (2026-05-06).
 *
 * Operator-facing surface for the trust ladder. Shows for each
 * (tool_id, template_class) pair: approvals count, rejections,
 * current granted tier, eligibility, and lock reason.
 *
 * Founder can raise / lower a tier. The mutation requires typing
 * the EXACT confirmation phrase the backend computes from the
 * (tool_id, tier) tuple. This is the single permitted path to
 * raise trust -- Daena's tool dispatches NEVER reach this page or
 * its backing endpoint.
 *
 * Honesty rules (locked, ADR-001):
 *   - All state comes from /api/v1/trust/policies and
 *     /api/v1/trust/eligible-tools. No hardcoded fake rows.
 *   - Forbidden tools render with a locked badge + reason; the UI
 *     refuses to even open a tier-raise dialog for them.
 *   - Inline error rendering for confirmation_phrase_mismatch /
 *     tool_forbidden / rejections_force_tier_none.
 */
import { useEffect, useState } from 'react'
import { Shield, Lock, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button } from '@/components/common'
import { api } from '@/lib/api'

interface PolicyRow {
  tool_id: string
  template_class: string
  max_auto_tier: 'none' | 'suggest_only' | 'auto_approve_low_risk' | 'auto_execute_low_risk_local'
  locked_reason: string | null
  approvals_count: number
  rejection_count: number
  last_approved_at: string | null
  last_rejected_at: string | null
  eligible: boolean
  forbidden: boolean
}

interface EligibilityResponse {
  eligible_tools: string[]
  forbidden_tools: string[]
  available_tiers: string[]
  min_approvals_to_graduate: number
}

interface TierSetResponse {
  tool_id: string
  template_class: string
  max_auto_tier: string
  expected_confirmation_phrase: string | null
  success: boolean
  error_code: string | null
}

interface TierDialogState {
  row: PolicyRow
  tier: 'none' | 'suggest_only' | 'auto_approve_low_risk'
  expectedPhrase: string
  typedPhrase: string
  error: string | null
}

const TIER_LABEL: Record<string, string> = {
  none: 'None',
  suggest_only: 'Suggest only',
  auto_approve_low_risk: 'Auto-approve low risk',
  auto_execute_low_risk_local: '[reserved -- unreachable]',
}

const TIER_COLOR: Record<string, 'gray' | 'gold' | 'green'> = {
  none: 'gray',
  suggest_only: 'gold',
  auto_approve_low_risk: 'green',
  auto_execute_low_risk_local: 'gray',
}

function buildExpectedPhrase(toolId: string, tier: string): string {
  return `I authorize trust tier ${tier} for ${toolId}`
}

export default function GovernanceTrustPage() {
  usePageTitle('Trust Ladder')
  const [rows, setRows] = useState<PolicyRow[] | null>(null)
  const [eligibility, setEligibility] = useState<EligibilityResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadCount, setReloadCount] = useState(0)
  const [dialog, setDialog] = useState<TierDialogState | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.get<PolicyRow[]>('/api/v1/trust/policies'),
      api.get<EligibilityResponse>('/api/v1/trust/eligible-tools'),
    ])
      .then(([policiesRes, eligibilityRes]) => {
        if (cancelled) return
        setRows(policiesRes.data)
        setEligibility(eligibilityRes.data)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setError('Failed to load trust state. Retry to refresh.')
        // eslint-disable-next-line no-console
        console.warn('trust.load_failed', err)
      })
    return () => {
      cancelled = true
    }
  }, [reloadCount])

  function openTierDialog(row: PolicyRow, tier: TierDialogState['tier']) {
    if (row.forbidden) return // double safety
    const expected = buildExpectedPhrase(row.tool_id, tier)
    setDialog({
      row,
      tier,
      expectedPhrase: expected,
      typedPhrase: '',
      error: null,
    })
  }

  async function submitTierChange() {
    if (!dialog) return
    setSubmitting(true)
    try {
      const r = await api.post<TierSetResponse>(
        '/api/v1/trust/policies/tier-set',
        {
          tool_id: dialog.row.tool_id,
          template_class: dialog.row.template_class,
          tier: dialog.tier,
          confirmation_phrase: dialog.typedPhrase,
        },
      )
      if (r.data.success) {
        setDialog(null)
        setReloadCount((c) => c + 1)
      } else {
        setDialog({ ...dialog, error: r.data.error_code || 'unknown_error' })
      }
    } catch (err) {
      setDialog({ ...dialog, error: 'request_failed' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-3">
              <Shield className="text-gold w-6 h-6" />
              Trust Ladder
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Per-(tool, template) approval graduation. Daena cannot raise
              her own tier. Operator graduates trust by repeated successful
              approval; rejection resets to NONE.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setReloadCount((c) => c + 1)}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </header>

        {eligibility && (
          <Card className="border-slate-700 bg-slate-900/50">
            <div className="p-4 space-y-2">
              <div className="text-xs uppercase tracking-wider text-slate-500">
                Eligibility (locked)
              </div>
              <div className="grid md:grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-slate-300 font-medium mb-1">
                    Eligible to graduate
                  </div>
                  <ul className="text-slate-400 text-xs space-y-1">
                    {eligibility.eligible_tools.map((t) => (
                      <li key={t} className="font-mono">{t}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-slate-300 font-medium mb-1 flex items-center gap-2">
                    <Lock className="w-3 h-3" />
                    Forbidden FOREVER
                  </div>
                  <ul className="text-slate-400 text-xs space-y-1">
                    {eligibility.forbidden_tools.map((t) => (
                      <li key={t} className="font-mono">{t}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="text-xs text-slate-500 pt-2 border-t border-slate-800">
                Minimum approvals to graduate: <strong className="text-slate-300">{eligibility.min_approvals_to_graduate}</strong>
                . Reserved tier <code>auto_execute_low_risk_local</code> is unreachable in Sprint-18.
              </div>
            </div>
          </Card>
        )}

        {error && (
          <Card className="border-red-700 bg-red-950/30">
            <div className="p-4 flex items-center gap-3 text-red-200">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </div>
          </Card>
        )}

        {rows === null && !error && (
          <Card className="border-slate-700 bg-slate-900/50">
            <div className="p-8 text-center text-slate-500">Loading...</div>
          </Card>
        )}

        {rows !== null && rows.length === 0 && (
          <Card className="border-slate-700 bg-slate-900/50">
            <div className="p-8 text-center text-slate-500">
              No trust rows yet. Approve a draft a few times and the ladder
              starts to build.
            </div>
          </Card>
        )}

        {rows && rows.length > 0 && (
          <div className="space-y-3">
            {rows.map((row) => (
              <Card
                key={`${row.tool_id}::${row.template_class}`}
                className="border-slate-700 bg-slate-900/50"
              >
                <div className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-sm text-slate-200 truncate">
                        {row.tool_id}
                      </div>
                      <div className="font-mono text-xs text-slate-500 truncate">
                        {row.template_class}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {row.forbidden ? (
                        <Badge color="red">
                          <Lock className="w-3 h-3 mr-1" /> Forbidden
                        </Badge>
                      ) : row.eligible ? (
                        <Badge color={TIER_COLOR[row.max_auto_tier] || 'gray'}>
                          {TIER_LABEL[row.max_auto_tier] || row.max_auto_tier}
                        </Badge>
                      ) : (
                        <Badge color="gray">Not eligible</Badge>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-xs">
                    <div>
                      <div className="text-slate-500">Approvals</div>
                      <div className="text-slate-200 font-medium">
                        {row.approvals_count}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Rejections</div>
                      <div
                        className={
                          row.rejection_count > 0
                            ? 'text-red-300 font-medium'
                            : 'text-slate-200 font-medium'
                        }
                      >
                        {row.rejection_count}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Last activity</div>
                      <div className="text-slate-300 truncate">
                        {row.last_approved_at?.slice(0, 16)
                          || row.last_rejected_at?.slice(0, 16)
                          || '—'}
                      </div>
                    </div>
                  </div>

                  {row.locked_reason && (
                    <div className="text-xs text-slate-400 italic">
                      Locked: {row.locked_reason.replace(/_/g, ' ')}
                    </div>
                  )}

                  {!row.forbidden && row.eligible && (
                    <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={row.max_auto_tier === 'none'}
                        onClick={() => openTierDialog(row, 'none')}
                      >
                        Lower to NONE
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={row.max_auto_tier === 'suggest_only'}
                        onClick={() => openTierDialog(row, 'suggest_only')}
                      >
                        Suggest only
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={row.max_auto_tier === 'auto_approve_low_risk'}
                        onClick={() =>
                          openTierDialog(row, 'auto_approve_low_risk')
                        }
                      >
                        <CheckCircle2 className="w-4 h-4 mr-1" />
                        Grant auto-approve
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {dialog && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <Card className="border-slate-700 bg-slate-900 max-w-lg w-full">
            <div className="p-5 space-y-4">
              <h2 className="text-lg font-semibold text-slate-100">
                Confirm tier change
              </h2>
              <div className="text-sm text-slate-400 space-y-2">
                <p>
                  Setting tier <strong className="text-gold">{TIER_LABEL[dialog.tier]}</strong> for:
                </p>
                <div className="font-mono text-xs bg-slate-800 rounded p-2">
                  {dialog.row.tool_id}
                  <br />
                  {dialog.row.template_class}
                </div>
                <p className="text-amber-300">
                  Type the confirmation phrase exactly:
                </p>
                <code className="block bg-slate-800 rounded p-2 text-xs text-slate-100 break-all">
                  {dialog.expectedPhrase}
                </code>
              </div>
              <input
                type="text"
                value={dialog.typedPhrase}
                onChange={(e) =>
                  setDialog({ ...dialog, typedPhrase: e.target.value, error: null })
                }
                className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100"
                placeholder="Type the phrase..."
                disabled={submitting}
              />
              {dialog.error && (
                <div className="text-xs text-red-300">
                  Error: {dialog.error.replace(/_/g, ' ')}
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setDialog(null)}
                  disabled={submitting}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={submitTierChange}
                  disabled={submitting || dialog.typedPhrase !== dialog.expectedPhrase}
                >
                  {submitting ? 'Saving...' : 'Confirm'}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

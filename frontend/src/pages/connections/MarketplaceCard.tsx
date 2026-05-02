/**
 * MarketplaceCard -- Daena App Store + MCP Store card.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): every catalog entry
 * renders as a card with an honest lifecycle pill, capabilities,
 * required-config preview (NEVER values), and a primary action that
 * matches the lifecycle:
 *   - available / needs_setup -> "Setup guide" (opens drawer)
 *   - installed / configured / reachable -> "Probe" (calls real probe)
 *   - callable -> "Re-test"
 *   - failed -> "Retry probe"
 *   - skill_pack -> "Open" (no probe)
 *   - disabled -> "Enable"
 *   - archived -> no primary action
 *
 * Honesty:
 *   - Status pill mirrors the V2 truth ladder; never claims callable
 *     without a real probe
 *   - Required env vars surface as NAMES only
 *   - install command shown as code block; Daena does NOT execute it
 *   - failure_reason inline below the lifecycle pill
 *   - last-checked timestamp visible when present
 */

import { useState } from 'react'
import {
  Activity, AlertTriangle, BookOpen, ExternalLink, Loader2, Power,
  ShieldAlert, Wrench, X,
} from 'lucide-react'

import {
  type InstallPlan,
  type MarketplaceCard as MarketplaceCardType,
  type RiskLevel,
  RISK_TONE,
  fetchInstallPlan,
  lifecycleTone,
} from '@/hooks/useMarketplace'

interface MarketplaceCardProps {
  card: MarketplaceCardType
  /** Probe action -- pass through to V2 probe endpoint when row exists. */
  onProbe?: (rowId: string) => Promise<void>
  /** Enable action -- toggles disabled=false on existing V2 row. */
  onEnable?: (rowId: string) => Promise<void>
  /** Optional click target when lifecycle is callable / enabled. */
  onOpen?: (card: MarketplaceCardType) => void
  /** When true, the parent has fired a probe and we should spinner the action button. */
  busy?: boolean
}

export default function MarketplaceCard({
  card, onProbe, onEnable, onOpen, busy = false,
}: MarketplaceCardProps) {
  const tone = lifecycleTone(card.lifecycle)
  const [setupOpen, setSetupOpen] = useState(false)
  const [setupBusy, setSetupBusy] = useState(false)
  const [installPlan, setInstallPlan] = useState<InstallPlan | null>(null)
  const [setupError, setSetupError] = useState<string | null>(null)

  async function openSetup() {
    setSetupOpen(true)
    if (installPlan) return
    setSetupBusy(true)
    setSetupError(null)
    const res = await fetchInstallPlan(card.catalog.id)
    setSetupBusy(false)
    if (res.ok && res.plan) {
      setInstallPlan(res.plan)
    } else {
      setSetupError(res.error ?? 'Failed to load install plan')
    }
  }

  function handleAction() {
    switch (card.primary_action) {
      case 'setup_guide':
        void openSetup()
        return
      case 'test':
        if (card.v2_row_id && onProbe) void onProbe(card.v2_row_id)
        return
      case 'enable':
        if (card.v2_row_id && onEnable) void onEnable(card.v2_row_id)
        return
      case 'open':
        if (onOpen) onOpen(card)
        return
      default:
        return
    }
  }

  const hasAction = card.primary_action !== 'none'
  const cat = card.catalog

  return (
    <>
      <article
        className={`flex h-full flex-col gap-3 rounded-xl border bg-midnight-400/40 p-4 transition-colors hover:border-white/10 ${tone.border}`}
      >
        <header className="flex items-start gap-3">
          <CardIcon kind={cat.kind} risk={cat.risk_level} />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-starlight-100">
                  {cat.display_name}
                </h3>
                <p className="text-[11px] text-starlight-500">
                  {cat.vendor} · {cat.category.replace(/_/g, ' ')}
                </p>
              </div>
              <RiskBadge risk={cat.risk_level} />
            </div>
          </div>
        </header>

        <p className="text-xs text-starlight-300">{cat.short_description}</p>

        {cat.capabilities.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {cat.capabilities.slice(0, 4).map((cap) => (
              <li
                key={cap}
                className="rounded bg-white/[0.04] px-2 py-0.5 text-[10px] text-starlight-300"
              >
                {cap}
              </li>
            ))}
            {cat.capabilities.length > 4 && (
              <li className="rounded bg-white/[0.04] px-2 py-0.5 text-[10px] text-starlight-500">
                +{cat.capabilities.length - 4} more
              </li>
            )}
          </ul>
        )}

        <div className="mt-auto space-y-2">
          {/* Lifecycle + auth requirement */}
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${tone.border} ${tone.bg} ${tone.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
              {tone.label}
            </span>
            {cat.auth_type !== 'none' && (
              <span
                className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-starlight-400"
                title={`Auth: ${cat.auth_type}`}
              >
                {cat.auth_type}
              </span>
            )}
            {cat.install_method === 'coming-soon' && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                coming soon
              </span>
            )}
          </div>

          {/* Required env var names (never values) */}
          {cat.required_env_vars.length > 0 && (
            <p className="text-[10px] text-starlight-500">
              Needs: {cat.required_env_vars.join(', ')}
            </p>
          )}

          {/* Last checked */}
          {card.v2_last_probe_at && (
            <p className="text-[10px] text-starlight-500">
              Last checked: {new Date(card.v2_last_probe_at).toLocaleString()}
            </p>
          )}

          {/* Failure inline */}
          {card.lifecycle === 'failed' && card.v2_failure_reason && (
            <div className="flex items-start gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/5 px-2 py-1 text-[11px] text-rose-200">
              <AlertTriangle size={11} className="mt-0.5 shrink-0" />
              <span>{card.v2_failure_reason}</span>
            </div>
          )}

          {/* Skill-pack honest disclaimer */}
          {card.lifecycle === 'skill_pack' && (
            <div className="flex items-start gap-1.5 rounded-md border border-violet-500/30 bg-violet-500/5 px-2 py-1 text-[11px] text-violet-200">
              <BookOpen size={11} className="mt-0.5 shrink-0" />
              <span>
                Skill pack -- not callable until paired with a runtime, MCP, or app.
              </span>
            </div>
          )}

          {/* Action row */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <a
              href={cat.official_url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-starlight-500 hover:text-starlight-300"
              onClick={(e) => {
                if (!cat.official_url) e.preventDefault()
              }}
            >
              <ExternalLink size={10} />
              Source
            </a>
            {hasAction && (
              <button
                onClick={handleAction}
                disabled={busy || (card.primary_action === 'enable' && !card.v2_row_id)}
                className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-[11px] font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
              >
                {busy && <Loader2 size={11} className="animate-spin" />}
                {!busy && card.primary_action === 'test' && <Activity size={11} />}
                {!busy && card.primary_action === 'enable' && <Power size={11} />}
                {!busy && card.primary_action === 'setup_guide' && <Wrench size={11} />}
                {!busy && card.primary_action === 'open' && <ExternalLink size={11} />}
                {card.primary_action_label}
              </button>
            )}
          </div>
        </div>
      </article>

      {setupOpen && (
        <SetupDrawer
          card={card}
          plan={installPlan}
          loading={setupBusy}
          error={setupError}
          onClose={() => setSetupOpen(false)}
        />
      )}
    </>
  )
}

// ── Sub-components ──

function CardIcon({ kind, risk }: { kind: string; risk: RiskLevel }) {
  const iconBg =
    risk === 'high'
      ? 'bg-rose-500/15 text-rose-200'
      : risk === 'medium'
        ? 'bg-amber-500/10 text-amber-200'
        : 'bg-cyan-500/10 text-cyan-200'
  return (
    <div
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${iconBg}`}
      title={`${kind.replace(/_/g, ' ')} (risk: ${risk})`}
    >
      <KindIcon kind={kind} />
    </div>
  )
}

function KindIcon({ kind }: { kind: string }) {
  // Use a simple letter-based icon to avoid importing 8 different
  // lucide icons for visual variety. Risk-tinted background already
  // distinguishes severity.
  const letter =
    kind === 'mcp_server' ? 'M' :
      kind === 'oauth_app' ? 'O' :
        kind === 'browser_tool' ? 'B' :
          kind === 'computer_use' ? 'C' :
            kind === 'cli_runtime' ? 'R' :
              kind === 'api_provider' ? 'A' :
                kind === 'local_model' ? 'L' :
                  kind === 'skill_pack' ? 'S' : '?'
  return <span className="font-mono text-sm">{letter}</span>
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  const tone = RISK_TONE[risk]
  return (
    <span
      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${tone.text} ${tone.bg}`}
      title={`Risk: ${risk}. Asset Shield + governance still gate every call.`}
    >
      {risk === 'high' && <ShieldAlert size={10} className="mr-1 inline" />}
      {risk}
    </span>
  )
}

function SetupDrawer({
  card, plan, loading, error, onClose,
}: {
  card: MarketplaceCardType
  plan: InstallPlan | null
  loading: boolean
  error: string | null
  onClose: () => void
}) {
  const cat = card.catalog
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              Setup guide
            </p>
            <h2 className="text-lg font-semibold text-starlight-100">
              {cat.display_name}
            </h2>
            <p className="mt-1 text-xs text-starlight-400">
              {cat.short_description}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 p-1.5 text-starlight-300 hover:bg-white/10"
            aria-label="Close setup guide"
          >
            <X size={14} />
          </button>
        </header>

        {loading && (
          <div className="rounded-lg border border-white/5 bg-white/[0.02] py-8 text-center text-sm text-starlight-400">
            <Loader2 size={16} className="mr-2 inline animate-spin" />
            Loading install plan...
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
            <AlertTriangle size={14} className="mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {plan && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 rounded-md border border-white/5 bg-white/[0.03] px-3 py-2 text-[11px] text-starlight-400">
              <span>
                Vendor: <strong className="text-starlight-200">{cat.vendor}</strong>
              </span>
              <span>·</span>
              <span>
                Auth: <strong className="text-starlight-200">{cat.auth_type}</strong>
              </span>
              <span>·</span>
              <span>
                Install:{' '}
                <strong className="text-starlight-200">{plan.install_method}</strong>
              </span>
              <span>·</span>
              <span>
                Risk: <strong className="text-starlight-200">{cat.risk_level}</strong>
              </span>
            </div>

            <ol className="space-y-3">
              {plan.steps.map((step, idx) => (
                <li
                  key={`${step.kind}-${idx}`}
                  className="rounded-lg border border-white/5 bg-white/[0.02] p-3"
                >
                  <div className="mb-1 flex items-center gap-2">
                    <span className="rounded-full bg-primary-500/15 px-2 py-0.5 text-[10px] font-medium text-primary-200">
                      {step.kind}
                    </span>
                    <span className="text-[10px] text-starlight-500">
                      Step {idx + 1}
                    </span>
                  </div>
                  <p className="text-sm text-starlight-200">{step.text}</p>
                  {step.command && (
                    <pre className="mt-2 overflow-x-auto rounded-md border border-white/5 bg-midnight-900/50 p-2 text-[11px] text-emerald-200">
                      <code>{step.command}</code>
                    </pre>
                  )}
                  {step.url && (
                    <a
                      href={step.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-[11px] text-accent-cyan hover:underline"
                    >
                      <ExternalLink size={11} />
                      {step.url}
                    </a>
                  )}
                </li>
              ))}
            </ol>

            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200">
              <strong>Daena does not execute install commands automatically.</strong>{' '}
              Copy each command into your own terminal. After install, run{' '}
              <strong>Discover installed tools</strong> in the Connections page
              header to import the new connector into Daena.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

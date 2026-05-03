/**
 * PluginDetailDrawer -- Codex/Claude Desktop-style detail modal.
 *
 * PR-CONN-PLUGIN-PARITY-UX (2026-05-02): replaces the inline
 * SetupDrawer that lived in PluginCardView. Now a dedicated component
 * that surfaces the FULL plugin contract:
 *
 *   - Title + brand icon + vendor
 *   - One-paragraph "what this plugin lets Daena do"
 *   - Included MCP server / OAuth provider (when applicable)
 *   - Included skills / capabilities (full list)
 *   - Required permissions
 *   - Required env var NAMES (never values)
 *   - Install / setup steps from /install-plan endpoint
 *   - Auth / connect status
 *   - Probe / test status
 *   - Risk level + supported OS
 *   - Action buttons matching the founder vocabulary
 *
 * Honesty:
 *   - Status reflects V2 truth. NEVER claims callable without a probe.
 *   - "Configure keys in Settings" deep-link for provider rows.
 *   - Install steps are metadata-only -- never auto-executed.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity, AlertTriangle, BookOpen, ExternalLink, Loader2, Power,
  ShieldAlert, ShieldCheck, X,
} from 'lucide-react'

import {
  type BrowserProbeReport,
  type InstallPlan,
  fetchInstallPlan,
  runBrowserProbe,
} from '@/hooks/useMarketplace'
import { type PluginCard, pluginStatusTone } from './pluginCard'
import { pluginIconFor, pluginIconTone } from './pluginIcons'

interface PluginDetailDrawerProps {
  plugin: PluginCard
  onClose: () => void
  onProbe?: (rowId: string) => Promise<void>
  onEnable?: (rowId: string) => Promise<void>
  busy?: boolean
}

export default function PluginDetailDrawer({
  plugin, onClose, onProbe, onEnable, busy = false,
}: PluginDetailDrawerProps) {
  const navigate = useNavigate()
  const [plan, setPlan] = useState<InstallPlan | null>(null)
  const [planLoading, setPlanLoading] = useState(true)
  const [planError, setPlanError] = useState<string | null>(null)
  const [browserProbe, setBrowserProbe] = useState<BrowserProbeReport | null>(null)
  const [browserProbeLoading, setBrowserProbeLoading] = useState(false)
  const [browserProbeError, setBrowserProbeError] = useState<string | null>(null)

  const isBrowserOrComputerUse =
    plugin.source.catalog.kind === 'browser_tool' ||
    plugin.source.catalog.kind === 'computer_use'

  async function handleVerifyLocally() {
    setBrowserProbeLoading(true)
    setBrowserProbeError(null)
    const res = await runBrowserProbe(plugin.id)
    setBrowserProbeLoading(false)
    if (res.ok && res.report) {
      setBrowserProbe(res.report)
    } else {
      setBrowserProbeError(res.error ?? 'Local probe failed')
    }
  }

  useEffect(() => {
    let cancelled = false
    setPlanLoading(true)
    setPlanError(null)
    void (async () => {
      const res = await fetchInstallPlan(plugin.id)
      if (cancelled) return
      setPlanLoading(false)
      if (res.ok && res.plan) setPlan(res.plan)
      else setPlanError(res.error ?? 'Failed to load install plan')
    })()
    return () => {
      cancelled = true
    }
  }, [plugin.id])

  const tone = pluginStatusTone(plugin.status)
  const Icon = pluginIconFor(plugin.id, plugin.source.catalog.kind, plugin.name)
  const iconBg = pluginIconTone(plugin.risk_level)
  const isProvider = plugin.source.catalog.kind === 'api_provider'

  function handlePrimary() {
    switch (plugin.primary_action) {
      case 'configure':
        if (isProvider) {
          navigate('/account/api-keys')
          onClose()
          return
        }
        return  // setup steps shown inline, no extra action
      case 'test':
        if (plugin.v2_row_id && onProbe) void onProbe(plugin.v2_row_id)
        return
      case 'connect':
        // OAuth flows live in legacy connector_oauth router today;
        // a future PR can wire the V2 OAuth flow inline.
        return
      case 'open':
      case 'install':
      case 'setup_guide':
        return
      default:
        return
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <header className="flex items-start gap-4 border-b border-white/5 p-5">
          <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
            <Icon size={32} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              {plugin.is_skill_pack ? 'Skill pack' : 'Plugin'}
            </p>
            <h2 className="mt-0.5 text-xl font-semibold text-starlight-100">
              {plugin.name}
            </h2>
            <p className="text-xs text-starlight-400">
              {plugin.vendor} · {plugin.category_label}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${tone.border} ${tone.bg} ${tone.text}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
                {plugin.status_label}
              </span>
              <RiskInline risk={plugin.risk_level} />
              {plugin.is_skill_pack && (
                <span className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[10px] text-violet-200">
                  <BookOpen size={9} className="mr-1 inline" />
                  skill pack
                </span>
              )}
              {plugin.install_method === 'coming-soon' && (
                <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                  coming soon
                </span>
              )}
              <span
                className="rounded-md bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-starlight-500"
                title="Internal backend type"
              >
                {plugin.backing_types.join(' / ')}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 p-1.5 text-starlight-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </header>

        <div className="space-y-5 p-5">
          {/* ── What this plugin does ── */}
          <Section title="What this plugin lets Daena do">
            <p className="text-sm text-starlight-200">{plugin.description}</p>
            {plugin.is_skill_pack_caption && (
              <div className="mt-2 flex items-start gap-1.5 rounded-md border border-violet-500/30 bg-violet-500/5 px-2 py-1.5 text-[11px] text-violet-100">
                <BookOpen size={12} className="mt-0.5 shrink-0" />
                <span>{plugin.is_skill_pack_caption}</span>
              </div>
            )}
            {plugin.is_skill_pack && (
              <p className="mt-2 text-[11px] text-starlight-500">
                Pair this skill pack with a runtime, MCP, or app that
                exposes the corresponding tools to make it actionable.
              </p>
            )}
          </Section>

          {/* ── Capabilities / included skills ── */}
          {plugin.included_skills.length > 0 && (
            <Section title="Included capabilities">
              <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {plugin.included_skills.map((cap) => (
                  <li
                    key={cap}
                    className="flex items-start gap-1.5 rounded-md bg-white/[0.03] px-2 py-1 text-[11px] text-starlight-200"
                  >
                    <ShieldCheck size={11} className="mt-0.5 text-emerald-300" />
                    {cap}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* ── Required permissions / env vars ── */}
          {plugin.required_env_vars.length > 0 && (
            <Section title="Required permissions">
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
                <strong>Env var NAMES (Daena never reads the values):</strong>
                <ul className="mt-1.5 grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {plugin.required_env_vars.map((env) => (
                    <li key={env}>
                      <code className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-100">
                        {env}
                      </code>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-[10px] text-amber-200/70">
                  Set these in Settings -&gt; API Keys (vault-backed) or in the
                  source CLI's own env. Daena's Configure flow never asks
                  you to paste secrets into the catalog UI.
                </p>
              </div>
            </Section>
          )}

          {/* ── Provider key deep-link ── */}
          {isProvider && (
            <Section title="Where keys live">
              <div className="flex items-start gap-2 rounded-lg border border-white/5 bg-white/[0.03] p-3 text-xs text-starlight-300">
                <ShieldCheck size={12} className="mt-0.5 text-accent-cyan" />
                <div className="flex-1">
                  <p>
                    <strong className="text-starlight-100">Configure keys in Settings.</strong>{' '}
                    Connections shows whether Daena can call the provider; the
                    actual API key lives in the vault-backed Settings -&gt;
                    API Keys page.
                  </p>
                  <button
                    onClick={() => {
                      navigate('/account/api-keys#provider-keys')
                      onClose()
                    }}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-[11px] font-medium text-accent-cyan hover:bg-accent-cyan/20"
                  >
                    Open Settings -&gt; API Keys
                    <ExternalLink size={11} />
                  </button>
                </div>
              </div>
            </Section>
          )}

          {/* ── Truth ladder snapshot ── */}
          {plugin.source.v2_truth && (
            <Section title="Probe status">
              <ul className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                {(
                  ['detected', 'configured', 'imported', 'reachable', 'authenticated', 'callable'] as const
                ).map((dim) => {
                  const t = plugin.source.v2_truth![dim]
                  const ok = t.value
                  const failed = !!t.failure_at && (!t.at || t.failure_at >= t.at)
                  return (
                    <li
                      key={dim}
                      title={t.failure_reason || (ok ? `${dim} ok` : `${dim} not yet proven`)}
                      className={`flex items-center justify-between rounded px-2 py-1 text-[10px] ${
                        ok
                          ? 'bg-emerald-500/15 text-emerald-200'
                          : failed
                            ? 'bg-rose-500/15 text-rose-200'
                            : 'bg-slate-500/15 text-slate-300'
                      }`}
                    >
                      <span>{dim}</span>
                      <span>{ok ? '✓' : failed ? '✗' : '·'}</span>
                    </li>
                  )
                })}
              </ul>
              {/* CLI runtimes: surface auth_unknown with a softer advisory.
                  PR-CONN-CLI-PROBE matches on failure_reason prefix
                  ('auth_unknown:') so the operator sees the CLI is
                  installed + reachable, just that Daena cannot safely
                  verify login yet (e.g. grok_cli has no documented
                  status command). */}
              {plugin.source.catalog.kind === 'cli_runtime' &&
                plugin.failure_reason &&
                plugin.failure_reason.startsWith('auth_unknown') && (
                  <div className="mt-2 flex items-start gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[11px] text-amber-100">
                    <ShieldCheck size={12} className="mt-0.5 shrink-0 text-amber-300" />
                    <span>
                      <strong>CLI installed, but Daena cannot safely verify login yet.</strong>{' '}
                      Run the runtime's own login command in your terminal,
                      then re-test from this drawer.
                    </span>
                  </div>
                )}
              {plugin.failure_reason &&
                !(
                  plugin.source.catalog.kind === 'cli_runtime' &&
                  plugin.failure_reason.startsWith('auth_unknown')
                ) && (
                  <p className="mt-2 text-[11px] text-rose-300">
                    Last failure: {plugin.failure_reason}
                  </p>
                )}
              {plugin.last_checked && (
                <p className="mt-1 text-[10px] text-starlight-500">
                  Last checked: {new Date(plugin.last_checked).toLocaleString()}
                </p>
              )}
            </Section>
          )}

          {/* ── Verify locally (browser / computer-use) ──
              PR-CONN-BROWSER-PROBE: lets the operator run a SAFE
              local check (Playwright launches headless to about:blank,
              other tools just check launcher binary on PATH) before
              installing. Never opens external sites. */}
          {isBrowserOrComputerUse && (
            <Section title="Verify locally">
              <p className="text-[11px] text-starlight-400">
                Run a SAFE pre-install check on this machine. Playwright
                launches a headless browser to <code>about:blank</code> and
                evaluates a tiny harmless expression; other tools just
                verify the launcher binary is present.
              </p>
              <div className="mt-2 flex items-start gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/5 px-2 py-1.5 text-[11px] text-amber-100">
                <ShieldAlert size={11} className="mt-0.5 shrink-0 text-amber-300" />
                <span>
                  Browser tools run locally and require explicit permission
                  per call. Daena does <strong>not</strong> bypass anti-bot
                  systems and never claims stealth or evasion.
                </span>
              </div>
              <button
                onClick={() => void handleVerifyLocally()}
                disabled={browserProbeLoading}
                className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-[11px] font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
              >
                {browserProbeLoading ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Activity size={11} />
                )}
                {browserProbeLoading ? 'Probing...' : 'Verify locally'}
              </button>

              {browserProbeError && (
                <div className="mt-2 flex items-start gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/5 px-2 py-1.5 text-[11px] text-rose-200">
                  <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                  <span>{browserProbeError}</span>
                </div>
              )}

              {browserProbe && (
                <div className="mt-3 space-y-2">
                  <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                    <ProbeKv
                      label="Package"
                      value={browserProbe.package_status}
                      ok={browserProbe.package_status === 'installed'}
                    />
                    <ProbeKv
                      label="Browser"
                      value={browserProbe.browser_status}
                      ok={
                        browserProbe.browser_status === 'ready' ||
                        browserProbe.browser_status === 'not_required'
                      }
                    />
                  </div>
                  {browserProbe.success && browserProbe.capabilities.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-starlight-500">
                        Safe local capabilities
                      </p>
                      <ul className="mt-1 flex flex-wrap gap-1">
                        {browserProbe.capabilities.map((cap) => (
                          <li
                            key={cap}
                            className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-200"
                          >
                            {cap}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {!browserProbe.success && browserProbe.failure_reason && (
                    <div className="rounded-md border border-rose-500/30 bg-rose-500/5 px-2 py-1.5 text-[11px] text-rose-200">
                      <code>{browserProbe.failure_reason}</code>
                    </div>
                  )}
                </div>
              )}
            </Section>
          )}

          {/* ── Install / setup steps ── */}
          {!plugin.is_skill_pack && (
            <Section title={`Install / setup (${plugin.install_method})`}>
              {planLoading && (
                <div className="rounded-lg border border-white/5 bg-white/[0.02] py-6 text-center text-xs text-starlight-400">
                  <Loader2 size={14} className="mr-2 inline animate-spin" />
                  Loading install plan...
                </div>
              )}
              {planError && (
                <div className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                  <AlertTriangle size={12} className="mt-0.5" />
                  <span>{planError}</span>
                </div>
              )}
              {plan && (
                <div className="space-y-2">
                  <ol className="space-y-2">
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
                        <p className="text-xs text-starlight-200">{step.text}</p>
                        {step.command && (
                          <pre className="mt-2 overflow-x-auto rounded-md border border-white/5 bg-midnight-900/60 p-2 text-[10px] text-emerald-200">
                            <code>{step.command}</code>
                          </pre>
                        )}
                        {step.url && (
                          <a
                            href={step.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-2 inline-flex items-center gap-1 text-[10px] text-accent-cyan hover:underline"
                          >
                            <ExternalLink size={10} />
                            {step.url}
                          </a>
                        )}
                      </li>
                    ))}
                  </ol>
                  <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[10px] text-amber-200">
                    <strong>Daena does not execute install commands automatically.</strong>{' '}
                    Copy each command into your own terminal. After install, run{' '}
                    <strong>Discover installed tools</strong> in the Connections
                    page header to import the new connector.
                  </div>
                </div>
              )}
            </Section>
          )}

          {/* ── Compatibility ── */}
          <Section title="Compatibility">
            <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
              <KV label="Auth" value={plugin.auth_type} />
              <KV label="Risk" value={plugin.risk_level} />
              <KV label="Install" value={plugin.install_method} />
              <KV
                label="OS"
                value={plugin.compatible_os.length === 0 ? 'any' : plugin.compatible_os.join(', ')}
              />
            </div>
            {plugin.official_url && (
              <a
                href={plugin.official_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1 text-[11px] text-accent-cyan hover:underline"
              >
                <ExternalLink size={11} />
                Vendor documentation
              </a>
            )}
          </Section>
        </div>

        {/* ── Footer action bar ── */}
        <footer className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-white/5 bg-midnight-400/95 px-5 py-3">
          <button
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
          >
            Close
          </button>
          {plugin.action_enabled && plugin.primary_action !== 'setup_guide' && (
            <button
              onClick={handlePrimary}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 size={11} className="animate-spin" />
              ) : plugin.primary_action === 'test' ? (
                <Activity size={11} />
              ) : plugin.primary_action === 'connect' ? (
                <Power size={11} />
              ) : (
                <ExternalLink size={11} />
              )}
              {plugin.primary_action_label}
            </button>
          )}
        </footer>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
        {title}
      </h3>
      {children}
    </section>
  )
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wider text-starlight-500">{label}</p>
      <p className="mt-0.5 truncate text-xs text-starlight-200">{value}</p>
    </div>
  )
}

function ProbeKv({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  const tone = ok
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
    : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
  return (
    <div className={`flex items-center justify-between gap-2 rounded-md border px-2 py-1 ${tone}`}>
      <span className="text-[10px] uppercase tracking-wider opacity-80">{label}</span>
      <span className="text-[11px]">{value}</span>
    </div>
  )
}

function RiskInline({ risk }: { risk: PluginCard['risk_level'] }) {
  const tone =
    risk === 'high'
      ? { text: 'text-rose-300', bg: 'bg-rose-500/10' }
      : risk === 'medium'
        ? { text: 'text-amber-300', bg: 'bg-amber-500/10' }
        : { text: 'text-emerald-300', bg: 'bg-emerald-500/10' }
  return (
    <span
      className={`rounded-md px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${tone.text} ${tone.bg}`}
    >
      {risk === 'high' && <ShieldAlert size={10} className="mr-1 inline" />}
      {risk}
    </span>
  )
}

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
  Activity, AlertTriangle, ArrowRight, BookOpen, CheckCircle2,
  ChevronDown, ChevronRight, ExternalLink, KeyRound, Loader2,
  MessageSquare, Power, Server, ShieldAlert, ShieldCheck, Sparkles, X,
} from 'lucide-react'

import {
  type BrowserProbeReport,
  type InstallPlan,
  fetchInstallPlan,
  runBrowserProbe,
} from '@/hooks/useMarketplace'
import {
  type PluginCard,
  officialityLabel,
  officialityTone,
  pluginStatusTone,
  skillReadiness,
} from './pluginCard'
import OAuthLifecyclePanel from './OAuthLifecyclePanel'
import SkillBundleSection from './SkillBundleSection'
import { pluginIconFor, pluginIconTone } from './pluginIcons'
// PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING (2026-05-03): writing into the
// chat composer is the FIRST safe execution path -- click a suggested
// prompt and a draft lands in the textarea (no auto-send, no tools).
import { draftFromSuggestedPrompt } from '@/lib/composerBridge'
import { toast } from '@/stores/toastStore'

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
          // PR-CONN-PHASE2-PREFLIGHT-GREEN (2026-05-03): canonical
          // anchor target. /account/api-keys is not a registered React
          // Router path -- AccountPage owns /account with section
          // anchors (#provider-keys / #oauth-clients). Same fix shape
          // as OAuthConnectDrawer.handleConfigure().
          navigate('/account#provider-keys')
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
              {/* Officiality badge: trust signal pulled from
                  PR-CONN-MCP-CATALOG-SKILL-BUNDLES so the operator can
                  distinguish vendor-shipped from community-curated
                  inside the drawer too (the card already shows it). */}
              {(() => {
                const oTone = officialityTone(plugin.officiality)
                const oLabel = officialityLabel(plugin.officiality)
                return (
                  <span
                    className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${oTone.border} ${oTone.bg} ${oTone.text}`}
                    title={`Source tier: ${oLabel}`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${oTone.dot}`} />
                    {oLabel}
                  </span>
                )
              })()}
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
          {/* ── What Daena can do ──
              PR-CONN-PLUGIN-SKILLS-UX-WIRING (2026-05-03): leads with
              concrete suggested_prompts when the catalog has them
              (Codex-style "Triage open issues for me"); falls back to
              the one-line short_description otherwise. This is the
              first thing the operator reads -- it should answer "what
              does Daena USE this plugin to do?" in plain English. */}
          <Section title="What Daena can do">
            <DaenaIntent plugin={plugin} navigate={navigate} onClose={onClose} />
          </Section>

          {/* ── Connection steps (4-rung ladder) ──
              Visual ladder showing where the plugin currently sits:
              MCP install -> Auth -> Test -> Skills ready. Each rung
              tints based on the V2 truth ladder so the operator sees
              exactly which step is blocking. */}
          {!plugin.is_skill_pack && (
            <Section title="Connection steps">
              <ConnectionLadder plugin={plugin} />
            </Section>
          )}

          {/* ── Skills (honeycomb cluster) ──
              Replaces the legacy flat "Included capabilities" list.
              Chips are LOCKED until lifecycle reaches callable; click
              shows a "Connect first" message instead of executing.
              PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1: ready chips with
              a registered Phase 1 action also surface a "Use in chat"
              button that drafts a safe template into the composer.
              The drawer's onClose is passed so a successful draft
              tear-down before navigating to /chat. */}
          <Section title="Skills">
            <SkillBundleSection plugin={plugin} onCloseParent={onClose} />
          </Section>

          {/* ── OAuth lifecycle (refresh / disconnect / archive) ──
              PR-CONN-OAUTH-LIFECYCLE-FRONTEND (2026-05-03):
              Renders only for OAuth-backed plugins (auth_type=oauth)
              with a CONNECTED ConnectorInstance. Otherwise the panel
              returns null -- no clutter on plugins that have nothing
              to manage. */}
          <OAuthLifecyclePanel plugin={plugin} />

          {/* ── Permissions ──
              Combines the catalog's permissions_summary (Read/Write/
              Network) with the env-var NAMES the plugin needs. We
              never display secret VALUES -- the operator pastes them
              in the API Keys page or the source CLI's own env. */}
          {(plugin.permissions_summary.length > 0 || plugin.required_env_vars.length > 0) && (
            <Section title="Permissions">
              <PermissionsBlock plugin={plugin} />
            </Section>
          )}

          {/* ── Provider key deep-link ── */}
          {isProvider && (
            <Section title="Where keys live">
              <div className="flex items-start gap-2 rounded-lg border border-white/5 bg-white/[0.03] p-3 text-xs text-starlight-300">
                <ShieldCheck size={12} className="mt-0.5 text-accent-cyan" />
                <div className="flex-1">
                  <p>
                    <strong className="text-starlight-100">Configure keys in Account.</strong>{' '}
                    Connections shows whether Daena can call the provider;
                    the actual API key lives in the vault-backed Account
                    -&gt; Provider Keys section.
                  </p>
                  <button
                    onClick={() => {
                      // PR-CONN-PHASE2-PREFLIGHT-GREEN (2026-05-03):
                      // canonical anchor /account#provider-keys (the
                      // /account/api-keys path is not a real route).
                      navigate('/account#provider-keys')
                      onClose()
                    }}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-[11px] font-medium text-accent-cyan hover:bg-accent-cyan/20"
                  >
                    Open Account -&gt; Provider Keys
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
              {/* PR-CONN-LOCAL-MODEL-PROBE (2026-05-03): WSL / Docker
                  localhost guidance. Local model probes use a
                  structured failure_reason prefix ("connection_failed:"
                  / "timeout:" / "no_models:"), so we only surface the
                  WSL hint for the connect-failure case where the
                  operator probably hit the cross-host localhost gotcha. */}
              {plugin.source.catalog.kind === 'local_model' &&
                plugin.failure_reason &&
                (plugin.failure_reason.startsWith('connection_failed:')
                 || plugin.failure_reason.startsWith('timeout:')) && (
                  <div className="mt-2 flex items-start gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[11px] text-amber-100">
                    <ShieldAlert size={12} className="mt-0.5 shrink-0 text-amber-300" />
                    <div className="space-y-1">
                      <p>
                        <strong>Cannot reach the local model server.</strong>{' '}
                        Check that the server is running and listening on the
                        configured base URL.
                      </p>
                      <ul className="list-disc pl-4 text-[10px] text-amber-100/80">
                        <li>
                          <strong>WSL / Docker:</strong> "localhost" inside a
                          container points at the container itself. From WSL,
                          use the Windows host IP (or
                          <code className="mx-1">host.docker.internal</code>)
                          instead of <code>127.0.0.1</code>.
                        </li>
                        <li>
                          <strong>Windows firewall:</strong> first run of
                          <code className="mx-1">ollama serve</code> /
                          <code className="mx-1">llama-server</code> may
                          prompt for network permission -- accept it.
                        </li>
                        <li>
                          <strong>Port:</strong> Ollama defaults to
                          <code className="mx-1">11434</code>, llama-server
                          to <code className="mx-1">8080</code>.
                        </li>
                      </ul>
                    </div>
                  </div>
                )}
              {/* "no_models" is reachable but empty -- different action
                  (pull a model), so a different hint. */}
              {plugin.source.catalog.kind === 'local_model' &&
                plugin.failure_reason &&
                plugin.failure_reason.startsWith('no_models:') && (
                  <div className="mt-2 flex items-start gap-1.5 rounded-md border border-cyan-500/30 bg-cyan-500/5 px-2 py-1.5 text-[11px] text-cyan-100">
                    <ShieldCheck size={12} className="mt-0.5 shrink-0 text-cyan-300" />
                    <span>
                      <strong>Server reachable, but no models loaded.</strong>{' '}
                      Pull or load a model in the local server's CLI, then
                      re-probe. Examples:
                      <code className="mx-1">ollama pull llama3.1:8b</code>
                      or launch llama-server with a GGUF file.
                    </span>
                  </div>
                )}
              {/* Connected local model: confirm what Daena sees. The
                  probe stores model names in ConnectionV2Capability;
                  surfacing them inline needs a separate
                  marketplace-card payload extension that's out of
                  scope for this PR. For now the green "callable" pill
                  in the truth ladder above is the operator's
                  confirmation. */}
              {plugin.source.catalog.kind === 'local_model' &&
                plugin.status === 'connected' && (
                  <p className="mt-2 text-[10px] text-emerald-200/80">
                    Local model server reachable + at least one model
                    loaded. Brain selector can route to it.
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

          {/* ── Source & trust ──
              Officiality + source URLs + last-verified date. Community
              entries get a "Review source before install" hint so the
              operator can self-vet before any install action. */}
          <Section title="Source & trust">
            <SourceTrustBlock plugin={plugin} />
          </Section>

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

// ── PR-CONN-PLUGIN-SKILLS-UX-WIRING (2026-05-03): drawer-only blocks ──

/** "What Daena can do" -- prefers `suggested_prompts` (Codex-style
 * concrete intents) and falls back to the catalog short_description.
 *
 * PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING (2026-05-03): each prompt is now
 * a clickable button. Click drafts a safe message into the chat
 * composer ("Use the <plugin> plugin to <prompt>") and navigates to
 * /chat. NEVER auto-sends. NEVER calls a tool. The composer-bridge
 * draft store survives the navigation; ChatPage hydrates from it on
 * mount. Honesty: this is the FIRST safe execution path -- it bridges
 * UI to chat without any side-effects. */
function DaenaIntent({
  plugin,
  navigate,
  onClose,
}: {
  plugin: PluginCard
  navigate: ReturnType<typeof useNavigate>
  onClose: () => void
}) {
  const prompts = plugin.suggested_prompts ?? []
  if (prompts.length === 0) {
    return (
      <p className="text-sm text-starlight-200">
        {plugin.description}
      </p>
    )
  }

  function handleUseInChat(prompt: string, index: number) {
    // Build the draft + drop it into the composer-draft store +
    // dispatch the daena:composer-draft event in one call. The
    // store survives navigation so ChatPage picks it up on mount.
    const drafted = draftFromSuggestedPrompt(prompt, plugin.name, {
      surface: 'connections.plugin_drawer',
      plugin_id: plugin.id,
      plugin_name: plugin.name,
      prompt_index: index,
    })
    toast.success(`Drafted from ${plugin.name}: opening chat...`)
    onClose()
    // Slight defer so the toast renders before navigation tears it
    // down. Pure-CSS animations would still fire, but mounting Chat
    // immediately makes the toast feel like it belongs to /chat
    // rather than the closing drawer.
    setTimeout(() => navigate('/chat'), 80)
    // Defensive log only (no PII): drafted text length so the
    // operator can confirm the draft made it across without exposing
    // the prompt contents in console (the prompt itself is safe but
    // we keep the log surface tight by habit).
    if (typeof console !== 'undefined') {
      console.debug('[connections] composer draft length:', drafted.length)
    }
  }

  return (
    <>
      <p className="mb-2 text-[12px] text-starlight-300">{plugin.description}</p>
      <ul className="space-y-1.5">
        {prompts.slice(0, 5).map((prompt, index) => (
          <li key={prompt}>
            <button
              type="button"
              onClick={() => handleUseInChat(prompt, index)}
              className="group flex w-full items-start gap-2 rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-left text-[12px] text-starlight-100 transition-colors hover:border-accent-cyan/30 hover:bg-accent-cyan/5"
              title="Open in chat composer as a draft (does not auto-send)"
            >
              <MessageSquare size={11} className="mt-0.5 shrink-0 text-accent-cyan" />
              <span className="flex-1">&ldquo;{prompt}&rdquo;</span>
              <span className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded bg-accent-cyan/10 px-1.5 py-0.5 text-[9px] font-medium text-accent-cyan opacity-0 transition-opacity group-hover:opacity-100">
                Use in chat <ArrowRight size={9} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[10px] text-starlight-500">
        Click any prompt to draft it in the chat composer. Daena does
        NOT auto-send -- review first, then send when ready. Tool
        execution still lands in a later PR.
      </p>
    </>
  )
}

/** ConnectionLadder -- visual 4-rung ladder driven by V2 truth.
 * MCP install / Auth / Test / Skills-ready. Each rung tints based on
 * the corresponding lifecycle dimension (configured / authenticated /
 * callable). The "skills ready" rung mirrors the callable rung so the
 * operator sees explicitly when chips will unlock. */
function ConnectionLadder({ plugin }: { plugin: PluginCard }) {
  const truth = plugin.source.v2_truth
  const lifecycle = plugin.source.lifecycle
  const isProvider = plugin.source.catalog.kind === 'api_provider'
  const isOAuth = plugin.auth_type === 'oauth'
  const isMcp = plugin.source.catalog.kind === 'mcp_server'

  // Step 1: Install (or "configured" for non-MCP kinds)
  const step1Done = !!truth?.configured.value || !!truth?.imported.value
    || ['installed', 'configured', 'reachable', 'callable', 'enabled'].includes(lifecycle)
  const step1Label = isMcp
    ? 'MCP server installed'
    : isProvider
      ? 'API key configured'
      : 'Plugin configured'

  // Step 2: Auth (only if the plugin needs auth)
  const needsAuthStep = isOAuth || plugin.auth_type === 'api_key' || plugin.auth_type === 'token'
  const step2Done = !!truth?.authenticated.value
    || lifecycle === 'callable' || lifecycle === 'enabled'
  const step2Label = isOAuth
    ? 'Account connected'
    : 'Credential present'

  // Step 3: Test / probe
  const step3Done = !!truth?.callable.value
    || lifecycle === 'callable' || lifecycle === 'enabled'
  const step3Label = 'Probe successful'

  // Step 4: Skills ready (mirrors callable so the operator can see
  // EXPLICITLY when chips unlock).
  const step4Done = step3Done && skillReadiness(plugin) === 'ready'
  const step4Label = 'Skills ready'

  const steps: Array<{ label: string; done: boolean; show: boolean; icon: typeof Server }> = [
    { label: step1Label, done: step1Done, show: true, icon: isMcp ? Server : KeyRound },
    { label: step2Label, done: step2Done, show: needsAuthStep, icon: KeyRound },
    { label: step3Label, done: step3Done, show: true, icon: Activity },
    { label: step4Label, done: step4Done, show: true, icon: Sparkles },
  ]
  const visible = steps.filter((s) => s.show)

  return (
    <ol className="space-y-1">
      {visible.map((step, idx) => {
        const Icon = step.icon
        return (
          <li
            key={`${step.label}-${idx}`}
            className={`flex items-center gap-2.5 rounded-md border px-2.5 py-1.5 text-[11px] ${
              step.done
                ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-100'
                : 'border-white/5 bg-white/[0.02] text-starlight-400'
            }`}
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full ${
                step.done
                  ? 'bg-emerald-500/20 text-emerald-200'
                  : 'bg-white/[0.05] text-starlight-500'
              }`}
            >
              {step.done ? <CheckCircle2 size={11} /> : <Icon size={10} />}
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wider opacity-70">
              {idx + 1}.
            </span>
            <span>{step.label}</span>
          </li>
        )
      })}
    </ol>
  )
}

/** PermissionsBlock -- merges catalog permissions_summary with the
 * env-var NAMES Daena needs. Highlights high-risk plugins with an
 * Asset Shield reminder. */
function PermissionsBlock({ plugin }: { plugin: PluginCard }) {
  const summary = plugin.permissions_summary ?? []
  return (
    <div className="space-y-2">
      {summary.length > 0 && (
        <div className="rounded-md border border-white/5 bg-white/[0.02] px-3 py-2">
          <p className="text-[10px] uppercase tracking-wider text-starlight-500">
            Scope
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {summary.map((perm) => (
              <li
                key={perm}
                className="inline-flex items-center gap-1 rounded bg-white/[0.04] px-1.5 py-0.5 text-[11px] text-starlight-200"
              >
                <ShieldCheck size={10} className="text-accent-cyan" />
                {perm}
              </li>
            ))}
          </ul>
          {plugin.risk_level === 'high' && (
            <p className="mt-2 flex items-start gap-1.5 text-[10px] text-rose-200">
              <ShieldAlert size={10} className="mt-0.5 shrink-0" />
              High-risk plugin. Asset Shield governance still gates every
              call regardless of OAuth scope.
            </p>
          )}
        </div>
      )}
      {plugin.required_env_vars.length > 0 && (
        <div className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
          <p className="text-[10px] uppercase tracking-wider opacity-80">
            Env var NAMES (Daena never reads the values)
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1">
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
            source CLI&rsquo;s own env. Daena&rsquo;s Configure flow never
            asks you to paste secrets into the catalog UI.
          </p>
        </div>
      )}
    </div>
  )
}

/** SourceTrustBlock -- collapsible source attribution section.
 * Open by default for community entries (operator should self-vet);
 * collapsed for high-trust tiers (vendor-official etc) where the
 * badge already conveys safety. */
function SourceTrustBlock({ plugin }: { plugin: PluginCard }) {
  const officiality = plugin.officiality
  const sources = plugin.source_refs ?? []
  const lastVerified = plugin.last_verified_at
  const isCommunity = officiality === 'community' || officiality === 'archived'
  const [open, setOpen] = useState(isCommunity || sources.length === 0)
  const oTone = officialityTone(officiality)
  const oLabel = officialityLabel(officiality)

  return (
    <div className="rounded-md border border-white/5 bg-white/[0.02]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${oTone.border} ${oTone.bg} ${oTone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${oTone.dot}`} />
            {oLabel}
          </span>
          {lastVerified && (
            <span className="text-[10px] text-starlight-500">
              Verified {lastVerified}
            </span>
          )}
        </div>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div className="border-t border-white/5 px-3 py-2 text-[11px] text-starlight-300">
          {isCommunity && (
            <p className="mb-2 flex items-start gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/5 px-2 py-1.5 text-amber-100">
              <ShieldAlert size={11} className="mt-0.5 shrink-0" />
              <span>
                Community-maintained. Review the source repository before
                installing -- Daena does not vet third-party MCP code.
              </span>
            </p>
          )}
          {sources.length === 0 ? (
            <p className="text-starlight-500">
              No source URLs declared yet for this catalog entry.
            </p>
          ) : (
            <ul className="space-y-1">
              {sources.map((url) => (
                <li key={url}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-accent-cyan hover:underline"
                  >
                    <ExternalLink size={10} />
                    {url}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
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

/**
 * OverviewPanel -- Connections at a glance.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): the operator's "what's
 * the state of my connectors right now" landing page. Pure summary;
 * every drill-down opens the dedicated tab below.
 *
 * Honesty:
 *   - "Callable" counts come from the V2 truth ladder; the UI never
 *     fabricates green pills for connectors that haven't been probed
 *   - Empty / failure states call out concrete next actions
 */

import { useMemo } from 'react'
import {
  AlertTriangle, AppWindow, BookOpen, BrainCircuit, Cpu, Globe, Loader2,
  PackageSearch, ShieldCheck, Server, Terminal, TrendingUp, Wrench,
} from 'lucide-react'

import {
  type BlockerReason,
  type CatalogCategory,
  type DiagnosticBlocker,
  type LifecycleState,
  type MarketplaceCard,
  useMarketplaceCards,
  useMarketplaceDiagnostic,
} from '@/hooks/useMarketplace'

interface OverviewPanelProps {
  /** Callback to navigate to a primary tab. */
  onNavigateTab?: (tab: string) => void
  /** Discovery report summary for the inline status block (optional). */
  lastDiscoveryAt?: string | null
}

const CATEGORY_TO_TAB: Record<string, string> = {
  cli_runtime: 'runtimes',
  ai_provider: 'runtimes',
  local_llm: 'local-models',
  filesystem: 'mcp',
  code_platform: 'mcp',
  communication: 'mcp',
  productivity: 'mcp',
  design: 'mcp',
  data_storage: 'mcp',
  payment: 'mcp',
  research: 'mcp',
  dev_tools: 'mcp',
  browser: 'browser',
  computer_use: 'browser',
}

export default function OverviewPanel({ onNavigateTab, lastDiscoveryAt }: OverviewPanelProps) {
  const { cards, loading, error, refresh } = useMarketplaceCards()
  // Sprint-6 PR-2: explain "0 of N callable" with concrete blockers.
  const { summary: diag } = useMarketplaceDiagnostic()

  const summary = useMemo(() => bucketCards(cards), [cards])

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-white/5 bg-midnight-400/30 p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.22em] text-accent-cyan">
              Connections overview
            </p>
            <h2 className="mt-1 text-xl font-semibold text-starlight-100">
              {summary.callable} of {summary.total} connectors callable
            </h2>
            <p className="mt-1 max-w-2xl text-xs text-starlight-400">
              The catalog tells you what Daena can support; the truth
              ladder shows what is actually working in your tenant. Click
              <strong className="text-starlight-200"> Discover installed tools</strong>{' '}
              in the page header to import detected connectors, then{' '}
              <strong className="text-starlight-200">Probe</strong> each one to flip
              callable=true.
            </p>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <PackageSearch size={12} />}
            Refresh
          </button>
        </div>
        {lastDiscoveryAt && (
          <p className="mt-3 text-[11px] text-starlight-500">
            Last discovery run: {new Date(lastDiscoveryAt).toLocaleString()}
          </p>
        )}
        {error && (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2 text-xs text-rose-200">
            <AlertTriangle size={12} className="mt-0.5" />
            <span>Backend error: {error}</span>
          </div>
        )}
      </div>

      {/* Sprint-6 PR-2: callability blockers diagnostic */}
      {diag && diag.totals.blocked > 0 && diag.top_blockers.length > 0 && (
        <BlockersBlock
          blockers={diag.top_blockers}
          callable={diag.totals.callable}
          blocked={diag.totals.blocked}
          total={diag.totals.catalog}
          onNavigateTab={onNavigateTab}
        />
      )}

      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-starlight-300">
          Lifecycle distribution
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryTile
            label="Callable"
            value={summary.callable}
            tone="emerald"
            icon={<TrendingUp size={14} />}
            hint="Real probe proved working"
          />
          <SummaryTile
            label="Reachable"
            value={summary.reachable}
            tone="blue"
            icon={<ShieldCheck size={14} />}
            hint="Connected, awaiting capability probe"
          />
          <SummaryTile
            label="Configured"
            value={summary.configured}
            tone="cyan"
            icon={<Wrench size={14} />}
            hint="Credentials present, not yet probed"
          />
          <SummaryTile
            label="Available"
            value={summary.available}
            tone="slate"
            icon={<PackageSearch size={14} />}
            hint="In catalog, not yet imported"
          />
          <SummaryTile
            label="Failed"
            value={summary.failed}
            tone="rose"
            icon={<AlertTriangle size={14} />}
            hint="Probe failed; check failure reason"
          />
          <SummaryTile
            label="Skill packs"
            value={summary.skill_packs}
            tone="violet"
            icon={<BookOpen size={14} />}
            hint="Capability bundles (not callable on their own)"
          />
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-starlight-300">
          By category
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <CategoryTile
            label="Main Brain"
            tab="main-brain"
            icon={<BrainCircuit size={14} />}
            counts={{ total: summary.runtimes_total, callable: summary.runtimes_callable }}
            hint="Pick the primary runtime that orchestrates Daena."
            onNavigateTab={onNavigateTab}
          />
          <CategoryTile
            label="Runtimes"
            tab="runtimes"
            icon={<Terminal size={14} />}
            counts={{ total: summary.runtimes_total, callable: summary.runtimes_callable }}
            hint="CLI runtimes + cloud LLM API providers."
            onNavigateTab={onNavigateTab}
          />
          <CategoryTile
            label="MCP Store"
            tab="mcp"
            icon={<Server size={14} />}
            counts={{ total: summary.mcp_total, callable: summary.mcp_callable }}
            hint="Curated catalog of MCP servers (filesystem, GitHub, ...)."
            onNavigateTab={onNavigateTab}
          />
          <CategoryTile
            label="Apps"
            tab="apps"
            icon={<AppWindow size={14} />}
            counts={{ total: summary.apps_total, callable: summary.apps_callable }}
            hint="OAuth-backed apps (Gmail, Drive, GitHub, Slack, ...)."
            onNavigateTab={onNavigateTab}
          />
          <CategoryTile
            label="Browser / Computer Use"
            tab="browser"
            icon={<Globe size={14} />}
            counts={{ total: summary.browser_total, callable: summary.browser_callable }}
            hint="Playwright + DevTools + desktop control. Explicit consent."
            onNavigateTab={onNavigateTab}
          />
          <CategoryTile
            label="Local Models"
            tab="local-models"
            icon={<Cpu size={14} />}
            counts={{ total: summary.local_total, callable: summary.local_callable }}
            hint="Ollama, vLLM, llama-server endpoints."
            onNavigateTab={onNavigateTab}
          />
          <CategoryTile
            label="Skill Packs"
            tab="skill-packs"
            icon={<BookOpen size={14} />}
            counts={{ total: summary.skill_packs, callable: 0 }}
            hint="Reusable instruction bundles. Never callable alone."
            onNavigateTab={onNavigateTab}
            valueSuffix="bundled"
          />
        </div>
      </section>

      {summary.failed > 0 && (
        <section className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-rose-200">
            <AlertTriangle size={14} />
            {summary.failed} connector{summary.failed === 1 ? '' : 's'} failed last probe
          </h3>
          <ul className="space-y-1 text-xs text-rose-200/90">
            {cards
              .filter((c) => c.lifecycle === 'failed')
              .slice(0, 5)
              .map((c) => (
                <li key={c.catalog.id} className="flex items-start gap-2">
                  <span className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
                  <span>
                    <strong className="text-rose-100">{c.catalog.display_name}</strong>{' '}
                    -- {c.v2_failure_reason || 'failure_reason missing'}
                  </span>
                </li>
              ))}
            {cards.filter((c) => c.lifecycle === 'failed').length > 5 && (
              <li className="text-rose-200/70">
                +{cards.filter((c) => c.lifecycle === 'failed').length - 5} more in their respective tabs
              </li>
            )}
          </ul>
        </section>
      )}
    </div>
  )
}

// ── Summary helpers ──

interface Summary {
  total: number
  callable: number
  reachable: number
  configured: number
  available: number
  failed: number
  skill_packs: number
  runtimes_total: number
  runtimes_callable: number
  mcp_total: number
  mcp_callable: number
  apps_total: number
  apps_callable: number
  browser_total: number
  browser_callable: number
  local_total: number
  local_callable: number
}

function emptySummary(): Summary {
  return {
    total: 0, callable: 0, reachable: 0, configured: 0, available: 0,
    failed: 0, skill_packs: 0,
    runtimes_total: 0, runtimes_callable: 0,
    mcp_total: 0, mcp_callable: 0,
    apps_total: 0, apps_callable: 0,
    browser_total: 0, browser_callable: 0,
    local_total: 0, local_callable: 0,
  }
}

function isCallable(state: LifecycleState): boolean {
  return state === 'callable' || state === 'enabled'
}

function bucketCards(cards: MarketplaceCard[]): Summary {
  const out = emptySummary()
  out.total = cards.length
  for (const card of cards) {
    if (card.lifecycle === 'callable' || card.lifecycle === 'enabled') out.callable += 1
    if (card.lifecycle === 'reachable') out.reachable += 1
    if (card.lifecycle === 'configured' || card.lifecycle === 'installed') out.configured += 1
    if (card.lifecycle === 'available' || card.lifecycle === 'needs_setup') out.available += 1
    if (card.lifecycle === 'failed') out.failed += 1
    if (card.lifecycle === 'skill_pack') out.skill_packs += 1

    const callable = isCallable(card.lifecycle)
    const cat = card.catalog.category as CatalogCategory
    if (cat === 'cli_runtime' || cat === 'ai_provider') {
      out.runtimes_total += 1
      if (callable) out.runtimes_callable += 1
    } else if (cat === 'local_llm') {
      out.local_total += 1
      if (callable) out.local_callable += 1
    } else if (cat === 'browser' || cat === 'computer_use') {
      out.browser_total += 1
      if (callable) out.browser_callable += 1
    } else if (card.catalog.kind === 'oauth_app') {
      out.apps_total += 1
      if (callable) out.apps_callable += 1
    } else if (card.catalog.kind === 'mcp_server') {
      out.mcp_total += 1
      if (callable) out.mcp_callable += 1
    }
  }
  return out
}

const TONES = {
  emerald: { text: 'text-emerald-200', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  blue: { text: 'text-blue-200', bg: 'bg-blue-500/10', border: 'border-blue-500/30' },
  cyan: { text: 'text-cyan-200', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' },
  amber: { text: 'text-amber-200', bg: 'bg-amber-500/10', border: 'border-amber-500/30' },
  rose: { text: 'text-rose-200', bg: 'bg-rose-500/10', border: 'border-rose-500/30' },
  violet: { text: 'text-violet-200', bg: 'bg-violet-500/10', border: 'border-violet-500/30' },
  slate: { text: 'text-slate-300', bg: 'bg-white/[0.02]', border: 'border-white/5' },
}

function SummaryTile({
  label, value, tone, icon, hint,
}: {
  label: string
  value: number
  tone: keyof typeof TONES
  icon: React.ReactNode
  hint: string
}) {
  const t = TONES[tone]
  return (
    <div className={`rounded-lg border ${t.border} ${t.bg} px-3 py-3`} title={hint}>
      <div className={`flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.16em] ${t.text}`}>
        {icon}
        <span>{label}</span>
      </div>
      <p className={`mt-1 text-2xl font-semibold ${t.text}`}>{value}</p>
      <p className="mt-1 text-[10px] text-starlight-500">{hint}</p>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────
// Sprint-6 PR-2: BlockersBlock -- explain why connectors aren't callable.
// ──────────────────────────────────────────────────────────────────

const BLOCKER_TONE: Record<BlockerReason, keyof typeof TONES> = {
  not_imported: 'cyan',
  coming_soon: 'slate',
  needs_api_key: 'amber',
  needs_oauth: 'amber',
  needs_probe: 'cyan',
  probe_failed: 'rose',
  disabled: 'slate',
  archived: 'slate',
  skill_pack: 'violet',
}

// Map blocker reason to the connections tab the operator should open.
// Coming-soon and skill-pack point to overview itself (no useful action).
const BLOCKER_TAB: Partial<Record<BlockerReason, string>> = {
  not_imported: 'mcp',
  needs_api_key: 'runtimes',
  needs_oauth: 'apps',
  needs_probe: 'mcp',
  probe_failed: 'mcp',
  disabled: 'mcp',
  archived: 'mcp',
}

function BlockersBlock({
  blockers, callable, blocked, total, onNavigateTab,
}: {
  blockers: DiagnosticBlocker[]
  callable: number
  blocked: number
  total: number
  onNavigateTab?: (tab: string) => void
}) {
  // The most-common blocker leads.
  const ordered = [...blockers].sort((a, b) => b.count - a.count)
  return (
    <section
      data-testid="overview-blockers-block"
      className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-100">
            <Wrench size={14} />
            Why aren't more connectors callable?
          </h3>
          <p className="mt-1 max-w-2xl text-xs text-amber-200/80">
            {callable} of {total} are callable; {blocked} are blocked
            for the reasons below. Each row is real (no fabricated
            green pills) -- click through to fix the top blocker first.
          </p>
        </div>
      </div>
      <ul className="mt-4 space-y-2">
        {ordered.slice(0, 5).map((b) => {
          const tone = TONES[BLOCKER_TONE[b.reason]]
          const targetTab = BLOCKER_TAB[b.reason]
          return (
            <li
              key={b.reason}
              className={`rounded-lg border ${tone.border} ${tone.bg} px-3 py-2.5`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className={`text-sm font-medium ${tone.text}`}>
                  {b.label}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold ${tone.text}`}>
                    {b.count}
                  </span>
                  {targetTab && onNavigateTab && (
                    <button
                      onClick={() => onNavigateTab(targetTab)}
                      className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-starlight-200 hover:bg-white/10"
                    >
                      Open ›
                    </button>
                  )}
                </div>
              </div>
              <p className="mt-1 text-[11px] text-starlight-400">
                {b.next_action}
              </p>
              {b.examples.length > 0 && (
                <p className="mt-1 text-[10px] text-starlight-500">
                  Examples:{' '}
                  {b.examples.map((e) => e.display_name || e.entry_id).join(', ')}
                  {b.count > b.examples.length && (
                    <span> (+{b.count - b.examples.length} more)</span>
                  )}
                </p>
              )}
            </li>
          )
        })}
      </ul>
      {ordered.length > 5 && (
        <p className="mt-3 text-[10px] text-starlight-500">
          +{ordered.length - 5} additional blocker categor
          {ordered.length - 5 === 1 ? 'y' : 'ies'} -- open the
          relevant tab to see them.
        </p>
      )}
    </section>
  )
}


function CategoryTile({
  label, tab, icon, counts, hint, onNavigateTab, valueSuffix,
}: {
  label: string
  tab: string
  icon: React.ReactNode
  counts: { total: number; callable: number }
  hint: string
  onNavigateTab?: (tab: string) => void
  valueSuffix?: string
}) {
  return (
    <button
      onClick={() => onNavigateTab?.(tab)}
      className="text-left rounded-lg border border-white/5 bg-midnight-400/30 px-4 py-3 transition-colors hover:border-primary-500/30 hover:bg-midnight-400/50"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-medium text-starlight-100">
          <span className="text-primary-200">{icon}</span>
          {label}
        </div>
        <span className="text-[10px] text-starlight-500">Open ›</span>
      </div>
      <p className="mt-2 text-lg font-semibold text-starlight-100">
        {counts.callable} <span className="text-sm text-starlight-500">/ {counts.total} {valueSuffix ?? 'callable'}</span>
      </p>
      <p className="mt-1 text-[10px] text-starlight-500">{hint}</p>
    </button>
  )
}

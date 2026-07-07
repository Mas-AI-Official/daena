import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { X, Brain, ChevronRight } from 'lucide-react'
import type { GraphNode } from '@/lib/graphApi'
import { api } from '@/lib/api'
import type { SoulDetail, SoulProposal } from '@/types/api'
import { useGraphStore } from '@/stores/graphStore'
import { govSignal, type GovSignal } from './governanceSignal'

type DetailTab = 'overview' | 'work' | 'access' | 'activity' | 'context'

const TABS: { key: DetailTab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'work', label: 'Work' },
  { key: 'access', label: 'AI Access' },
  { key: 'activity', label: 'Activity' },
  { key: 'context', label: 'AI Context' },
]

// Governance presentation helpers. Colour follows Daena's documented convention
// (audit RiskLevel + GoaAuditEvent.result + governance tier). All inputs are real
// projected fields; unknown values fall back to neutral, never fabricated.
function riskClass(risk?: string | null): string {
  switch (String(risk ?? '').toLowerCase()) {
    case 'critical':
      return 'font-semibold text-red-400'
    case 'high':
      return 'text-red-400'
    case 'medium':
      return 'text-amber-300'
    default:
      return 'text-white/40'
  }
}

function resultClass(result?: string | null): string {
  switch (String(result ?? '').toLowerCase()) {
    case 'allowed':
    case 'completed':
      return 'text-emerald-300'
    case 'approval_required':
      return 'text-amber-300'
    case 'blocked':
    case 'failed':
      return 'text-red-400'
    default:
      return 'text-white/50'
  }
}

function tierLabel(tier: number): string {
  if (tier >= 3) return `Tier ${tier} -- approval required`
  if (tier === 2) return `Tier ${tier} -- notified`
  return `Tier ${tier} -- logged`
}

function tierClass(tier: number): string {
  if (tier >= 3) return 'text-red-400'
  if (tier === 2) return 'text-amber-300'
  return 'text-white/60'
}

// A member counts as "active" on the same convention the list lens uses for its
// status tone, so the two Brain views agree on what "active" means.
const ACTIVE_STATUSES = new Set(['active', 'running', 'in_progress'])

interface DeptRollup {
  memberCount: number
  byKind: { kind: string; total: number; active: number }[]
  attention: { node: GraphNode; sig: GovSignal }[]
  workstreams: GraphNode[]
}

/**
 * Per-department rollup, derived ENTIRELY from the in-memory projection (nodes
 * whose department_id points at this department). Everything here is real
 * projected data -- composition counts, governance-attention via the shared
 * govSignal, and the genuine "next governed action" text that lives on
 * workstreams (next_step / blocker). We deliberately do NOT invent a "maturity"
 * or "owner" field: the backend has none, so painting one would be fabrication
 * (Rule 17). Projects/skills/tools carry no department FK in the projection, so
 * they simply do not appear -- the rollup shows only what is truly linked.
 */
function buildDeptRollup(deptId: string, nodes: GraphNode[]): DeptRollup {
  const members = nodes.filter((n) => n.department_id === deptId)
  const kindMap = new Map<string, { total: number; active: number }>()
  for (const m of members) {
    const e = kindMap.get(m.kind) ?? { total: 0, active: 0 }
    e.total += 1
    if (ACTIVE_STATUSES.has(String(m.status ?? '').toLowerCase())) e.active += 1
    kindMap.set(m.kind, e)
  }
  const byKind = Array.from(kindMap, ([kind, v]) => ({ kind, ...v })).sort(
    (a, b) => b.total - a.total || a.kind.localeCompare(b.kind),
  )
  const attention = members
    .map((node) => ({ node, sig: govSignal(node) }))
    .filter((x): x is { node: GraphNode; sig: GovSignal } => !!x.sig && x.sig.severity > 0)
    .sort((a, b) => b.sig.severity - a.sig.severity || a.node.label.localeCompare(b.node.label))
  const workstreams = members.filter((m) => m.kind === 'workstream')
  return { memberCount: members.length, byKind, attention, workstreams }
}

/**
 * Right-hand slide-over for the selected node. Overview and Work read the
 * in-memory projection; AI Access / Activity / AI Context render the live
 * detail payload fetched per node (PR-5). Empty and offline states are honest
 * (Rule 17, no fabricated data).
 */
export default function NodeDetailPanel() {
  const data = useGraphStore((s) => s.data)
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId)
  const selectNode = useGraphStore((s) => s.selectNode)
  const nodeDetail = useGraphStore((s) => s.nodeDetail)
  const nodeDetailLoading = useGraphStore((s) => s.nodeDetailLoading)
  const nodeDetailError = useGraphStore((s) => s.nodeDetailError)
  const fetchNodeDetail = useGraphStore((s) => s.fetchNodeDetail)
  const navigate = useNavigate()
  const [tab, setTab] = useState<DetailTab>('overview')
  // The soul ("Mind") behind a department node, fetched lazily so the drawer can
  // offer a first-class entry into the founder governance workflow at /minds/:slug.
  const [mind, setMind] = useState<{ soul: SoulDetail; pendingCount: number } | null>(null)

  // Fetch the detail payload whenever the selection changes.
  useEffect(() => {
    if (selectedNodeId) void fetchNodeDetail(selectedNodeId)
  }, [selectedNodeId, fetchNodeDetail])

  const node = data?.nodes.find((n) => n.id === selectedNodeId) ?? null

  // Department nodes carry a soul. Resolve it via the backend, which normalizes
  // the department label to a soul slug (404 when none matches) -- on a miss we
  // render no Mind block rather than fabricate one (Rule 17). The Brain graph is
  // now the canonical way to reach a Mind, so this link is the surviving entry to
  // the standalone /minds/:slug workstation (the redundant gallery is archived).
  useEffect(() => {
    if (!node || node.kind !== 'department') {
      setMind(null)
      return
    }
    const label = node.label
    let ignore = false
    void (async () => {
      try {
        const soulRes = await api.get<SoulDetail>(`/souls/${encodeURIComponent(label)}`)
        const soul = soulRes.data
        if (!soul?.slug) {
          if (!ignore) setMind(null)
          return
        }
        const propRes = await api
          .get<SoulProposal[]>(
            `/souls/proposals?slug=${encodeURIComponent(soul.slug)}&status=pending&limit=100`,
          )
          .catch(() => ({ data: [] as SoulProposal[] }))
        if (!ignore) setMind({ soul, pendingCount: (propRes.data ?? []).length })
      } catch {
        // 404 (no soul for this department) or transient error: show nothing.
        if (!ignore) setMind(null)
      }
    })()
    return () => {
      ignore = true
    }
  }, [node?.id, node?.kind, node?.label])
  const neighborIds = node
    ? (data?.edges ?? [])
        .filter((e) => e.source === node.id || e.target === node.id)
        .map((e) => (e.source === node.id ? e.target : e.source))
    : []

  // For a department, the "Work" tab shows a rollup of its members instead of a
  // flat edge list -- this is the honest Step C "adoption" view, scoped to the
  // existing drawer (no new top-level surface).
  const deptRollup =
    node && node.kind === 'department' ? buildDeptRollup(node.id, data?.nodes ?? []) : null

  // Only trust the fetched detail when it matches the current selection; a
  // stale payload from a prior node must never render against this one.
  const detail =
    nodeDetail && nodeDetail.node.id === selectedNodeId ? nodeDetail : null

  // Real governance fields off the projection (meta is Record<string, unknown>,
  // so narrow before use -- Rule 17, never paint data we don't actually have).
  const govTier =
    typeof node?.meta?.governance_tier === 'number' ? (node.meta.governance_tier as number) : null
  const blocker = node?.meta?.blocker ? String(node.meta.blocker) : null

  return (
    <AnimatePresence>
      {node ? (
        <motion.aside
          key="node-detail"
          initial={{ x: 380, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 380, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 320, damping: 32 }}
          className="absolute right-0 top-0 flex h-full w-[360px] flex-col border-l border-white/10 bg-black/80 backdrop-blur"
        >
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-white/40">{node.kind}</div>
              <div className="text-sm font-medium text-white">{node.label}</div>
            </div>
            <button
              onClick={() => selectNode(null)}
              className="rounded p-1 text-white/50 hover:bg-white/10 hover:text-white"
              aria-label="Close detail panel"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex flex-wrap gap-1 border-b border-white/10 px-2 py-2">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={
                  tab === t.key
                    ? 'rounded bg-white/10 px-2 py-1 text-xs text-white'
                    : 'rounded px-2 py-1 text-xs text-white/50 hover:text-white'
                }
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 text-sm text-white/80">
            {tab === 'overview' ? (
              <dl className="space-y-3">
                {mind ? (
                  <div className="rounded-lg border border-amber-400/25 bg-amber-400/5 px-3 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-amber-300/80">
                        <Brain size={13} /> Department Mind
                      </span>
                      {mind.pendingCount > 0 ? (
                        <span className="rounded-full bg-amber-400/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-200">
                          {mind.pendingCount} pending review
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-1 text-sm font-medium text-white">
                      {mind.soul.name ?? mind.soul.slug}
                    </div>
                    <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-white/45">
                      {mind.soul.runtime_preference ? (
                        <span>runtime: {mind.soul.runtime_preference}</span>
                      ) : null}
                      {typeof mind.soul.temperature === 'number' ? (
                        <span>temp: {mind.soul.temperature}</span>
                      ) : null}
                      {mind.soul.voice ? <span>voice: {mind.soul.voice}</span> : null}
                    </div>
                    <button
                      onClick={() =>
                        navigate(
                          `/minds/${mind.soul.slug}${mind.pendingCount > 0 ? '#proposals' : ''}`,
                        )
                      }
                      className="mt-2 flex w-full items-center justify-center gap-1 rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-1.5 text-xs font-medium text-amber-200 transition-colors hover:bg-amber-400/20"
                    >
                      {mind.pendingCount > 0 ? 'Review proposals' : 'Open Mind'}{' '}
                      <ChevronRight size={13} />
                    </button>
                  </div>
                ) : null}
                <div>
                  <dt className="text-xs text-white/40">ID</dt>
                  <dd className="break-all text-white/80">{node.id}</dd>
                </div>
                <div>
                  <dt className="text-xs text-white/40">Kind</dt>
                  <dd className="text-white/80">{node.kind}</dd>
                </div>
                <div>
                  <dt className="text-xs text-white/40">Status</dt>
                  <dd className="text-white/80">{node.status ?? 'unknown'}</dd>
                </div>
                {node.sunflower_index != null ? (
                  <div>
                    <dt className="text-xs text-white/40">Sunflower index</dt>
                    <dd className="text-white/80">{node.sunflower_index}</dd>
                  </div>
                ) : null}
                {govTier != null || blocker ? (
                  <div className="rounded border border-white/10 bg-white/5 px-2 py-2">
                    <dt className="text-xs text-white/40">Governance</dt>
                    {govTier != null ? (
                      <dd className={`mt-0.5 ${tierClass(govTier)}`}>{tierLabel(govTier)}</dd>
                    ) : null}
                    {blocker ? <dd className="mt-1 text-amber-300/90">Blocked: {blocker}</dd> : null}
                  </div>
                ) : null}
              </dl>
            ) : null}

            {tab === 'work' ? (
              deptRollup ? (
                deptRollup.memberCount === 0 ? (
                  <div className="text-white/40">No agents or workstreams linked to this department yet.</div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <div className="mb-1.5 text-xs text-white/40">Composition ({deptRollup.memberCount})</div>
                      <div className="flex flex-wrap gap-1.5">
                        {deptRollup.byKind.map((k) => (
                          <span
                            key={k.kind}
                            className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/70"
                          >
                            {k.kind} {k.total}
                            {k.active > 0 ? <span className="text-teal-300/80"> {'·'} {k.active} active</span> : null}
                          </span>
                        ))}
                      </div>
                    </div>

                    {deptRollup.attention.length > 0 ? (
                      <div>
                        <div className="mb-1.5 text-xs text-white/40">
                          Needs governance attention ({deptRollup.attention.length})
                        </div>
                        <ul className="space-y-1">
                          {deptRollup.attention.map(({ node: m, sig }) => (
                            <li
                              key={m.id}
                              onClick={() => selectNode(m.id)}
                              className="flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1 hover:bg-white/10"
                            >
                              <span className="truncate text-white/80" title={m.label}>
                                <span className="text-white/40">{m.kind}</span> {m.label}
                              </span>
                              <span className="shrink-0 text-xs" style={{ color: sig.ring }}>
                                {sig.label}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {deptRollup.workstreams.length > 0 ? (
                      <div>
                        <div className="mb-1.5 text-xs text-white/40">Next governed action</div>
                        <ul className="space-y-2">
                          {deptRollup.workstreams.map((w) => {
                            const next = w.meta?.next_step ? String(w.meta.next_step) : null
                            const blk = w.meta?.blocker ? String(w.meta.blocker) : null
                            return (
                              <li
                                key={w.id}
                                onClick={() => selectNode(w.id)}
                                className="cursor-pointer rounded border border-white/10 px-2 py-1.5 hover:bg-white/5"
                              >
                                <div className="truncate text-white/80" title={w.label}>
                                  {w.label}
                                </div>
                                {next ? <div className="mt-0.5 text-xs text-teal-300/80">next: {next}</div> : null}
                                {blk ? <div className="mt-0.5 text-xs text-amber-300/90">blocked: {blk}</div> : null}
                                {!next && !blk ? (
                                  <div className="mt-0.5 text-xs text-white/30">status: {w.status ?? 'unknown'}</div>
                                ) : null}
                              </li>
                            )
                          })}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                )
              ) : (
                <div>
                  <div className="mb-2 text-xs text-white/40">Connections ({neighborIds.length})</div>
                  {neighborIds.length > 0 ? (
                    <ul className="space-y-1">
                      {neighborIds.map((id) => {
                        const nb = data?.nodes.find((n) => n.id === id)
                        return (
                          <li
                            key={id}
                            onClick={() => selectNode(id)}
                            className="cursor-pointer rounded px-2 py-1 hover:bg-white/10"
                          >
                            <span className="text-white/40">{nb?.kind ?? 'node'}</span>{' '}
                            <span className="text-white/80">{nb?.label ?? id}</span>
                          </li>
                        )
                      })}
                    </ul>
                  ) : (
                    <div className="text-white/40">No connections.</div>
                  )}
                </div>
              )
            ) : null}

            {tab === 'activity' ? (
              nodeDetailLoading && !detail ? (
                <div className="text-white/40">Loading...</div>
              ) : nodeDetailError ? (
                <div className="text-amber-400/80">{nodeDetailError}</div>
              ) : detail && detail.activity.length > 0 ? (
                <div>
                  <div className="mb-2 rounded border border-white/10 bg-white/5 px-2 py-1.5 text-xs text-white/50">
                    Daena separates command authority from execution; every governed
                    action is recorded here with its policy result and risk tier.
                  </div>
                  <ul className="space-y-2">
                    {detail.activity.map((a) => (
                      <li key={a.id} className="rounded border border-white/10 px-2 py-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="text-white/80">{a.action_type}</div>
                          {a.result ? (
                            <span className={`shrink-0 text-[10px] font-medium uppercase tracking-wide ${resultClass(a.result)}`}>
                              {a.result}
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-white/40">
                          {a.actor_type ? <span>{a.actor_type}</span> : null}
                          {a.risk_level ? <span className={riskClass(a.risk_level)}>risk: {a.risk_level}</span> : null}
                          <span>{new Date(a.created_at).toLocaleString()}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="text-white/40">No recorded activity for this node.</div>
              )
            ) : null}

            {tab === 'access' ? (
              nodeDetailLoading && !detail ? (
                <div className="text-white/40">Loading...</div>
              ) : nodeDetailError ? (
                <div className="text-amber-400/80">{nodeDetailError}</div>
              ) : detail ? (
                <div className="space-y-4">
                  <div className="text-xs uppercase tracking-wide text-white/40">
                    Scope: {detail.ai_access.scope}
                  </div>
                  {detail.ai_access.note ? (
                    <div className="rounded border border-white/10 bg-white/5 px-2 py-2 text-xs text-white/60">
                      {detail.ai_access.note}
                    </div>
                  ) : null}

                  {detail.ai_access.mcp_tools.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs text-white/40">
                        Tools ({detail.ai_access.mcp_tools.length})
                      </div>
                      <ul className="space-y-1">
                        {detail.ai_access.mcp_tools.map((t) => (
                          <li key={t.name} className="rounded px-2 py-1 hover:bg-white/5">
                            <span className="text-white/80">{t.name}</span>
                            {t.description ? (
                              <span className="text-white/40"> -- {t.description}</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {detail.ai_access.mcp_servers.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs text-white/40">
                        Connected apps ({detail.ai_access.mcp_servers.length})
                      </div>
                      <ul className="space-y-1">
                        {detail.ai_access.mcp_servers.map((m) => (
                          <li
                            key={m.id}
                            onClick={() => selectNode(m.id)}
                            className="flex cursor-pointer items-center justify-between rounded px-2 py-1 hover:bg-white/10"
                          >
                            <span className="text-white/80">{m.label}</span>
                            <span className="text-xs text-white/40">
                              {m.status ?? 'unknown'} - {m.tool_count} tools
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {detail.ai_access.skills.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs text-white/40">
                        Skills ({detail.ai_access.skills.length})
                      </div>
                      <ul className="space-y-1">
                        {detail.ai_access.skills.map((s) => (
                          <li key={s.id} className="rounded px-2 py-1 hover:bg-white/5">
                            <span className="text-white/80">{s.title}</span>
                            {s.domain ? (
                              <span className="text-white/40"> ({s.domain})</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {!detail.ai_access.note &&
                  detail.ai_access.mcp_tools.length === 0 &&
                  detail.ai_access.mcp_servers.length === 0 &&
                  detail.ai_access.skills.length === 0 ? (
                    <div className="text-white/40">No AI access mapped for this node.</div>
                  ) : null}
                </div>
              ) : (
                <div className="text-white/40">No AI access mapped for this node.</div>
              )
            ) : null}

            {tab === 'context' ? (
              nodeDetailLoading && !detail ? (
                <div className="text-white/40">Loading...</div>
              ) : nodeDetailError ? (
                <div className="text-amber-400/80">{nodeDetailError}</div>
              ) : detail ? (
                <div className="space-y-3">
                  {!detail.ai_context.available ? (
                    <div className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-2 text-xs text-amber-300/90">
                      Semantic context is offline (ragx unavailable or abstained).
                      No evidence is shown rather than fabricating context.
                    </div>
                  ) : null}
                  {detail.ai_context.requested.length > 0 ? (
                    <div className="text-xs text-white/40">
                      Collections: {detail.ai_context.requested.join(', ')}
                    </div>
                  ) : null}
                  {detail.ai_context.citations.length > 0 ? (
                    <ul className="space-y-2">
                      {detail.ai_context.citations.map((c) => (
                        <li key={c.chunk_id} className="rounded border border-white/10 px-2 py-2">
                          <div className="flex items-center justify-between text-xs text-white/40">
                            <span className="truncate">{c.source_path}</span>
                            <span>{c.score.toFixed(2)}</span>
                          </div>
                          <div className="mt-1 text-white/70">{c.snippet}</div>
                          <div className="mt-1 text-xs text-white/30">{c.collection}</div>
                        </li>
                      ))}
                    </ul>
                  ) : detail.ai_context.available ? (
                    <div className="text-white/40">No semantic context found.</div>
                  ) : null}
                </div>
              ) : (
                <div className="text-white/40">No semantic context.</div>
              )
            ) : null}
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  )
}

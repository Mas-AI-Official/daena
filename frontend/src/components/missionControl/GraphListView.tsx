import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import type { GraphNode } from '@/lib/graphApi'
import { useGraphStore } from '@/stores/graphStore'
import { KIND_COLORS } from '@/styles/designTokens'
import { govSignal, type GovSignal } from './governanceSignal'

/**
 * GraphListView -- the second Brain lens. The force-graph canvas is great for
 * "where does this sit in the org", but it cannot SCAN or SORT: at enterprise
 * scale you cannot answer "what is awaiting approval / blocked right now" by
 * staring at a physics sim. This flat, dense, sortable table does exactly that,
 * with governance as a first-class default-sorted column -- the one job the
 * graph structurally cannot do.
 *
 * State invariance (no schism with the canvas): this reads the SAME graphStore
 * `data.nodes` (already kind-filtered server-side via load()), the SAME
 * `highlightedIds` from ragx search, and routes row clicks through the SAME
 * `selectNode` -> NodeDetailPanel drawer. Toggling graph<->list never changes
 * the active node subset.
 */

type SortKey = 'governance' | 'label' | 'kind' | 'status' | 'department'
type SortDir = 'asc' | 'desc'

interface Row {
  node: GraphNode
  deptLabel: string
  sig: GovSignal | null
}

const COLUMNS: { key: SortKey; label: string; className: string }[] = [
  { key: 'label', label: 'Name', className: 'w-[34%]' },
  { key: 'kind', label: 'Kind', className: 'w-[14%]' },
  { key: 'status', label: 'Status', className: 'w-[14%]' },
  { key: 'department', label: 'Department', className: 'w-[18%]' },
  { key: 'governance', label: 'Governance', className: 'w-[20%]' },
]

const ATTENTION_STATUSES = new Set(['blocked', 'failed'])

function statusTone(status: string): string {
  const s = status.toLowerCase()
  if (ATTENTION_STATUSES.has(s)) return 'text-red-300'
  if (s === 'running' || s === 'active' || s === 'in_progress') return 'text-teal-300'
  return 'text-white/55'
}

export default function GraphListView() {
  const data = useGraphStore((s) => s.data)
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId)
  const selectNode = useGraphStore((s) => s.selectNode)
  const highlightedIds = useGraphStore((s) => s.highlightedIds)

  // Governance triage IS the reason this view exists, so default to it, loudest
  // first. Secondary alpha sort happens inside the comparator.
  const [sortKey, setSortKey] = useState<SortKey>('governance')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [query, setQuery] = useState('')
  // When a ragx search is live, default to showing only its matches so the list
  // mirrors what the canvas highlights (state invariance). The user can widen
  // back to the full set without losing the search.
  const [matchesOnly, setMatchesOnly] = useState(true)

  const hasSearch = highlightedIds.size > 0

  const deptNames = useMemo(() => {
    const m = new Map<string, string>()
    for (const n of data?.nodes ?? []) {
      if (n.kind === 'department') m.set(n.id, n.label)
    }
    return m
  }, [data])

  const rows = useMemo<Row[]>(() => {
    const nodes = data?.nodes ?? []
    const q = query.trim().toLowerCase()
    const out: Row[] = []
    for (const node of nodes) {
      if (hasSearch && matchesOnly && !highlightedIds.has(node.id)) continue
      const deptLabel = node.department_id ? (deptNames.get(node.department_id) ?? '') : ''
      if (q) {
        const hay = `${node.label} ${node.kind} ${node.status ?? ''} ${deptLabel}`.toLowerCase()
        if (!hay.includes(q)) continue
      }
      out.push({ node, deptLabel, sig: govSignal(node) })
    }

    const dir = sortDir === 'asc' ? 1 : -1
    out.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'governance':
          cmp = (a.sig?.severity ?? -1) - (b.sig?.severity ?? -1)
          break
        case 'kind':
          cmp = a.node.kind.localeCompare(b.node.kind)
          break
        case 'status':
          cmp = String(a.node.status ?? '').localeCompare(String(b.node.status ?? ''))
          break
        case 'department':
          cmp = a.deptLabel.localeCompare(b.deptLabel)
          break
        default:
          cmp = a.node.label.localeCompare(b.node.label)
      }
      // Stable, predictable tiebreaker so equal-severity rows are alphabetical.
      if (cmp === 0) cmp = a.node.label.localeCompare(b.node.label)
      return cmp * dir
    })
    return out
  }, [data, deptNames, query, sortKey, sortDir, hasSearch, matchesOnly, highlightedIds])

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      // Governance defaults to loudest-first; text columns default A->Z.
      setSortDir(key === 'governance' ? 'desc' : 'asc')
    }
  }

  const total = data?.nodes?.length ?? 0

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-white/5 px-6 py-2">
        <div className="relative">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-white/30" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter rows..."
            className="w-56 rounded-md border border-white/10 bg-black/30 py-1 pl-7 pr-2 text-xs text-white/80 placeholder:text-white/30 focus:border-white/25 focus:outline-none"
          />
        </div>
        {hasSearch ? (
          <button
            onClick={() => setMatchesOnly((v) => !v)}
            className={
              matchesOnly
                ? 'rounded-full border border-teal-400/40 bg-teal-400/15 px-3 py-1 text-xs text-teal-200 transition-colors'
                : 'rounded-full border border-white/10 px-3 py-1 text-xs text-white/50 transition-colors hover:text-white'
            }
            title="Limit the list to ragx search matches (keeps it in sync with the canvas highlight)"
          >
            Search matches only
          </button>
        ) : null}
        <span className="ml-auto text-xs text-white/40">
          {rows.length}
          {rows.length === total ? '' : ` / ${total}`} nodes
        </span>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full table-fixed border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 bg-[#0b0f17]/95 backdrop-blur">
            <tr className="border-b border-white/10 text-white/40">
              {COLUMNS.map((c) => {
                const active = sortKey === c.key
                return (
                  <th key={c.key} className={`${c.className} px-6 py-2 font-medium`}>
                    <button
                      onClick={() => toggleSort(c.key)}
                      className={
                        active
                          ? 'flex items-center gap-1 text-white/80 transition-colors'
                          : 'flex items-center gap-1 transition-colors hover:text-white/70'
                      }
                    >
                      {c.label}
                      {active ? <span className="text-[10px]">{sortDir === 'asc' ? '↑' : '↓'}</span> : null}
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ node, deptLabel, sig }) => {
              const selected = node.id === selectedNodeId
              const highlighted = highlightedIds.has(node.id)
              const kindColor = KIND_COLORS[node.kind] ?? '#7c8696'
              return (
                <tr
                  key={node.id}
                  onClick={() => selectNode(node.id)}
                  className={
                    selected
                      ? 'cursor-pointer border-b border-white/5 bg-white/10'
                      : 'cursor-pointer border-b border-white/5 hover:bg-white/5'
                  }
                >
                  <td className="px-6 py-1.5">
                    <div className="flex items-center gap-2">
                      {highlighted ? (
                        <span className="h-3 w-0.5 shrink-0 rounded-full bg-teal-400" title="ragx search match" />
                      ) : (
                        <span className="h-3 w-0.5 shrink-0" />
                      )}
                      <span className="truncate text-white/85" title={node.label}>
                        {node.label}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-1.5">
                    <span className="flex items-center gap-1.5 text-white/55">
                      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: kindColor }} />
                      {node.kind}
                    </span>
                  </td>
                  <td className={`px-6 py-1.5 ${statusTone(String(node.status ?? ''))}`}>
                    {node.status ? node.status : '--'}
                  </td>
                  <td className="px-6 py-1.5 text-white/55">
                    <span className="block truncate" title={deptLabel}>
                      {deptLabel || '--'}
                    </span>
                  </td>
                  <td className="px-6 py-1.5">
                    {sig ? (
                      <span className="flex items-center gap-1.5" style={{ color: sig.ring }}>
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{
                            backgroundColor: sig.ring,
                            boxShadow: sig.glow ? `0 0 6px ${sig.ring}` : undefined,
                          }}
                        />
                        {sig.label}
                      </span>
                    ) : (
                      <span className="text-white/30">--</span>
                    )}
                  </td>
                </tr>
              )
            })}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-6 py-10 text-center text-white/40">
                  {total === 0 ? 'No nodes in the current projection.' : 'No rows match the current filter.'}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}

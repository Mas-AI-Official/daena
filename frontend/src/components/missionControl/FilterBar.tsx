import type { CSSProperties } from 'react'
import { useGraphStore } from '@/stores/graphStore'
import { KIND_COLORS, RELATIONAL_KINDS, HIVE_HEX_COLORS } from '@/styles/designTokens'

/**
 * The structural entity kinds, each rendered as a filter chip. The virtual
 * daena root is implicit and always present, so it gets no chip. ``tool`` joins
 * the chips in PR-8 (projected from the tool_records table). The session /
 * execution continuity layers are projected by default too, but stay chip-less:
 * they are high-cardinality (capped per kind, see SESSION_NODE_CAP /
 * EXECUTION_NODE_CAP) and would crowd the structural filter.
 */
const ENTITY_KINDS: { key: string; label: string }[] = [
  { key: 'department', label: 'Departments' },
  { key: 'agent', label: 'Agents' },
  { key: 'project', label: 'Projects' },
  { key: 'workstream', label: 'Workstreams' },
  { key: 'mcp_server', label: 'MCP Servers' },
  { key: 'skill', label: 'Skills' },
  { key: 'tool', label: 'Tools' },
]

// A relational kind (department / agent / workstream) inherits its color from a
// parent department in the canvas, so a single swatch color would lie. Its chip
// shows a multi-hue conic gradient -- "this category varies by department" --
// and tints its active state with a neutral slate instead of a fake hue.
const RELATIONAL_SWATCH = `conic-gradient(${HIVE_HEX_COLORS.slice(0, 5).join(', ')}, ${HIVE_HEX_COLORS[0]})`
const RELATIONAL_TINT = '#cbd5e1'

function swatchStyle(key: string): CSSProperties {
  if (RELATIONAL_KINDS.has(key)) return { background: RELATIONAL_SWATCH }
  return { background: KIND_COLORS[key] ?? '#7c8696' }
}

/** Active-chip border/bg tint. 8C ~= 55% alpha, 24 ~= 14% alpha (6-digit hex). */
function tintFor(key: string): string {
  if (RELATIONAL_KINDS.has(key)) return RELATIONAL_TINT
  return KIND_COLORS[key] ?? '#7c8696'
}

export default function FilterBar() {
  const kindFilters = useGraphStore((s) => s.kindFilters)
  const toggleKind = useGraphStore((s) => s.toggleKind)

  return (
    <div className="flex flex-wrap items-center gap-2">
      {ENTITY_KINDS.map((k) => {
        const active = kindFilters.has(k.key)
        const tint = tintFor(k.key)
        return (
          <button
            key={k.key}
            onClick={() => toggleKind(k.key)}
            className={
              active
                ? 'flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-white transition-colors'
                : 'flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1 text-xs text-white/50 transition-colors hover:text-white'
            }
            style={active ? { borderColor: `${tint}8C`, backgroundColor: `${tint}24` } : undefined}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ ...swatchStyle(k.key), opacity: active ? 1 : 0.55 }}
            />
            {k.label}
          </button>
        )
      })}
    </div>
  )
}

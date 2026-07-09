import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Pause, Play, Zap, ZapOff, Maximize2, Plus, Minus } from 'lucide-react'
import type { GraphData, GraphNode } from '@/lib/graphApi'
import { useGraphStore, type GraphPulse } from '@/stores/graphStore'
import { HIVE_HEX_COLORS, DEPARTMENT_COLORS, GOV_GOLD, GOV_TEAL, BACKGROUNDS, KIND_COLORS } from '@/styles/designTokens'
import { govSignal, type GovSignal } from './governanceSignal'
import { WORKING_STATUS } from './workingStatus'

/**
 * BrainCanvas: a hand-drawn 2D canvas lens over Daena's org graph, ported from
 * the approved companion design so /brain reads as a living brain -- Daena core
 * at the centre, six faculties on the inner ring, ten departments on the mid
 * ring, their sixty agent limbs fanned outward, eight shared MCP servers on the
 * outer rim. Structure is grounded (every node/edge comes from the live store);
 * the comet signals are illustrative flow.
 *
 * Honesty (Rule 17 / ADR-001): the expanding "working" ring and the per-node
 * activity label light ONLY on a genuine working status / real task meta. The
 * grounded fallback's all-active nodes carry no live telemetry, so both stay
 * dark until real data arrives -- the brain never invents "current work".
 * Reuses NodeDetailPanel via selectNode (no second inspector).
 *
 * The first frame is painted synchronously on mount/resize and redrawn
 * synchronously inside every pointer handler, so the scene is never blank even
 * where requestAnimationFrame is throttled; rAF only layers the motion on top.
 */

type Tier = 'root' | 'faculty' | 'department' | 'agent' | 'mcp' | 'other'
type EdgeClass = 'core' | 'limb' | 'mcp'

interface Placed {
  node: GraphNode
  x: number
  y: number
  r: number
  color: string
  tier: Tier
  working: boolean
  gov: GovSignal | null
  phase: number
}

interface LEdge {
  source: string
  target: string
  phase: number
  cx: number
  cy: number
  cls: EdgeClass
}

interface Bounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

// A department "cortex lobe": a soft glow centroid parked behind one
// department's agent fan. agentCount/workingCount are grounded counts;
// workingCount uses the SAME WORKING_STATUS predicate as the node ring and the
// StatsRibbon, so the lobe's activity glow can never disagree with them
// (Rule 5 single source, Rule 17 honesty).
interface Lobe {
  x: number
  y: number
  color: string
  spread: number
  agentCount: number
  workingCount: number
}

interface Layout {
  placed: Map<string, Placed>
  edges: LEdge[]
  order: Placed[]
  lobes: Lobe[]
  bounds: Bounds
}

interface Star {
  x: number
  y: number
  z: number
  tw: number
}

// One in-flight event-driven comet (#10): a single honest pulse fired when the
// backend reports a real status change (task_status_changed / workstream_*).
// src->tgt animates a comet along an incident synapse toward the node that
// moved; when the node has no drawable edge, ringNodeId ring-flashes it instead.
// cx/cy is the incident edge's quadratic control point, captured at emit so the
// curve matches section 5 even if the layout re-fits mid-flight.
interface EventComet {
  born: number
  color: string
  src: string | null
  tgt: string | null
  cx: number
  cy: number
  ringNodeId: string | null
}

const ROOT_ID = 'daena:root'
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5))
const CAP_ORDER = ['MIND', 'EYES', 'HANDS', 'VOICE', 'SHIELD', 'MEMORY']
// WORKING_STATUS now lives in ./workingStatus (shared with the StatsRibbon count
// and the adaptive poll) so the ring, the count, and the cadence never drift.
// Live-only meta keys that can carry a real "what is this agent doing now"
// string. Grounded nodes never set these, so the activity label stays honest.
const TASK_KEYS = ['current_task', 'task', 'working_on', 'activity', 'current_activity']
const FACULTY_COLOR = KIND_COLORS.faculty
const MCP_COLOR = KIND_COLORS.mcp_server
const NEUTRAL = '#7c8696'
const HIVE = HIVE_HEX_COLORS.length

const FAC_R = 170
const DEPT_R = 388
const AGENT_R = 496
const MCP_R = 636
const OTHER_R = 560

const R_ROOT = 26
const R_FAC = 12
const R_DEPT = 14
const R_AGENT = 7
const R_MCP = 9
const R_OTHER = 6

const MIN_SCALE = 0.18
const MAX_SCALE = 4
const STAR_COUNT = 150

// #10 event-driven comet: how long one honest status-change pulse lives on the
// canvas, and a hard cap so a burst of backend events can never grow the buffer
// unbounded (the graphStore pulse queue is already bounded at 32; this bounds
// the render side too). Expiry runs every frame regardless of signalsOn.
const EVENT_COMET_MS = 1100
const EVENT_COMET_MAX = 24

function hash01(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) % 10000) / 10000
}

function hexA(hex: string, a: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  const alpha = Math.max(0, Math.min(1, a))
  return `rgba(${r},${g},${b},${alpha.toFixed(3)})`
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}...` : s
}

function capKey(n: GraphNode): string {
  if (n.kind === 'faculty') return (n.id.split(':')[1] ?? '').toUpperCase()
  if (n.kind === 'agent') {
    const i = n.id.lastIndexOf('-')
    return i >= 0 ? n.id.slice(i + 1).toUpperCase() : ''
  }
  return ''
}

function capIndex(n: GraphNode): number {
  const i = CAP_ORDER.indexOf(capKey(n))
  return i < 0 ? 99 : i
}

function sunflower(n: GraphNode): number {
  return typeof n.sunflower_index === 'number' ? n.sunflower_index : 1e9
}

/**
 * Honest activity read: returns a real live task string from meta, or null.
 * Grounded nodes carry only static role/description meta (no TASK_KEYS), so this
 * is null under the fallback and the activity label never fabricates work.
 */
function taskOf(node: GraphNode): string | null {
  const m = (node.meta ?? {}) as Record<string, unknown>
  for (const k of TASK_KEYS) {
    const v = m[k]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return null
}

function placeNode(
  node: GraphNode,
  x: number,
  y: number,
  r: number,
  color: string,
  tier: Tier,
): Placed {
  const status = String(node.status ?? '').toLowerCase()
  return {
    node,
    x,
    y,
    r,
    color,
    tier,
    working: WORKING_STATUS.has(status),
    gov: govSignal(node),
    phase: hash01(node.id),
  }
}

/**
 * Deterministic seeded starfield (no Math.random, so the same canvas size always
 * yields the same field). A small LCG over an integer seed keeps it pure.
 */
function makeStars(w: number, h: number, n: number): Star[] {
  const stars: Star[] = []
  let seed = (0x9e3779b9 ^ Math.round(w) ^ (Math.round(h) << 16)) >>> 0
  const next = (): number => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    return seed / 4294967296
  }
  for (let i = 0; i < n; i++) {
    stars.push({
      x: next() * w,
      y: next() * h,
      z: 0.4 + next() * 0.6,
      tw: next(),
    })
  }
  return stars
}

/**
 * Crisp label with a dark backing pass so text stays legible over bright glows.
 * Uses ctx.letterSpacing for tracking; resets it before returning.
 */
function paintLabel(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  size: number,
  weight: number,
  color: string,
  alpha: number,
  spacing: number,
): void {
  ctx.font = `${weight} ${size}px Inter, system-ui, sans-serif`
  ctx.letterSpacing = `${spacing}px`
  ctx.fillStyle = hexA('#02040a', 0.7 * alpha)
  ctx.fillText(text, x + 0.6, y + 0.6)
  ctx.fillStyle = hexA(color, alpha)
  ctx.fillText(text, x, y)
  ctx.letterSpacing = '0px'
}

/**
 * Deterministic radial phyllotaxis: pure function of the graph, so the same
 * data always lays out identically (no physics jitter). Degrades gracefully for
 * live data that adds project/workstream/skill kinds -- those land in an outer
 * golden-angle band rather than collapsing to the centre. Edge control points
 * (cx, cy) are precomputed in world space so the synapse curves are stable and
 * cheap to redraw every frame.
 */
function buildLayout(data: GraphData | null): Layout {
  const empty: Layout = {
    placed: new Map(),
    edges: [],
    order: [],
    lobes: [],
    bounds: { minX: -1, minY: -1, maxX: 1, maxY: 1 },
  }
  if (!data || !data.nodes || data.nodes.length === 0) return empty

  const nodes = data.nodes
  const placed = new Map<string, Placed>()

  const root = nodes.find((n) => n.kind === 'daena') ?? nodes.find((n) => n.id === ROOT_ID)
  const faculties = nodes
    .filter((n) => n.kind === 'faculty')
    .sort((a, b) => capIndex(a) - capIndex(b) || sunflower(a) - sunflower(b))
  const departments = nodes
    .filter((n) => n.kind === 'department')
    .sort((a, b) => sunflower(a) - sunflower(b))
  const agents = nodes.filter((n) => n.kind === 'agent')
  const mcps = nodes.filter((n) => n.kind === 'mcp_server')

  // Agent -> department via the employs edge (falls back to department_id).
  const agentParent = new Map<string, string>()
  for (const e of data.edges) {
    if (e.rel === 'employs') agentParent.set(e.target, e.source)
  }

  // Each department gets its BRAND hue keyed by name (Engineering blue, Finance
  // gold, Security pink, ...); agents and the agent fan inherit that hue
  // (RELATIONAL_KINDS rule). Any live department whose name is not in the brand
  // map falls back to a stable hive hue by sunflower index, so nothing ever
  // renders colourless.
  const deptColor = new Map<string, string>()
  departments.forEach((d, i) => {
    const idx = typeof d.sunflower_index === 'number' ? d.sunflower_index : i
    const brand = DEPARTMENT_COLORS[d.label]?.hex
    deptColor.set(d.id, brand ?? HIVE_HEX_COLORS[((idx % HIVE) + HIVE) % HIVE])
  })

  if (root) placed.set(root.id, placeNode(root, 0, 0, R_ROOT, GOV_GOLD, 'root'))

  const facN = faculties.length || 1
  faculties.forEach((f, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / facN
    placed.set(f.id, placeNode(f, Math.cos(ang) * FAC_R, Math.sin(ang) * FAC_R, R_FAC, FACULTY_COLOR, 'faculty'))
  })

  const deptN = departments.length || 1
  const deptPos = new Map<string, { x: number; y: number; ang: number }>()
  departments.forEach((d, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / deptN
    const x = Math.cos(ang) * DEPT_R
    const y = Math.sin(ang) * DEPT_R
    deptPos.set(d.id, { x, y, ang })
    placed.set(d.id, placeNode(d, x, y, R_DEPT, deptColor.get(d.id) ?? NEUTRAL, 'department'))
  })

  const byDept = new Map<string, GraphNode[]>()
  for (const a of agents) {
    const pid = a.department_id ?? agentParent.get(a.id)
    if (!pid) continue
    const list = byDept.get(pid)
    if (list) list.push(a)
    else byDept.set(pid, [a])
  }
  const fan = ((2 * Math.PI) / deptN) * 0.82
  for (const [pid, list] of byDept) {
    const dp = deptPos.get(pid)
    if (!dp) continue
    const sorted = list
      .slice()
      .sort((a, b) => capIndex(a) - capIndex(b) || (a.label ?? '').localeCompare(b.label ?? ''))
    const k = sorted.length
    sorted.forEach((a, j) => {
      const off = k > 1 ? (j / (k - 1) - 0.5) * fan : 0
      const ang = dp.ang + off
      const x = Math.cos(ang) * AGENT_R
      const y = Math.sin(ang) * AGENT_R
      placed.set(a.id, placeNode(a, x, y, R_AGENT, deptColor.get(pid) ?? NEUTRAL, 'agent'))
    })
  }

  // Department cortex lobes (precomputed once per layout, never per frame): one
  // soft glow centroid per department, parked midway between the department ring
  // and its agent fan. workingCount reuses each agent's placed .working flag --
  // the exact WORKING_STATUS predicate the ring + StatsRibbon use -- so the
  // lobe's activity glow stays honest and in lockstep (Rule 5 / Rule 17).
  const lobes: Lobe[] = []
  const LOBE_R = (DEPT_R + AGENT_R) / 2
  for (const d of departments) {
    const dp = deptPos.get(d.id)
    if (!dp) continue
    const kids = byDept.get(d.id) ?? []
    let workingCount = 0
    for (const a of kids) if (placed.get(a.id)?.working) workingCount++
    lobes.push({
      x: Math.cos(dp.ang) * LOBE_R,
      y: Math.sin(dp.ang) * LOBE_R,
      color: deptColor.get(d.id) ?? NEUTRAL,
      spread: 132 + Math.min(kids.length, 8) * 8,
      agentCount: kids.length,
      workingCount,
    })
  }

  const mcpN = mcps.length || 1
  mcps.forEach((m, i) => {
    // Half-step offset so MCP servers sit between department spokes, not on them.
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / mcpN + Math.PI / mcpN
    placed.set(m.id, placeNode(m, Math.cos(ang) * MCP_R, Math.sin(ang) * MCP_R, R_MCP, MCP_COLOR, 'mcp'))
  })

  // Any live-only kinds (projects, workstreams, skills, tools, sessions) the
  // grounded brain does not model: scatter them in an outer band so they stay
  // visible and clickable instead of stacking on the origin.
  let oi = 0
  for (const n of nodes) {
    if (placed.has(n.id)) continue
    const ang = oi * GOLDEN_ANGLE - Math.PI / 2
    const rad = OTHER_R + Math.sqrt(oi) * 16
    oi++
    const col = (KIND_COLORS as Record<string, string>)[n.kind] ?? NEUTRAL
    placed.set(n.id, placeNode(n, Math.cos(ang) * rad, Math.sin(ang) * rad, R_OTHER, col, 'other'))
  }

  const edges: LEdge[] = []
  for (const e of data.edges) {
    const a = placed.get(e.source)
    const b = placed.get(e.target)
    if (!a || !b) continue
    // Precompute a quadratic control point: bow the synapse perpendicular to the
    // parent->child chord, sign chosen by edge hash for an organic weave.
    const mx = (a.x + b.x) / 2
    const my = (a.y + b.y) / 2
    const dx = b.x - a.x
    const dy = b.y - a.y
    const len = Math.hypot(dx, dy) || 1
    const bow = len * 0.13 * (hash01(e.id) < 0.5 ? 1 : -1)
    const cx = mx + (-dy / len) * bow
    const cy = my + (dx / len) * bow
    const cls: EdgeClass = b.tier === 'mcp' ? 'mcp' : a.tier === 'root' ? 'core' : 'limb'
    edges.push({ source: e.source, target: e.target, phase: hash01(e.id), cx, cy, cls })
  }

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const p of placed.values()) {
    minX = Math.min(minX, p.x - p.r)
    minY = Math.min(minY, p.y - p.r)
    maxX = Math.max(maxX, p.x + p.r)
    maxY = Math.max(maxY, p.y + p.r)
  }
  if (!Number.isFinite(minX)) {
    minX = -1
    minY = -1
    maxX = 1
    maxY = 1
  }

  const order = [...placed.values()].sort((a, b) => a.r - b.r)
  return { placed, edges, order, lobes, bounds: { minX, minY, maxX, maxY } }
}

function tierLabel(tier: Tier, kind: string): string {
  switch (tier) {
    case 'root':
      return 'Daena core'
    case 'faculty':
      return 'Faculty'
    case 'department':
      return 'Department'
    case 'agent':
      return 'Agent'
    case 'mcp':
      return 'MCP server'
    default:
      return kind
  }
}

function subLine(p: Placed): string {
  const m = (p.node.meta ?? {}) as Record<string, unknown>
  const role = m.role || m.sub_capability || m.description
  let s = tierLabel(p.tier, p.node.kind)
  if (role) s += ` - ${String(role)}`
  if (p.working) s += ` - ${String(p.node.status ?? '')}`
  return s
}

// Static nebula-wash stops (color, reach-scale). Hoisted to module scope so the
// per-frame draw loop never re-allocates this literal.
const NEBULA: ReadonlyArray<readonly [string, number]> = [
  ['rgba(212,168,67,0.09)', 0.30],
  ['rgba(212,168,67,0.10)', 0.55],
  ['rgba(45,212,191,0.06)', 0.8],
  ['rgba(40,52,74,0.05)', 1.05],
]

// Tier captions for the orbit rings (radius, label). Drawn faint along a quiet
// upper-left ray so the radial structure self-documents at a glance -- these are
// the real node tiers (grounded), so the labelling invents nothing.
const RING_LABELS: ReadonlyArray<readonly [number, string]> = [
  [FAC_R, 'FACULTIES'],
  [DEPT_R, 'DEPARTMENTS'],
  [AGENT_R, 'AGENTS'],
  [MCP_R, 'MCP SERVERS'],
]

interface CanvasState {
  layout: Layout
  selectedNodeId: string | null
  highlighted: Set<string>
  signalsOn: boolean
  paused: boolean
}

export default function BrainCanvas() {
  const data = useGraphStore((s) => s.data)
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId)
  const selectNode = useGraphStore((s) => s.selectNode)
  const highlightedIds = useGraphStore((s) => s.highlightedIds)

  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [paused, setPaused] = useState(false)
  const [signalsOn, setSignalsOn] = useState(true)
  const [tip, setTip] = useState<{ x: number; y: number; title: string; sub: string } | null>(null)

  const layout = useMemo(() => buildLayout(data), [data])

  const cameraRef = useRef({ scale: 1, tx: 0, ty: 0 })
  const sizeRef = useRef({ dpr: 1, cssW: 1, cssH: 1 })
  const hoverRef = useRef<string | null>(null)
  const rafRef = useRef(0)
  const dragRef = useRef({ active: false, lastX: 0, lastY: 0, moved: 0 })
  const starsRef = useRef<Star[]>([])
  // #10: in-flight event comets and the last pulse.seq we have already turned
  // into a comet. The subscribe effect appends here (never re-renders); draw()
  // expires them by age. Kept in refs so the stable draw closure sees the live
  // buffer without a rebuild.
  const activeCometsRef = useRef<EventComet[]>([])
  const lastPulseSeqRef = useRef(0)

  const stateRef = useRef<CanvasState>({
    layout,
    selectedNodeId,
    highlighted: highlightedIds,
    signalsOn,
    paused,
  })
  // Keep the imperative renderer reading the freshest props without rebuilding
  // the stable draw closure.
  stateRef.current.layout = layout
  stateRef.current.selectedNodeId = selectedNodeId
  stateRef.current.highlighted = highlightedIds
  stateRef.current.signalsOn = signalsOn
  stateRef.current.paused = paused

  const nodeScreenR = (r: number): number => {
    const cam = cameraRef.current
    const f = Math.max(0.7, Math.min(1.7, cam.scale))
    return r * f
  }

  const draw = useCallback((nowMs: number) => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    const { dpr, cssW, cssH } = sizeRef.current
    const cam = cameraRef.current
    const st = stateRef.current
    const lay = st.layout
    const now = nowMs / 1000

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, cssW, cssH)

    // Scalar world->screen (no per-call tuple allocation: this runs ~1000x/frame).
    const toSx = (x: number): number => x * cam.scale + cam.tx
    const toSy = (y: number): number => y * cam.scale + cam.ty
    const rcx = toSx(0)
    const rcy = toSy(0)
    const hasHl = st.highlighted.size > 0
    const hoveredId = hoverRef.current
    const selId = st.selectedNodeId
    const dimOf = (id: string): number => (hasHl && !st.highlighted.has(id) ? 0.16 : 1)

    // 1) Deep-space fill.
    ctx.fillStyle = BACKGROUNDS.midnight
    ctx.fillRect(0, 0, cssW, cssH)

    // 2) Nebula wash: layered radial tints so the core reads as lit from within.
    const reach = Math.max(cssW, cssH)
    for (const [stop, scale] of NEBULA) {
      const g = ctx.createRadialGradient(rcx, rcy, 0, rcx, rcy, reach * scale)
      g.addColorStop(0, stop)
      g.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, cssW, cssH)
    }

    // 3) Twinkling starfield (screen-space, additive). Pure backdrop depth.
    ctx.globalCompositeOperation = 'lighter'
    for (const s of starsRef.current) {
      const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(now * 1.3 + s.tw * 6.283))
      ctx.beginPath()
      ctx.arc(s.x, s.y, s.z * 0.9, 0, Math.PI * 2)
      ctx.fillStyle = hexA('#dbe6ff', 0.5 * tw * s.z)
      ctx.fill()
    }
    ctx.globalCompositeOperation = 'source-over'

    // 4) Orbit guide rings.
    for (const ringR of [FAC_R, DEPT_R, AGENT_R, MCP_R]) {
      ctx.beginPath()
      ctx.arc(rcx, rcy, ringR * cam.scale, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(255,255,255,0.04)'
      ctx.lineWidth = 1
      ctx.stroke()
    }
    // Faint tier captions riding each ring along a quiet upper-left ray, so the
    // radial structure (faculties -> departments -> agents -> mcp) reads at a
    // glance. These name the real node tiers, so the labelling invents nothing.
    {
      const la = -2.356
      const lac = Math.cos(la)
      const las = Math.sin(la)
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      for (const [ringR, name] of RING_LABELS) {
        const lr = ringR * cam.scale
        paintLabel(ctx, name, rcx + lac * lr, rcy + las * lr, 8.5, 600, '#9fb0c4', 0.4, 2)
      }
    }

    // 4b) Department cortex lobes: a soft radial bloom behind each department's
    // agent fan, in the department's brand hue, so the ten departments read as
    // distinct brain regions (the conducting.ai cortex look). The base wash is
    // pure STRUCTURE -- departments and their agents are grounded nodes -- drawn
    // static like the orbit rings, so it claims no activity. ONLY the additive
    // activity boost (and its breathing) scales with the fraction of agents in
    // genuine WORKING_STATUS, so an idle or grounded-fallback brain shows calm,
    // even regions and never fakes "current work" (Rule 17 / ADR-001).
    ctx.globalCompositeOperation = 'lighter'
    for (const lobe of lay.lobes) {
      const sx = toSx(lobe.x)
      const sy = toSy(lobe.y)
      const br = lobe.spread * cam.scale
      const active = lobe.agentCount > 0 ? lobe.workingCount / lobe.agentCount : 0
      const pulse = active > 0 ? 0.6 + 0.4 * (0.5 + 0.5 * Math.sin(now * 2.2)) : 1
      const intensity = 0.05 + 0.16 * active * pulse
      const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, br)
      g.addColorStop(0, hexA(lobe.color, intensity))
      g.addColorStop(0.6, hexA(lobe.color, intensity * 0.4))
      g.addColorStop(1, hexA(lobe.color, 0))
      ctx.fillStyle = g
      ctx.beginPath()
      ctx.arc(sx, sy, br, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.globalCompositeOperation = 'source-over'

    // 5) Curved synapse edges (parent->child gradient; MCP links dashed).
    for (const e of lay.edges) {
      const a = lay.placed.get(e.source)
      const b = lay.placed.get(e.target)
      if (!a || !b) continue
      const d = Math.min(dimOf(a.node.id), dimOf(b.node.id))
      const focusNear = a.node.id === selId || b.node.id === selId || a.node.id === hoveredId || b.node.id === hoveredId
      const x0 = toSx(a.x)
      const y0 = toSy(a.y)
      const x1 = toSx(b.x)
      const y1 = toSy(b.y)
      const cxp = toSx(e.cx)
      const cyp = toSy(e.cy)
      const grad = ctx.createLinearGradient(x0, y0, x1, y1)
      grad.addColorStop(0, hexA(a.color, (focusNear ? 0.5 : 0.16) * d))
      grad.addColorStop(1, hexA(b.color, (focusNear ? 0.6 : 0.2) * d))
      if (e.cls === 'mcp') ctx.setLineDash([5, 5])
      ctx.beginPath()
      ctx.moveTo(x0, y0)
      ctx.quadraticCurveTo(cxp, cyp, x1, y1)
      ctx.strokeStyle = grad
      ctx.lineWidth = focusNear ? 1.6 : 1
      ctx.stroke()
      ctx.setLineDash([])
    }

    // 6) Comet signals riding the synapse curves (illustrative flow). Hot when
    // either endpoint is genuinely working; otherwise a calm base drift.
    if (st.signalsOn) {
      ctx.globalCompositeOperation = 'lighter'
      const trail = 7
      for (const e of lay.edges) {
        const a = lay.placed.get(e.source)
        const b = lay.placed.get(e.target)
        if (!a || !b) continue
        const d = Math.min(dimOf(a.node.id), dimOf(b.node.id))
        if (d < 0.5) continue
        const hot = a.working || b.working
        const base = e.cls === 'core' ? 0.3 : e.cls === 'mcp' ? 0.2 : 0.24
        const speed = hot ? 0.55 : base
        const t = (((now * speed + e.phase) % 1) + 1) % 1
        for (let k = trail; k >= 0; k--) {
          const tt = t - k * 0.016
          if (tt < 0 || tt > 1) continue
          const u = 1 - tt
          // Quadratic Bezier sample in world space, then to screen.
          const wx = u * u * a.x + 2 * u * tt * e.cx + tt * tt * b.x
          const wy = u * u * a.y + 2 * u * tt * e.cy + tt * tt * b.y
          const sx = toSx(wx)
          const sy = toSy(wy)
          const alpha = (1 - k / (trail + 1)) * (hot ? 0.95 : 0.5) * d
          const rad = (hot ? 2.6 : 1.7) * (1 - k / (trail + 2))
          ctx.beginPath()
          ctx.arc(sx, sy, Math.max(0.6, rad), 0, Math.PI * 2)
          ctx.fillStyle = hexA(b.color, alpha)
          ctx.fill()
          if (k === 0) {
            // Leading-head halo so signal DIRECTION (parent -> child flow) reads
            // clearly -- this is the "see the process" cue, still illustrative.
            ctx.beginPath()
            ctx.arc(sx, sy, Math.max(1.2, rad * 2.1), 0, Math.PI * 2)
            ctx.fillStyle = hexA(b.color, alpha * 0.28)
            ctx.fill()
          }
        }
      }
      ctx.globalCompositeOperation = 'source-over'
    }

    // 6b) Event-driven comets (#10): one honest pulse per real backend status
    // change (task_status_changed / workstream_*). Unlike section 6 these are
    // NOT illustrative -- each rides an incident synapse toward the node that
    // actually moved, then self-expires after EVENT_COMET_MS. Expiry runs every
    // frame so the buffer stays bounded even while signals are toggled off; only
    // the draw is gated on signalsOn.
    const comets = activeCometsRef.current
    if (comets.length) {
      const survivors: EventComet[] = []
      const drawOn = st.signalsOn
      if (drawOn) ctx.globalCompositeOperation = 'lighter'
      for (const cm of comets) {
        const age = nowMs - cm.born
        if (age < 0 || age >= EVENT_COMET_MS) continue // expired -> dropped
        survivors.push(cm)
        if (!drawOn) continue
        const life = age / EVENT_COMET_MS
        // smoothstep travel so the head eases in then settles on the target.
        const p = life * life * (3 - 2 * life)
        const fade = 1 - life // whole comet dims as it ages
        if (cm.src && cm.tgt) {
          const a = lay.placed.get(cm.src)
          const b = lay.placed.get(cm.tgt)
          if (!a || !b) continue // layout re-fit dropped an endpoint; expire by age
          const trail = 6
          for (let k = trail; k >= 0; k--) {
            const tt = p - k * 0.02
            if (tt < 0 || tt > 1) continue
            const u = 1 - tt
            // Same quadratic Bezier sampler as section 6, with the control point
            // captured at emit so the curve matches the drawn synapse.
            const wx = u * u * a.x + 2 * u * tt * cm.cx + tt * tt * b.x
            const wy = u * u * a.y + 2 * u * tt * cm.cy + tt * tt * b.y
            const sx = toSx(wx)
            const sy = toSy(wy)
            const alpha = (1 - k / (trail + 1)) * fade
            const rad = (k === 0 ? 3.6 : 2.4) * (1 - k / (trail + 2))
            ctx.beginPath()
            ctx.arc(sx, sy, Math.max(0.8, rad), 0, Math.PI * 2)
            ctx.fillStyle = hexA(cm.color, alpha)
            ctx.fill()
            if (k === 0) {
              ctx.beginPath()
              ctx.arc(sx, sy, Math.max(1.6, rad * 2.4), 0, Math.PI * 2)
              ctx.fillStyle = hexA(cm.color, alpha * 0.3)
              ctx.fill()
            }
          }
        } else if (cm.ringNodeId) {
          // Fallback: the moved node has no drawable incident edge, so flash an
          // expanding ring on the node itself rather than fabricate a path.
          const n = lay.placed.get(cm.ringNodeId)
          if (!n) continue
          const sx = toSx(n.x)
          const sy = toSy(n.y)
          const baseR = nodeScreenR(n.r)
          const rr = baseR + p * baseR * 3.2
          ctx.beginPath()
          ctx.arc(sx, sy, rr, 0, Math.PI * 2)
          ctx.strokeStyle = hexA(cm.color, fade * 0.7)
          ctx.lineWidth = 2
          ctx.stroke()
        }
      }
      if (drawOn) ctx.globalCompositeOperation = 'source-over'
      activeCometsRef.current = survivors
    }

    // 7) Heartbeat throughput rings pulsing out from the core.
    if (st.signalsOn) {
      ctx.globalCompositeOperation = 'lighter'
      for (let i = 0; i < 2; i++) {
        const cyc = (((now * 0.35 + i * 0.5) % 1) + 1) % 1
        const rr = (R_ROOT + cyc * (DEPT_R - R_ROOT)) * cam.scale
        ctx.beginPath()
        ctx.arc(rcx, rcy, rr, 0, Math.PI * 2)
        ctx.strokeStyle = hexA(GOV_GOLD, (1 - cyc) * 0.14)
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
    }

    // 8) Bloom halos behind every node (additive), sized by tier.
    ctx.globalCompositeOperation = 'lighter'
    for (const p of lay.order) {
      const dim = dimOf(p.node.id)
      if (dim < 0.5) continue
      const sx = toSx(p.x)
      const sy = toSy(p.y)
      const r = nodeScreenR(p.r)
      const isFocus = p.node.id === selId || p.node.id === hoveredId
      const breathe = p.tier === 'root' ? 0.65 + 0.35 * (0.5 + 0.5 * Math.sin(now * 1.6)) : 1
      const bloomR = r * (p.tier === 'root' ? 4.2 : isFocus ? 3.4 : 2.4)
      const intensity =
        (p.tier === 'root' ? 0.28 : p.tier === 'department' || p.tier === 'faculty' ? 0.18 : 0.12) *
        breathe *
        (isFocus ? 1.5 : 1) *
        dim
      const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, bloomR)
      g.addColorStop(0, hexA(p.color, intensity))
      g.addColorStop(1, hexA(p.color, 0))
      ctx.fillStyle = g
      ctx.beginPath()
      ctx.arc(sx, sy, bloomR, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.globalCompositeOperation = 'source-over'

    // 8b) Living core nucleus: counter-rotating gold/teal corona arcs so Daena's
    // core reads as a thinking brain, not just the largest dot. Pure ambient
    // aesthetic on the root only -- carries no telemetry claim.
    {
      const coreR = nodeScreenR(R_ROOT)
      ctx.globalCompositeOperation = 'lighter'
      const spin = now * 0.25
      for (let i = 0; i < 3; i++) {
        const a0 = spin + (i * Math.PI * 2) / 3
        ctx.beginPath()
        ctx.arc(rcx, rcy, coreR * 1.7, a0, a0 + 1.05)
        ctx.strokeStyle = hexA(GOV_GOLD, 0.22)
        ctx.lineWidth = 1.4
        ctx.stroke()
      }
      const inner = -now * 0.4
      for (let i = 0; i < 2; i++) {
        const a0 = inner + i * Math.PI
        ctx.beginPath()
        ctx.arc(rcx, rcy, coreR * 1.32, a0, a0 + 1.35)
        ctx.strokeStyle = hexA(GOV_TEAL, 0.18)
        ctx.lineWidth = 1.2
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
    }

    // 9) Crisp node bodies (small first, so the core lands on top).
    for (const p of lay.order) {
      const sx = toSx(p.x)
      const sy = toSy(p.y)
      const r = nodeScreenR(p.r)
      const dim = dimOf(p.node.id)
      const isSel = p.node.id === selId
      const isHover = p.node.id === hoveredId

      // Working aura: lights ONLY on a genuine working status (honesty).
      if (p.working) {
        const cyc = (((now * 0.7 + p.phase) % 1) + 1) % 1
        ctx.beginPath()
        ctx.arc(sx, sy, r + 3 + 16 * cyc, 0, Math.PI * 2)
        ctx.strokeStyle = hexA(p.color, (1 - cyc) * 0.55 * dim)
        ctx.lineWidth = 2
        ctx.stroke()
      }

      // Governance ring (escalations / approvals carry their own colour).
      if (p.gov) {
        ctx.beginPath()
        ctx.arc(sx, sy, r + 4, 0, Math.PI * 2)
        if (p.gov.dashed) ctx.setLineDash([3, 3])
        ctx.strokeStyle = hexA(p.gov.ring, 0.8 * dim)
        ctx.lineWidth = 1.5
        ctx.stroke()
        ctx.setLineDash([])
      }

      // Body: a soft radial fill so nodes read as little lamps, not flat dots.
      const body = ctx.createRadialGradient(sx - r * 0.3, sy - r * 0.3, r * 0.1, sx, sy, r)
      body.addColorStop(0, hexA('#ffffff', (isSel || isHover ? 0.85 : 0.55) * dim))
      body.addColorStop(0.35, hexA(p.color, (isSel || isHover ? 1 : 0.95) * dim))
      body.addColorStop(1, hexA(p.color, (isSel || isHover ? 1 : 0.85) * dim))
      ctx.beginPath()
      ctx.arc(sx, sy, r, 0, Math.PI * 2)
      ctx.fillStyle = body
      ctx.fill()
      ctx.lineWidth = isSel ? 2 : 1
      ctx.strokeStyle = isSel || isHover ? hexA(GOV_TEAL, dim) : hexA('#ffffff', 0.25 * dim)
      ctx.stroke()

      // Tiered typography.
      if (dim > 0.5) {
        ctx.textAlign = 'center'
        if (p.tier === 'root') {
          ctx.textBaseline = 'top'
          paintLabel(ctx, p.node.label || 'Daena', sx, sy + r + 7, 14, 700, GOV_GOLD, 0.95 * dim, 0.5)
        } else if (p.tier === 'faculty') {
          ctx.textBaseline = 'bottom'
          const lab = (p.node.label || capKey(p.node)).toUpperCase()
          paintLabel(ctx, truncate(lab, 14), sx, sy - r - 6, 10, 600, FACULTY_COLOR, 0.82 * dim, 1.4)
        } else if (p.tier === 'department') {
          ctx.textBaseline = 'top'
          paintLabel(ctx, truncate(p.node.label || p.node.id, 18), sx, sy + r + 5, 11, 600, '#e8edf4', 0.8 * dim, 0.2)
        } else if (p.tier === 'mcp') {
          ctx.textBaseline = 'top'
          paintLabel(ctx, truncate(p.node.label || p.node.id, 16), sx, sy + r + 4, 10, 500, MCP_COLOR, 0.78 * dim, 0.2)
        } else if (isSel || isHover) {
          ctx.textBaseline = 'top'
          paintLabel(ctx, truncate(p.node.label || p.node.id, 22), sx, sy + r + 4, 11, 500, '#e8edf4', dim, 0.2)
        }
      }

      // 10) Honest activity label: ONLY when a real live task exists AND the node
      // is working or focused. Grounded nodes have no task meta, so this is silent
      // under the fallback -- it never invents "current work".
      const task = taskOf(p.node)
      if (task && (p.working || isSel || isHover) && dim > 0.5) {
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        const yBase = p.tier === 'faculty' ? sy - r - 20 : sy + r + (p.tier === 'agent' || p.tier === 'other' ? 18 : 22)
        paintLabel(ctx, truncate(task, 28), sx, yBase, 9, 500, GOV_TEAL, 0.85 * dim, 0.1)
      }
    }

    // 11) Vignette to settle the edges of the frame.
    const vig = ctx.createRadialGradient(
      cssW / 2,
      cssH / 2,
      Math.min(cssW, cssH) * 0.35,
      cssW / 2,
      cssH / 2,
      Math.max(cssW, cssH) * 0.75,
    )
    vig.addColorStop(0, 'rgba(0,0,0,0)')
    vig.addColorStop(1, 'rgba(0,0,0,0.45)')
    ctx.fillStyle = vig
    ctx.fillRect(0, 0, cssW, cssH)
  }, [])

  const drawNow = useCallback(() => {
    draw(typeof performance !== 'undefined' ? performance.now() : 0)
  }, [draw])

  const fit = useCallback(() => {
    const { cssW, cssH } = sizeRef.current
    const b = stateRef.current.layout.bounds
    const bw = Math.max(b.maxX - b.minX, 1)
    const bh = Math.max(b.maxY - b.minY, 1)
    const pad = 90
    const scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, Math.min((cssW - pad * 2) / bw, (cssH - pad * 2) / bh)))
    const cx = (b.minX + b.maxX) / 2
    const cy = (b.minY + b.maxY) / 2
    cameraRef.current.scale = scale
    cameraRef.current.tx = cssW / 2 - cx * scale
    cameraRef.current.ty = cssH / 2 - cy * scale
  }, [])

  const hitTest = useCallback((mx: number, my: number): Placed | null => {
    const cam = cameraRef.current
    let best: Placed | null = null
    let bestD = Infinity
    for (const p of stateRef.current.layout.placed.values()) {
      const sx = p.x * cam.scale + cam.tx
      const sy = p.y * cam.scale + cam.ty
      const rr = nodeScreenR(p.r) + 6
      const d = Math.hypot(mx - sx, my - sy)
      if (d <= rr && d < bestD) {
        best = p
        bestD = d
      }
    }
    return best
  }, [])

  // #10: turn graphStore pulses into on-canvas event comets. The store has no
  // selector middleware, so a vanilla subscribe fires the full-state listener on
  // every set; we drain by monotonic seq so each honest backend pulse spawns
  // exactly one comet even across React batching, and read the FRESH layout from
  // stateRef so a comet always rides the currently drawn synapse.
  useEffect(() => {
    const consume = (pulses: GraphPulse[]) => {
      if (!pulses.length) return
      const lay = stateRef.current.layout
      for (const pulse of pulses) {
        if (pulse.seq <= lastPulseSeqRef.current) continue
        lastPulseSeqRef.current = pulse.seq
        const moved = lay.placed.get(pulse.nodeId)
        if (!moved) continue // node absent from the current projection -> nothing honest to show
        // Prefer an edge ARRIVING at the moved node ("signal reaching the thing
        // that changed"); else an edge leaving it; else ring-flash the node.
        let edge = lay.edges.find((e) => e.target === pulse.nodeId)
        if (!edge) edge = lay.edges.find((e) => e.source === pulse.nodeId)
        const comet: EventComet = edge
          ? {
              born: performance.now(),
              color: moved.color,
              src: edge.source,
              tgt: edge.target,
              cx: edge.cx,
              cy: edge.cy,
              ringNodeId: null,
            }
          : {
              born: performance.now(),
              color: moved.color,
              src: null,
              tgt: null,
              cx: 0,
              cy: 0,
              ringNodeId: pulse.nodeId,
            }
        const buf = activeCometsRef.current
        buf.push(comet)
        if (buf.length > EVENT_COMET_MAX) buf.splice(0, buf.length - EVENT_COMET_MAX)
      }
    }
    // Drain anything queued before we subscribed, then follow the stream.
    consume(useGraphStore.getState().pulses)
    return useGraphStore.subscribe((s) => consume(s.pulses))
  }, [])

  // Mount: size the canvas, wire pointer/wheel, paint the first frame, run rAF.
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const resize = () => {
      const rect = container.getBoundingClientRect()
      const dpr = Math.min(2, typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1)
      const cssW = Math.max(1, Math.round(rect.width))
      const cssH = Math.max(1, Math.round(rect.height))
      sizeRef.current = { dpr, cssW, cssH }
      canvas.width = Math.round(cssW * dpr)
      canvas.height = Math.round(cssH * dpr)
      canvas.style.width = `${cssW}px`
      canvas.style.height = `${cssH}px`
      starsRef.current = makeStars(cssW, cssH, STAR_COUNT)
      fit()
      drawNow()
    }

    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(container)

    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault()
      const rect = canvas.getBoundingClientRect()
      const mx = ev.clientX - rect.left
      const my = ev.clientY - rect.top
      const cam = cameraRef.current
      const factor = Math.exp(-ev.deltaY * 0.0015)
      const ns = Math.max(MIN_SCALE, Math.min(MAX_SCALE, cam.scale * factor))
      const wx = (mx - cam.tx) / cam.scale
      const wy = (my - cam.ty) / cam.scale
      cam.scale = ns
      cam.tx = mx - wx * ns
      cam.ty = my - wy * ns
      drawNow()
    }

    const localXY = (ev: PointerEvent): [number, number] => {
      const rect = canvas.getBoundingClientRect()
      return [ev.clientX - rect.left, ev.clientY - rect.top]
    }

    const onDown = (ev: PointerEvent) => {
      const [mx, my] = localXY(ev)
      dragRef.current = { active: true, lastX: mx, lastY: my, moved: 0 }
      canvas.setPointerCapture?.(ev.pointerId)
      canvas.style.cursor = 'grabbing'
    }

    const onMove = (ev: PointerEvent) => {
      const [mx, my] = localXY(ev)
      const drag = dragRef.current
      if (drag.active) {
        const dx = mx - drag.lastX
        const dy = my - drag.lastY
        drag.lastX = mx
        drag.lastY = my
        drag.moved += Math.abs(dx) + Math.abs(dy)
        cameraRef.current.tx += dx
        cameraRef.current.ty += dy
        setTip(null)
        drawNow()
        return
      }
      const hit = hitTest(mx, my)
      const id = hit ? hit.node.id : null
      if (id !== hoverRef.current) {
        hoverRef.current = id
        canvas.style.cursor = id ? 'pointer' : 'grab'
        setTip(hit ? { x: mx, y: my, title: hit.node.label || hit.node.id, sub: subLine(hit) } : null)
        drawNow()
      } else if (hit) {
        setTip({ x: mx, y: my, title: hit.node.label || hit.node.id, sub: subLine(hit) })
      }
    }

    const onUp = (ev: PointerEvent) => {
      const drag = dragRef.current
      const [mx, my] = localXY(ev)
      canvas.style.cursor = hoverRef.current ? 'pointer' : 'grab'
      if (drag.active && drag.moved < 5) {
        const hit = hitTest(mx, my)
        selectNode(hit ? hit.node.id : null)
      }
      drag.active = false
    }

    const onLeave = () => {
      dragRef.current.active = false
      if (hoverRef.current) {
        hoverRef.current = null
        setTip(null)
        drawNow()
      }
    }

    // Abnormal gesture termination (touch interruption, OS gesture steal, palm
    // rejection) fires pointercancel, NOT pointerup -- and while pointer capture
    // is held, pointerleave is suppressed. Without this, dragRef.active would
    // stay true and the next move would read as a phantom drag.
    const onCancel = () => {
      dragRef.current.active = false
      hoverRef.current = null
      setTip(null)
      canvas.style.cursor = 'grab'
      drawNow()
    }

    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('pointerdown', onDown)
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerup', onUp)
    canvas.addEventListener('pointerleave', onLeave)
    canvas.addEventListener('pointercancel', onCancel)
    canvas.style.cursor = 'grab'

    const frame = (t: number) => {
      if (!stateRef.current.paused) draw(t)
      rafRef.current = requestAnimationFrame(frame)
    }
    rafRef.current = requestAnimationFrame(frame)

    return () => {
      cancelAnimationFrame(rafRef.current)
      ro.disconnect()
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerup', onUp)
      canvas.removeEventListener('pointerleave', onLeave)
      canvas.removeEventListener('pointercancel', onCancel)
    }
  }, [draw, drawNow, fit, hitTest, selectNode])

  // New data (grounded -> live upgrade) re-fits and repaints synchronously.
  useEffect(() => {
    fit()
    drawNow()
  }, [layout, fit, drawNow])

  // Selection / search-highlight / control changes repaint immediately, so the
  // scene stays correct even when rAF is throttled.
  useEffect(() => {
    drawNow()
  }, [selectedNodeId, highlightedIds, signalsOn, paused, drawNow])

  const zoomBy = (factor: number) => {
    const { cssW, cssH } = sizeRef.current
    const cam = cameraRef.current
    const ns = Math.max(MIN_SCALE, Math.min(MAX_SCALE, cam.scale * factor))
    const wx = (cssW / 2 - cam.tx) / cam.scale
    const wy = (cssH / 2 - cam.ty) / cam.scale
    cam.scale = ns
    cam.tx = cssW / 2 - wx * ns
    cam.ty = cssH / 2 - wy * ns
    drawNow()
  }

  const ctrlBtn =
    'flex h-8 w-8 items-center justify-center rounded-md border border-white/10 bg-black/60 text-white/70 backdrop-blur transition-colors hover:border-white/20 hover:text-white'

  return (
    <div ref={containerRef} className="absolute inset-0">
      <h2 className="sr-only">
        Daena brain: the core, six faculties, ten departments and their sixty agents, plus connected services and live
        work, laid out as a radial map. Signals are illustrative; the working ring and activity label light only on live status.
      </h2>
      <canvas ref={canvasRef} className="block h-full w-full" />

      {tip ? (
        <div
          className="pointer-events-none absolute z-30 max-w-xs rounded-md border border-white/10 bg-black/85 px-2.5 py-1.5 text-xs leading-snug backdrop-blur"
          style={{ left: tip.x + 14, top: tip.y + 14 }}
        >
          <div className="font-medium text-white">{tip.title}</div>
          <div className="mt-0.5 text-white/55">{tip.sub}</div>
        </div>
      ) : null}

      <div className="absolute left-4 top-1/2 z-20 flex -translate-y-1/2 flex-col gap-1.5">
        <button
          onClick={() => setPaused((v) => !v)}
          className={ctrlBtn}
          title={paused ? 'Resume motion' : 'Pause motion'}
          aria-pressed={paused}
        >
          {paused ? <Play size={15} /> : <Pause size={15} />}
        </button>
        <button
          onClick={() => setSignalsOn((v) => !v)}
          className={ctrlBtn}
          title={signalsOn ? 'Hide signals' : 'Show signals'}
          aria-pressed={signalsOn}
        >
          {signalsOn ? <Zap size={15} /> : <ZapOff size={15} />}
        </button>
        <button onClick={() => zoomBy(1.2)} className={ctrlBtn} title="Zoom in">
          <Plus size={15} />
        </button>
        <button onClick={() => zoomBy(1 / 1.2)} className={ctrlBtn} title="Zoom out">
          <Minus size={15} />
        </button>
        <button
          onClick={() => {
            fit()
            drawNow()
          }}
          className={ctrlBtn}
          title="Reset view"
        >
          <Maximize2 size={15} />
        </button>
      </div>
    </div>
  )
}

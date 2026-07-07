import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { ZoomIn, ZoomOut, Maximize2, Crosshair } from 'lucide-react'
import { BACKGROUNDS, GOV_GOLD, GOV_TEAL, HIVE_HEX_COLORS, KIND_COLORS } from '@/styles/designTokens'
import { useGraphStore } from '@/stores/graphStore'
import { govSignal, GOV_APPROVAL, GOV_BLOCKER, GOV_NOTIFY, SETTLED_STATUS } from './governanceSignal'

interface Size {
  width: number
  height: number
}

// One signal-carrying dendrite, precomputed as a fixed segment (nodes are
// pinned, so endpoints never move) plus an animation phase + a "hot" flag.
// onRenderFramePost travels a pulse along each one every frame -- the live
// process layer over the static structure.
interface PulseEdge {
  source: string
  target: string
  x1: number
  y1: number
  x2: number
  y2: number
  len: number
  color: string
  phase: number
  hot: boolean
}

/**
 * Mission Control canvas: a deterministic radial org map, NOT a free force blob.
 *
 * Daena is the central core. Departments sit on one clean ring around her,
 * evenly spaced in `sunflower_index` order -- the honeycomb ordering preserved
 * as the angular sequence (the outer resource band keeps the phyllotaxis spiral
 * where the sunflower topology earns its keep). Each department is itself a
 * core: its six sub-capability agents orbit it in a ring, with workstreams and
 * sessions on an outer ring; tenant-wide resources (projects, MCP servers,
 * skills, tools, ontology) sit in an outer resource band around everything.
 *
 * Every node is pinned (fx/fy) so the picture is stable and readable instead of
 * jittering into a pile. Labels use level-of-detail: Daena and departments are
 * always named, agents appear as you zoom in, leaves only when close (or when
 * focused/searched), which is what fixes the "all labels into each other"
 * problem at wide zoom. Hover / selection dims everything except the focused
 * node and its neighbours so a single core's relationships read cleanly.
 *
 * Sized by a ResizeObserver on the wrapper (ForceGraph2D needs explicit pixel
 * width/height). If the react-kapsule fiber-reuse bug (#596) ever bites on
 * back/forward nav, swap to vanilla force-graph in a ref wrapper, the pattern
 * graphview already uses.
 */

const ROOT_ID = 'daena:root'
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5)) // ~137.5 degrees

// Layout radii, in graph units (fitView scales the whole picture to fit).
//
// Department cores sit on ONE clean ring around Daena, evenly spaced in
// sunflower_index order. The honeycomb ordering is preserved as the angular
// sequence, but the spiral's varying radius is dropped: with only ~10 cores a
// constant-radius ring makes every Daena->department spoke equal-length and
// evenly spaced, which is the wide-zoom legibility the golden-angle spiral
// lacked (its 430->700 radius spread read as an asymmetric tangle). The outer
// resource band still uses the phyllotaxis spiral, where packing many nodes is
// exactly what the sunflower topology is good at.
const DEPT_R0 = 460 // single department ring radius (even spokes around Daena)
const FACULTY_RING = 215 // Daena's six faculties orbit closer in -- her mind, a hex around the core
const AGENT_RING = 72 // sub-capability agents orbit their department core
const WORK_RING = 124 // workstreams / sessions on the outer department ring
const EXEC_RING = 28 // executions hug the session that spawned them
const OUTER_BASE = 720 // empty-data fallback for the resource-band radius
const OUTER_GROW = 30 // band thickness growth per resource

// Drawn node radii by tier (graph units).
const R_DAENA = 30
const R_DEPT = 16
const R_FACULTY = 13
const R_AGENT = 8
const R_WORK = 7
const R_LEAF = 5
const R_EXEC = 4

// Daena's own faculties read as part of the core (light gold), distinct from
// department agents which take their department's hive colour.
const FACULTY_COLOR = '#E6C46A'

// Faint orbit guide rings: the faculty ring around the core, then the
// department annulus (decorative depth).
const ORBIT_RINGS = [FACULTY_RING, DEPT_R0 - 110, DEPT_R0 + 140]

// Canonical sub-capability order so an agent ring always reads the same way.
const CAP_ORDER = ['MIND', 'EYES', 'HANDS', 'VOICE', 'SHIELD', 'MEMORY']

// The NodeDetailPanel slides in from the right at this width when a node is
// selected. Camera framing biases the cluster left of it so the focused core is
// never hidden behind the panel.
const DETAIL_PANEL_W = 360

// LIVE PROCESS LAYER -----------------------------------------------------------
// Statuses that mean a node is genuinely mid-work RIGHT NOW. The grounded
// fallback architecture uses a steady 'active' status (it is structure, not
// telemetry) and 'active' is deliberately ABSENT here -- so the offline brain
// shows only the calm ambient signal flow, and the brighter "working now" pulse
// fires ONLY on real live state once /graph is reachable (Rule 17: motion
// intensity tracks real activity, it never fabricates a busy node).
const WORKING_STATUS = new Set([
  'running',
  'executing',
  'in_progress',
  'in-progress',
  'working',
  'processing',
  'busy',
])

// Structural relations that carry a travelling signal pulse: Daena -> department
// (contains), Daena -> faculty (embodies), department -> agent (employs), Daena
// -> resource (runs / provides). These are the dendrites the brain fires along.
const PULSE_RELS = new Set(['contains', 'embodies', 'employs', 'runs', 'provides'])

type Tier = 'daena' | 'faculty' | 'department' | 'agent' | 'work' | 'leaf' | 'exec'

function tierFor(kind: string): Tier {
  if (kind === 'daena') return 'daena'
  if (kind === 'faculty') return 'faculty'
  if (kind === 'department') return 'department'
  if (kind === 'agent') return 'agent'
  if (kind === 'workstream' || kind === 'session') return 'work'
  if (kind === 'execution') return 'exec'
  return 'leaf'
}

function radiusFor(tier: Tier): number {
  switch (tier) {
    case 'daena':
      return R_DAENA
    case 'faculty':
      return R_FACULTY
    case 'department':
      return R_DEPT
    case 'agent':
      return R_AGENT
    case 'work':
      return R_WORK
    case 'exec':
      return R_EXEC
    default:
      return R_LEAF
  }
}

function ringRadiusFor(kind: string): number {
  if (kind === 'agent') return AGENT_RING
  if (kind === 'execution') return EXEC_RING
  return WORK_RING // workstream / session / anything else parented to a core
}

// Canonical sub-capability slot, shared by department agents AND Daena's own
// faculties (both carry meta.sub_capability), so the six always read in the
// same angular order around their core.
function capIndex(node: any): number {
  if (node.kind !== 'agent' && node.kind !== 'faculty') return 0
  const cap = String(node.meta?.sub_capability ?? '').toUpperCase()
  const i = CAP_ORDER.indexOf(cap)
  return i >= 0 ? i : CAP_ORDER.length
}

/** LOD gate: which labels are worth drawing at the current zoom. */
function labelVisible(tier: Tier, scale: number, forced: boolean): boolean {
  if (forced) return true
  if (tier === 'daena' || tier === 'department') return true
  if (tier === 'faculty') return true // Daena's six faculties: always named, they are the core's mind
  if (tier === 'agent') return scale >= 0.9
  if (tier === 'work') return scale >= 1.5
  return scale >= 2.4 // leaf / exec only when zoomed in close
}

/**
 * Wide-zoom de-emphasis. The core constellation (Daena, her faculties, the
 * department cores and their agents) always renders at full strength; the
 * peripheral tiers (sessions, projects, executions) fade toward a floor as you
 * zoom out, so the org reads as a clean skeleton at fit-scale and resolves into
 * full detail as you zoom in -- standard level-of-detail, not state-hiding.
 */
function lodAlpha(tier: Tier, scale: number): number {
  if (tier === 'daena' || tier === 'faculty' || tier === 'department' || tier === 'agent') {
    return 1
  }
  const t = Math.min(Math.max((scale - 0.55) / 0.6, 0), 1)
  return 0.3 + 0.7 * t
}

function strokeHexagon(ctx: CanvasRenderingContext2D, x: number, y: number, r: number) {
  ctx.beginPath()
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 6 + (i * Math.PI) / 3
    const px = x + r * Math.cos(a)
    const py = y + r * Math.sin(a)
    if (i === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  }
  ctx.closePath()
  ctx.stroke()
}

function hexA(hex: string, a: number): string {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(full, 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}

// Governance overlay (govSignal + GOV_* colours) lives in ./governanceSignal so
// the canvas and the list lens share ONE source of truth for Daena's moat.

const edgeEnd = (x: any): string => (typeof x === 'object' && x ? String(x.id) : String(x))

export default function GraphCanvas() {
  const data = useGraphStore((s) => s.data)
  const selected = useGraphStore((s) => s.selectedNodeId)
  const selectNode = useGraphStore((s) => s.selectNode)
  const highlightedIds = useGraphStore((s) => s.highlightedIds)
  const wrapRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<any>(null)
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  const [hovered, setHovered] = useState<string | null>(null)

  // Measure the wrapper synchronously on mount, then track changes. A bare
  // ResizeObserver is fragile: some embedded/headless Chromium builds do not
  // deliver the initial callback, leaving size at {0,0} so <ForceGraph2D>
  // never mounts. useLayoutEffect + getBoundingClientRect guarantees a real
  // size before first paint; the observer + window resize + rAF re-measure
  // cover every later change.
  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const measure = () => {
      const rect = el.getBoundingClientRect()
      const width = Math.round(rect.width)
      const height = Math.round(rect.height)
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }))
    }
    measure()
    const raf = requestAnimationFrame(measure)
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    window.addEventListener('resize', measure)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [])

  // Deterministic layout: pin every node to a computed position. Recomputed
  // only when the projection changes (not on hover/selection), so interaction
  // never disturbs the picture.
  const built = useMemo(() => {
    if (!data) {
      return {
        nodes: [] as any[],
        links: [] as any[],
        neighborMap: new Map<string, Set<string>>(),
        colorById: new Map<string, string>(),
        childIds: new Map<string, string[]>(),
        bounds: null as { minX: number; maxX: number; minY: number; maxY: number } | null,
        bandBase: OUTER_BASE,
        pulseEdges: [] as PulseEdge[],
      }
    }

    // Departments first: stable order by sunflower_index drives both the spiral
    // position and the hive colour.
    const depts = data.nodes
      .filter((n) => n.kind === 'department')
      .slice()
      .sort(
        (a, b) =>
          (a.sunflower_index ?? 0) - (b.sunflower_index ?? 0) ||
          String(a.label).localeCompare(String(b.label)),
      )
    const deptColor = new Map<string, string>()
    depts.forEach((d, i) => {
      const idx = d.sunflower_index ?? i
      deptColor.set(d.id, HIVE_HEX_COLORS[idx % HIVE_HEX_COLORS.length] ?? '#9aa4b2')
    })

    // Parent of each node, derived from the real edges (dangling-safe upstream).
    const parent = new Map<string, string>()
    for (const e of data.edges) {
      const s = String(e.source)
      const t = String(e.target)
      if (s === ROOT_ID) parent.set(t, ROOT_ID) // contains / provides / runs / ontology
      else if (e.rel === 'employs' || e.rel === 'owns') parent.set(t, s) // dept -> agent / workstream
      else if (e.rel === 'belongs_to') parent.set(s, t) // session -> dept
      else if (e.rel === 'spawned_by' || e.rel === 'part_of') parent.set(s, t) // execution -> session / task
    }

    const childrenOf = new Map<string, any[]>()
    for (const n of data.nodes) {
      if (n.kind === 'daena' || n.kind === 'department') continue
      const p = parent.get(n.id)
      if (!p) continue
      if (!childrenOf.has(p)) childrenOf.set(p, [])
      childrenOf.get(p)!.push(n)
    }

    const pos = new Map<string, { x: number; y: number }>()
    pos.set(ROOT_ID, { x: 0, y: 0 })

    // Department cores: one clean ring around Daena, evenly spaced in
    // sunflower_index order (depts is already sorted by it). Equal-length,
    // evenly-spaced spokes read as clear relations to the core at wide zoom.
    const deptN = Math.max(depts.length, 1)
    depts.forEach((d, i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / deptN
      pos.set(d.id, { x: DEPT_R0 * Math.cos(a), y: DEPT_R0 * Math.sin(a) })
    })

    // Daena's own six faculties: a tight inner ring of spokes around the core,
    // in canonical CAP_ORDER (MIND at top, clockwise). They are her own mind --
    // the SubCapability constant, not tenant rows -- so they sit close in,
    // inside the department annulus, and read as part of the core rather than as
    // outer resources. Placed explicitly here (not via the BFS band) and
    // excluded from rootLeaves below so they never drift to the far edge.
    const faculties = data.nodes
      .filter((n) => n.kind === 'faculty')
      .slice()
      .sort((a, b) => capIndex(a) - capIndex(b) || String(a.label).localeCompare(String(b.label)))
    faculties.forEach((f) => {
      const slot = capIndex(f)
      const i = slot < CAP_ORDER.length ? slot : faculties.indexOf(f)
      const a = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(faculties.length, CAP_ORDER.length)
      pos.set(f.id, { x: FACULTY_RING * Math.cos(a), y: FACULTY_RING * Math.sin(a) })
    })

    // Resource band sits JUST outside the real department cluster (outermost
    // core radius + an agent ring), not at a fixed faraway radius. A hardcoded
    // band exploded the frame: a handful of edge-less sessions parked at r=1180
    // blew up the bounding box and collapsed the governed core into a corner.
    // Anchoring the band to the actual cluster extent keeps the picture compact
    // and readable however many departments exist.
    const deptMaxR = DEPT_R0
    const bandBase = deptMaxR + AGENT_RING + 80

    // Tenant-wide resources (children of root that are not departments): outer
    // resource band, its own phyllotaxis spiral so it spreads evenly.
    const rootLeaves = (childrenOf.get(ROOT_ID) ?? [])
      .filter((n) => n.kind !== 'department' && n.kind !== 'faculty')
      .slice()
      .sort(
        (a, b) =>
          String(a.kind).localeCompare(String(b.kind)) ||
          String(a.label).localeCompare(String(b.label)),
      )
    let bandIdx = 0
    const placeInBand = (n: any) => {
      const r = bandBase + OUTER_GROW * Math.sqrt(bandIdx)
      const a = bandIdx * GOLDEN_ANGLE
      pos.set(n.id, { x: r * Math.cos(a), y: r * Math.sin(a) })
      bandIdx++
    }
    rootLeaves.forEach(placeInBand)

    // Everything else orbits its placed parent. BFS from the cores outward so
    // arbitrarily deep chains (dept -> session -> execution) all get placed.
    const queue: string[] = [...depts.map((d) => d.id), ...rootLeaves.map((n) => n.id)]
    while (queue.length) {
      const pid = queue.shift()!
      const ppos = pos.get(pid)
      if (!ppos) continue
      const kids = (childrenOf.get(pid) ?? []).filter((k) => !pos.has(k.id))
      if (!kids.length) continue
      const phi = Math.atan2(ppos.y, ppos.x) || 0 // outward radial direction
      const byRing = new Map<number, any[]>()
      for (const k of kids) {
        const radius = ringRadiusFor(k.kind)
        if (!byRing.has(radius)) byRing.set(radius, [])
        byRing.get(radius)!.push(k)
      }
      for (const [radius, group] of byRing) {
        group.sort(
          (a, b) =>
            capIndex(a) - capIndex(b) || String(a.label).localeCompare(String(b.label)),
        )
        const m = group.length
        const phase = radius === WORK_RING ? 0.5 : 0 // stagger work ring vs agent ring
        group.forEach((k, idx) => {
          const a = phi + (2 * Math.PI * idx) / m + phase
          pos.set(k.id, { x: ppos.x + radius * Math.cos(a), y: ppos.y + radius * Math.sin(a) })
          queue.push(k.id)
        })
      }
    }

    // Any orphan (missing/cross-tenant parent) lands in the outer band so it is
    // visible rather than stacked at the origin (Rule 17: never hide state).
    for (const n of data.nodes) {
      if (!pos.has(n.id)) placeInBand(n)
    }

    const colorFor = (n: any): string => {
      if (n.kind === 'daena') return GOV_GOLD
      if (n.kind === 'faculty') return FACULTY_COLOR
      if (n.kind === 'department') return deptColor.get(n.id) ?? '#9aa4b2'
      if (n.kind === 'agent' || n.kind === 'workstream' || n.kind === 'session') {
        const p = parent.get(n.id)
        return (p && deptColor.get(p)) || '#7c8696'
      }
      // Parent-less kinds (project / skill / tool / mcp_server / execution) take
      // their canonical per-kind hue so the chip swatch and the node agree.
      return KIND_COLORS[n.kind] ?? '#7c8696'
    }

    const nodes = data.nodes.map((n) => {
      const p = pos.get(n.id) ?? { x: 0, y: 0 }
      const tier = tierFor(n.kind)
      return {
        ...n,
        x: p.x,
        y: p.y,
        fx: p.x,
        fy: p.y,
        __tier: tier,
        __color: colorFor(n),
        __r: radiusFor(tier),
      }
    })
    const links = data.edges.map((e) => ({ ...e }))

    const neighborMap = new Map<string, Set<string>>()
    const link = (a: string, b: string) => {
      if (!neighborMap.has(a)) neighborMap.set(a, new Set())
      neighborMap.get(a)!.add(b)
    }
    for (const e of data.edges) {
      link(String(e.source), String(e.target))
      link(String(e.target), String(e.source))
    }

    const colorById = new Map<string, string>(nodes.map((n) => [String(n.id), n.__color]))

    // LIVE PROCESS LAYER: precompute the signal-carrying dendrites as fixed
    // segments (nodes are pinned, so endpoints never move) plus a per-edge phase
    // and a "hot" flag. onRenderFramePost travels a pulse along each one every
    // frame -- the motion that turns the static structure into a brain you can
    // watch think. Built here, inside the layout memo, so the per-frame draw is
    // O(edges) with zero layout work or allocation. `hot` = incident to a node
    // genuinely mid-work (WORKING_STATUS); the grounded fallback has none, so it
    // stays calm and only real telemetry lights the bright fast pulse (Rule 17).
    const workingIds = new Set(
      data.nodes
        .filter((n) => WORKING_STATUS.has(String(n.status ?? '').toLowerCase()))
        .map((n) => String(n.id)),
    )
    const pulseEdges: PulseEdge[] = []
    data.edges.forEach((e, i) => {
      if (!PULSE_RELS.has(e.rel)) return
      const s = String(e.source)
      const t = String(e.target)
      const ps = pos.get(s)
      const pt = pos.get(t)
      if (!ps || !pt) return
      pulseEdges.push({
        source: s,
        target: t,
        x1: ps.x,
        y1: ps.y,
        x2: pt.x,
        y2: pt.y,
        len: Math.hypot(pt.x - ps.x, pt.y - ps.y),
        // A resource spoke (runs) fires in its target's hue so an MCP synapse
        // glows in its own colour; every other spoke takes the source (core)
        // colour, so a department's signal travels outward in the dept colour.
        color: (e.rel === 'runs' ? colorById.get(t) : colorById.get(s)) ?? GOV_GOLD,
        // Golden-ratio phase stagger so pulses never march in lockstep.
        phase: (i * 0.61803398875) % 1,
        hot: workingIds.has(s) || workingIds.has(t),
      })
    })

    // Subtree index (parent id -> child ids), used by focus-cluster to frame a
    // core plus everything that orbits it without re-deriving parentage.
    const childIds = new Map<string, string[]>()
    for (const [pid, kids] of childrenOf) {
      childIds.set(pid, kids.map((k) => String(k.id)))
    }

    // Tight bounding box (node centre +/- drawn radius) for deterministic
    // framing. Computing it here means the fit never depends on engine timing.
    //
    // Frame to the CONNECTED CORE (Daena + department cores + their agent rings)
    // only. Disconnected sessions / orphan resources still render in the outer
    // band and are reachable by panning, but they must not enlarge the fit box:
    // a handful of edge-less test sessions parked far out did exactly that and
    // collapsed the whole org into a tiny central blob.
    const isCore = (t: Tier) => t === 'daena' || t === 'department' || t === 'agent'
    let minX = Infinity
    let maxX = -Infinity
    let minY = Infinity
    let maxY = -Infinity
    let framed = 0
    for (const n of nodes) {
      if (!isCore(n.__tier as Tier)) continue
      const r = n.__r as number
      if (n.x - r < minX) minX = n.x - r
      if (n.x + r > maxX) maxX = n.x + r
      if (n.y - r < minY) minY = n.y - r
      if (n.y + r > maxY) maxY = n.y + r
      framed++
    }
    if (!framed) {
      // Degenerate org (no core nodes): fall back to framing everything so the
      // view is never empty.
      for (const n of nodes) {
        const r = n.__r as number
        if (n.x - r < minX) minX = n.x - r
        if (n.x + r > maxX) maxX = n.x + r
        if (n.y - r < minY) minY = n.y - r
        if (n.y + r > maxY) maxY = n.y + r
      }
    }
    const bounds = nodes.length ? { minX, maxX, minY, maxY } : null

    return { nodes, links, neighborMap, colorById, childIds, bounds, bandBase, pulseEdges }
  }, [data])

  const { neighborMap, colorById } = built
  const graph = useMemo(() => ({ nodes: built.nodes, links: built.links }), [built])

  // Deterministic framing: centre on the layout bounding box and pick a zoom
  // that fits it with padding. This replaces zoomToFit(), which depends on the
  // force engine ticking -- with cooldownTicks=0 it fired before the canvas had
  // a real size, mis-framing the org into a corner. centerAt + zoom from the
  // precomputed bounds is timing-independent; the rAF retry covers the first
  // frame after a resize where canvas internals may not be ready yet.
  const fitView = useCallback(() => {
    const fg = fgRef.current
    const b = built.bounds
    if (!fg || !b || size.width <= 0 || size.height <= 0) return
    const PAD = 80
    const w = Math.max(b.maxX - b.minX, 1)
    const h = Math.max(b.maxY - b.minY, 1)
    const k = Math.min((size.width - 2 * PAD) / w, (size.height - 2 * PAD) / h)
    // force-graph runs a continuous rAF render loop (independent of the cooled
    // engine), so an instant zoom plus an animated centerAt both repaint on the
    // following frame and the picture lands at the correct fitted transform. No
    // manual refresh() is needed; the ref handle does not expose one anyway.
    fg.zoom(Math.max(k, 0.02), 0)
    fg.centerAt((b.minX + b.maxX) / 2, (b.minY + b.maxY) / 2, 280)
  }, [built.bounds, size.width, size.height])

  useEffect(() => {
    if (size.width <= 0 || !graph.nodes.length) return
    fitView()
    const raf = requestAnimationFrame(fitView)
    return () => cancelAnimationFrame(raf)
  }, [fitView, graph, size.width, size.height])

  // Camera controls. The deterministic layout is readable as a whole only at the
  // fitted zoom; agent/work labels stay hidden there by design (showing them all
  // is the "everything piled together" blob). These give a one-gesture path to a
  // readable scale instead: zoom in/out, refit, or frame a single core's cluster.
  const zoomBy = useCallback((factor: number) => {
    const fg = fgRef.current
    if (!fg) return
    const z = fg.zoom()
    fg.zoom(Math.max(0.02, Math.min(z * factor, 12)), 250)
  }, [])

  // Frame a core (Daena or a department) plus everything orbiting it, so its
  // agents/workstreams cross the label LOD threshold and its spoke to Daena reads
  // clearly. This is the "go close to one core" gesture the wide view can't give.
  const focusCluster = useCallback(
    (id: string) => {
      const fg = fgRef.current
      if (!fg || size.width <= 0 || size.height <= 0) return
      const byId = new Map(built.nodes.map((n) => [String(n.id), n]))
      const root = byId.get(id)
      if (!root) return
      const ids: string[] = [id]
      const queue: string[] = [id]
      while (queue.length) {
        const pid = queue.shift()!
        for (const c of built.childIds.get(pid) ?? []) {
          ids.push(c)
          queue.push(c)
        }
      }
      let minX = Infinity
      let maxX = -Infinity
      let minY = Infinity
      let maxY = -Infinity
      for (const nid of ids) {
        const n = byId.get(nid)
        if (!n) continue
        const r = (n.__r as number) + 16
        if (n.x - r < minX) minX = n.x - r
        if (n.x + r > maxX) maxX = n.x + r
        if (n.y - r < minY) minY = n.y - r
        if (n.y + r > maxY) maxY = n.y + r
      }
      if (!isFinite(minX)) return
      const PAD = 70
      // The detail panel opens on the right when a node is selected, so the
      // usable canvas is narrower; shrink the fit width and bias the centre left
      // by half the panel so the focused core lands in the visible area.
      const usableW = Math.max(size.width - 2 * PAD - DETAIL_PANEL_W, 160)
      const w = Math.max(maxX - minX, 1)
      const h = Math.max(maxY - minY, 1)
      const k = Math.min(usableW / w, (size.height - 2 * PAD) / h)
      const z = Math.max(0.05, Math.min(k, 6))
      const cx = (minX + maxX) / 2 + DETAIL_PANEL_W / 2 / z
      const cy = (minY + maxY) / 2
      fg.zoom(z, 600)
      fg.centerAt(cx, cy, 600)
    },
    [built, size.width, size.height],
  )

  // force-graph's continuous render loop repaints every frame, so focus-state
  // changes (hover / selection / search highlight) are picked up automatically
  // through the updated nodeCanvasObject / linkColor closures; no manual nudge.

  const focusId = hovered ?? selected
  const activeSet = focusId
    ? new Set<string>([focusId, ...(neighborMap.get(focusId) ?? [])])
    : null

  const dimFor = (id: string): number => {
    if (activeSet) return activeSet.has(id) ? 1 : 0.12
    if (highlightedIds.size) return highlightedIds.has(id) ? 1 : 0.2
    return 1
  }

  const linkColor = (l: any): string => {
    const s = edgeEnd(l.source)
    const t = edgeEnd(l.target)
    let base: string
    if (l.rel === 'contains' && s === ROOT_ID) base = GOV_GOLD
    else if (l.rel === 'embodies') base = hexA(GOV_GOLD, 0.7) // Daena -> her own faculty
    else if (l.rel === 'employs') base = colorById.get(s) ?? 'rgba(255,255,255,0.2)'
    else if (l.rel === 'owns' || l.rel === 'belongs_to')
      base = hexA(colorById.get(s) || colorById.get(t) || '#5b6470', 0.45)
    else base = 'rgba(255,255,255,0.06)'
    if (focusId) return s === focusId || t === focusId ? base : 'rgba(255,255,255,0.025)'
    return base
  }

  const linkWidth = (l: any): number => {
    const s = edgeEnd(l.source)
    const t = edgeEnd(l.target)
    let w: number
    if (l.rel === 'contains' && s === ROOT_ID) w = 5 // Daena -> department spokes
    else if (l.rel === 'embodies') w = 3 // Daena -> faculty spokes
    else if (l.rel === 'employs') w = 2.5 // department -> agent
    else w = 1
    if (focusId && (s === focusId || t === focusId)) w *= 2.2
    return w
  }

  return (
    <div ref={wrapRef} className="absolute inset-0">
      {size.width > 0 ? (
        <ForceGraph2D
          ref={fgRef}
          width={size.width}
          height={size.height}
          graphData={graph}
          backgroundColor={BACKGROUNDS.midnight}
          cooldownTicks={0}
          warmupTicks={0}
          d3VelocityDecay={1}
          enableNodeDrag={false}
          nodeRelSize={5}
          linkColor={linkColor}
          linkWidth={linkWidth}
          onNodeHover={(n: any) => setHovered(n ? String(n.id) : null)}
          onNodeClick={(n: any) => {
            const id = String(n.id)
            selectNode(id)
            // Clicking a core takes you "close" to it: frame its cluster so its
            // agents/workstreams become legible and its spokes read clearly.
            if (n.__tier === 'daena' || n.__tier === 'department') {
              requestAnimationFrame(() => focusCluster(id))
            }
          }}
          onBackgroundClick={() => selectNode(null)}
          onEngineStop={fitView}
          onRenderFramePre={(ctx: CanvasRenderingContext2D, scale: number) => {
            // Soft core glow behind Daena.
            const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, 540)
            glow.addColorStop(0, 'rgba(212, 168, 67, 0.10)')
            glow.addColorStop(1, 'rgba(212, 168, 67, 0)')
            ctx.fillStyle = glow
            ctx.beginPath()
            ctx.arc(0, 0, 540, 0, 2 * Math.PI)
            ctx.fill()
            // Faint orbit guides.
            ctx.lineWidth = 1 / scale
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)'
            for (const rr of ORBIT_RINGS) {
              ctx.beginPath()
              ctx.arc(0, 0, rr, 0, 2 * Math.PI)
              ctx.stroke()
            }
            // Resource-band boundary (anchored to the real cluster extent).
            ctx.strokeStyle = 'rgba(45, 212, 191, 0.05)'
            ctx.beginPath()
            ctx.arc(0, 0, built.bandBase - 40, 0, 2 * Math.PI)
            ctx.stroke()
          }}
          onRenderFramePost={(ctx: CanvasRenderingContext2D) => {
            // LIVE PROCESS LAYER: travel a glow along every structural dendrite so
            // the brain reads as ALIVE -- signal flowing core -> faculties ->
            // departments -> agents -> MCP synapses -- not a frozen diagram. Drawn
            // AFTER the links/nodes so the heads sit on top of their wire. Pure
            // function of performance.now(); the ForceGraph render loop already
            // runs every frame (cooled sim, continuous rAF), so this animates with
            // zero extra timers. ctx is in graph space here (same as onRenderFramePre).
            const pulses = built.pulseEdges
            if (!pulses.length) return
            const now = performance.now() / 1000
            ctx.save()
            // Additive blend so a head crossing a node or another head BRIGHTENS
            // rather than muddies -- the "synapse firing" look.
            ctx.globalCompositeOperation = 'lighter'
            for (let i = 0; i < pulses.length; i++) {
              const e = pulses[i]
              // Honour the focus lens: when a node is hovered/selected, only its
              // own dendrites keep a live pulse (mirrors linkColor's de-emphasis of
              // non-incident edges), so inspecting a cluster stays legible.
              if (focusId && e.source !== focusId && e.target !== focusId) continue
              const hot = e.hot
              // Hot (genuinely mid-work) dendrites pulse brighter, faster, denser.
              const speed = hot ? 0.6 : 0.22
              const headR = hot ? 4.2 : 2.8
              const headAlpha = hot ? 0.9 : 0.42
              // More travelling heads on longer spokes so a long wire is not one
              // lonely dot; a hot wire carries one extra.
              const baseCount = Math.min(3, Math.max(1, Math.round(e.len / 260)))
              const count = hot ? baseCount + 1 : baseCount
              const dx = e.x2 - e.x1
              const dy = e.y2 - e.y1
              for (let k = 0; k < count; k++) {
                const u = (now * speed + e.phase + k / count) % 1
                const px = e.x1 + dx * u
                const py = e.y1 + dy * u
                const g = ctx.createRadialGradient(px, py, 0, px, py, headR)
                g.addColorStop(0, hexA(e.color, headAlpha))
                g.addColorStop(1, hexA(e.color, 0))
                ctx.fillStyle = g
                ctx.beginPath()
                ctx.arc(px, py, headR, 0, 2 * Math.PI)
                ctx.fill()
              }
            }
            ctx.restore()
          }}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
            const id = String(node.id)
            const tier: Tier = node.__tier
            const color: string = node.__color
            const r: number = node.__r
            const isSel = id === selected
            const isHover = id === hovered
            const isHi = highlightedIds.has(id)
            const status = String(node.status ?? '').toLowerCase()
            const sig = govSignal(node)
            const forced =
              isSel || isHover || isHi || (activeSet?.has(id) ?? false) || (sig?.force ?? false)
            // Focused / selected / matched / live-governance nodes never fade;
            // everything else follows the wide-zoom level-of-detail curve.
            // Settled work recedes (0.5) so attention rides what is still live.
            const settledDim = !forced && SETTLED_STATUS.has(status) ? 0.5 : 1
            ctx.globalAlpha = dimFor(id) * (forced ? 1 : lodAlpha(tier, scale)) * settledDim

            // LIVE PROCESS LAYER: a node genuinely mid-work emits an expanding
            // "working now" ring in its own colour -- the single brightest live
            // tell on the brain. Gated on WORKING_STATUS, which the grounded
            // fallback (every node 'active') never matches, so the offline
            // architecture stays calm and ONLY real telemetry fires this ring
            // (Rule 17). Deterministic per-node phase (from the pinned position)
            // keeps the rings out of lockstep without a timer or stored state.
            if (WORKING_STATUS.has(status)) {
              const phase = (((node.x * 12.9898 + node.y * 78.233) % 1) + 1) % 1
              const cycle = (performance.now() / 1400 + phase) % 1
              const ringR = r + (3 + 13 * cycle) / scale
              const prevA = ctx.globalAlpha
              ctx.globalAlpha = prevA * (1 - cycle) * 0.7
              ctx.strokeStyle = color
              ctx.lineWidth = 2 / scale
              ctx.beginPath()
              ctx.arc(node.x, node.y, ringR, 0, 2 * Math.PI)
              ctx.stroke()
              ctx.globalAlpha = prevA
            }

            // Governance glow halo, painted UNDER the node so the smallest /
            // most-faded execution nodes (where tier 3+ lives) cannot hide the moat.
            if (sig?.glow) {
              const gr = Math.max(r * 3, 16)
              const halo = ctx.createRadialGradient(node.x, node.y, r * 0.5, node.x, node.y, gr)
              halo.addColorStop(0, hexA(sig.ring, 0.5))
              halo.addColorStop(1, hexA(sig.ring, 0))
              ctx.fillStyle = halo
              ctx.beginPath()
              ctx.arc(node.x, node.y, gr, 0, 2 * Math.PI)
              ctx.fill()
            }

            if (tier === 'daena') {
              const g = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r * 2.4)
              g.addColorStop(0, 'rgba(212, 168, 67, 0.55)')
              g.addColorStop(1, 'rgba(212, 168, 67, 0)')
              ctx.fillStyle = g
              ctx.beginPath()
              ctx.arc(node.x, node.y, r * 2.4, 0, 2 * Math.PI)
              ctx.fill()
              ctx.fillStyle = GOV_GOLD
              ctx.beginPath()
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
              ctx.fill()
              ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)'
              ctx.lineWidth = 2 / scale
              strokeHexagon(ctx, node.x, node.y, r * 1.25)
            } else if (tier === 'faculty') {
              // Daena's own faculty: a small gold gem with a faint gold hex
              // halo so it reads as part of the core, distinct from a department.
              ctx.fillStyle = color
              ctx.beginPath()
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
              ctx.fill()
              const prev = ctx.globalAlpha
              ctx.globalAlpha = prev * 0.6
              ctx.strokeStyle = GOV_GOLD
              ctx.lineWidth = 1.25 / scale
              strokeHexagon(ctx, node.x, node.y, r * 1.45)
              ctx.globalAlpha = prev
            } else if (tier === 'department') {
              ctx.fillStyle = color
              ctx.beginPath()
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
              ctx.fill()
              const prev = ctx.globalAlpha
              ctx.globalAlpha = prev * 0.55
              ctx.strokeStyle = color
              ctx.lineWidth = 1.5 / scale
              strokeHexagon(ctx, node.x, node.y, r * 1.5)
              ctx.globalAlpha = prev
            } else if (tier === 'work') {
              ctx.strokeStyle = color
              ctx.lineWidth = 1.6 / scale
              ctx.beginPath()
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
              ctx.stroke()
            } else {
              ctx.fillStyle = color
              ctx.beginPath()
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
              ctx.fill()
            }

            // Crisp governance ring on top of the node body (survives wide zoom).
            if (sig) {
              ctx.strokeStyle = sig.ring
              ctx.lineWidth = (sig.force ? 2.4 : 1.6) / scale
              if (sig.dashed) ctx.setLineDash([4 / scale, 3 / scale])
              ctx.beginPath()
              ctx.arc(node.x, node.y, r + 2 / scale, 0, 2 * Math.PI)
              ctx.stroke()
              if (sig.dashed) ctx.setLineDash([])
            }

            if (isSel) {
              ctx.strokeStyle = GOV_TEAL
              ctx.lineWidth = 2.5 / scale
              ctx.beginPath()
              ctx.arc(node.x, node.y, r + 3 / scale, 0, 2 * Math.PI)
              ctx.stroke()
            } else if (isHover) {
              ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)'
              ctx.lineWidth = 1.8 / scale
              ctx.beginPath()
              ctx.arc(node.x, node.y, r + 3 / scale, 0, 2 * Math.PI)
              ctx.stroke()
            }
            // PR-4 ragx-highlight ring. Distinct width so a node that is both
            // selected and matched still reads as both.
            if (isHi) {
              ctx.strokeStyle = GOV_TEAL
              ctx.lineWidth = 3 / scale
              ctx.beginPath()
              ctx.arc(node.x, node.y, r + 5 / scale, 0, 2 * Math.PI)
              ctx.stroke()
            }

            if (labelVisible(tier, scale, forced)) {
              const label = String(node.label ?? '')
              if (label) {
                const fs =
                  (tier === 'daena'
                    ? 15
                    : tier === 'department'
                      ? 13
                      : tier === 'faculty'
                        ? 11
                        : tier === 'agent'
                          ? 11
                          : 10) / scale
                ctx.font = `${fs}px Inter, sans-serif`
                ctx.textBaseline = 'middle'
                const tw = ctx.measureText(label).width
                const pad = 3 / scale
                const lx = node.x + r + 4 / scale
                const ly = node.y
                ctx.fillStyle = 'rgba(2, 4, 8, 0.72)'
                ctx.fillRect(lx - pad, ly - fs / 2 - pad, tw + 2 * pad, fs + 2 * pad)
                ctx.fillStyle =
                  tier === 'daena'
                    ? '#f5e6c0'
                    : tier === 'faculty'
                      ? '#f0dca8'
                      : tier === 'department'
                        ? '#e8edf2'
                        : '#c9d1d9'
                ctx.fillText(label, lx, ly)
              }
            }
            ctx.globalAlpha = 1
          }}
          nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
            const r = Math.max(node.__r ?? R_LEAF, 7)
            ctx.beginPath()
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
            ctx.fillStyle = color
            ctx.fill()
          }}
        />
      ) : null}

      {size.width > 0 ? (
        <div className="absolute bottom-4 left-4 z-20 flex flex-col gap-1.5">
          <button
            onClick={() => zoomBy(1.4)}
            className="rounded-md border border-white/10 bg-black/70 p-2 text-white/70 backdrop-blur transition-colors hover:border-white/25 hover:text-white"
            title="Zoom in"
            aria-label="Zoom in"
          >
            <ZoomIn size={16} />
          </button>
          <button
            onClick={() => zoomBy(1 / 1.4)}
            className="rounded-md border border-white/10 bg-black/70 p-2 text-white/70 backdrop-blur transition-colors hover:border-white/25 hover:text-white"
            title="Zoom out"
            aria-label="Zoom out"
          >
            <ZoomOut size={16} />
          </button>
          <button
            onClick={() => fitView()}
            className="rounded-md border border-white/10 bg-black/70 p-2 text-white/70 backdrop-blur transition-colors hover:border-white/25 hover:text-white"
            title="Fit whole org"
            aria-label="Fit whole org"
          >
            <Maximize2 size={16} />
          </button>
          <button
            onClick={() => selected && focusCluster(selected)}
            disabled={!selected}
            className="rounded-md border border-white/10 bg-black/70 p-2 text-white/70 backdrop-blur transition-colors hover:border-white/25 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            title="Focus selected cluster"
            aria-label="Focus selected cluster"
          >
            <Crosshair size={16} />
          </button>
        </div>
      ) : null}

      {/* Governance legend -- decodes the overlay. Placed left of the zoom column
          so it clears the 360px detail panel that opens on the right. */}
      {size.width > 0 ? (
        <div className="absolute bottom-4 left-16 z-20 rounded-md border border-white/10 bg-black/70 px-2.5 py-2 text-[10px] leading-tight text-white/55 backdrop-blur">
          <div className="mb-1 font-medium uppercase tracking-wide text-white/70">Governance</div>
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: GOV_APPROVAL }} />
              <span>Approval / failed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: GOV_BLOCKER }} />
              <span>Blocked</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: GOV_NOTIFY }} />
              <span>Notified</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-white/25" />
              <span>Settled</span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

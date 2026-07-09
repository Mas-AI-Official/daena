import { create } from 'zustand'
import {
  fetchGraph,
  fetchNodeDetail as fetchNodeDetailApi,
  searchGraph,
  type GraphData,
  type GraphSearchCitation,
  type NodeDetail,
} from '@/lib/graphApi'
import { streamWithRetry } from '@/lib/sse'
import { buildGroundedBrain } from '@/components/missionControl/groundedBrain'

// ── Realtime connection singletons (module-level, NOT reactive state) ──
// The brain holds at most ONE SSE connection per app. Keeping the
// AbortController and the coalescing timer out of the store avoids
// needless re-renders (no component selects them) and makes connect()
// idempotent under React 18 StrictMode's double-invoke.
let realtimeController: AbortController | null = null
let refreshTimer: ReturnType<typeof setTimeout> | null = null

// Monotonic id for Brain activity pulses (see pulseNode). Module-level so it
// never resets mid-session; BrainCanvas drains by this seq, so a bounded buffer
// plus a briefly-slow consumer can never double-fire the same comet.
let pulseSeq = 0
// The pulse queue is a fire-and-forget animation cue, not a log: the canvas
// consumes within a frame or two, so anything older than a small tail is stale.
const PULSE_BUFFER = 32

/**
 * Order-independent fingerprint of a projection used to gate the background poll
 * (refresh): id:status per node plus node/edge counts. Excludes stats.generated_at
 * (which changes on every projection) so an unchanged graph yields an unchanged
 * signature -- a re-poll that changed nothing must NOT churn the layout, because
 * BrainCanvas re-fits the camera whenever the layout ref changes. The poll only
 * swaps data when a node's status actually flipped or a node/edge appeared.
 */
function graphSignature(d: GraphData | null): string {
  if (!d || !d.nodes) return ''
  const parts = d.nodes.map((n) => `${n.id}:${n.status ?? ''}`)
  parts.sort()
  return `${d.nodes.length}|${d.edges?.length ?? 0}|${parts.join(',')}`
}

/**
 * One Brain activity cue: "node <nodeId> just moved because <reason>". Enqueued
 * by pulseNode when a typed graph event names a node the CURRENT projection
 * actually contains; drained by BrainCanvas into exactly one comet along an edge
 * incident to that node. Purely decorative over the SAME GET /graph re-pull -- it
 * carries no projection data, so the thin-doorbell contract still holds.
 */
export interface GraphPulse {
  seq: number
  nodeId: string
  reason: string
}

/**
 * Extract the change detail from a graph SSE envelope, or null when there is
 * nothing to pulse (heartbeat ping, malformed frame, or an older backend whose
 * doorbell did not name a node). The route dumps the WHOLE SSEChannel envelope
 * as the data line, so the typed detail lives at e.data.data: { reason, node_id }
 * -- NOT at e.data.node_id. Kept pure and exported so the SSE router is
 * unit-testable without standing up the stream.
 */
export function parseGraphEvent(
  e: { type: string; data: unknown },
): { nodeId: string; reason: string } | null {
  if (e.type === 'ping') return null
  const detail = (e.data as { data?: unknown } | null)?.data
  if (!detail || typeof detail !== 'object') return null
  const { node_id: nodeId, reason } = detail as { node_id?: unknown; reason?: unknown }
  if (typeof nodeId !== 'string' || !nodeId) return null
  return { nodeId, reason: typeof reason === 'string' ? reason : 'graph.changed' }
}

interface GraphState {
  data: GraphData | null
  loading: boolean
  error: string | null
  // When /graph is unreachable we fall back to a grounded ARCHITECTURE graph
  // (groundedBrain) so the Brain is still legible. This flag tells the UI to
  // render the canvas under an honest "representative architecture, not live
  // telemetry" banner instead of a blocking error (Rule 17). Cleared the moment
  // a live projection loads.
  usingFallback: boolean
  fallbackNotice: string | null
  // Wall-clock ms of the last SUCCESSFUL projection fetch (load or refresh).
  // Drives the honest freshness pill: a climbing "updated Ns ago" truthfully
  // signals a stalled poll; null until the first load resolves.
  lastUpdated: number | null
  // True ONLY while a graph SSE stream is actively connected (Rule 17): the
  // transport is open AND the server is reachable. Flips false the instant we
  // drop into reconnect backoff or the stream ends, so LiveStatusPill never
  // claims "Live" while we are really back on the polling fallback.
  live: boolean
  // Brain activity pulses: a bounded, monotonic queue of "this node just moved"
  // cues the SSE router enqueues and BrainCanvas drains into event-driven comets.
  // Reactive so the store stays the single source, but NO component selects it
  // (the canvas reads it via a vanilla subscribe into a ref), so appends never
  // trigger a React re-render.
  pulses: GraphPulse[]
  selectedNodeId: string | null
  // Brain lens: 'graph' = force-directed canvas, 'list' = sortable triage table.
  // Both lenses read the SAME data / kindFilters / highlightedIds so the active
  // node subset stays invariant when you toggle (no state schism between modes).
  graphViewMode: 'graph' | 'list'
  kindFilters: Set<string>
  // PR-4 ragx-highlight state
  highlightedIds: Set<string>
  searchCitations: GraphSearchCitation[]
  searching: boolean
  searchOffline: boolean
  // PR-5 node-detail state (Activity / AI Access / AI Context tabs)
  nodeDetail: NodeDetail | null
  nodeDetailLoading: boolean
  nodeDetailError: string | null
  load: () => Promise<void>
  // Silent background re-poll (no loading chip, no fallback drop on a blip).
  refresh: () => Promise<void>
  // Open the always-live SSE stream (idempotent). Each push hint triggers a
  // coalesced refresh() so the canvas updates sub-second on a real change,
  // while the change-gate still suppresses no-op churn. Degrades cleanly to
  // the adaptive poll whenever the stream is unavailable.
  connectRealtime: () => void
  // Tear the stream down (component unmount); flips `live` false.
  disconnectRealtime: () => void
  // Enqueue one activity pulse for a node -- but only if the CURRENT projection
  // actually contains it (Rule 17: never paint activity on a node we cannot
  // show). Called by the SSE router with the node_id a typed event names.
  pulseNode: (nodeId: string, reason: string) => void
  selectNode: (id: string | null) => void
  setGraphViewMode: (mode: 'graph' | 'list') => void
  toggleKind: (k: string) => void
  semanticSearch: (q: string) => Promise<void>
  clearSearch: () => void
  fetchNodeDetail: (id: string) => Promise<void>
}

export const useGraphStore = create<GraphState>((set, get) => ({
  data: null,
  loading: false,
  error: null,
  usingFallback: false,
  fallbackNotice: null,
  lastUpdated: null,
  live: false,
  pulses: [],
  selectedNodeId: null,
  graphViewMode: 'graph',
  kindFilters: new Set(),
  highlightedIds: new Set(),
  searchCitations: [],
  searching: false,
  searchOffline: false,
  nodeDetail: null,
  nodeDetailLoading: false,
  nodeDetailError: null,
  load: async () => {
    set({ loading: true, error: null })
    try {
      const filters = get().kindFilters
      const kinds = filters.size > 0 ? Array.from(filters).join(',') : undefined
      const data = await fetchGraph(kinds ? { kinds } : undefined)
      // Live projection wins: clear any prior fallback so the banner disappears.
      set({ data, loading: false, usingFallback: false, fallbackNotice: null, error: null, lastUpdated: Date.now() })
    } catch (e) {
      // Backend unreachable: paint the grounded ARCHITECTURE graph instead of a
      // dead red error, and tell the user plainly that it is not live telemetry
      // (Rule 17). `error` stays null so the canvas renders; the honest signal
      // travels via usingFallback/fallbackNotice.
      const reason = e instanceof Error ? e.message : 'Failed to load graph'
      set({
        data: buildGroundedBrain(),
        usingFallback: true,
        fallbackNotice: `Showing Daena's architecture (10 departments and their agent limbs). Live org telemetry is unavailable -- the graph service did not respond (${reason}).`,
        error: null,
        loading: false,
      })
    }
  },
  /**
   * Silent background re-poll for the live Brain. Unlike load() it never toggles
   * `loading` (so the "Loading graph..." chip does not flash every cycle) and on
   * a transient failure it KEEPS the current projection on screen instead of
   * dropping to the grounded fallback -- a blip should not yank a live brain back
   * to architecture. Honest (Rule 17): it only swaps in a new projection when the
   * graph ACTUALLY changed (a node's status flipped, a node/edge appeared), so the
   * camera/zoom the user set is never reset by an unchanged re-fit; an identical
   * poll just stamps lastUpdated. A failed poll stamps nothing, so the freshness
   * pill's "updated Ns ago" climbs and honestly signals the gap.
   */
  refresh: async () => {
    try {
      const filters = get().kindFilters
      const kinds = filters.size > 0 ? Array.from(filters).join(',') : undefined
      const data = await fetchGraph(kinds ? { kinds } : undefined)
      const changed = graphSignature(data) !== graphSignature(get().data)
      if (changed) {
        set({ data, usingFallback: false, fallbackNotice: null, error: null, lastUpdated: Date.now() })
      } else {
        set({ lastUpdated: Date.now() })
      }
    } catch {
      // Keep the current screen; the next successful poll refreshes it.
    }
  },
  /**
   * Always-live brain transport. Opens ONE authenticated SSE stream to
   * GET /api/v1/graph/stream (fetch + ReadableStream, because native
   * EventSource cannot attach the Bearer header and we never put a token in a
   * URL). The stream is a THIN NOTIFICATION channel: each push carries only a
   * "graph changed" signal, and we respond by calling refresh() -- which keeps
   * /graph as the single projection source and reuses the signature change-gate
   * so a no-op never churns the layout. Bursts are coalesced behind a 250ms
   * timer so a flurry of backend events triggers exactly one refetch.
   *
   * HONEST (Rule 17 / ADR-001): `live` flips true only at the real transport
   * connect (onOpen) and false the instant we drop into reconnect backoff or
   * the stream ends -- LiveStatusPill therefore says "Live" ONLY while a stream
   * is genuinely open. If /stream is unavailable (older backend, route not yet
   * deployed) the retry loop simply keeps trying every <=15s while `live` stays
   * false and the adaptive poll in MissionControlPage carries updates -- a
   * clean, zero-regression degrade to today's behavior.
   *
   * Idempotent: a live controller short-circuits the call, so React 18
   * StrictMode's double-mount opens exactly one stream.
   */
  connectRealtime: () => {
    if (realtimeController && !realtimeController.signal.aborted) return
    const controller = new AbortController()
    realtimeController = controller
    // Coalesce a burst of change hints into a single refresh.
    const scheduleRefresh = () => {
      if (refreshTimer) return
      refreshTimer = setTimeout(() => {
        refreshTimer = null
        void get().refresh()
      }, 250)
    }
    void streamWithRetry({
      open: () =>
        fetch('/api/v1/graph/stream', {
          headers: {
            Accept: 'text/event-stream',
            Authorization: `Bearer ${localStorage.getItem('daena_token') ?? ''}`,
          },
          signal: controller.signal,
        }),
      onOpen: () => {
        // Transport is genuinely open: honest "Live" + pull the freshest
        // projection immediately so a just-connected brain is never stale.
        set({ live: true })
        scheduleRefresh()
      },
      onEvent: (e) => {
        // Drop heartbeat pings (they carry no change); any real event hints a
        // possible projection change -> coalesced refetch decides if it moved.
        if (e.type === 'ping') return
        // A typed doorbell (task_status_changed / workstream_*) names the exact
        // node that moved: fire a single Brain comet on it NOW, before the
        // debounced refetch, so the pulse feels instant. The refetch below still
        // runs and remains the sole source of projection truth -- the comet is
        // pure decoration over the same re-pull, so the thin-doorbell contract
        // holds even for an older backend that names no node (pulse is skipped).
        const detail = parseGraphEvent(e)
        if (detail) get().pulseNode(detail.nodeId, detail.reason)
        scheduleRefresh()
      },
      onReconnecting: () => {
        // Dropped to backoff: stop claiming "Live" (poll fallback resumes).
        set({ live: false })
      },
      signal: controller.signal,
      // Effectively infinite: the brain should keep trying to reconnect for the
      // life of the page. The backoff caps at 15s so it is never a hot loop.
      maxRetries: Number.MAX_SAFE_INTEGER,
      // The /stream doorbell is persistent: a clean EOF means the backend
      // closed the body (graceful restart) or a proxy recycled the idle
      // connection -- reconnect instead of silently dropping to polling.
      // Without this the brain never returns to "Live" after a restart.
      reconnectOnClose: true,
    })
      .catch(() => {
        // Aborted on unmount, or terminal transport failure -> degrade to poll.
      })
      .finally(() => {
        if (realtimeController === controller) realtimeController = null
        set({ live: false })
      })
  },
  disconnectRealtime: () => {
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
    realtimeController?.abort()
    realtimeController = null
    set({ live: false })
  },
  pulseNode: (nodeId, reason) => {
    // Rule 17: only paint activity on a node the live projection actually shows.
    // A doorbell can name a task/workstream the current /graph slice does not
    // contain (kind-filtered out, or not yet in this poll); silently skip it
    // rather than emit a comet pointing at nothing.
    const nodes = get().data?.nodes
    if (!nodes || !nodes.some((n) => n.id === nodeId)) return
    // Monotonic seq lets a briefly-slow canvas consumer drain by id and never
    // double-fire; the bounded slice keeps this a fire-and-forget cue, not a log.
    const pulse: GraphPulse = { seq: ++pulseSeq, nodeId, reason }
    set({ pulses: [...get().pulses, pulse].slice(-PULSE_BUFFER) })
  },
  selectNode: (id) =>
    set(
      id === null
        ? { selectedNodeId: null, nodeDetail: null, nodeDetailError: null }
        : { selectedNodeId: id },
    ),
  setGraphViewMode: (mode) => set({ graphViewMode: mode }),
  toggleKind: (k) => {
    const next = new Set(get().kindFilters)
    if (next.has(k)) {
      next.delete(k)
    } else {
      next.add(k)
    }
    set({ kindFilters: next })
    void get().load()
  },
  /**
   * PR-4: ask the backend for ragx-highlight matches and apply them to the
   * canvas. On a network/server error we surface `searchOffline=true` (Rule
   * 17) rather than swallowing the failure into an empty highlight set --
   * the user must see why the canvas did not change.
   */
  semanticSearch: async (q) => {
    const trimmed = q.trim()
    if (!trimmed) {
      set({ highlightedIds: new Set(), searchCitations: [], searchOffline: false })
      return
    }
    set({ searching: true })
    try {
      const resp = await searchGraph(trimmed)
      set({
        highlightedIds: new Set(resp.matched_node_ids),
        searchCitations: resp.citations,
        searchOffline: !resp.available,
        searching: false,
      })
    } catch {
      set({
        highlightedIds: new Set(),
        searchCitations: [],
        searchOffline: true,
        searching: false,
      })
    }
  },
  clearSearch: () =>
    set({
      highlightedIds: new Set(),
      searchCitations: [],
      searchOffline: false,
    }),
  /**
   * PR-5: load the detail payload (neighbors + Activity/AI Access/AI Context)
   * for a node. Race guard: a fast click sequence can leave responses arriving
   * out of order, so we only apply a result if the node is still selected
   * (`selectedNodeId === id`). A 404/network error surfaces honestly via
   * `nodeDetailError` rather than leaving a stale panel (Rule 17).
   */
  fetchNodeDetail: async (id) => {
    set({ nodeDetailLoading: true, nodeDetailError: null })
    try {
      const detail = await fetchNodeDetailApi(id)
      if (get().selectedNodeId !== id) return
      set({ nodeDetail: detail, nodeDetailLoading: false })
    } catch (e) {
      if (get().selectedNodeId !== id) return
      set({
        nodeDetail: null,
        nodeDetailError: e instanceof Error ? e.message : 'Failed to load node detail',
        nodeDetailLoading: false,
      })
    }
  },
}))

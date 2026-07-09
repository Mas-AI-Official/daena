import { useEffect, useState, lazy, Suspense } from 'react'
import { MessageSquare, Network, List, LayoutDashboard, BarChart3, X } from 'lucide-react'
import { BACKGROUNDS } from '@/styles/designTokens'
// Dashboard folded into the Brain cockpit 2026-06-25 (founder go-ahead): the
// Control Room's unique panels (KPI tiles, SunflowerHive, System Status,
// Governance Pulse, Quick Actions, Recent Activity) live here as an "Overview"
// overlay. Lazy so the dashboard's data burst + bundle load only on open,
// keeping the default canvas view lean. /dashboard now redirects to /brain.
const DashboardPage = lazy(() => import('@/components/brain/DashboardPage'))
// Analytics folded into the Brain cockpit 2026-07-02 (FM-5): the usage/cost/
// governance metrics that lived at /analytics are a second read-only lens on
// the same org the brain graphs, so they belong here as an "Analytics" overlay
// rather than a peer route. Lazy so its /analytics/dashboard burst fires only
// on open. /analytics now redirects to /brain.
const AnalyticsPage = lazy(() => import('@/components/brain/AnalyticsPage'))
import { useGraphStore } from '@/stores/graphStore'
import BrainCanvas from '@/components/missionControl/BrainCanvas'
import { countWorking } from '@/components/missionControl/workingStatus'
import GraphListView from '@/components/missionControl/GraphListView'
import NodeDetailPanel from '@/components/missionControl/NodeDetailPanel'
import FilterBar from '@/components/missionControl/FilterBar'
import StatsRibbon from '@/components/missionControl/StatsRibbon'
import GraphSearchBar from '@/components/missionControl/GraphSearchBar'
import SearchCitationsPanel from '@/components/missionControl/SearchCitationsPanel'
import Legend from '@/components/missionControl/Legend'
import ChatDrawer from '@/components/missionControl/ChatDrawer'
import LiveStatusPill from '@/components/missionControl/LiveStatusPill'

/**
 * Mission Control: a read-only force-graph over Daena's live org projection
 * (root -> departments -> agents -> projects / workstreams / mcp servers /
 * skills). Lazy-loaded, so this must default-export.
 */
export default function MissionControlPage() {
  const load = useGraphStore((s) => s.load)
  const refresh = useGraphStore((s) => s.refresh)
  const connectRealtime = useGraphStore((s) => s.connectRealtime)
  const disconnectRealtime = useGraphStore((s) => s.disconnectRealtime)
  const live = useGraphStore((s) => s.live)
  const loading = useGraphStore((s) => s.loading)
  const error = useGraphStore((s) => s.error)
  const usingFallback = useGraphStore((s) => s.usingFallback)
  const fallbackNotice = useGraphStore((s) => s.fallbackNotice)
  const viewMode = useGraphStore((s) => s.graphViewMode)
  const setViewMode = useGraphStore((s) => s.setGraphViewMode)
  // Cadence driver: true the moment any node is in WORKING_STATUS (same source
  // the canvas ring + StatsRibbon count use). A boolean keeps the poll interval
  // from re-arming on every count tick -- it only flips when work starts/stops.
  const hasWorking = useGraphStore((s) => countWorking(s.data) > 0)
  const [chatOpen, setChatOpen] = useState(false)
  const [overviewOpen, setOverviewOpen] = useState(false)
  const [analyticsOpen, setAnalyticsOpen] = useState(false)

  useEffect(() => {
    void load()
  }, [load])

  // Always-live transport: open ONE authenticated SSE stream for the lifetime
  // of the page; every backend "graph changed" push triggers a coalesced
  // refetch so the brain updates sub-second on a real change. If /stream is
  // unavailable (older backend) the store's retry loop keeps trying while the
  // adaptive poll below carries updates -- a clean, zero-regression degrade.
  useEffect(() => {
    connectRealtime()
    return () => disconnectRealtime()
  }, [connectRealtime, disconnectRealtime])

  // Poll: primary update path until the SSE stream connects, then a SAFETY NET.
  // When `live`, the stream drives refreshes on real change, so we slow the poll
  // to a 15s backstop (catches anything a dropped push missed) instead of
  // hammering /graph. When NOT live, fall back to the adaptive cadence: 2s while
  // something is working so its ring animates smoothly, 5s when idle. refresh()
  // never flashes the load chip and is signature-gated, so an unchanged graph
  // causes no layout churn.
  useEffect(() => {
    const intervalMs = live ? 15000 : hasWorking ? 2000 : 5000
    const id = setInterval(() => {
      void refresh()
    }, intervalMs)
    return () => clearInterval(id)
  }, [refresh, hasWorking, live])

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: BACKGROUNDS.midnight }}>
      <div className="flex items-center justify-between gap-4 border-b border-white/5 px-6 py-3">
        <StatsRibbon />
        <div className="flex items-center gap-4">
          <GraphSearchBar />
          <FilterBar />
          {/* Overview: opens the folded-in Control Room (KPI tiles, SunflowerHive,
              System Status, Governance Pulse, Quick Actions, Recent Activity) as an
              overlay over the canvas. Lazy-mounted, so its data burst fires only on
              open. This is the consolidation of the old /dashboard page. */}
          <button
            onClick={() => setOverviewOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/70 transition-colors hover:border-white/20 hover:text-white"
            title="Overview: KPIs, system status, governance pulse, quick actions"
          >
            <LayoutDashboard size={15} /> Overview
          </button>
          {/* Analytics: opens the folded-in usage/cost/governance metrics (the old
              /analytics page) as an overlay. Lazy-mounted, so its dashboard burst
              fires only on open. */}
          <button
            onClick={() => setAnalyticsOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/70 transition-colors hover:border-white/20 hover:text-white"
            title="Analytics: usage, cost trend, department activity, governance metrics"
          >
            <BarChart3 size={15} /> Analytics
          </button>
          {/* Dual-mode Brain: physics canvas for structure, list for scan/sort
              triage. Both lenses read the same store, so the toggle never
              changes the active node subset. */}
          <div className="flex items-center gap-0.5 rounded-lg border border-white/10 p-0.5">
            <button
              onClick={() => setViewMode('graph')}
              className={
                viewMode === 'graph'
                  ? 'rounded-md bg-white/10 p-1.5 text-white transition-colors'
                  : 'rounded-md p-1.5 text-white/45 transition-colors hover:text-white'
              }
              title="Graph view"
              aria-pressed={viewMode === 'graph'}
            >
              <Network size={15} />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={
                viewMode === 'list'
                  ? 'rounded-md bg-white/10 p-1.5 text-white transition-colors'
                  : 'rounded-md p-1.5 text-white/45 transition-colors hover:text-white'
              }
              title="List view"
              aria-pressed={viewMode === 'list'}
            >
              <List size={15} />
            </button>
          </div>
        </div>
      </div>
      <div className="relative flex-1 overflow-hidden">
        {error ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-red-300">
            {error}
          </div>
        ) : viewMode === 'list' ? (
          <GraphListView />
        ) : (
          <BrainCanvas />
        )}
        {loading ? (
          <div className="absolute left-4 top-4 rounded-md bg-black/60 px-3 py-1 text-xs text-white/70">
            Loading graph...
          </div>
        ) : null}
        <LiveStatusPill />
        {/* Honest, non-blocking degrade banner (Rule 17): the canvas below is the
            grounded ARCHITECTURE, not live org telemetry. Clears the instant a
            live /graph projection loads. */}
        {usingFallback && !loading ? (
          <div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-center px-6">
            <div className="pointer-events-auto max-w-2xl rounded-lg border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-center text-xs leading-relaxed text-amber-200/90 backdrop-blur">
              {fallbackNotice ?? "Showing Daena's architecture -- live telemetry unavailable."}
            </div>
          </div>
        ) : null}
        {!loading && !error && viewMode === 'graph' ? <Legend /> : null}
        {!error ? <SearchCitationsPanel /> : null}
        <NodeDetailPanel />
        {!chatOpen ? (
          <button
            onClick={() => setChatOpen(true)}
            className="absolute bottom-4 right-4 z-20 flex items-center gap-2 rounded-full border border-white/10 bg-black/70 px-4 py-2 text-sm text-white/80 backdrop-blur transition-colors hover:border-white/20 hover:text-white"
            title="Open Mission Control chat"
          >
            <MessageSquare size={16} /> Chat
          </button>
        ) : null}
        <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
        {/* Overview overlay: the folded-in Control Room. Conditionally mounted so
            DashboardPage's 9-call data burst only fires on open (its 30s module
            cache absorbs repeat opens). DashboardPage's root is h-full
            overflow-y-auto, so it fills + scrolls inside this flex column. */}
        {overviewOpen ? (
          <div
            className="absolute inset-0 z-40 flex flex-col"
            style={{ backgroundColor: BACKGROUNDS.midnight }}
          >
            <div className="flex shrink-0 items-center justify-between border-b border-white/5 px-6 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-white/80">
                <LayoutDashboard size={16} /> Overview
              </div>
              <button
                onClick={() => setOverviewOpen(false)}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/70 transition-colors hover:border-white/20 hover:text-white"
                title="Back to the brain"
              >
                <X size={15} /> Close
              </button>
            </div>
            <div className="relative flex-1 overflow-hidden">
              <Suspense
                fallback={
                  <div className="flex h-full items-center justify-center text-sm text-white/50">
                    Loading overview...
                  </div>
                }
              >
                <DashboardPage />
              </Suspense>
            </div>
          </div>
        ) : null}
        {/* Analytics overlay: the folded-in usage/cost/governance metrics.
            Conditionally mounted so AnalyticsPage's /analytics/dashboard fetch
            only fires on open. AnalyticsPage's root is h-full overflow-y-auto,
            so it fills + scrolls inside this flex column. */}
        {analyticsOpen ? (
          <div
            className="absolute inset-0 z-40 flex flex-col"
            style={{ backgroundColor: BACKGROUNDS.midnight }}
          >
            <div className="flex shrink-0 items-center justify-between border-b border-white/5 px-6 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-white/80">
                <BarChart3 size={16} /> Analytics
              </div>
              <button
                onClick={() => setAnalyticsOpen(false)}
                className="flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs text-white/70 transition-colors hover:border-white/20 hover:text-white"
                title="Back to the brain"
              >
                <X size={15} /> Close
              </button>
            </div>
            <div className="relative flex-1 overflow-hidden">
              <Suspense
                fallback={
                  <div className="flex h-full items-center justify-center text-sm text-white/50">
                    Loading analytics...
                  </div>
                }
              >
                <AnalyticsPage />
              </Suspense>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

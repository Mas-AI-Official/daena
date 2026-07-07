import { useGraphStore } from '@/stores/graphStore'
import { countWorking } from './workingStatus'

export default function StatsRibbon() {
  const data = useGraphStore((s) => s.data)
  // Same WORKING_STATUS source the canvas ring uses, so this number can never
  // claim activity the brain does not also light up (Rule 17). Hidden at 0 --
  // no "0 working" noise, and the all-active grounded fallback stays silent.
  const working = useGraphStore((s) => countWorking(s.data))
  const nodeCount = data?.stats.node_count ?? 0
  const edgeCount = data?.stats.edge_count ?? 0

  return (
    <div className="flex items-center gap-3 text-sm text-white/70">
      <div>
        <span className="font-semibold text-white">{nodeCount}</span> entities{' '}
        <span className="text-white/30">/</span>{' '}
        <span className="font-semibold text-white">{edgeCount}</span> connections
      </div>
      {working > 0 ? (
        <div className="flex items-center gap-1.5 rounded-full border border-teal-400/30 bg-teal-500/10 px-2.5 py-0.5 text-teal-200">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-400 animate-pulse" aria-hidden />
          <span className="font-semibold">{working}</span> working
        </div>
      ) : null}
    </div>
  )
}

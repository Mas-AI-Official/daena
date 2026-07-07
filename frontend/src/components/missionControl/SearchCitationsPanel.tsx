import { useState } from 'react'
import { ChevronDown, ChevronRight, X } from 'lucide-react'
import { GOV_GOLD, GOV_TEAL } from '@/styles/designTokens'
import { useGraphStore } from '@/stores/graphStore'

/**
 * Grounding-evidence panel for the Mission Control semantic search.
 *
 * The search bar fires POST /graph/search, which returns BOTH the matched node
 * ids (painted as teal rings on the canvas) AND the ragx citations that justify
 * those matches. Previously the citations were fetched into graphStore and
 * silently discarded -- the user saw dots light up with no way to know WHY.
 * This panel surfaces that evidence (source_path, snippet, score, collection)
 * so the "why" is visible, which is the whole point of a grounded graph.
 *
 * Honest states (Rule 17):
 *  - searching: in-flight indicator, no fabricated results.
 *  - searchOffline: amber note that ragx (the grounding layer) was unavailable /
 *    abstained. The backend still falls back to lexical keyword matching against
 *    the query alone, so the canvas DOES highlight those matches; we say so and
 *    flag that they are unranked and have no grounding evidence behind them.
 *  - matches but no citations: ragx matched nodes but returned no text evidence.
 *
 * Anchored bottom-left so it never collides with the Legend (top-left), the
 * NodeDetailPanel (right slide-over), or the Chat button (bottom-right).
 */
export default function SearchCitationsPanel() {
  const [open, setOpen] = useState(true)
  const searching = useGraphStore((s) => s.searching)
  const searchOffline = useGraphStore((s) => s.searchOffline)
  const citations = useGraphStore((s) => s.searchCitations)
  const matchCount = useGraphStore((s) => s.highlightedIds.size)
  const clearSearch = useGraphStore((s) => s.clearSearch)

  // Render only once a search is in flight or has produced something to report.
  const hasResult = searchOffline || citations.length > 0 || matchCount > 0
  if (!searching && !hasResult) return null

  return (
    <div
      className="absolute bottom-4 left-4 z-20 flex max-h-[46%] w-[360px] flex-col rounded-lg border bg-black/75 backdrop-blur"
      style={{ borderColor: 'rgba(212,168,67,0.35)' }}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 text-left text-xs font-medium transition-colors hover:text-white"
          style={{ color: GOV_GOLD }}
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          Grounding evidence
          {citations.length > 0 ? (
            <span className="text-white/40">({citations.length})</span>
          ) : null}
        </button>
        <button
          onClick={clearSearch}
          className="rounded p-1 text-white/40 hover:bg-white/10 hover:text-white"
          aria-label="Clear search and close evidence panel"
        >
          <X size={14} />
        </button>
      </div>

      {open ? (
        <div className="flex-1 overflow-y-auto px-3 py-2 text-sm text-white/80">
          {searching ? (
            <div className="text-white/40">Searching ragx...</div>
          ) : (
            <>
              {searchOffline ? (
                <div className="mb-2 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-2 text-xs text-amber-300/90">
                  Semantic grounding offline (ragx unavailable or abstained).{' '}
                  {matchCount > 0
                    ? `Showing ${matchCount} keyword ${matchCount === 1 ? 'match' : 'matches'} against your query, unranked and with no grounding evidence behind them.`
                    : 'No matches surfaced for this query.'}
                </div>
              ) : citations.length > 0 ? (
                <div className="mb-2 text-xs text-white/40">
                  <span style={{ color: GOV_TEAL }}>{matchCount}</span>{' '}
                  {matchCount === 1 ? 'node' : 'nodes'} matched, grounded in{' '}
                  {citations.length} {citations.length === 1 ? 'source' : 'sources'}
                </div>
              ) : (
                <div className="text-white/40">
                  Matched {matchCount} {matchCount === 1 ? 'node' : 'nodes'}; ragx
                  returned no text evidence for this query.
                </div>
              )}

              {citations.length > 0 ? (
                <ul className="space-y-2">
                  {citations.map((c) => (
                    <li key={c.chunk_id} className="rounded border border-white/10 px-2 py-2">
                      <div className="flex items-center justify-between text-xs text-white/40">
                        <span className="truncate" title={c.source_path}>
                          {c.source_path}
                        </span>
                        <span>{c.score.toFixed(2)}</span>
                      </div>
                      <div className="mt-1 text-white/70">{c.snippet}</div>
                      <div className="mt-1 text-xs text-white/30">{c.collection}</div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}

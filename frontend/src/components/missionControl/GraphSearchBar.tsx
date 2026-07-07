import { useState, type FormEvent } from 'react'
import { BACKGROUNDS, GOV_TEAL } from '@/styles/designTokens'
import { useGraphStore } from '@/stores/graphStore'

/**
 * PR-4 ragx-highlight search input. Submits the query to POST /graph/search;
 * matching node ids land in graphStore.highlightedIds which GraphCanvas paints
 * with a teal ring. When ragx (the grounding layer) is offline the backend still
 * falls back to lexical keyword matching, so the canvas may still highlight nodes;
 * the pill then says "grounding offline" AND reports that keyword-match count
 * rather than hiding it or claiming the canvas was untouched (Rule 17).
 */
export default function GraphSearchBar() {
  const [q, setQ] = useState('')
  const searching = useGraphStore((s) => s.searching)
  const searchOffline = useGraphStore((s) => s.searchOffline)
  const highlightedCount = useGraphStore((s) => s.highlightedIds.size)
  const semanticSearch = useGraphStore((s) => s.semanticSearch)
  const clearSearch = useGraphStore((s) => s.clearSearch)

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void semanticSearch(q)
  }

  const onClear = () => {
    setQ('')
    clearSearch()
  }

  return (
    <form
      onSubmit={onSubmit}
      className="flex items-center gap-2"
      role="search"
      aria-label="Mission Control semantic search"
    >
      <div className="flex items-center gap-2">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search the org graph..."
          aria-label="Semantic search query"
          className="w-64 rounded-md px-3 py-1.5 text-sm text-white/90 placeholder-white/40 outline-none focus:ring-1 focus:ring-white/20"
          style={{
            backgroundColor: BACKGROUNDS.input,
            border: `1px solid ${BACKGROUNDS.border}`,
          }}
        />
        <button
          type="submit"
          disabled={searching || q.trim().length === 0}
          className="rounded-md px-3 py-1.5 text-xs text-white/80 transition-colors hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          style={{
            backgroundColor: BACKGROUNDS.input,
            border: `1px solid ${BACKGROUNDS.border}`,
          }}
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
        {highlightedCount > 0 || searchOffline ? (
          <button
            type="button"
            onClick={onClear}
            className="rounded-md px-2 py-1.5 text-xs text-white/60 hover:text-white/90"
          >
            Clear
          </button>
        ) : null}
      </div>
      {searchOffline ? (
        <span
          className="rounded-md px-2 py-0.5 text-xs"
          style={{
            color: '#fcd34d',
            backgroundColor: 'rgba(245,158,11,0.12)',
            border: '1px solid rgba(245,158,11,0.35)',
          }}
          title={
            highlightedCount > 0
              ? 'ragx grounding is offline; the canvas shows unranked keyword matches with no grounding evidence behind them.'
              : 'ragx grounding is offline; no keyword matches surfaced for this query.'
          }
        >
          {highlightedCount > 0
            ? `grounding offline (${highlightedCount} keyword ${highlightedCount === 1 ? 'match' : 'matches'})`
            : 'grounding offline'}
        </span>
      ) : highlightedCount > 0 ? (
        <span
          className="rounded-md px-2 py-0.5 text-xs"
          style={{
            color: GOV_TEAL,
            backgroundColor: 'rgba(45,212,191,0.12)',
            border: `1px solid ${GOV_TEAL}`,
          }}
        >
          {highlightedCount} {highlightedCount === 1 ? 'match' : 'matches'}
        </span>
      ) : null}
    </form>
  )
}

/**
 * SkillPacksPanel -- PR-CONN-UX-RESCUE.
 *
 * Skill packs are reusable instructions / capability bundles. They are
 * NOT callable connectors -- the LLM uses the packaged skills as
 * context; nothing is invoked over the network. This panel surfaces
 * skill_pack rows in their own tab so they never visually compete with
 * real callable connectors.
 *
 * Honesty rules:
 *   - No Probe button (skill packs are categorically not callable)
 *   - No "healthy" pill possibility (label is always "skill_pack")
 *   - Explicit copy at top: "Not callable until connected to a runtime/MCP/app"
 */

import { useMemo, useState } from 'react'
import {
  AlertTriangle, BookOpen, Loader2, RefreshCw, Search,
} from 'lucide-react'

import {
  type ConnectionV2Row,
  labelTone,
  useConnectionsV2,
} from '@/hooks/useConnectionsV2'

export default function SkillPacksPanel() {
  const { rows, loading, error, refresh } = useConnectionsV2('skill_pack')
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(
      (r) =>
        r.display_name.toLowerCase().includes(q) ||
        r.slug.toLowerCase().includes(q),
    )
  }, [rows, search])

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-violet-300">
              <BookOpen size={14} />
              Skill Packs
            </div>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              {rows.length} skill pack{rows.length === 1 ? '' : 's'} detected
            </h2>
            <p className="mt-1 max-w-3xl text-xs text-starlight-400">
              Skill packs are reusable instructions / capabilities. They are
              not callable tools until connected to a runtime, MCP server, or
              app. Daena uses them as context so the LLM knows how to do
              specific tasks.
            </p>
          </div>
          <button
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          <AlertTriangle size={14} />
          <span>Backend error: {error}</span>
        </div>
      )}

      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search skill packs..."
          aria-label="Search skill packs"
          className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-2 pl-9 pr-3 text-sm text-starlight-100 placeholder:text-starlight-500 focus:border-primary-500/40 focus:outline-none"
        />
      </div>

      {loading && rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] py-12 text-center text-sm text-starlight-400">
          <Loader2 size={16} className="mr-2 inline animate-spin" />
          Loading skill packs...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-white/5 bg-white/[0.02] px-6 py-10 text-center text-sm text-starlight-400">
          <p className="mb-2 text-starlight-300">No skill packs imported yet.</p>
          <p className="mx-auto max-w-xl text-xs text-starlight-500">
            Click <strong className="text-starlight-200">Discover installed tools</strong> in
            the page header to import skill packs from the bundled catalog.
            Skill packs that ship as MCP servers will appear under MCP
            Servers instead.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-white/5 overflow-hidden rounded-lg border border-white/5 bg-midnight-400/20">
          {filtered.map((row) => (
            <SkillPackRow key={row.id} row={row} />
          ))}
        </ul>
      )}
    </div>
  )
}

function SkillPackRow({ row }: { row: ConnectionV2Row }) {
  const tone = labelTone(row.label)
  const cfg = (row.config || {}) as Record<string, unknown>
  const skillCount = Number(cfg.skill_count ?? 0)
  const category = String(cfg._category || '')
  const subtitle = String(cfg._subtitle || '')
  const skillIds = (cfg._skill_ids as string[] | undefined) || []

  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-violet-500/15 text-violet-200">
        <BookOpen size={16} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-starlight-100">{row.display_name}</span>
          {category && (
            <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-starlight-400">
              {category}
            </span>
          )}
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone.border} ${tone.bg} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            skill pack
          </span>
          <span
            className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-violet-200"
            title="Skill packs are not callable on their own. Connect them to a runtime, MCP, or app to invoke their capabilities."
          >
            not callable
          </span>
          {skillCount > 0 && (
            <span className="text-[11px] text-starlight-500">
              {skillCount} skill{skillCount === 1 ? '' : 's'}
            </span>
          )}
        </div>
        {subtitle && (
          <p className="mt-1 text-xs text-starlight-400">{subtitle}</p>
        )}
        {skillIds.length > 0 && (
          <p
            className="mt-1 truncate text-[11px] text-starlight-500"
            title={skillIds.join(', ')}
          >
            Skills: {skillIds.slice(0, 4).join(', ')}
            {skillIds.length > 4 ? `, +${skillIds.length - 4} more` : ''}
          </p>
        )}
      </div>
      <span
        className="inline-flex items-center gap-1.5 rounded-md border border-violet-500/30 bg-violet-500/5 px-3 py-1.5 text-xs text-violet-200/70"
        title="Skill packs are capability/instruction bundles, not callable surfaces."
      >
        No probe
      </span>
    </li>
  )
}

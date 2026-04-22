/**
 * MindsPage -- Gallery of the 10 Department Minds (soul personas).
 *
 * One card per department. Click to open the detail view; founders get
 * a "Refine All" action that kicks the weekly 3-pass refinement and
 * drops pending proposals into /souls/proposals for review.
 *
 * Consumes: GET /souls, POST /souls/refine-all (founder-gated).
 */
import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Brain,
  Sparkles,
  Thermometer,
  Cpu,
  ChevronRight,
  Wand2,
  FileCheck2,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer, Button, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/stores/toastStore'
import type { SoulSummary, SoulRefineVerdict, SoulProposal } from '@/types/api'

// Solid hex -> Tailwind-friendly inline style. Accent colors live in the
// backend soul metadata (per-department), so we honor them instead of
// hard-coding a palette here.
function accentStyle(hex?: string | null) {
  const color = hex && /^#?[0-9a-fA-F]{6}$/.test(hex.replace('#', '')) ? hex : '#D4A843'
  const normalized = color.startsWith('#') ? color : `#${color}`
  return {
    border: `1px solid ${normalized}33`,
    background: `${normalized}14`,
    color: normalized,
  }
}

export function MindsPage() {
  usePageTitle('Minds')
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const isFounder = user?.role === 'FOUNDER'

  const [souls, setSouls] = useState<SoulSummary[]>([])
  const [proposals, setProposals] = useState<SoulProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [refining, setRefining] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [soulsRes, proposalsRes] = await Promise.all([
          api.get<SoulSummary[]>('/souls'),
          api.get<SoulProposal[]>('/souls/proposals?status=pending&limit=100').catch(() => ({ data: [] as SoulProposal[] })),
        ])
        if (cancelled) return
        setSouls(soulsRes.data ?? [])
        setProposals(proposalsRes.data ?? [])
      } catch (err) {
        console.error('Failed to load Minds:', err)
        if (!cancelled) toast.error('Could not load Department Minds')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  // Count pending proposals per slug so each card can show a "N pending"
  // badge and the header shows the grand total.
  const pendingBySlug = useMemo(() => {
    const map: Record<string, number> = {}
    for (const p of proposals) {
      if (p.status !== 'pending') continue
      map[p.department_slug] = (map[p.department_slug] ?? 0) + 1
    }
    return map
  }, [proposals])

  const totalPending = useMemo(
    () => proposals.filter((p) => p.status === 'pending').length,
    [proposals],
  )

  const runRefineAll = async () => {
    if (!isFounder || refining) return
    setRefining(true)
    try {
      const { data } = await api.post<SoulRefineVerdict[]>('/souls/refine-all', {
        use_research: true,
        persist_proposal: true,
      })
      const successes = data?.filter((r) => !r.error).length ?? 0
      toast.success(`Refine-all complete: ${successes}/${data?.length ?? 0} Minds proposed updates`)
      // Re-fetch proposals so badges refresh.
      const proposalsRes = await api.get<SoulProposal[]>('/souls/proposals?status=pending&limit=100')
      setProposals(proposalsRes.data ?? [])
    } catch (err) {
      console.error('refine-all failed:', err)
      toast.error('Refine-all failed. See server logs.')
    } finally {
      setRefining(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex flex-wrap items-center justify-between gap-3"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
              <Brain size={22} className="text-primary-400" /> Department Minds
            </h1>
            <p className="text-sm text-starlight-400">
              10 persona overlays. Each Mind steers its department's voice, tools, and runtime preference.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {totalPending > 0 && (
              <button
                onClick={() => navigate('/minds/proposals')}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-status-warning/30 bg-status-warning/10 text-status-warning text-xs hover:bg-status-warning/15 transition-colors cursor-pointer"
                title="Review pending soul proposals"
              >
                <FileCheck2 size={14} />
                {totalPending} pending proposal{totalPending === 1 ? '' : 's'}
              </button>
            )}
            {isFounder && (
              <Button
                variant="premium"
                size="sm"
                isLoading={refining}
                onClick={runRefineAll}
              >
                <span className="flex items-center gap-2">
                  <Wand2 size={14} /> Refine all
                </span>
              </Button>
            )}
          </div>
        </motion.div>

        {loading ? (
          <Shimmer count={10} layout="card-grid" />
        ) : souls.length === 0 ? (
          <EmptyState
            icon={<Brain size={32} />}
            title="No Minds seeded yet"
            description="Department Minds live in backend/app/soul/departments/. Run the seed migration or ask a founder to refine them once."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {souls.map((soul, i) => {
              const pending = pendingBySlug[soul.slug] ?? 0
              return (
                <motion.div
                  key={soul.slug}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <Card
                    variant="glass"
                    padding="md"
                    className="cursor-pointer hover:border-white/10 hover:bg-white/[0.02] transition-all group h-full flex flex-col"
                    onClick={() => navigate(`/minds/${soul.slug}`)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div
                        className="px-2.5 py-1.5 rounded-lg text-[11px] font-mono uppercase tracking-wider"
                        style={accentStyle(soul.accent_color)}
                      >
                        {soul.department ?? soul.slug}
                      </div>
                      {pending > 0 && (
                        <Badge variant="warning" size="sm">
                          {pending} new
                        </Badge>
                      )}
                    </div>
                    <h3 className="text-sm font-display font-semibold text-starlight-100 mb-1 flex items-center gap-2">
                      <Sparkles size={14} className="text-primary-400" />
                      {soul.name ?? soul.slug}
                    </h3>
                    <div className="flex flex-wrap gap-2 text-[10px] text-starlight-400 mb-3">
                      {soul.runtime_preference && (
                        <span className="flex items-center gap-1">
                          <Cpu size={11} /> {soul.runtime_preference}
                        </span>
                      )}
                      {typeof soul.temperature === 'number' && (
                        <span className="flex items-center gap-1">
                          <Thermometer size={11} /> temp {soul.temperature.toFixed(2)}
                        </span>
                      )}
                      {soul.voice && <span>voice {soul.voice}</span>}
                    </div>
                    <div className="mt-auto flex items-center justify-between text-[10px] text-starlight-500">
                      <span className="font-mono">{soul.slug}</span>
                      <span className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-primary-400">
                        Open
                        <ChevronRight size={12} />
                      </span>
                    </div>
                  </Card>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default MindsPage

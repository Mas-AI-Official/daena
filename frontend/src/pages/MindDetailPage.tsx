/**
 * MindDetailPage -- Full Department Mind view with refine + proposal review.
 *
 * Layout: left pane shows the live soul body (mono, read-only). Right
 * pane shows meta + refine controls + pending proposal list for that
 * department. Only founders can refine or decide proposals; everyone
 * else gets a read-only view.
 *
 * Consumes:
 *   GET  /souls/{slug}
 *   GET  /souls/proposals?slug=
 *   POST /souls/{slug}/refine                (founder)
 *   POST /souls/proposals/{id}/approve|reject (founder)
 */
import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Brain,
  ArrowLeft,
  Wand2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Cpu,
  Thermometer,
  Wrench,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, EmptyState, Shimmer } from '@/components/common'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { toast } from '@/stores/toastStore'
import type { SoulDetail, SoulProposal, SoulRefineVerdict } from '@/types/api'

const PROPOSAL_STATUS_VARIANT: Record<string, 'default' | 'warning' | 'success' | 'danger'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}

export function MindDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  usePageTitle(`Mind · ${slug}`)
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const isFounder = user?.role === 'FOUNDER'

  const [soul, setSoul] = useState<SoulDetail | null>(null)
  const [proposals, setProposals] = useState<SoulProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [refining, setRefining] = useState(false)
  const [decisionLoading, setDecisionLoading] = useState<string | null>(null)
  const [lastVerdict, setLastVerdict] = useState<SoulRefineVerdict | null>(null)

  const fetchAll = useMemo(
    () => async () => {
      if (!slug) return
      const [soulRes, propRes] = await Promise.all([
        api.get<SoulDetail>(`/souls/${slug}`),
        api
          .get<SoulProposal[]>(`/souls/proposals?slug=${encodeURIComponent(slug)}&status=all&limit=50`)
          .catch(() => ({ data: [] as SoulProposal[] })),
      ])
      setSoul(soulRes.data)
      setProposals(propRes.data ?? [])
    },
    [slug],
  )

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        await fetchAll()
      } catch (err) {
        console.error('Failed to load Mind:', err)
        if (!cancelled) toast.error('Could not load this Mind')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [fetchAll])

  const runRefine = async () => {
    if (!isFounder || refining) return
    setRefining(true)
    setLastVerdict(null)
    try {
      const { data } = await api.post<SoulRefineVerdict>(`/souls/${slug}/refine`, {
        use_research: true,
        persist_proposal: true,
      })
      setLastVerdict(data)
      if (data.error) toast.error(`Refinement errored: ${data.error}`)
      else toast.success(`Refinement verdict: ${data.verdict} (${Math.round((data.confidence ?? 0) * 100)}%)`)
      await fetchAll()
    } catch (err) {
      console.error('refine failed:', err)
      toast.error('Refinement failed')
    } finally {
      setRefining(false)
    }
  }

  const decideProposal = async (proposalId: string, decision: 'approve' | 'reject') => {
    if (!isFounder || decisionLoading) return
    setDecisionLoading(proposalId)
    try {
      await api.post(`/souls/proposals/${proposalId}/${decision}`, { notes: null })
      toast.success(decision === 'approve' ? 'Proposal approved and promoted' : 'Proposal rejected')
      await fetchAll()
    } catch (err) {
      console.error('decision failed:', err)
      toast.error(`Could not ${decision} proposal`)
    } finally {
      setDecisionLoading(null)
    }
  }

  if (loading) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-7xl mx-auto p-6 space-y-4">
          <Shimmer count={4} layout="list" />
        </div>
      </div>
    )
  }

  if (!soul) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6">
          <EmptyState
            icon={<AlertCircle size={32} />}
            title="Mind not found"
            description={`No Department Mind matched slug "${slug}".`}
            action={
              <Button variant="outline" size="sm" onClick={() => navigate('/minds')}>
                Back to Minds
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  const pendingForThis = proposals.filter((p) => p.status === 'pending')

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex flex-wrap items-center justify-between gap-3"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/minds')}
              className="p-2 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
              aria-label="Back to Minds"
            >
              <ArrowLeft size={16} />
            </button>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
                <Brain size={22} className="text-primary-400" /> {soul.name ?? soul.slug}
              </h1>
              <p className="text-sm text-starlight-400">
                {soul.department ?? soul.slug} · {soul.body.length.toLocaleString()} chars in live soul file
              </p>
            </div>
          </div>
          {isFounder && (
            <Button variant="premium" size="sm" isLoading={refining} onClick={runRefine}>
              <span className="flex items-center gap-2">
                <Wand2 size={14} /> Refine this Mind
              </span>
            </Button>
          )}
        </motion.div>

        {/* Meta card */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card variant="glass" padding="md" className="md:col-span-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <MetaStat icon={<Cpu size={14} />} label="Runtime" value={soul.runtime_preference ?? '—'} />
              <MetaStat
                icon={<Thermometer size={14} />}
                label="Temperature"
                value={typeof soul.temperature === 'number' ? soul.temperature.toFixed(2) : '—'}
              />
              <MetaStat icon={<Brain size={14} />} label="Voice" value={soul.voice ?? '—'} />
              <MetaStat icon={<Wrench size={14} />} label="Tools" value={String(soul.tools_enabled.length)} />
            </div>
            {soul.fallback_runtimes.length > 0 && (
              <div className="mt-4">
                <div className="text-[10px] font-mono uppercase tracking-widest text-starlight-500 mb-2">
                  Fallback runtimes
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {soul.fallback_runtimes.map((rt) => (
                    <Badge key={rt} variant="default" size="sm">
                      {rt}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </Card>
          <Card variant="glass" padding="md">
            <div className="text-[10px] font-mono uppercase tracking-widest text-starlight-500 mb-2">
              Proposals
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-status-warning">{pendingForThis.length} pending</span>
              <span className="text-starlight-500">
                {proposals.length - pendingForThis.length} decided
              </span>
            </div>
            {lastVerdict && (
              <div className="mt-3 pt-3 border-t border-white/5 text-xs text-starlight-300">
                Last verdict:{' '}
                <span className="text-starlight-100 font-medium">{lastVerdict.verdict}</span>{' '}
                <span className="text-starlight-500">
                  · {Math.round((lastVerdict.confidence ?? 0) * 100)}% · {lastVerdict.gap_count ?? 0} gaps ·{' '}
                  {lastVerdict.evidence_sources ?? 0} sources
                </span>
              </div>
            )}
          </Card>
        </div>

        {/* Live body */}
        <Card variant="glass" padding="md">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-mono uppercase tracking-widest text-starlight-500">
              Live soul body
            </div>
            {soul.version && (
              <Badge variant="default" size="sm">
                v{soul.version}
              </Badge>
            )}
          </div>
          <pre className="text-xs text-starlight-200 whitespace-pre-wrap leading-relaxed max-h-[420px] overflow-y-auto bg-midnight-400/40 border border-white/5 rounded-lg p-3 font-mono">
            {soul.body}
          </pre>
        </Card>

        {/* Proposals list */}
        <div>
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">
            Refinement proposals
          </h2>
          {proposals.length === 0 ? (
            <EmptyState
              icon={<Clock size={28} />}
              title="No proposals yet"
              description={
                isFounder
                  ? 'Click "Refine this Mind" to produce a pending proposal. Nothing overwrites the live soul until you approve it.'
                  : 'Founders can trigger refinements from here.'
              }
            />
          ) : (
            <div className="space-y-2">
              {proposals.map((p) => (
                <Card key={p.proposal_id} variant="glass" padding="md">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={PROPOSAL_STATUS_VARIANT[p.status] ?? 'default'} size="sm">
                          {p.status}
                        </Badge>
                        {p.verdict && (
                          <span className="text-[10px] text-starlight-400 font-mono">
                            {p.verdict}
                            {typeof p.confidence === 'number'
                              ? ` · ${Math.round(p.confidence * 100)}%`
                              : ''}
                          </span>
                        )}
                        <span className="text-[10px] text-starlight-500">
                          {new Date(p.created_at).toLocaleString()}
                        </span>
                      </div>
                      {(p.improvement_notes ?? []).slice(0, 3).map((note, idx) => (
                        <p key={idx} className="text-xs text-starlight-300 line-clamp-2">
                          · {note}
                        </p>
                      ))}
                    </div>
                    {isFounder && p.status === 'pending' && (
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          isLoading={decisionLoading === p.proposal_id}
                          onClick={() => decideProposal(p.proposal_id, 'reject')}
                        >
                          <span className="flex items-center gap-1.5">
                            <XCircle size={13} /> Reject
                          </span>
                        </Button>
                        <Button
                          variant="premium"
                          size="sm"
                          isLoading={decisionLoading === p.proposal_id}
                          onClick={() => decideProposal(p.proposal_id, 'approve')}
                        >
                          <span className="flex items-center gap-1.5">
                            <CheckCircle2 size={13} /> Approve & promote
                          </span>
                        </Button>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetaStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-starlight-500 flex items-center gap-1.5 mb-1">
        {icon}
        {label}
      </div>
      <div className="text-sm text-starlight-100 truncate" title={value}>
        {value}
      </div>
    </div>
  )
}

export default MindDetailPage

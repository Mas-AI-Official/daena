/**
 * OpportunityInboxPage -- Sprint-19 PR-2 (2026-05-06).
 *
 * Operator-facing inbox of discovered business opportunities.
 * Status pills: discovered / drafted / queued / approved / sent /
 * rejected / archived.
 *
 * Honesty rules (locked, ADR-001):
 *   - All state from /api/v1/opportunities. No hardcoded demo rows.
 *   - "Run discovery now" button calls real orchestrator.
 *   - NO send button on this page; external action only flows
 *     through the controlled execution dispatcher elsewhere.
 */
import { useEffect, useState } from 'react'
import { Briefcase, RefreshCw, Archive, X, AlertTriangle, ShieldAlert, GitBranch } from 'lucide-react'
import { Link } from 'react-router-dom'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button } from '@/components/common'
import { api } from '@/lib/api'
import { useGoogleActivationSummary } from '@/hooks/useGoogleActivationSummary'

interface OpportunityRow {
  id: string
  type: string
  title: string
  description: string | null
  source_name: string
  source_url: string | null
  score: number
  deadline_at: string | null
  estimated_value_usd: number | null
  effort_hours: number | null
  risk_label: string | null
  next_action: string | null
  assigned_department: string | null
  status: string
  created_at: string
  updated_at: string | null
}

const STATUS_COLOR: Record<string, 'gray' | 'gold' | 'green' | 'red'> = {
  discovered: 'gray',
  drafted: 'gold',
  queued: 'gold',
  approved: 'green',
  sent: 'green',
  rejected: 'red',
  archived: 'gray',
}

const TYPE_LABEL: Record<string, string> = {
  customer_lead: 'Customer lead',
  grant: 'Grant',
  accelerator: 'Accelerator',
  hackathon: 'Hackathon',
  freelance_project: 'Freelance',
  partnership: 'Partnership',
  bug_bounty_program: 'Bug bounty',
  content_opportunity: 'Content',
}

export default function OpportunityInboxPage() {
  usePageTitle('Opportunities')
  const [rows, setRows] = useState<OpportunityRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadCount, setReloadCount] = useState(0)
  const [running, setRunning] = useState(false)
  const [lastRunSummary, setLastRunSummary] = useState<string | null>(null)
  const { summary: activation } = useGoogleActivationSummary()

  useEffect(() => {
    let cancelled = false
    api.get<OpportunityRow[]>('/api/v1/opportunities/')
      .then((r) => {
        if (cancelled) return
        setRows(r.data)
        setError(null)
      })
      .catch(() => {
        if (cancelled) return
        setError('Failed to load opportunities. Retry to refresh.')
      })
    return () => { cancelled = true }
  }, [reloadCount])

  async function runDiscovery() {
    setRunning(true)
    setLastRunSummary(null)
    try {
      const r = await api.post('/api/v1/opportunities/run-discovery', { top_n: 10 })
      const d = r.data as Record<string, unknown>
      const persisted = Number(d.persisted_count ?? 0)
      const updated = Number(d.updated_count ?? 0)
      const capped = Number(d.capped_count ?? 0)
      setLastRunSummary(
        `Discovered ${d.discovered_count} -> deduped ${d.deduped_count} -> persisted ${persisted} (updated ${updated}, capped ${capped}).`,
      )
      setReloadCount((c) => c + 1)
    } catch {
      setLastRunSummary('Discovery failed. Check server logs.')
    } finally {
      setRunning(false)
    }
  }

  async function setStatus(id: string, action: 'archive' | 'reject') {
    try {
      await api.post(`/api/v1/opportunities/${id}/${action}`)
      setReloadCount((c) => c + 1)
    } catch {
      // surfaced via api error store
    }
  }

  async function createWorkstream(id: string) {
    try {
      const r = await api.post<{ workstream_id: string; department_name: string }>(
        `/api/v1/opportunities/${id}/create-workstream`,
      )
      setLastRunSummary(
        `Promoted to ${r.data.department_name}. Workstream ${r.data.workstream_id.slice(0, 8)} created.`,
      )
      setReloadCount((c) => c + 1)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to create workstream'
      setLastRunSummary(`Promotion failed: ${msg}`)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-3">
              <Briefcase className="text-gold w-6 h-6" />
              Opportunity Inbox
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Discovered business opportunities ranked by deterministic
              score. No external action is taken here -- send / submit /
              post / pay are NOT reachable from this page.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setReloadCount((c) => c + 1)}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={runDiscovery}
              disabled={running}
            >
              {running ? 'Running...' : 'Run discovery'}
            </Button>
          </div>
        </header>

        {activation && !activation.ready && (
          <Card
            className="border-amber-500/30 bg-amber-500/5"
            data-testid="opportunities-activation-blocker"
          >
            <div className="p-4 flex items-start gap-3 text-amber-200">
              <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
              <div className="text-xs space-y-1 flex-1 min-w-0">
                <p className="font-semibold">
                  Google not fully connected. Outreach drafts cannot
                  reach Gmail until both accounts are ready.
                </p>
                <ul className="space-y-0.5 text-amber-300/90">
                  {activation.blockers.map((b) => (
                    <li key={`${b.role}:${b.email ?? 'client'}`}>
                      <span className="font-mono">
                        {b.email ?? 'OAuth client'}
                      </span>{' '}
                      missing: {b.missing.join(', ')}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/connections"
                  className="inline-block mt-2 underline decoration-dotted hover:text-amber-100"
                >
                  Open the Connections page →
                </Link>
              </div>
            </div>
          </Card>
        )}

        {lastRunSummary && (
          <Card className="border-slate-700 bg-slate-900/50">
            <div className="p-3 text-xs text-slate-400">{lastRunSummary}</div>
          </Card>
        )}

        {error && (
          <Card className="border-red-700 bg-red-950/30">
            <div className="p-4 flex items-center gap-3 text-red-200">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </div>
          </Card>
        )}

        {rows === null && !error && (
          <Card className="border-slate-700 bg-slate-900/50">
            <div className="p-8 text-center text-slate-500">Loading...</div>
          </Card>
        )}

        {rows !== null && rows.length === 0 && (
          <Card className="border-slate-700 bg-slate-900/50">
            <div className="p-8 text-center text-slate-500 space-y-2">
              <p>No opportunities yet.</p>
              <p className="text-xs">
                Drop a JSON list of opportunities into{' '}
                <code className="bg-slate-800 px-1 py-0.5 rounded">
                  backend/.opportunity_seed.json
                </code>{' '}
                and click Run discovery.
              </p>
            </div>
          </Card>
        )}

        {rows && rows.length > 0 && (
          <div className="space-y-3">
            {rows.map((row) => (
              <Card key={row.id} className="border-slate-700 bg-slate-900/50">
                <div className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge color={STATUS_COLOR[row.status] || 'gray'}>
                          {row.status}
                        </Badge>
                        <Badge color="gray">{TYPE_LABEL[row.type] || row.type}</Badge>
                        <span className="text-xs text-slate-500">
                          score {row.score}
                        </span>
                      </div>
                      <h3 className="text-slate-100 font-medium mt-2 truncate">
                        {row.title}
                      </h3>
                      {row.description && (
                        <p className="text-sm text-slate-400 mt-1 line-clamp-2">
                          {row.description}
                        </p>
                      )}
                    </div>
                    {row.status === 'discovered' && (
                      <div className="flex gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => createWorkstream(row.id)}
                          title="Promote to workstream owned by the right department"
                        >
                          <GitBranch className="w-3 h-3 mr-1" />
                          Workstream
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setStatus(row.id, 'archive')}
                          title="Archive this opportunity"
                        >
                          <Archive className="w-3 h-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setStatus(row.id, 'reject')}
                          title="Reject this opportunity"
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div>
                      <div className="text-slate-500">Source</div>
                      <div className="text-slate-300 truncate">
                        {row.source_name}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Deadline</div>
                      <div className="text-slate-300">
                        {row.deadline_at?.slice(0, 10) || '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Value</div>
                      <div className="text-slate-300">
                        {row.estimated_value_usd
                          ? `$${row.estimated_value_usd.toLocaleString()}`
                          : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500">Effort</div>
                      <div className="text-slate-300">
                        {row.effort_hours ? `${row.effort_hours}h` : '—'}
                      </div>
                    </div>
                  </div>

                  {row.next_action && (
                    <div className="text-xs text-slate-400 italic border-t border-slate-800 pt-2">
                      Next: {row.next_action}
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * ScanPage -- Intelligence-as-a-Service scan submission and management.
 *
 * This is the core IaaS product page. Users submit targets for security
 * intelligence analysis. Each scan runs through the 21-stage Laevateinn
 * pipeline with tier-appropriate depth.
 *
 * Tiers:
 *   T1 Scout    -- Find vulnerabilities (Free)
 *   T2 Analyst  -- Find + explain + remediation (Pro)
 *   T3 Operator -- Find + explain + fix code (Enterprise)
 *   T4 Architect -- Full + verify fix + retest (Enterprise+)
 *   T5 Founder  -- Full adversarial walkthrough (internal tier: 3vilbob)
 *
 * Endpoints:
 *   POST /security/scans/start      -- Start a scan
 *   GET  /security/scans/:id/status  -- Poll progress
 *   GET  /security/scans/:id/report  -- Get completed report
 *   GET  /security/scans/:id/report/pdf -- Download PDF
 */
import { useCallback, useEffect, useState, useRef } from 'react'
import { Crosshair, FileText, Activity, ShieldCheck, AlertTriangle, X, Loader2 } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { useSecurityModeStore } from '@/stores/securityModeStore'
import { useAuthStore } from '@/stores/authStore'
import { confirmDialog } from '@/stores/confirmStore'
import { toast } from '@/stores/toastStore'

// PR-SCAN-ADD-TO-SCOPE-INLINE-CTA (Sprint-9 PR-1):
// founder-only inline CTA when /scans/start returns target_not_in_scope.
// scope_type values mirror the backend's Literal exactly. Default is
// `exact_url` (host-only). Wildcard is OPT-IN, never the default.
type ScopeType = 'exact_url' | 'domain' | 'wildcard_subdomain'
import {
  type ScanJob,
  type ScanReport as ScanReportData,
  TIER_ID_TO_ENUM,
} from './scan/types'
import { TIERS, T5_TIER } from './scan/tiers'
import ScanLauncher from './scan/ScanLauncher'
import ScanList from './scan/ScanList'
import ScanReport from './scan/ScanReport'
import ScopeStatusBanner from './scan/ScopeStatusBanner'

export function ScanPage() {
  usePageTitle('Security Scan')

  // Elevated-mode store feeds the T5 tier. When the founder activates
  // the hidden command, securityModeStore.state.active flips True and
  // the tier list gains the Offensive tier. Mount effect triggers the
  // first state fetch so tiers rehydrate on page load; downstream
  // poll loops keep it fresh.
  const elevatedActive = useSecurityModeStore((s) => s.state.active)
  const fetchElevatedState = useSecurityModeStore((s) => s.fetchState)
  useEffect(() => {
    fetchElevatedState()
  }, [fetchElevatedState])
  const visibleTiers = elevatedActive ? [...TIERS, T5_TIER] : TIERS

  const [target, setTarget] = useState('')
  const [selectedTier, setSelectedTier] = useState('T1')
  const [activeJobs, setActiveJobs] = useState<ScanJob[]>([])
  const [selectedJob, setSelectedJob] = useState<ScanJob | null>(null)
  const [report, setReport] = useState<ScanReportData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // PR-SCAN-ADD-TO-SCOPE-INLINE-CTA (Sprint-9 PR-1): track the target
  // that just got blocked so the founder-only CTA can surface it.
  // scopeBlockedTarget is set ONLY on a 403 target_not_in_scope response.
  // Cleared after a successful add OR an explicit retry.
  const [scopeBlockedTarget, setScopeBlockedTarget] = useState<string | null>(null)
  const [scopeModalOpen, setScopeModalOpen] = useState(false)
  const [scopeType, setScopeType] = useState<ScopeType>('exact_url')
  const [scopeAdding, setScopeAdding] = useState(false)
  const [scopeAddError, setScopeAddError] = useState<string | null>(null)
  const [scopeAddSuccess, setScopeAddSuccess] = useState<string | null>(null)
  const userRole = useAuthStore((s) => s.user?.role)
  const isFounder = userRole === 'FOUNDER'
  const [history, setHistory] = useState<any[]>([])
  // Phase 10b B3: when true, /security/scans is queried with
  // archived=true so the founder can recover scans they soft-archived.
  const [showArchived, setShowArchived] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Phase 10b B2: track which job IDs have already fired the
  // "report ready" toast so we never double-fire on poll races.
  const reportReadyNotifiedRef = useRef<Set<string>>(new Set())

  // Load scan history on mount
  const refreshHistory = useCallback(async () => {
    try {
      const { data } = await api.get('/security/scans', {
        params: { limit: 20, archived: showArchived },
      })
      if (Array.isArray(data)) setHistory(data)
    } catch {
      // Silent -- history is optional
    }
  }, [showArchived])

  useEffect(() => {
    refreshHistory()
  }, [refreshHistory])

  // Poll active jobs
  const pollJobs = useCallback(async () => {
    const inProgress = activeJobs.filter(j => !['complete', 'failed'].includes(j.status))
    for (const job of inProgress) {
      try {
        const { data } = await api.get(`/security/scans/${job.job_id}/status`)
        setActiveJobs(prev =>
          prev.map(j => j.job_id === job.job_id ? { ...j, ...data } : j)
        )
        // Phase 10b B2: scan completion is currently silent except for
        // the icon flip on the active card. When the user has scrolled
        // to the report or has multiple scans running they miss it.
        // Surface a toast on the first complete-transition per job and
        // refresh the history list so the new report appears in
        // Recent Scans without a manual refresh.
        if (
          (data.status === 'complete' || data.status === 'failed') &&
          !reportReadyNotifiedRef.current.has(job.job_id)
        ) {
          reportReadyNotifiedRef.current.add(job.job_id)
          if (data.status === 'complete') {
            toast.success(`Scan complete — report ready for ${job.target}`)
          } else {
            toast.error(`Scan failed for ${job.target}`)
          }
          // Best-effort: refresh history so the row shows up below.
          refreshHistory()
        }
      } catch {
        // Silently continue polling
      }
    }
  }, [activeJobs, refreshHistory])

  // F-SCAN-BACKOFF fix: was hardcoded 3s polling with no backoff. With 5
  // parallel scans that's 100 status calls/min - wastes backend cycles
  // when jobs are stuck or moving slowly. Exponential backoff matches the
  // Sidebar.tsx pattern: start fast (2s), double on each unchanged tick,
  // cap at 60s. Reset to 2s the moment any job advances.
  const pollDelayRef = useRef(2000)
  const lastJobSignatureRef = useRef('')
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const inProgress = activeJobs.some(j => !['complete', 'failed'].includes(j.status))
    if (!inProgress) {
      pollDelayRef.current = 2000
      lastJobSignatureRef.current = ''
      return
    }
    const tick = async () => {
      const before = activeJobs.map(j => `${j.job_id}:${j.status}`).join('|')
      await pollJobs()
      if (cancelled) return
      const after = activeJobs.map(j => `${j.job_id}:${j.status}`).join('|')
      if (before === lastJobSignatureRef.current && after === before) {
        // No state change since last tick - back off
        pollDelayRef.current = Math.min(pollDelayRef.current * 2, 60000)
      } else {
        pollDelayRef.current = 2000
      }
      lastJobSignatureRef.current = after
      timer = setTimeout(tick, pollDelayRef.current)
    }
    timer = setTimeout(tick, pollDelayRef.current)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [activeJobs, pollJobs])

  // Start scan
  const startScan = async () => {
    if (!target.trim()) return
    setLoading(true)
    setError('')
    setScopeBlockedTarget(null)
    setScopeAddSuccess(null)
    try {
      const { data } = await api.post('/security/scans/start', {
        target: target.trim(),
        tier: TIER_ID_TO_ENUM[selectedTier] || selectedTier,
      })
      setActiveJobs(prev => [data, ...prev])
      setTarget('')
    } catch (err: any) {
      // PR-4: backend returns structured detail on 403 scope-block:
      // { code: "target_not_in_scope", target, hint }
      // Previously we crammed that into setError as [object Object].
      // Now we surface the hint inline so the operator knows the FIX,
      // not just the failure.
      const detail = err?.response?.data?.detail
      if (detail && typeof detail === 'object' && detail.code === 'target_not_in_scope') {
        setError(
          `Target "${detail.target}" is not in your authorized scope. ${detail.hint || ''}`.trim()
        )
        // PR-SCAN-ADD-TO-SCOPE-INLINE-CTA: capture the target so the
        // founder-only "Add this target to Scan Scope" CTA can prefill
        // the modal without re-typing.
        setScopeBlockedTarget(detail.target ?? target.trim())
      } else if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Failed to start scan')
      }
    } finally {
      setLoading(false)
    }
  }

  // PR-SCAN-ADD-TO-SCOPE-INLINE-CTA: open the modal preloaded with the
  // last scope-blocked target. Founder-only -- the CTA button is gated
  // on isFounder so this handler should never be invoked otherwise; the
  // backend role gate is the second line of defense.
  const openScopeModal = () => {
    if (!isFounder || !scopeBlockedTarget) return
    setScopeModalOpen(true)
    setScopeType('exact_url')
    setScopeAddError(null)
    setScopeAddSuccess(null)
  }

  // Confirm-add handler. NEVER auto-starts a scan after success: the
  // brief explicitly forbids it. Operator must click Start Scan again.
  const confirmScopeAdd = async () => {
    if (!isFounder || !scopeBlockedTarget) return
    setScopeAdding(true)
    setScopeAddError(null)
    try {
      await api.post('/security/authorized-scope/add', {
        target: scopeBlockedTarget,
        scope_type: scopeType,
      })
      setScopeAddSuccess(
        `Target added to Scan Scope as ${scopeType.replace(/_/g, ' ')}. ` +
        `Click Start Scan again to run.`,
      )
      // Clear the blocked-target marker so the CTA disappears.
      setScopeBlockedTarget(null)
      setError('')
      setScopeModalOpen(false)
      toast.success('Target added to Scan Scope')
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (detail && typeof detail === 'object' && detail.code) {
        setScopeAddError(`${detail.code}: ${detail.hint || ''}`.trim())
      } else if (typeof detail === 'string') {
        setScopeAddError(detail)
      } else {
        setScopeAddError('Failed to add target to scope.')
      }
    } finally {
      setScopeAdding(false)
    }
  }

  // Load report
  const loadReport = async (jobId: string) => {
    try {
      const { data } = await api.get(`/security/scans/${jobId}/report`)
      setReport(data)
    } catch {
      setError('Failed to load report')
    }
  }

  // Download PDF
  const downloadPdf = async (jobId: string) => {
    try {
      const response = await api.get(`/security/scans/${jobId}/report/pdf`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `daena-scan-${jobId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Failed to download PDF')
    }
  }

  // Archive a single scan (CLAUDE.md rule 2: archive by default).
  // Phase 2.7 (2026-04-25): the disclaimer is explicit about what
  // actually gets touched. Masoud surfaced the UX bug where a Recent
  // Scan labelled "app.py, x.py" looked like it might delete real
  // backend Python files when archived. It doesn't -- the scan RECORD
  // (a JSON file in var/security_reports/) is what moves; the actual
  // files on the user's disk are never touched.
  const archiveScan = async (jobId: string) => {
    const confirmed = await confirmDialog({
      title: 'Archive this scan record?',
      message: (
        'This moves the SCAN RECORD JSON files (trace + report) from ' +
        'var/security_reports/ to var/security_reports/.archive/. ' +
        'The records are recoverable.\n\n' +
        '⚠️ This does NOT delete any actual files on your disk. If the ' +
        "scan target was 'app.py' or any other file, that source file " +
        'is untouched -- only the scan history record is archived.'
      ),
      confirmLabel: 'Archive record',
      cancelLabel: 'Cancel',
      variant: 'warning',
    })
    if (!confirmed) return
    try {
      await api.delete(`/security/scans/${jobId}`)
      setActiveJobs(prev => prev.filter(j => j.job_id !== jobId))
      setHistory(prev => prev.filter(h => (h.scan_id || h.id) !== jobId))
      if (selectedJob?.job_id === jobId) {
        setSelectedJob(null)
        setReport(null)
      }
    } catch {
      setError(`Failed to archive scan ${jobId}`)
    }
  }

  // Re-run a scan with the same target + tier as the original.
  // Phase 2.7 (2026-04-25): backend POST /security/scans/{id}/rerun.
  // Adds a new scan job to the active list; the original record stays
  // untouched in history.
  const rerunScan = async (jobId: string) => {
    try {
      const { data } = await api.post(`/security/scans/${jobId}/rerun`)
      const newJob = data as { job_id: string; target: string; tier: string; status: string; created_at: string }
      if (newJob?.job_id) {
        setActiveJobs(prev => [
          {
            job_id: newJob.job_id,
            target: newJob.target,
            tier: newJob.tier,
            status: newJob.status,
            created_at: newJob.created_at,
            progress_pct: 0,
            findings_count: 0,
          } as any,
          ...prev,
        ])
      }
    } catch (err) {
      console.error('Failed to rerun scan:', err)
      setError(`Failed to re-run scan ${jobId}`)
    }
  }

  // Archive everything in history.
  const archiveAll = async () => {
    const confirmed = await confirmDialog({
      title: 'Archive all scans?',
      message: (
        `This archives ${history.length} scan(s). Trace + report JSON ` +
        'files move to var/security_reports/.archive/. Active scans ' +
        'in progress are not affected.'
      ),
      confirmLabel: `Archive ${history.length}`,
      cancelLabel: 'Cancel',
      variant: 'warning',
    })
    if (!confirmed) return
    try {
      await api.delete('/security/scans')
      setHistory([])
      setReport(null)
      setSelectedJob(null)
    } catch {
      setError('Failed to archive scans')
    }
  }

  // Open the Manus-style walkthrough window for a given scan.
  const openWalkthrough = (jobId: string) => {
    window.open(`/scan/walkthrough/${jobId}`, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      {/* PR-4: scope precondition is the FIRST thing the operator sees.
          Founder + scope empty: warning + Open Scan Scope button.
          Founder + scope populated: subtle confirmation pill.
          Non-founder: passive informational copy.
          Closes the "press Start, surprise 403" gap. */}
      <ScopeStatusBanner />

      <ScanLauncher
        visibleTiers={visibleTiers}
        selectedTier={selectedTier}
        onSelectTier={setSelectedTier}
        target={target}
        onTargetChange={setTarget}
        onStartScan={startScan}
        loading={loading}
        error={error}
      />

      {/* PR-SCAN-ADD-TO-SCOPE-INLINE-CTA (Sprint-9 PR-1): when the last
          scan was blocked by target_not_in_scope AND the operator has
          the FOUNDER role, surface a one-click CTA that opens a
          confirmation modal. Non-founder roles see only the existing
          "go to /security/scope" hint above; the CTA never appears for
          them, and the backend role gate is the second line of defense. */}
      {scopeBlockedTarget && isFounder && (
        <div
          data-testid="scan-scope-cta-row"
          className="flex flex-wrap items-center gap-3 rounded-md border border-amber-500/30 bg-amber-500/[0.05] px-3 py-2 text-[12px] text-amber-100"
        >
          <ShieldCheck size={14} className="shrink-0 text-amber-300" />
          <span className="flex-1 min-w-0">
            <strong>Founder authorized?</strong>{' '}
            Add <code className="rounded bg-amber-500/10 px-1">{scopeBlockedTarget}</code>{' '}
            to your Scan Scope. Daena will not auto-start the scan; you click Start Scan again.
          </span>
          <button
            data-testid="scan-scope-cta-add"
            onClick={openScopeModal}
            className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/15 px-2.5 py-1 text-[11px] font-medium text-amber-50 hover:bg-amber-500/25"
          >
            Add this target to Scan Scope
          </button>
        </div>
      )}

      {scopeAddSuccess && (
        <div className="flex items-start gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/[0.05] px-3 py-2 text-[12px] text-emerald-100">
          <ShieldCheck size={13} className="mt-0.5 shrink-0 text-emerald-300" />
          <span>{scopeAddSuccess}</span>
        </div>
      )}

      {scopeModalOpen && isFounder && scopeBlockedTarget && (
        <div
          data-testid="scan-scope-cta-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
          onClick={() => !scopeAdding && setScopeModalOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-start justify-between gap-3 border-b border-white/5 p-4">
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
                  Add to Scan Scope
                </p>
                <h3 className="mt-0.5 text-sm font-semibold text-starlight-100">
                  Authorize this target for scanning
                </h3>
              </div>
              <button
                onClick={() => !scopeAdding && setScopeModalOpen(false)}
                disabled={scopeAdding}
                className="rounded-md border border-white/10 bg-white/5 p-1 text-starlight-300 hover:bg-white/10 disabled:opacity-40"
                aria-label="Close"
              >
                <X size={12} />
              </button>
            </header>

            <div className="space-y-4 p-4">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-starlight-500">Target</p>
                <p className="mt-0.5 break-all rounded-md border border-white/10 bg-midnight-500/50 px-2.5 py-1.5 font-mono text-[12px] text-starlight-100">
                  {scopeBlockedTarget}
                </p>
              </div>

              <div>
                <p className="mb-1.5 text-[10px] uppercase tracking-wider text-starlight-500">
                  Scope type (default: exact URL only)
                </p>
                <div className="space-y-1.5">
                  {([
                    { id: 'exact_url' as const, label: 'Exact URL', hint: 'Authorize only this exact host. Most conservative.' },
                    { id: 'domain' as const, label: 'Domain', hint: 'Authorize this domain only (no subdomains).' },
                    { id: 'wildcard_subdomain' as const, label: 'Wildcard subdomain', hint: 'Authorize this domain AND every subdomain. Use with care.' },
                  ]).map((opt) => {
                    const checked = scopeType === opt.id
                    return (
                      <label
                        key={opt.id}
                        data-testid={`scan-scope-cta-radio-${opt.id}`}
                        className={`flex cursor-pointer items-start gap-2 rounded-md border px-2.5 py-1.5 text-[11px] ${
                          checked
                            ? 'border-amber-500/50 bg-amber-500/10 text-amber-100'
                            : 'border-white/10 bg-white/[0.03] text-starlight-200 hover:bg-white/[0.06]'
                        }`}
                      >
                        <input
                          type="radio"
                          name="scope-type"
                          value={opt.id}
                          checked={checked}
                          onChange={() => setScopeType(opt.id)}
                          disabled={scopeAdding}
                          className="mt-0.5 accent-amber-400"
                        />
                        <span className="min-w-0">
                          <strong className="block text-[11px] text-starlight-100">{opt.label}</strong>
                          <span className="block text-[10px] text-starlight-400">{opt.hint}</span>
                        </span>
                      </label>
                    )
                  })}
                </div>
              </div>

              <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/[0.05] px-2.5 py-1.5 text-[11px] text-rose-200">
                <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                <span>
                  <strong>Only add targets you are authorized to test.</strong>{' '}
                  Daena will scan within your declared scope; the legal authorization is yours.
                </span>
              </div>

              {scopeAddError && (
                <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/[0.05] px-2.5 py-1.5 text-[11px] text-rose-200">
                  <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                  <span>{scopeAddError}</span>
                </div>
              )}
            </div>

            <footer className="flex items-center justify-end gap-2 border-t border-white/5 p-3">
              <button
                onClick={() => setScopeModalOpen(false)}
                disabled={scopeAdding}
                className="rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-starlight-300 hover:bg-white/10 disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                data-testid="scan-scope-cta-confirm"
                onClick={() => void confirmScopeAdd()}
                disabled={scopeAdding}
                className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/15 px-3 py-1 text-[11px] font-medium text-amber-50 hover:bg-amber-500/25 disabled:opacity-40"
              >
                {scopeAdding
                  ? <Loader2 size={11} className="animate-spin" />
                  : <ShieldCheck size={11} />}
                Confirm add
              </button>
            </footer>
          </div>
        </div>
      )}

      {/* PR-4: tell the operator where reports actually land. Brief said
          "improve copy so user knows where reports go" - this paragraph
          is the answer. No new UI, no new endpoint - just honesty. */}
      <div className="flex items-start gap-3 text-[11px] text-starlight-500 px-1">
        <FileText size={13} className="mt-0.5 shrink-0 text-starlight-400" />
        <p>
          Reports land below in <span className="text-starlight-300">Recent Scans</span>.
          Click <span className="text-starlight-300">View Report</span> to read inline,
          <span className="text-starlight-300"> Open walkthrough</span> for the live phase-by-phase view (opens in a new tab),
          or <span className="text-starlight-300">Export</span> for a downloadable PDF/Markdown.
          Archive moves the JSON record to <span className="font-mono">var/security_reports/.archive/</span> - your source files are never touched.
          <span className="block mt-1 text-starlight-600">
            <Activity size={10} className="inline mr-1" />
            Scans run within Daena&apos;s installed tool set. If a tier requires a tool that
            is not installed (Security Ops &gt; Tools), the scan completes with what is
            available and the report notes which tools were skipped.
          </span>
        </p>
      </div>

      <ScanList
        activeJobs={activeJobs}
        history={history}
        showArchived={showArchived}
        onToggleArchived={() => setShowArchived((v) => !v)}
        onLoadReport={loadReport}
        onDownloadPdf={downloadPdf}
        onOpenWalkthrough={openWalkthrough}
        onArchiveScan={archiveScan}
        onRerunScan={rerunScan}
        onSelectJob={setSelectedJob}
        onRefreshHistory={refreshHistory}
        onArchiveAll={archiveAll}
      />

      {report && (
        <ScanReport report={report} selectedJob={selectedJob} />
      )}

      {/* Empty state */}
      {activeJobs.length === 0 && !report && history.length === 0 && (
        <EmptyState
          icon={<Crosshair size={40} className="text-starlight-500" />}
          title="No scans yet"
          description="Submit a target above to start your first security intelligence scan. Each scan runs through Daena's multi-model verification pipeline."
        />
      )}
    </div>
  )
}

// Need this for lazy loading
export default ScanPage

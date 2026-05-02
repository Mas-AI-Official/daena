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
import { Crosshair, FileText, Activity } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { useSecurityModeStore } from '@/stores/securityModeStore'
import { confirmDialog } from '@/stores/confirmStore'
import { toast } from '@/stores/toastStore'
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
      } else if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Failed to start scan')
      }
    } finally {
      setLoading(false)
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

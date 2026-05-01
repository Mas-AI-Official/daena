/**
 * ScanList -- the Active Scans list (running with progress) and the
 * Recent Scans list (history). Both are scan rows with action buttons,
 * grouped here so the orchestrator stays thin.
 */
import { motion } from 'framer-motion'
import {
  Activity,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  FileText,
  Download,
  Archive,
  ExternalLink,
  RefreshCw,
  RotateCw,
} from 'lucide-react'
import { Badge } from '@/components/common'
import {
  type ScanJob,
  STATUS_LABELS,
  BACKEND_TO_DISPLAY,
  relativeAgo,
} from './types'

interface Props {
  activeJobs: ScanJob[]
  history: any[]
  // Phase 10b B3: archive-visibility toggle (parent owns the
  // boolean + the GET /security/scans?archived=true call site).
  showArchived: boolean
  onToggleArchived: () => void
  onLoadReport: (jobId: string) => void
  onDownloadPdf: (jobId: string) => void
  onOpenWalkthrough: (jobId: string) => void
  onArchiveScan: (jobId: string) => void
  onRerunScan: (jobId: string) => void
  onSelectJob: (job: ScanJob) => void
  onRefreshHistory: () => void
  onArchiveAll: () => void
}

function scanId(trace: any) {
  return trace.scan_id || trace.id || trace.job_id
}

function scanTitle(trace: any, fallback: string) {
  return trace.title || trace.scan_title || trace.name || `Security report ${fallback}`
}

function scanTarget(trace: any) {
  return trace.target || trace.target_path || trace.repository || trace.scope || 'unknown target'
}

function scanType(trace: any) {
  return trace.scan_type || trace.type || trace.tier || 'defensive security review'
}

function authorizationScope(trace: any) {
  return trace.authorization_scope || trace.scope_label || trace.authorized_scope || 'Owner-authorized workspace'
}

function runtimeUsed(trace: any, toolsUsed: string[]) {
  return trace.runtime_used || trace.model_used || trace.provider || toolsUsed[0] || 'not recorded'
}

function severitySummary(trace: any, findings: number) {
  const counts = trace.severity_counts || trace.severity_summary
  if (counts && typeof counts === 'object') {
    const ordered = ['critical', 'high', 'medium', 'low', 'info']
    const parts = ordered
      .map((key) => [key, counts[key] ?? counts[key.toUpperCase()]] as const)
      .filter(([, value]) => Number(value) > 0)
      .map(([key, value]) => `${String(value)} ${key}`)
    if (parts.length > 0) return parts.join(' / ')
  }
  const sev = trace.severity || trace.highest_severity
  if (sev) return `${findings} findings, highest ${String(sev).toLowerCase()}`
  return findings > 0 ? `${findings} findings` : 'No findings recorded'
}

function toJob(trace: any, sid: string): ScanJob {
  const status = ['queued', 'scanning', 'analyzing', 'reporting', 'complete', 'failed'].includes(trace.status)
    ? trace.status
    : 'complete'
  return {
    job_id: sid,
    target: scanTarget(trace),
    tier: trace.tier || trace.scan_type || 'SCOUT',
    status: status as ScanJob['status'],
    progress_pct: 100,
    files_scanned: trace.files_scanned ?? 0,
    files_total: trace.files_total ?? 0,
    findings_count: trace.finding_count ?? trace.total_findings ?? 0,
    created_at: trace.created_at || trace.timestamp || trace.completed_at || new Date().toISOString(),
    duration_secs: trace.duration_secs,
    cost_usd: trace.cost_usd,
  }
}

export default function ScanList({
  activeJobs,
  history,
  showArchived,
  onToggleArchived,
  onLoadReport,
  onDownloadPdf,
  onOpenWalkthrough,
  onArchiveScan,
  onRerunScan,
  onSelectJob,
  onRefreshHistory,
  onArchiveAll,
}: Props) {
  return (
    <>
      {/* Active Scans */}
      {activeJobs.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-starlight-300 flex items-center gap-2">
            <Activity size={14} className="text-primary-400" />
            Active Scans
          </h2>
          {activeJobs.map(job => {
            const statusInfo = STATUS_LABELS[job.status] || STATUS_LABELS.queued
            const isComplete = job.status === 'complete'
            return (
              <motion.div
                key={job.job_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-midnight-200/60 border border-white/5 rounded-xl p-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {isComplete ? (
                      <CheckCircle2 size={18} className="text-status-success" />
                    ) : job.status === 'failed' ? (
                      <AlertTriangle size={18} className="text-status-error" />
                    ) : (
                      <Loader2 size={18} className="text-primary-400 animate-spin" />
                    )}
                    <div>
                      <p className="text-sm text-starlight-100 font-medium">{job.target}</p>
                      <p className={`text-xs ${statusInfo.color}`}>{statusInfo.label}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="text-[10px]">{BACKEND_TO_DISPLAY[job.tier] ?? job.tier}</Badge>
                    {job.findings_count > 0 && (
                      <span className="text-xs text-status-warning font-mono">{job.findings_count} findings</span>
                    )}
                    {isComplete && (
                      <>
                        {/* Phase 10b B2: explicit "Report ready" pill so
                            the user spots a freshly-completed scan
                            without inspecting icon glyphs. */}
                        <Badge variant="success" className="text-[10px]" data-testid="scan-report-ready-badge">
                          Report ready
                        </Badge>
                        <div className="flex gap-1">
                          <button
                            data-testid="scan-active-view-report"
                            onClick={() => { onSelectJob(job); onLoadReport(job.job_id) }}
                            className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-primary-400 transition-colors cursor-pointer"
                            title="View report"
                          >
                            <FileText size={14} />
                          </button>
                          <button
                            onClick={() => onDownloadPdf(job.job_id)}
                            className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-accent-amber transition-colors cursor-pointer"
                            title="Download report"
                          >
                            <Download size={14} />
                          </button>
                          {/* Phase 10b B1: completed scans on the active
                              list now expose Re-run too. Previously the
                              Re-run button only existed in the Recent
                              Scans (history) list, so users had to wait
                              for a refresh-history pass before they
                              could repeat the scan. */}
                          <button
                            data-testid="scan-active-rerun"
                            onClick={() => onRerunScan(job.job_id)}
                            className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-accent-amber transition-colors cursor-pointer"
                            title="Re-run this scan with the same target"
                          >
                            <RotateCw size={14} />
                          </button>
                          <button
                            onClick={() => onOpenWalkthrough(job.job_id)}
                            className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-accent-cyan transition-colors cursor-pointer"
                            title="Open live walkthrough window"
                          >
                            <ExternalLink size={14} />
                          </button>
                          <button
                            onClick={() => onArchiveScan(job.job_id)}
                            className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-status-error transition-colors cursor-pointer"
                            title="Archive scan"
                          >
                            <Archive size={14} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                {!['complete', 'failed'].includes(job.status) && (
                  <div className="mt-3">
                    <div className="h-1.5 bg-midnight-400 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-primary-500 to-accent-cyan rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${job.progress_pct}%` }}
                        transition={{ duration: 0.5, ease: 'easeOut' }}
                      />
                    </div>
                    <div className="flex justify-between mt-1 text-[10px] text-starlight-500">
                      <span>{job.files_scanned}/{job.files_total} files</span>
                      <span>{job.progress_pct}%</span>
                    </div>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      )}

      {/* Scan History */}
      {(history.length > 0 || showArchived) && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-starlight-300 flex items-center gap-2">
              <Clock size={14} className="text-starlight-400" />
              {showArchived ? 'Archived Scans' : 'Recent Scans'}
              <span className="text-[10px] text-starlight-500 ml-1">({history.length})</span>
            </h2>
            <div className="flex items-center gap-2">
              {/* Phase 10b B3: archive visibility toggle. Closes the
                  "archive == data lost" gap surfaced in Phase 9B. */}
              <button
                data-testid="scan-show-archived-toggle"
                onClick={onToggleArchived}
                aria-pressed={showArchived}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs transition-colors cursor-pointer ${
                  showArchived
                    ? 'bg-accent-amber/15 text-accent-amber'
                    : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/5'
                }`}
                title={showArchived ? 'Show recent (active) scans' : 'Show archived scans'}
              >
                <Archive size={12} />
                {showArchived ? 'Show recent' : 'Show archived'}
              </button>
              <button
                onClick={onRefreshHistory}
                className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs text-starlight-400 hover:text-starlight-200 hover:bg-white/5 transition-colors cursor-pointer"
                title="Refresh"
              >
                <RefreshCw size={12} />
              </button>
              {!showArchived && (
                <button
                  onClick={onArchiveAll}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs text-status-error/80 hover:text-status-error hover:bg-status-error/10 transition-colors cursor-pointer"
                  title="Archive all scans"
                >
                  <Archive size={12} />
                  Archive all
                </button>
              )}
            </div>
          </div>

          {showArchived && history.length === 0 && (
            <p className="text-[11px] text-starlight-500 px-1 py-2">
              No archived scans. Archived reports remain on disk in
              <code className="mx-1 px-1 py-0.5 rounded bg-midnight-800/40 text-starlight-300">
                var/security_reports/.archive/
              </code>
              and can be restored manually.
            </p>
          )}
          <div className="space-y-2">
            {history.map((trace: any, idx: number) => {
              const sid = scanId(trace)
              const findings = trace.finding_count ?? trace.total_findings ?? 0
              const toolsUsed: string[] = Array.isArray(trace.tools_used) ? trace.tools_used : []
              const shortId = sid ? String(sid).slice(0, 8) : `#${history.length - idx}`
              const ts = trace.completed_at || trace.created_at || trace.timestamp
              const ago = ts ? relativeAgo(ts) : null
              const sev = trace.severity || trace.highest_severity || (findings > 0 ? 'medium' : 'none')
              const target = scanTarget(trace)
              const title = scanTitle(trace, shortId)
              const status = trace.status || 'complete'
              const reportJob = sid ? toJob(trace, sid) : null
              return (
                <div
                  key={sid || idx}
                  className="bg-midnight-200/40 border border-white/5 rounded-lg p-4 hover:border-white/15 transition-colors"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className={`rounded-md px-2 py-0.5 text-[10px] font-mono uppercase ${
                          status === 'complete' ? 'bg-status-success/10 text-status-success' :
                          status === 'failed' ? 'bg-status-error/10 text-status-error' :
                          'bg-starlight-500/10 text-starlight-400'
                        }`}>
                          {status}
                        </span>
                        <span className={`rounded-md px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider ${
                          sev === 'critical' || sev === 'CRITICAL' ? 'bg-status-error/15 text-status-error' :
                          sev === 'high' || sev === 'HIGH' ? 'bg-accent-amber/15 text-accent-amber' :
                          sev === 'medium' || sev === 'MEDIUM' ? 'bg-accent-cyan/15 text-accent-cyan' :
                          sev === 'low' || sev === 'LOW' ? 'bg-status-success/10 text-status-success' :
                          'bg-starlight-500/10 text-starlight-400'
                        }`}>
                          {severitySummary(trace, findings)}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-wider text-starlight-500">
                          Report {shortId}
                        </span>
                        {ago && <span className="text-[10px] text-starlight-500">{ago}</span>}
                      </div>
                      <h3 className="truncate text-sm font-semibold text-starlight-100" title={title}>
                        {title}
                      </h3>
                      <div className="mt-3 grid gap-2 text-[11px] text-starlight-400 md:grid-cols-2">
                        <ReportField label="Target" value={target} mono />
                        <ReportField label="Scan type" value={scanType(trace)} />
                        <ReportField label="Authorization scope" value={authorizationScope(trace)} />
                        <ReportField label="Runtime / tool" value={runtimeUsed(trace, toolsUsed)} />
                        <ReportField label="Findings" value={String(findings)} />
                        <ReportField label="Created" value={ts ? `${new Date(ts).toLocaleString()}${ago ? ` (${ago})` : ''}` : 'not recorded'} />
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 shrink-0 lg:justify-end">
                      <button
                        onClick={(e) => { e.stopPropagation(); if (sid) { if (reportJob) onSelectJob(reportJob); onLoadReport(sid) } }}
                        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-starlight-200 hover:bg-white/10"
                        title="View report"
                      >
                        <FileText size={13} />
                        View Report
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (sid) onRerunScan(sid) }}
                        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-starlight-200 hover:bg-white/10"
                        title="Re-run this scan with the same target"
                      >
                        <RotateCw size={13} />
                        Re-run
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (sid) onDownloadPdf(sid) }}
                        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-starlight-200 hover:bg-white/10"
                        title="Export PDF report"
                      >
                        <Download size={13} />
                        Export
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (sid) onOpenWalkthrough(sid) }}
                        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-starlight-200 hover:bg-white/10"
                        title="Open walkthrough"
                      >
                        <ExternalLink size={13} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (sid) onArchiveScan(sid) }}
                        className="inline-flex items-center gap-1.5 rounded-md border border-status-error/20 bg-status-error/5 px-2.5 py-1.5 text-xs text-status-error/90 hover:bg-status-error/10"
                        title="Archive scan record. Source files are untouched."
                      >
                        <Archive size={13} />
                        Archive
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </>
  )
}

function ReportField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-md bg-black/10 px-2.5 py-2">
      <div className="text-[10px] uppercase tracking-wider text-starlight-600">{label}</div>
      <div className={`mt-1 truncate text-starlight-300 ${mono ? 'font-mono' : ''}`} title={value}>
        {value}
      </div>
    </div>
  )
}

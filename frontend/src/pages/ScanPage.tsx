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
 *   T5 3vilbob  -- Offensive mode (Founder only)
 *
 * Endpoints:
 *   POST /security/scans/start      -- Start a scan
 *   GET  /security/scans/:id/status  -- Poll progress
 *   GET  /security/scans/:id/report  -- Get completed report
 *   GET  /security/scans/:id/report/pdf -- Download PDF
 */
import { useCallback, useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Shield,
  ShieldCheck,
  Crosshair,
  Play,
  Download,
  FileText,
  Clock,
  Target,
  Zap,
  Brain,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ChevronRight,
  Eye,
  Layers,
  DollarSign,
  BarChart3,
  RefreshCw,
  Activity,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, EmptyState } from '@/components/common'
import { api } from '@/lib/api'

// ── Types ──

interface ScanTier {
  id: string
  name: string
  description: string
  features: string[]
  price: string
  pipelineStages: number
  color: string
  icon: React.ReactNode
  locked: boolean
}

interface ScanJob {
  job_id: string
  target: string
  tier: string
  status: 'queued' | 'scanning' | 'analyzing' | 'reporting' | 'complete' | 'failed'
  progress_pct: number
  files_scanned: number
  files_total: number
  findings_count: number
  created_at: string
  duration_secs?: number
  cost_usd?: number
}

interface ScanFinding {
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
  title: string
  file_path: string
  line_number: number
  description: string
  remediation?: string
  fix_code?: string
  verified?: boolean
  cve_id?: string
}

interface ScanReport {
  job_id: string
  tier: string
  findings: ScanFinding[]
  summary: string
  report_pdf_path?: string
  cost_usd: number
  duration_secs: number
  pipeline_stages_used: number
  models_used: string[]
}

// ── Tier definitions ──

const TIERS: ScanTier[] = [
  {
    id: 'T1',
    name: 'Scout',
    description: 'Find vulnerabilities',
    features: ['Vulnerability detection', 'Severity classification', 'File-level findings'],
    price: 'Free',
    pipelineStages: 6,
    color: 'text-starlight-300',
    icon: <Eye size={20} />,
    locked: false,
  },
  {
    id: 'T2',
    name: 'Analyst',
    description: 'Find + explain + remediation',
    features: ['Everything in Scout', 'Detailed explanations', 'Remediation guidance', 'CVE mapping'],
    price: '$49/scan',
    pipelineStages: 12,
    color: 'text-accent-cyan',
    icon: <Brain size={20} />,
    locked: false,
  },
  {
    id: 'T3',
    name: 'Operator',
    description: 'Find + explain + fix code',
    features: ['Everything in Analyst', 'Auto-generated fix patches', 'Multi-model verification', 'Adversarial testing'],
    price: '$199/scan',
    pipelineStages: 17,
    color: 'text-primary-400',
    icon: <Zap size={20} />,
    locked: false,
  },
  {
    id: 'T4',
    name: 'Architect',
    description: 'Full analysis + verify + retest',
    features: ['Everything in Operator', 'Fix verification', 'Regression testing', 'Architecture review', 'Full reasoning chain'],
    price: '$499/scan',
    pipelineStages: 21,
    color: 'text-accent-amber',
    icon: <Layers size={20} />,
    locked: false,
  },
]

// ── Severity colors ──

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-status-error/20 text-status-error border-status-error/30',
  HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  MEDIUM: 'bg-status-warning/20 text-status-warning border-status-warning/30',
  LOW: 'bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30',
  INFO: 'bg-starlight-400/20 text-starlight-400 border-starlight-400/30',
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  queued: { label: 'Queued', color: 'text-starlight-400' },
  scanning: { label: 'Scanning files...', color: 'text-accent-cyan' },
  analyzing: { label: 'Running pipeline...', color: 'text-primary-400' },
  reporting: { label: 'Generating report...', color: 'text-accent-amber' },
  complete: { label: 'Complete', color: 'text-status-success' },
  failed: { label: 'Failed', color: 'text-status-error' },
}

export function ScanPage() {
  usePageTitle('Security Scan')

  const [target, setTarget] = useState('')
  const [selectedTier, setSelectedTier] = useState('T1')
  const [activeJobs, setActiveJobs] = useState<ScanJob[]>([])
  const [selectedJob, setSelectedJob] = useState<ScanJob | null>(null)
  const [report, setReport] = useState<ScanReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<any[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load scan history on mount
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/security/scans', { params: { limit: 20 } })
        if (Array.isArray(data)) setHistory(data)
      } catch {
        // Silent -- history is optional
      }
    })()
  }, [])

  // Poll active jobs
  const pollJobs = useCallback(async () => {
    const inProgress = activeJobs.filter(j => !['complete', 'failed'].includes(j.status))
    for (const job of inProgress) {
      try {
        const { data } = await api.get(`/security/scans/${job.job_id}/status`)
        setActiveJobs(prev =>
          prev.map(j => j.job_id === job.job_id ? { ...j, ...data } : j)
        )
      } catch {
        // Silently continue polling
      }
    }
  }, [activeJobs])

  useEffect(() => {
    if (activeJobs.some(j => !['complete', 'failed'].includes(j.status))) {
      pollRef.current = setInterval(pollJobs, 3000)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [activeJobs, pollJobs])

  // Map display tier IDs (T1-T4) to backend enum values (SCOUT/ANALYST/...)
  const TIER_ID_TO_ENUM: Record<string, string> = {
    T1: 'SCOUT',
    T2: 'ANALYST',
    T3: 'OPERATOR',
    T4: 'ARCHITECT',
    T5: 'EVILBOB',
  }

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
      setError(err?.response?.data?.detail || 'Failed to start scan')
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

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-3">
          <Shield className="text-primary-400" size={28} />
          Security Intelligence
        </h1>
        <p className="text-sm text-starlight-400 mt-1">
          Intelligence-as-a-Service -- submit targets for multi-model verified security analysis
        </p>
      </div>

      {/* Tier Selector */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {TIERS.map(tier => (
          <button
            key={tier.id}
            disabled={tier.locked}
            onClick={() => setSelectedTier(tier.id)}
            className={`
              relative p-4 rounded-xl border transition-all duration-200 text-left cursor-pointer
              ${selectedTier === tier.id
                ? 'bg-primary-500/10 border-primary-500/40 shadow-[var(--shadow-glow-sm)]'
                : tier.locked
                  ? 'bg-midnight-200/40 border-white/5 opacity-50 cursor-not-allowed'
                  : 'bg-midnight-200/60 border-white/5 hover:border-white/15'
              }
            `}
          >
            <div className={`flex items-center gap-2 mb-2 ${tier.color}`}>
              {tier.icon}
              <span className="font-semibold text-sm">{tier.id}</span>
            </div>
            <p className="text-xs font-medium text-starlight-100">{tier.name}</p>
            <p className="text-[10px] text-starlight-500 mt-0.5">{tier.description}</p>
            <div className="mt-2 flex items-center gap-1">
              <Layers size={10} className="text-starlight-500" />
              <span className="text-[10px] text-starlight-500">{tier.pipelineStages} stages</span>
            </div>
            <p className="text-xs font-mono text-accent-amber mt-1">{tier.price}</p>
          </button>
        ))}
      </div>

      {/* Scan Input */}
      <Card className="p-6">
        <div className="flex gap-3">
          <div className="flex-1">
            <div className="relative">
              <Target size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
              <input
                type="text"
                value={target}
                onChange={e => setTarget(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && startScan()}
                placeholder="Enter target: GitHub URL, file path, or paste code..."
                className="w-full pl-10 pr-4 py-3 rounded-lg bg-midnight-400/60 border border-white/10
                           text-sm text-starlight-100 placeholder:text-starlight-600
                           focus:outline-none focus:border-primary-500/50 focus:shadow-[var(--shadow-glow-sm)]
                           transition-all"
              />
            </div>
          </div>
          <button
            onClick={startScan}
            disabled={loading || !target.trim()}
            className="px-6 py-3 rounded-lg bg-primary-500 hover:bg-primary-400 disabled:bg-primary-500/30
                       text-white font-medium text-sm flex items-center gap-2 transition-colors
                       disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {loading ? 'Starting...' : 'Start Scan'}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-xs text-status-error flex items-center gap-1">
            <AlertTriangle size={12} /> {error}
          </p>
        )}

        {/* Selected tier details */}
        <div className="mt-4 flex items-center gap-4 text-xs text-starlight-500">
          <span className="flex items-center gap-1">
            <Layers size={12} />
            Tier: <span className="text-starlight-300 font-medium">{selectedTier}</span>
          </span>
          <span className="flex items-center gap-1">
            <Brain size={12} />
            Pipeline: <span className="text-starlight-300 font-medium">
              {TIERS.find(t => t.id === selectedTier)?.pipelineStages} stages
            </span>
          </span>
          <span className="flex items-center gap-1">
            <DollarSign size={12} />
            <span className="text-accent-amber font-medium">
              {TIERS.find(t => t.id === selectedTier)?.price}
            </span>
          </span>
        </div>
      </Card>

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
                    <Badge variant="outline" className="text-[10px]">{job.tier}</Badge>
                    {job.findings_count > 0 && (
                      <span className="text-xs text-status-warning font-mono">{job.findings_count} findings</span>
                    )}
                    {isComplete && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => { setSelectedJob(job); loadReport(job.job_id) }}
                          className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-primary-400 transition-colors cursor-pointer"
                          title="View report"
                        >
                          <FileText size={14} />
                        </button>
                        <button
                          onClick={() => downloadPdf(job.job_id)}
                          className="p-1.5 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-accent-amber transition-colors cursor-pointer"
                          title="Download PDF"
                        >
                          <Download size={14} />
                        </button>
                      </div>
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

      {/* Report Viewer */}
      {report && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-starlight-300 flex items-center gap-2">
              <FileText size={14} className="text-accent-amber" />
              Scan Report -- {report.tier}
            </h2>
            <div className="flex items-center gap-4 text-[10px] text-starlight-500">
              <span><Clock size={10} className="inline mr-1" />{report.duration_secs ?? 0}s</span>
              <span><Layers size={10} className="inline mr-1" />{report.pipeline_stages_used ?? 0} stages</span>
              <span><DollarSign size={10} className="inline mr-1" />${(report.cost_usd ?? 0).toFixed(2)}</span>
              <span><Brain size={10} className="inline mr-1" />{(report.models_used ?? []).join(', ') || 'n/a'}</span>
            </div>
          </div>

          {/* Summary */}
          <Card className="p-4">
            <p className="text-sm text-starlight-300 leading-relaxed">{report.summary}</p>
          </Card>

          {/* Findings */}
          <div className="space-y-2">
            {(report.findings ?? []).map((finding, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="bg-midnight-200/60 border border-white/5 rounded-xl p-4"
              >
                <div className="flex items-start gap-3">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${SEVERITY_COLORS[finding.severity]}`}>
                    {finding.severity}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-starlight-100">{finding.title}</p>
                    <p className="text-xs text-starlight-500 mt-0.5 font-mono">
                      {finding.file_path}:{finding.line_number}
                      {finding.cve_id && (
                        <span className="ml-2 text-status-warning">{finding.cve_id}</span>
                      )}
                    </p>
                    <p className="text-xs text-starlight-400 mt-2 leading-relaxed">{finding.description}</p>

                    {finding.remediation && (
                      <div className="mt-3 p-3 bg-status-success/5 border border-status-success/20 rounded-lg">
                        <p className="text-[10px] uppercase tracking-wider text-status-success font-semibold mb-1">Remediation</p>
                        <p className="text-xs text-starlight-300">{finding.remediation}</p>
                      </div>
                    )}

                    {finding.fix_code && (
                      <div className="mt-2">
                        <p className="text-[10px] uppercase tracking-wider text-primary-400 font-semibold mb-1">Suggested Fix</p>
                        <pre className="text-xs text-starlight-300 bg-midnight-400/60 p-3 rounded-lg overflow-x-auto font-mono">
                          {finding.fix_code}
                        </pre>
                      </div>
                    )}

                    {finding.verified && (
                      <div className="mt-2 flex items-center gap-1 text-[10px] text-status-success">
                        <CheckCircle2 size={10} /> Fix verified by pipeline retest
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Scan History */}
      {history.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-starlight-300 flex items-center gap-2">
            <Clock size={14} className="text-starlight-400" />
            Recent Scans
          </h2>
          <div className="space-y-2">
            {history.map((trace: any) => (
              <button
                key={trace.scan_id || trace.id}
                onClick={() => trace.scan_id && loadReport(trace.scan_id)}
                className="w-full text-left bg-midnight-200/40 border border-white/5 rounded-xl p-3 hover:border-white/15 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-starlight-200 truncate font-mono">{trace.target || 'unknown target'}</p>
                    <p className="text-[10px] text-starlight-500 mt-0.5">
                      {trace.tier || 'SCOUT'} · {trace.finding_count ?? 0} findings · {trace.timestamp || trace.created_at || ''}
                    </p>
                  </div>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                    trace.status === 'complete' ? 'bg-status-success/10 text-status-success' :
                    trace.status === 'failed' ? 'bg-status-error/10 text-status-error' :
                    'bg-starlight-500/10 text-starlight-400'
                  }`}>
                    {trace.status || 'complete'}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
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

/**
 * ScanReport -- the completed-scan report viewer. Renders the
 * summary card, empty-clean-scan state, and the per-finding cards
 * (with PoC artifact embeds).
 */
import { motion } from 'framer-motion'
import {
  FileText,
  Clock,
  Layers,
  DollarSign,
  Brain,
  CheckCircle2,
  Shield,
} from 'lucide-react'
import { Card } from '@/components/common'
import PocArtifactBlock from './ScanArtifacts'
import {
  type ScanJob,
  type ScanReport as ScanReportData,
  SEVERITY_COLORS,
  BACKEND_TO_DISPLAY,
} from './types'

interface Props {
  report: ScanReportData
  selectedJob: ScanJob | null
}

export default function ScanReport({ report, selectedJob }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-starlight-300 flex items-center gap-2">
          <FileText size={14} className="text-accent-amber" />
          Scan Report -- {report.tier}
        </h2>
        <div className="flex items-center gap-4 text-[10px] text-starlight-500">
          <span><Clock size={10} className="inline mr-1" />{report.duration_secs ?? 0}s</span>
          <span>
            <Layers size={10} className="inline mr-1" />
            {(report.pipeline_stages_used ?? []).length} stages
          </span>
          <span><DollarSign size={10} className="inline mr-1" />${(report.cost_usd ?? 0).toFixed(2)}</span>
          <span><Brain size={10} className="inline mr-1" />{(report.models_used ?? []).join(', ') || 'n/a'}</span>
        </div>
      </div>

      {/* Summary */}
      <Card className="p-4">
        <p className="text-sm text-starlight-300 leading-relaxed">{report.summary}</p>
      </Card>

      {/* Findings (empty state when scan returned zero) */}
      {(!report.findings || report.findings.length === 0) && (
        <Card className="p-5 border-status-success/20 bg-status-success/5">
          <div className="flex items-start gap-3">
            <CheckCircle2 size={18} className="text-status-success shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-starlight-100">
                Clean scan
              </p>
              <p className="text-xs text-starlight-400 mt-1 leading-relaxed">
                No security findings were surfaced for this scan. Daena
                walked the full {BACKEND_TO_DISPLAY[report.tier] ?? report.tier}
                {' '}tier pipeline ({(report.pipeline_stages_used ?? []).length} stages)
                {selectedJob && (
                  <>
                    {' '}across {selectedJob.files_total} {selectedJob.files_total === 1 ? 'file' : 'files'}
                  </>
                )} and found nothing above the detection threshold.
              </p>
              <p className="text-[11px] text-starlight-500 mt-2">
                This does not mean the target is secure, only that this
                tier did not uncover anything. Consider running a higher
                tier, a supply-chain audit of dependencies, or the
                Founder-tier walkthrough for a broader defensive validation sweep.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Findings */}
      <div className="space-y-2">
        {(report.findings ?? []).map((finding, i) => {
          // Backend sends `location` as "<file>:<line>" or URL.
          // Legacy field `file_path` kept as fallback. CVE refs
          // come as an array on the backend.
          const locStr = finding.location
            ?? (finding.file_path
                ? `${finding.file_path}${finding.line_number ? `:${finding.line_number}` : ''}`
                : '')
          const cves = (finding.cve_references && finding.cve_references.length)
            ? finding.cve_references
            : (finding.cve_id ? [finding.cve_id] : [])
          const cvss = typeof finding.confidence === 'number'
            ? (finding.confidence * 10).toFixed(1)
            : ''
          const isVerified = finding.fix_verified ?? finding.verified

          // Supply-chain findings get a purple/amber accent strip
          // and a "package" chip in the header.
          const isSupplyChain = finding.kind === 'supply_chain'
          // Pull ecosystem + package + version out of a
          // package_reference PoC when present (SupplyChainScanner
          // always attaches one).
          const pkgMeta = finding.poc_artifact?.metadata as
            {ecosystem?: string; package?: string; version?: string} | undefined
          const allCwes = finding.cwe_references ?? []
          // Combine CWE + CVE for header display (CVE wins when both carry the same code).
          const allCodeRefs = [
            ...new Set([...cves, ...allCwes]),
          ]

          return (
            <motion.div
              key={finding.id ?? i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`border rounded-xl p-4 ${
                isSupplyChain
                  ? 'bg-purple-500/5 border-purple-500/30'
                  : 'bg-midnight-200/60 border-white/5'
              }`}
            >
              <div className="flex items-start gap-3">
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${SEVERITY_COLORS[finding.severity]}`}>
                  {finding.severity}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-starlight-100">{finding.title}</p>
                    {isSupplyChain && (
                      <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">
                        supply-chain
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-starlight-500 mt-0.5 font-mono">
                    {locStr}
                    {allCodeRefs.map((ref) => (
                      <span key={ref} className="ml-2 text-status-warning">{ref}</span>
                    ))}
                    {cvss && (
                      <span className="ml-2 text-accent-amber">CVSS {cvss}</span>
                    )}
                  </p>

                  {/* Supply-chain package chip row */}
                  {isSupplyChain && pkgMeta?.package && (
                    <div className="mt-2 flex items-center gap-2 text-[11px] text-starlight-300 font-mono bg-midnight-400/60 rounded-md px-2 py-1 w-fit">
                      <Layers size={11} className="text-purple-400" />
                      <span className="text-purple-300">{pkgMeta.ecosystem ?? 'pkg'}</span>
                      <span>:</span>
                      <span className="text-starlight-100">{pkgMeta.package}</span>
                      {pkgMeta.version && (
                        <>
                          <span>@</span>
                          <span className="text-starlight-300">{pkgMeta.version}</span>
                        </>
                      )}
                    </div>
                  )}

                  <p className="text-xs text-starlight-400 mt-2 leading-relaxed">
                    {finding.description}
                  </p>

                  {finding.explanation && (
                    <p className="text-xs text-starlight-400 mt-2 leading-relaxed italic">
                      {finding.explanation}
                    </p>
                  )}

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

                  {finding.exploit_path && (
                    <div className="mt-2 p-3 bg-accent-amber/5 border border-accent-amber/25 rounded-lg">
                      <p className="text-[10px] uppercase tracking-wider text-accent-amber font-semibold mb-1">
                        Proof-of-impact path
                      </p>
                      <pre className="text-xs text-starlight-300 overflow-x-auto font-mono whitespace-pre-wrap">
                        {finding.exploit_path}
                      </pre>
                    </div>
                  )}

                  {/* Proof-of-Concept artifact (Klyntar zero-FP gate).
                      Different kinds get different renders; all carry
                      a SHA-256 link to the EvidenceChain vault. */}
                  {finding.poc_artifact && (
                    <PocArtifactBlock artifact={finding.poc_artifact} />
                  )}
                  {!finding.poc_artifact && finding.poc_artifact_sha256 && (
                    <div className="mt-2 flex items-center gap-2 text-[10px] text-starlight-500">
                      <Shield size={10} />
                      <span>Evidence: PoC artifact stored at sha256 {finding.poc_artifact_sha256.slice(0, 16)}...</span>
                    </div>
                  )}

                  {isVerified && (
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-status-success">
                      <CheckCircle2 size={10} /> Fix verified by pipeline retest
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

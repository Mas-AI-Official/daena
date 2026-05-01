/**
 * Shared types + constants for the ScanPage and its sub-components.
 *
 * Tier definitions with JSX icons live in ./tiers.tsx. This module
 * stays pure-TS so it can be imported anywhere without dragging in
 * React.
 */
import type React from 'react'

// ── Types ──

export interface ScanTier {
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

export interface ScanJob {
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

export interface PocArtifactDict {
  kind: string                  // curl | http_pair | screenshot | replay_script
                                // | package_reference | diff_hunk | behavioral_trace
  content_type: string
  sha256: string
  description?: string
  target?: string
  reproducible?: boolean
  destructive?: boolean
  safe_handover?: boolean
  created_at?: string
  content?: string              // present when backend included content
  content_encoding?: string     // "base64" for binary
  metadata?: Record<string, unknown>
}

export interface ScanFinding {
  id?: string
  kind?: string                 // "supply_chain" for SupplyChainScanner results
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
  title: string
  file_path?: string            // backend returns `location`; kept for legacy
  location?: string             // backend field: "<path>:<line>" or URL
  line_number?: number
  description: string
  explanation?: string
  remediation?: string
  fix_code?: string
  fix_verified?: boolean
  exploit_path?: string         // T5 Offensive only
  verified?: boolean
  cve_id?: string
  cve_references?: string[]     // backend field
  cwe_references?: string[]     // supply-chain findings carry CWE list
  confidence?: number           // 0.0 to 1.0
  manifest_path?: string        // supply-chain: which package.json
  poc_artifact_sha256?: string
  poc_artifact?: PocArtifactDict
}

export interface ScanReport {
  job_id: string
  tier: string
  findings: ScanFinding[]
  summary: string
  report_pdf_path?: string
  cost_usd: number
  duration_secs: number
  pipeline_stages_used: string[]   // backend sends list of stage names
  models_used: string[]
}

// ── Severity colors ──

export const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-status-error/20 text-status-error border-status-error/30',
  HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  MEDIUM: 'bg-status-warning/20 text-status-warning border-status-warning/30',
  LOW: 'bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30',
  INFO: 'bg-starlight-400/20 text-starlight-400 border-starlight-400/30',
}

export const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  queued: { label: 'Queued', color: 'text-starlight-400' },
  scanning: { label: 'Scanning files...', color: 'text-accent-cyan' },
  analyzing: { label: 'Running pipeline...', color: 'text-primary-400' },
  reporting: { label: 'Generating report...', color: 'text-accent-amber' },
  complete: { label: 'Complete', color: 'text-status-success' },
  failed: { label: 'Failed', color: 'text-status-error' },
}

// Map display tier IDs (T1-T4) to backend enum values (SCOUT/ANALYST/...)
export const TIER_ID_TO_ENUM: Record<string, string> = {
  T1: 'SCOUT',
  T2: 'ANALYST',
  T3: 'OPERATOR',
  T4: 'ARCHITECT',
  T5: 'EVILBOB',
}

// Reverse: backend enum -> friendly display label for active-scan
// cards. Secrecy rule: never surface the internal codename (the T5
// backend enum value) anywhere the operator sees it. Public label
// is "Founder" (access-level framing). The word "Offensive" is
// intentionally avoided because it reads aggressive to customers
// watching demos; operators understand Founder-tier means the
// adversarial depth is unlocked.
export const BACKEND_TO_DISPLAY: Record<string, string> = {
  SCOUT: 'Scout',
  ANALYST: 'Analyst',
  OPERATOR: 'Operator',
  ARCHITECT: 'Architect',
  EVILBOB: 'Founder',
}

// Phase 2.7 (2026-04-25): relativeAgo turns an ISO timestamp into a
// human-readable "5m ago" / "2d ago" badge for the Recent Scans list.
// Used by the redesigned scan-history row -- one of the missing fields
// that made it confusing which scans were recent vs old.
export function relativeAgo(iso: string | number | Date): string {
  try {
    const then = new Date(iso).getTime()
    if (!Number.isFinite(then)) return ''
    // F-DATE-EPOCH defensive: scans persisted before created_at had a
    // server_default come back as 1970-01-01 and render as "1/21/1970"
    // via the toLocaleDateString fallback below. Treat anything before
    // 2020 as missing date until backend backfill runs.
    if (then < 1577836800000) return ''
    const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000))
    if (diffSec < 60) return `${diffSec}s ago`
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 30) return `${diffDay}d ago`
    return new Date(iso).toLocaleDateString()
  } catch {
    return ''
  }
}

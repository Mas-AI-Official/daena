/**
 * Shared TypeScript interfaces + constants for the Security Dashboard
 * tab components. Extracted from SecurityDashboardPage.tsx during the
 * 2026-04-24 split refactor -- no behavior change, just relocation.
 */

export interface DashboardStatus {
  evilbob_active: boolean
  environment: string
  activated_at: string
  activated_by: string
  capabilities: string[]
  shield_status: Record<string, boolean>
  tool_stats: {
    total_known: number
    total_installed: number
    total_capabilities: number
    categories: string[]
    installed_names: string[]
    detection_state?: 'fresh' | 'stale' | 'pending' | 'failed' | string
    refreshing?: boolean
    last_checked?: number | null
    duration_ms?: number
    failure_reason?: string
  }
  scan_history: ScanSummary[]
  self_improvement: {
    total_traces: number
    upgrades_triggered: number
    next_upgrade_at: number
    traces_until_next: number
  }
}

export interface ScanSummary {
  scan_id: string
  target: string
  target_type: string
  total_findings: number
  cycles_used: number
  strategies_tried: string[]
  offensive_mode: boolean
  exploits_succeeded: number
  waf_detected: string
  status?: string
  source?: string
  tier?: string
  created_at?: string | number
  completed_at?: string | number
  finding_count?: number
  duration_secs?: number
  tools_used?: string[]
  severity_counts?: Record<string, number>
}

export interface ToolInfo {
  name: string
  category: string
  description: string
  capabilities: string[]
  installed: boolean
  install_cmd: string
  offensive_only: boolean
  enabled: boolean
  install_state?: 'fresh' | 'stale' | 'pending' | 'failed' | string
}

export interface OpsecStatus {
  gated: boolean
  evilbob_active: boolean
  fingerprint_profile: string
  fingerprint_rotations: number
  request_count: number
  timing_delay_ms: number
  evidence_vault_count: number
  fingerprinting_detected: boolean
  stealth_tools_installed: Record<string, boolean>
  note: string
}

export interface ShieldDetails {
  evilbob_active: boolean
  departments: Record<string, {
    mode: string
    active: boolean
    role_summary: string
  }>
  total_offensive: number
  total_departments: number
}

export type InstalledFilter = 'all' | 'installed' | 'missing'

// ── Category colors ──
export const CATEGORY_COLORS: Record<string, string> = {
  recon: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  scanning: 'text-status-warning bg-status-warning/10 border-status-warning/20',
  exploitation: 'text-status-error bg-status-error/10 border-status-error/20',
  credential: 'text-accent-purple bg-accent-purple/10 border-accent-purple/20',
  network: 'text-primary-400 bg-primary-400/10 border-primary-400/20',
  osint: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  fuzzing: 'text-status-success bg-status-success/10 border-status-success/20',
  wireless: 'text-starlight-400 bg-starlight-400/10 border-starlight-400/20',
  cloud: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  container: 'text-primary-300 bg-primary-300/10 border-primary-300/20',
  web: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  reporting: 'text-starlight-500 bg-starlight-500/10 border-starlight-500/20',
}

// ── Shared StatCard component ──
import type React from 'react'
import { Card } from '@/components/common'

export function StatCard({
  icon, label, value, sub, color,
}: {
  icon: React.ReactNode
  label: string
  value: number
  sub: string
  color: string
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className={color}>{icon}</span>
        <span className="text-xs text-starlight-500">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-starlight-100">{value}</div>
      <div className="text-xs text-starlight-500 mt-0.5">{sub}</div>
    </Card>
  )
}

// ── Shared ScanRow component (used by Overview + Scans tabs) ──
import { Target, ChevronRight } from 'lucide-react'

export function ScanRow({ scan, expanded }: { scan: ScanSummary; expanded?: boolean }) {
  const title = scan.target || `Scan report ${scan.scan_id?.slice(0, 8) || ''}`
  const findings = scan.total_findings ?? scan.finding_count ?? 0
  const severity = scan.severity_counts ?? {}
  const status = scan.status || 'complete'
  const scanType = scan.target_type || scan.tier || scan.source || 'security scan'
  const created = scan.completed_at || scan.created_at
  const createdLabel = typeof created === 'number'
    ? new Date(created * 1000).toLocaleString()
    : created || ''
  const tools = scan.tools_used ?? []

  return (
    <Card className={`
      p-3 transition-colors
      ${expanded ? 'border-primary-500/30' : 'hover:border-starlight-600'}
    `}>
      <div className="flex items-start gap-3">
        <div className={`
          mt-0.5 p-1.5 rounded
          ${scan.offensive_mode ? 'bg-accent-amber/10 text-accent-amber' : 'bg-starlight-800 text-starlight-400'}
        `}>
          <Target size={14} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-medium text-starlight-200">
              {title}
            </span>
            <span className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-starlight-400">
              {status}
            </span>
            {scan.waf_detected && (
              <span className="rounded border border-status-warning/20 bg-status-warning/10 px-1.5 py-0.5 text-[10px] text-status-warning">
                WAF: {scan.waf_detected}
              </span>
            )}
          </div>

          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-starlight-500">
            <span>Type: {scanType}</span>
            <span>Scope: authorized defensive review</span>
            {createdLabel && <span>{createdLabel}</span>}
            {tools.length > 0 && <span>Runtime/tool: {tools.slice(0, 2).join(', ')}</span>}
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as const).map((level) => {
              const count = severity[level] ?? 0
              if (!count) return null
              return (
                <span key={level} className="rounded bg-white/5 px-2 py-0.5 text-[10px] text-starlight-400">
                  {level}: {count}
                </span>
              )
            })}
            {Object.keys(severity).length === 0 && (
              <span className="rounded bg-white/5 px-2 py-0.5 text-[10px] text-starlight-500">
                No severity summary
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="text-center">
            <div className="font-medium text-starlight-200">{findings}</div>
            <div className="text-starlight-600">findings</div>
          </div>
        </div>

        <ChevronRight
          size={14}
          className={`mt-2 text-starlight-600 transition-transform ${expanded ? 'rotate-90' : ''}`}
        />
      </div>
    </Card>
  )
}

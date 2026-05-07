/**
 * SecurityOverview -- the Overview tab.
 *
 * Live counters (tools known, capabilities, scans, next-upgrade), the
 * authorized security mode panel, SHIELD activation summary,
 * browser/evidence controls, recent scans list and self-improvement
 * progress bar.
 *
 * Pure presentational -- all data flows in via props from
 * SecurityDashboardPage / useSecurityDashboardState. No fetches here.
 */
import {
  Shield,
  ShieldAlert,
  Crosshair,
  Package,
  ChevronRight,
  Activity,
  Zap,
  AlertTriangle,
  Target,
  Brain,
  TrendingUp,
  Lock,
  Unlock,
} from 'lucide-react'
import { Card } from '@/components/common'
import {
  type DashboardStatus,
  type OpsecStatus,
  type ShieldDetails,
  ScanRow,
  StatCard,
} from './types'

interface Props {
  status: DashboardStatus
  shields: ShieldDetails | null
  opsec: OpsecStatus | null
}

export default function SecurityOverview({ status, shields, opsec }: Props) {
  const ts = status.tool_stats
  const si = status.self_improvement
  const toolInventoryState = ts.detection_state || 'unknown'
  const toolInventorySub = toolInventoryState === 'pending'
    ? 'checking inventory'
    : toolInventoryState === 'stale'
      ? `${ts.total_installed} installed, refreshing`
      : toolInventoryState === 'failed'
        ? 'inventory check failed'
        : `${ts.total_installed} installed`
  const capabilityLabel = (capability: string) => {
    const labels: Record<string, string> = {
      defensive_scanning: 'defensive scanning',
      offensive_exploitation: 'controlled validation',
      post_exploitation: 'posture impact review',
      evidence_capture: 'evidence capture',
      proxy_rotation: 'network isolation',
      opsec_reasoning: 'operator safety review',
      constraint_bypass: 'control bypass detection',
      target_interaction: 'authorized target interaction',
    }
    return labels[capability] || capability.replace(/_/g, ' ')
  }

  return (
    <div className="space-y-6">
      {/* IaaS CTA Banner */}
      <a
        href="/scan"
        className="block p-4 rounded-xl bg-gradient-to-r from-primary-500/10 via-accent-cyan/5 to-accent-amber/10 border border-primary-500/20 hover:border-primary-500/40 transition-all group"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Crosshair size={20} className="text-primary-400" />
            <div>
              <p className="text-sm font-semibold text-starlight-100 group-hover:text-primary-400 transition-colors">
                Launch Security Intelligence Scan
              </p>
              <p className="text-xs text-starlight-500">
                Submit a target for multi-model verified analysis -- T1 Scout through T5 Founder
              </p>
            </div>
          </div>
          <ChevronRight size={16} className="text-starlight-500 group-hover:text-primary-400 transition-colors" />
        </div>
      </a>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<Package size={20} />}
          label="Tools Known"
          value={ts.total_known}
          sub={toolInventorySub}
          color="text-accent-cyan"
        />
        <StatCard
          icon={<Zap size={20} />}
          label="Capabilities"
          value={ts.total_capabilities}
          sub={`${(ts.categories || []).length} categories`}
          color="text-accent-amber"
        />
        <StatCard
          icon={<Target size={20} />}
          label="Scans Run"
          value={si.total_traces}
          sub={`${si.upgrades_triggered} upgrades`}
          color="text-status-success"
        />
        <StatCard
          icon={<Brain size={20} />}
          label="Next Upgrade"
          value={si.traces_until_next}
          sub="scans remaining"
          color="text-accent-purple"
        />
      </div>

      {/* Mode + capabilities */}
      {status.evilbob_active && (
        <Card className="p-4 border-accent-amber/20 bg-accent-amber/5">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="text-accent-amber" size={18} />
            <span className="text-sm font-medium text-accent-amber">
              Authorized Security Mode Active
            </span>
            {status.activated_at && (
              <span className="text-xs text-starlight-500 ml-auto">
                Since {status.activated_at}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {status.capabilities.map(cap => (
              <span
                key={cap}
                className="px-2 py-0.5 text-xs rounded bg-accent-amber/10
                           text-accent-amber/90 border border-accent-amber/20"
              >
                {capabilityLabel(cap)}
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* SHIELD summary */}
      {shields && shields.total_offensive > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="text-accent-amber" size={18} />
            <span className="text-sm font-medium text-starlight-200">
              SHIELD Defensive Activation
            </span>
            <span className="text-xs text-starlight-500 ml-auto">
              {shields.total_offensive}/{shields.total_departments} departments in elevated review
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {Object.entries(shields.departments).map(([dept, info]) => (
              <div
                key={dept}
                className={`
                  px-3 py-2 rounded-lg text-xs border
                  ${info.active
                    ? 'bg-accent-amber/5 border-accent-amber/20 text-accent-amber'
                    : 'bg-starlight-800/50 border-starlight-700 text-starlight-500'}
                `}
              >
                <div className="font-medium truncate">{dept}</div>
                <div className="opacity-70">
                  {info.active ? 'elevated defensive review' : info.mode}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Browser/evidence control status */}
      {opsec && (
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            {opsec.gated ? (
              <Lock className="text-starlight-500" size={18} />
            ) : (
              <Unlock className="text-accent-amber" size={18} />
            )}
            <span className="text-sm font-medium text-starlight-200">
              Browser Profile and Evidence Controls
            </span>
            <span className="text-xs text-starlight-500 ml-auto">
              {opsec.gated ? 'GATED' : 'READY'}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div>
              <div className="text-xs text-starlight-500">Active profile</div>
              <div className="text-starlight-200 truncate" title={opsec.fingerprint_profile}>
                {opsec.fingerprint_profile || '--'}
              </div>
            </div>
            <div>
              <div className="text-xs text-starlight-500">Rotations</div>
              <div className="text-starlight-200">{opsec.fingerprint_rotations}</div>
            </div>
            <div>
              <div className="text-xs text-starlight-500">Requests</div>
              <div className="text-starlight-200">{opsec.request_count}</div>
            </div>
            <div>
              <div className="text-xs text-starlight-500">Evidence vault</div>
              <div className="text-starlight-200">{opsec.evidence_vault_count}</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(opsec.stealth_tools_installed).map(([tool, installed]) => (
              <span
                key={tool}
                className={`px-2 py-0.5 text-xs rounded border ${
                  installed
                    ? 'bg-status-success/10 border-status-success/30 text-status-success'
                    : 'bg-starlight-800/50 border-starlight-700 text-starlight-500'
                }`}
              >
                {tool} {installed ? 'installed' : 'missing'}
              </span>
            ))}
          </div>

          {opsec.fingerprinting_detected && (
            <div className="mt-3 flex items-center gap-2 text-xs text-status-warning">
              <AlertTriangle size={14} />
              <span>Target detected automation on a prior authorized request -- rotate the browser profile before another defensive check.</span>
            </div>
          )}

          <div className="mt-3 text-xs text-starlight-500 italic">
            {opsec.note}
          </div>
        </Card>
      )}

      {/* Recent scans */}
      {status.scan_history.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="text-accent-cyan" size={18} />
            <span className="text-sm font-medium text-starlight-200">
              Recent Scans
            </span>
          </div>
          <div className="space-y-2">
            {status.scan_history.slice(0, 5).map(scan => (
              <ScanRow key={scan.scan_id} scan={scan} />
            ))}
          </div>
        </Card>
      )}

      {/* Self-improvement progress */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="text-accent-purple" size={18} />
          <span className="text-sm font-medium text-starlight-200">
            Self-Improvement Loop
          </span>
        </div>
        <div className="space-y-2 text-sm text-starlight-400">
          <div className="flex justify-between">
            <span>Total scan traces archived</span>
            <span className="text-starlight-200">{si.total_traces}</span>
          </div>
          <div className="flex justify-between">
            <span>Upgrade cycles triggered</span>
            <span className="text-starlight-200">{si.upgrades_triggered}</span>
          </div>
          <div className="flex justify-between">
            <span>Next upgrade in</span>
            <span className="text-starlight-200">{si.traces_until_next} scans</span>
          </div>
          {/* Progress bar */}
          <div className="w-full bg-starlight-800 rounded-full h-1.5 mt-2">
            <div
              className="bg-accent-purple rounded-full h-1.5 transition-all"
              style={{
                width: `${si.next_upgrade_at > 0
                  ? ((si.next_upgrade_at - si.traces_until_next) / si.next_upgrade_at) * 100
                  : 0}%`
              }}
            />
          </div>
        </div>
      </Card>
    </div>
  )
}

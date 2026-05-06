/**
 * BrainReadinessPanel — Sprint-12A PR-4.
 *
 * One honest panel that tells the operator which brain Daena will
 * actually use right now, what's degraded, and what needs setup.
 * Consumes the read-only endpoints introduced in Sprint-12A:
 *
 *   GET /api/v1/system/runtime-readiness
 *   GET /api/v1/system/qe-readiness
 *
 * Hard rules:
 *   - No secret values. Booleans + metadata only.
 *   - "Ready" is callable + reachable for free_local, configured +
 *     authenticated for metered_api. We never label a runtime
 *     "connected" off key-presence alone.
 *   - QE mode is rendered exactly as the backend emits it
 *     (full / degraded / unavailable). We do NOT round up to "full"
 *     in the UI.
 *
 * Drop into any settings/connections page; the component is self-
 * contained and read-only.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertCircle,
  Brain,
  CheckCircle2,
  Cpu,
  RefreshCw,
  Terminal,
  XCircle,
  ShieldCheck,
} from 'lucide-react'
import { api } from '@/lib/api'

type CostClass = 'free_local' | 'subscription' | 'metered_api' | 'unknown'
type ReadinessState =
  | 'ready'
  | 'configured_untested'
  | 'not_configured'
  | 'detected_offline'
  | 'unknown'
type Kind = 'local_llm' | 'cli_runtime' | 'api_provider' | 'runtime' | 'other'

interface ReadinessItem {
  id: string
  display_name: string
  kind: Kind
  detected: boolean
  configured: boolean
  authenticated_or_key_present: boolean
  reachable: boolean
  callable: boolean
  model_count: number
  cost_class: CostClass
  recommended_role: string
  secondary_roles: string[]
  readiness_state: ReadinessState
  recommended_role_rationale: string
  safe_failure_reason: string | null
  endpoint: string | null
  last_health_check: string | null
}

interface RouterSummary {
  main_brain_id: string | null
  main_brain_cost_class: CostClass | null
  web_grounding_id: string | null
  coder_id: string | null
  researcher_id: string | null
  qe_reviewers_ready: string[]
  qe_mode: 'full' | 'degraded' | 'unavailable'
  qe_mode_reason: string
  next_action: string
}

interface QESlotAssignment {
  slot: string
  intent: string
  runtime_id: string | null
  runtime_display_name: string | null
  fill_source: 'preferred' | 'fallback_role' | 'unfilled'
  rationale: string
}

interface QEReadiness {
  mode: 'full' | 'degraded' | 'unavailable'
  mode_reason: string
  distinct_runtime_ids: string[]
  slot_assignments: QESlotAssignment[]
}

const STATE_STYLE: Record<ReadinessState, { label: string; cls: string; icon: React.ReactNode }> = {
  ready: {
    label: 'Ready',
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    icon: <CheckCircle2 size={11} />,
  },
  configured_untested: {
    label: 'Configured, untested',
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    icon: <AlertCircle size={11} />,
  },
  detected_offline: {
    label: 'Detected, offline',
    cls: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    icon: <XCircle size={11} />,
  },
  not_configured: {
    label: 'Not configured',
    cls: 'bg-starlight-700/40 text-starlight-400 border-starlight-600/30',
    icon: <XCircle size={11} />,
  },
  unknown: {
    label: 'Unknown',
    cls: 'bg-starlight-700/40 text-starlight-400 border-starlight-600/30',
    icon: <AlertCircle size={11} />,
  },
}

const KIND_ICON: Record<Kind, React.ReactNode> = {
  local_llm: <Cpu size={12} />,
  cli_runtime: <Terminal size={12} />,
  api_provider: <Activity size={12} />,
  runtime: <Terminal size={12} />,
  other: <Brain size={12} />,
}

const COST_CLASS_LABEL: Record<CostClass, string> = {
  free_local: 'Free / local',
  subscription: 'Subscription',
  metered_api: 'Metered API',
  unknown: 'Unknown',
}

const QE_MODE_STYLE: Record<QEReadiness['mode'], { label: string; cls: string; icon: React.ReactNode }> = {
  full: {
    label: 'QE Full',
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    icon: <ShieldCheck size={11} />,
  },
  degraded: {
    label: 'QE Degraded',
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    icon: <AlertCircle size={11} />,
  },
  unavailable: {
    label: 'QE Unavailable',
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    icon: <XCircle size={11} />,
  },
}

function StatePill({ state }: { state: ReadinessState }) {
  const meta = STATE_STYLE[state]
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${meta.cls}`}>
      {meta.icon}
      {meta.label}
    </span>
  )
}

function ItemRow({ item }: { item: ReadinessItem }) {
  return (
    <div className="border border-white/5 rounded-md bg-white/[.02] p-2.5">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-starlight-400">{KIND_ICON[item.kind]}</span>
          <span className="text-[11px] font-semibold text-starlight-100 truncate">
            {item.display_name}
          </span>
          <span className="text-[9px] text-starlight-500 font-mono">{item.id}</span>
        </div>
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[9px] text-starlight-500">{COST_CLASS_LABEL[item.cost_class]}</span>
          <StatePill state={item.readiness_state} />
        </div>
      </div>
      <div className="text-[10px] text-starlight-400 mt-1 flex flex-wrap gap-3">
        {item.recommended_role !== 'none' && (
          <span>
            <span className="text-starlight-500">role:</span>{' '}
            <span className="text-accent-teal">{item.recommended_role}</span>
          </span>
        )}
        {item.endpoint && (
          <span className="font-mono truncate" title={item.endpoint}>
            {item.endpoint.length > 40 ? `${item.endpoint.slice(0, 40)}…` : item.endpoint}
          </span>
        )}
        {item.model_count > 0 && (
          <span>
            <span className="text-starlight-500">models:</span> {item.model_count}
          </span>
        )}
      </div>
      {item.safe_failure_reason && item.readiness_state !== 'ready' && (
        <div className="text-[10px] text-amber-300 mt-1 leading-snug">
          {item.safe_failure_reason}
        </div>
      )}
    </div>
  )
}

export function BrainReadinessPanel() {
  const [items, setItems] = useState<ReadinessItem[]>([])
  const [router, setRouter] = useState<RouterSummary | null>(null)
  const [qe, setQe] = useState<QEReadiness | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (refresh: boolean = false) => {
    setLoading(true)
    setError(null)
    try {
      const [readiness, qeRes] = await Promise.all([
        api.get('/system/runtime-readiness', { params: refresh ? { refresh: true } : {} }),
        api.get('/system/qe-readiness', { params: refresh ? { refresh: true } : {} }),
      ])
      setItems(readiness.data?.data?.items ?? [])
      setRouter(readiness.data?.data?.router_summary ?? null)
      setQe(qeRes.data?.data ?? null)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(false)
  }, [load])

  return (
    <div className="glass-panel rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <div className="text-sm font-bold text-starlight-100 flex items-center gap-2">
            <Brain size={14} className="text-accent-teal" /> Brain readiness
          </div>
          <div className="text-[11px] text-starlight-500 max-w-prose">
            Daena's view of which brains are actually ready right now. No paid call has fired.
            "Configured" doesn't mean "callable." This panel never displays secret values.
          </div>
        </div>
        <button
          onClick={() => void load(true)}
          className="text-[10px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
          title="Re-discover runtimes"
        >
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="text-[11px] text-amber-300">Failed to load: {error}</div>}

      {router && (
        <div className="border border-white/10 rounded-lg p-2.5 bg-white/[.02] space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-starlight-500">
              Router decisions
            </span>
            {qe && (
              <span
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${QE_MODE_STYLE[qe.mode].cls}`}
                title={qe.mode_reason}
              >
                {QE_MODE_STYLE[qe.mode].icon}
                {QE_MODE_STYLE[qe.mode].label}
              </span>
            )}
          </div>
          <div className="text-[11px] text-starlight-300 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-0.5">
            <div>
              <span className="text-starlight-500">main brain:</span>{' '}
              <span className={router.main_brain_id ? 'text-accent-teal' : 'text-amber-300'}>
                {router.main_brain_id ?? '— none ready —'}
              </span>
              {router.main_brain_cost_class && (
                <span className="text-[9px] text-starlight-500 ml-1">
                  ({COST_CLASS_LABEL[router.main_brain_cost_class]})
                </span>
              )}
            </div>
            <div>
              <span className="text-starlight-500">web grounding:</span>{' '}
              <span className={router.web_grounding_id ? 'text-accent-teal' : 'text-starlight-500'}>
                {router.web_grounding_id ?? '— none ready —'}
              </span>
            </div>
            <div>
              <span className="text-starlight-500">coder:</span>{' '}
              <span className={router.coder_id ? 'text-accent-teal' : 'text-starlight-500'}>
                {router.coder_id ?? '— none ready —'}
              </span>
            </div>
            <div>
              <span className="text-starlight-500">researcher:</span>{' '}
              <span className={router.researcher_id ? 'text-accent-teal' : 'text-starlight-500'}>
                {router.researcher_id ?? '— none ready —'}
              </span>
            </div>
          </div>
          {router.next_action && (
            <div className="text-[11px] text-amber-200 pt-1 border-t border-white/5 leading-snug">
              <span className="text-amber-400 font-semibold">next: </span>
              {router.next_action}
            </div>
          )}
        </div>
      )}

      {qe && qe.slot_assignments.length > 0 && (
        <details className="border border-white/10 rounded-lg p-2.5 bg-white/[.02]">
          <summary className="cursor-pointer text-[10px] uppercase tracking-wider font-semibold text-starlight-500">
            QE/Council slot assignment
          </summary>
          <div className="mt-2 space-y-1">
            {qe.slot_assignments.map(slot => (
              <div key={slot.slot} className="text-[11px] flex items-start gap-2">
                <span className="font-mono text-[10px] text-starlight-500 w-32 shrink-0">
                  {slot.slot}
                </span>
                <span className={slot.runtime_id ? 'text-starlight-200' : 'text-starlight-500 italic'}>
                  {slot.runtime_id
                    ? `${slot.runtime_display_name} (${slot.fill_source})`
                    : 'unfilled'}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="space-y-1.5">
        {loading && items.length === 0 ? (
          <div className="text-[11px] text-starlight-400">Loading readiness…</div>
        ) : items.length === 0 ? (
          <div className="text-[11px] text-starlight-500 italic">
            No runtimes detected. Click Refresh to probe.
          </div>
        ) : (
          items.map(item => <ItemRow key={item.id} item={item} />)
        )}
      </div>
    </div>
  )
}

export default BrainReadinessPanel

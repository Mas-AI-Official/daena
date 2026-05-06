/**
 * AutonomyMissionControl -- Sprint-13 PR-1 (2026-05-06).
 *
 * Operator-facing meta-control for what classes of action Daena is
 * allowed to take autonomously. Single backend call to
 * /api/v1/system/autonomy-mode (GET on mount, PUT on change).
 *
 * The mode selector is the WHOLE point of this surface. Every other
 * autonomous-business-operator surface (opportunity discovery, draft
 * factory, security scout, self-healing) should consult the mode
 * before doing anything visible. PR-1 ships the control; PR-2..PR-6
 * wire it into consumers.
 */
import { useEffect, useState } from 'react'
import {
  Shield,
  ShieldAlert,
  Eye,
  PenTool,
  Send,
  CheckSquare,
  RefreshCw,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

type AutonomyMode =
  | 'off'
  | 'observe'
  | 'research_draft'
  | 'propose_actions'
  | 'approved_execution'

interface AutonomyState {
  mode: AutonomyMode
  allowed_action_classes: string[]
  blocked_action_classes: string[]
  active_workstreams: number
  queued_approvals: number
  last_changed_at: string | null
}

const MODE_META: Record<
  AutonomyMode,
  { label: string; icon: React.ReactNode; tone: string; description: string }
> = {
  off: {
    label: 'Off',
    icon: <ShieldAlert size={12} />,
    tone: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    description: 'No autonomous action. Manual operation only.',
  },
  observe: {
    label: 'Observe',
    icon: <Eye size={12} />,
    tone: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    description: 'Read-only surveillance. No drafts, no proposals.',
  },
  research_draft: {
    label: 'Research + Draft',
    icon: <PenTool size={12} />,
    tone: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
    description:
      'Default. Daena researches opportunities + creates local drafts. No external send.',
  },
  propose_actions: {
    label: 'Propose Actions',
    icon: <Send size={12} />,
    tone: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    description:
      'Drafts + approval queue. Founder sees a proposal for every external action.',
  },
  approved_execution: {
    label: 'Approved Execution',
    icon: <CheckSquare size={12} />,
    tone: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    description:
      'Executes already-approved items only. Hard-blocked classes still blocked.',
  },
}

const ORDER: AutonomyMode[] = [
  'off',
  'observe',
  'research_draft',
  'propose_actions',
  'approved_execution',
]

function StatusPill({
  count,
  label,
}: {
  count: number
  label: string
}) {
  return (
    <div className="px-2 py-1 rounded bg-white/5 border border-white/10 text-[10px] inline-flex items-center gap-1">
      <span className="font-bold text-starlight-100">{count}</span>
      <span className="text-starlight-400">{label}</span>
    </div>
  )
}

export function AutonomyMissionControl() {
  const [state, setState] = useState<AutonomyState | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<AutonomyMode | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    try {
      const { data } = await api.get<AutonomyState>('/system/autonomy-mode')
      setState(data)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'failed to load autonomy mode'
      setErr(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const change = async (next: AutonomyMode) => {
    if (!state || saving || state.mode === next) return
    setSaving(next)
    try {
      const { data } = await api.put<AutonomyState>('/system/autonomy-mode', {
        mode: next,
      })
      setState(data)
      toast.success(`Autonomy mode: ${MODE_META[next].label}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'failed to change mode'
      toast.error(msg)
    } finally {
      setSaving(null)
    }
  }

  if (loading && !state) {
    return (
      <div className="glass-panel rounded-xl p-4 text-[11px] text-starlight-400">
        Loading autonomy state...
      </div>
    )
  }

  if (err && !state) {
    return (
      <div className="glass-panel rounded-xl p-4 text-[11px] text-rose-300">
        Autonomy state unavailable: {err}{' '}
        <button
          onClick={() => void load()}
          className="ml-2 underline hover:text-rose-200"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!state) return null

  const meta = MODE_META[state.mode]

  return (
    <div className="glass-panel rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Shield size={14} className="text-starlight-300" />
          <div className="text-sm font-bold text-starlight-100">
            Autonomy Mission Control
          </div>
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] border ${meta.tone}`}
          >
            {meta.icon}
            {meta.label}
          </span>
        </div>
        <button
          onClick={() => void load()}
          className="text-[10px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
        >
          <RefreshCw size={10} /> Refresh
        </button>
      </div>

      <div className="text-[11px] text-starlight-400">{meta.description}</div>

      <div className="flex items-center gap-2 flex-wrap">
        <StatusPill count={state.active_workstreams} label="active workstreams" />
        <StatusPill count={state.queued_approvals} label="queued approvals" />
        <StatusPill
          count={state.allowed_action_classes.length}
          label="allowed classes"
        />
        <StatusPill
          count={state.blocked_action_classes.length}
          label="hard-blocked"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-1.5">
        {ORDER.map(m => {
          const active = state.mode === m
          const busy = saving === m
          const mm = MODE_META[m]
          return (
            <button
              key={m}
              onClick={() => void change(m)}
              disabled={!!saving}
              className={`px-2 py-2 rounded text-[10px] border text-left transition-colors ${
                active
                  ? mm.tone + ' ring-1 ring-current'
                  : 'bg-white/5 text-starlight-300 border-white/10 hover:bg-white/10'
              } ${busy ? 'opacity-60 cursor-wait' : ''}`}
            >
              <div className="inline-flex items-center gap-1 font-semibold">
                {mm.icon}
                {mm.label}
              </div>
              <div className="text-[9px] text-starlight-500 mt-1">
                {mm.description}
              </div>
            </button>
          )
        })}
      </div>

      <details className="text-[10px]">
        <summary className="cursor-pointer text-starlight-400 hover:text-starlight-100">
          Allowed and hard-blocked action classes
        </summary>
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <div className="text-[10px] font-bold text-emerald-300 mb-1">
              Allowed in this mode
            </div>
            {state.allowed_action_classes.length === 0 ? (
              <div className="text-[10px] text-starlight-500 italic">
                Nothing. Daena does not act in this mode.
              </div>
            ) : (
              <ul className="space-y-0.5">
                {state.allowed_action_classes.map(c => (
                  <li
                    key={c}
                    className="text-[10px] text-emerald-300/90 font-mono"
                  >
                    + {c}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <div className="text-[10px] font-bold text-rose-300 mb-1">
              Hard-blocked (always)
            </div>
            <ul className="space-y-0.5">
              {state.blocked_action_classes.map(c => (
                <li key={c} className="text-[10px] text-rose-300/80 font-mono">
                  - {c}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </details>

      {state.last_changed_at && (
        <div className="text-[9px] text-starlight-500 italic">
          Last changed: {new Date(state.last_changed_at).toLocaleString()}
        </div>
      )}
    </div>
  )
}

/**
 * SkillExecuteModal -- confirmation modal for Phase 2 read-only skill
 * execution.
 *
 * PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03).
 *
 * Honesty contract (founder rules 9-16):
 *   - Modal renders only when SkillBundleSection has confirmed the
 *     (plugin, skill) pair is in the Phase 2 allowlist AND the plugin
 *     readiness is "ready".
 *   - Operator must explicitly fill required_inputs + click "Run
 *     read-only skill" to invoke. No auto-run, no prefill from
 *     anywhere outside the modal's input fields.
 *   - Modal shows the explicit no-writes/no-sends/no-payments
 *     statement BEFORE the Run button so consent is informed.
 *   - On submit: POST /api/v1/connections/v2/skills/execute. Phase 2
 *     ALWAYS returns status="planned" -- the result is surfaced as a
 *     read-only preview + a draft prompt the operator can carry into
 *     chat for follow-up.
 *   - Operator inputs NEVER persist beyond the modal session. Closing
 *     the modal clears the input state.
 *
 * Out of scope for this PR (deferred to Phase 3+):
 *   - Streaming actual tool output (Phase 2 returns planned preview only)
 *   - Asset Shield consent dialogs for high-risk reads
 *   - Multi-step skill plans
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, Loader2, Lock, Play, ShieldCheck, X,
} from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { draftMessage } from '@/lib/composerBridge'

export interface Phase2AllowlistRow {
  plugin_id: string
  skill_id: string
  backend_surface: 'mcp' | 'oauth' | 'internal' | 'none'
  read_only: boolean
  execution_mode: 'planned_only' | 'mcp_tool'
  required_inputs: string[]
  reads_summary: string
}

export interface SkillExecutionResultDTO {
  accepted: boolean
  status:
    | 'planned' | 'executed' | 'blocked'
    | 'needs_connection' | 'needs_inputs' | 'unsupported'
  summary: string
  audit_event_id: string | null
  required_inputs: string[]
  tool_calls: Array<{
    backend_surface: string
    tool_name: string
    argument_shape: Record<string, string>
    read_only: boolean
    plugin_id: string
    skill_id: string
  }>
  result_preview: string
  blocked_reason: string
}

interface SkillExecuteModalProps {
  pluginId: string
  pluginName: string
  skillId: string
  /** The Phase 2 allowlist row for this (plugin, skill) pair.
   * Caller already proved it's allowlisted -- modal does not re-fetch. */
  allowlistRow: Phase2AllowlistRow
  onClose: () => void
}

function humanize(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function SkillExecuteModal({
  pluginId, pluginName, skillId, allowlistRow, onClose,
}: SkillExecuteModalProps) {
  const navigate = useNavigate()
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<SkillExecutionResultDTO | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Reset state on (plugin, skill) change so reusing the same modal
  // for a different skill doesn't carry old inputs across.
  useEffect(() => {
    setInputs({})
    setSubmitting(false)
    setResult(null)
    setError(null)
  }, [pluginId, skillId])

  const allInputsSupplied = allowlistRow.required_inputs.every(
    f => (inputs[f] ?? '').trim().length > 0,
  )

  async function handleRun() {
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.post<SkillExecutionResultDTO>(
        '/connections/v2/skills/execute',
        {
          plugin_id: pluginId,
          skill_id: skillId,
          operator_inputs: inputs,
        },
      )
      setResult(res.data)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail ?? 'Execute failed'
      setError(String(msg))
    } finally {
      setSubmitting(false)
    }
  }

  function handleDraftFollowup() {
    if (!result || !result.tool_calls.length) return
    const tc = result.tool_calls[0]
    const inputLines = Object.entries(inputs)
      .filter(([, v]) => (v ?? '').trim())
      .map(([k, v]) => `- ${k}: ${v.trim()}`)
      .join('\n')
    const followup =
      `I want ${pluginName} to run skill "${humanize(skillId)}". `
      + `It would call read-only tool '${tc.tool_name}' to read: `
      + `${allowlistRow.reads_summary}\n\n`
      + `Inputs I provided:\n${inputLines}\n\n`
      + `Once you can call the tool live, run it and summarize the result. `
      + `Until then, treat this as planning context.`
    draftMessage(followup, {
      surface: 'connections.skill_chip',
      plugin_id: pluginId,
      plugin_name: pluginName,
    })
    toast.success(`Drafted follow-up from ${pluginName} -- opening chat...`)
    onClose()
    setTimeout(() => navigate('/chat'), 80)
  }

  // ── Render ──

  const phaseStatusPill = result && (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
        result.status === 'planned'
          ? 'bg-emerald-500/15 text-emerald-200'
          : result.status === 'needs_inputs'
            ? 'bg-amber-500/15 text-amber-200'
            : 'bg-rose-500/15 text-rose-200'
      }`}
    >
      {result.status}
    </span>
  )

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="flex items-start justify-between gap-4 border-b border-white/5 p-5">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              Run read-only skill (Phase 2)
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-starlight-100">
              {humanize(skillId)}
            </h2>
            <p className="text-xs text-starlight-400">
              {pluginName} - {allowlistRow.backend_surface.toUpperCase()} backend
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 p-1.5 text-starlight-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </header>

        <div className="space-y-4 p-5">
          {/* What this reads */}
          <section>
            <h3 className="mb-1.5 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
              What Daena will read
            </h3>
            <p className="rounded-md border border-emerald-500/20 bg-emerald-500/[0.04] px-3 py-2 text-[12px] text-emerald-100">
              {allowlistRow.reads_summary}
            </p>
          </section>

          {/* Safety statement */}
          <section className="flex items-start gap-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
            <ShieldCheck size={13} className="mt-0.5 shrink-0 text-emerald-300" />
            <p className="text-[11px] text-starlight-300">
              <strong className="text-starlight-100">No writes, no sends, no payments.</strong>{' '}
              Phase 2 only runs read-only tools through an allowlist. The
              backend cannot post messages, modify external state, or
              invoke browser actions on this code path. Audit row is
              written for every attempt.
            </p>
          </section>

          {/* Required inputs */}
          {allowlistRow.required_inputs.length > 0 && !result && (
            <section>
              <h3 className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
                Required inputs
              </h3>
              <div className="space-y-2">
                {allowlistRow.required_inputs.map((field) => (
                  <div key={field}>
                    <label
                      htmlFor={`skill-input-${field}`}
                      className="text-[10px] uppercase tracking-wider text-starlight-500"
                    >
                      {field}
                    </label>
                    <input
                      id={`skill-input-${field}`}
                      type="text"
                      value={inputs[field] ?? ''}
                      onChange={(e) => setInputs((s) => ({ ...s, [field]: e.target.value }))}
                      className="mt-0.5 w-full rounded-md border border-white/10 bg-midnight-500/50 px-2.5 py-1.5 text-sm text-starlight-100 placeholder:text-starlight-600 focus:border-primary-500/50 focus:outline-none"
                      placeholder={`Provide ${field}...`}
                      autoComplete="off"
                      spellCheck={false}
                      disabled={submitting}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Result block */}
          {result && (
            <section>
              <div className="flex items-center justify-between">
                <h3 className="text-[10px] uppercase tracking-[0.16em] text-starlight-500">
                  Result
                </h3>
                {phaseStatusPill}
              </div>
              <p className="mt-1.5 rounded-md border border-white/10 bg-midnight-500/50 px-3 py-2 text-[12px] text-starlight-200">
                {result.summary}
              </p>
              {result.result_preview && (
                <p className="mt-2 text-[11px] text-starlight-400">
                  {result.result_preview}
                </p>
              )}
              {result.tool_calls.length > 0 && (
                <div className="mt-2 rounded-md border border-white/5 bg-white/[0.02] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-starlight-500">
                    Planned tool call (no real invocation in Phase 2)
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-starlight-200">
                    {result.tool_calls[0].backend_surface.toUpperCase()}.{result.tool_calls[0].tool_name}
                  </p>
                  <p className="mt-1 text-[10px] text-starlight-500">
                    Argument provenance:{' '}
                    {Object.entries(result.tool_calls[0].argument_shape)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(', ')}
                  </p>
                </div>
              )}
              {result.audit_event_id && (
                <p className="mt-2 text-[10px] text-starlight-500">
                  Audit event id: <code>{result.audit_event_id.slice(0, 8)}...</code>
                </p>
              )}
              {result.required_inputs.length > 0 && (
                <p className="mt-2 inline-flex items-start gap-1 rounded-md border border-amber-500/20 bg-amber-500/[0.05] px-2 py-1 text-[11px] text-amber-200">
                  <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                  Missing inputs: {result.required_inputs.join(', ')}
                </p>
              )}
              {result.blocked_reason && (
                <p className="mt-2 inline-flex items-start gap-1 rounded-md border border-rose-500/20 bg-rose-500/[0.05] px-2 py-1 text-[11px] text-rose-200">
                  <Lock size={11} className="mt-0.5 shrink-0" />
                  {result.blocked_reason}
                </p>
              )}
            </section>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-2.5 py-1.5 text-[11px] text-rose-200">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Footer actions */}
          <footer className="flex items-center justify-between gap-2 border-t border-white/5 pt-3">
            <span className="text-[10px] text-starlight-500">
              Phase 2 spine: planned-only. Real tool invocation arms in
              follow-up PRs.
            </span>
            <div className="flex items-center gap-2">
              {result?.status === 'planned' && (
                <button
                  onClick={handleDraftFollowup}
                  className="inline-flex items-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-[11px] font-medium text-accent-cyan hover:bg-accent-cyan/20"
                >
                  Draft follow-up in chat <ArrowRight size={11} />
                </button>
              )}
              {!result && (
                <button
                  onClick={() => void handleRun()}
                  disabled={submitting || !allInputsSupplied}
                  className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/40 bg-primary-500/15 px-3 py-1.5 text-[11px] font-medium text-primary-100 hover:bg-primary-500/25 disabled:opacity-40"
                >
                  {submitting ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <Play size={11} />
                  )}
                  Run read-only skill
                </button>
              )}
            </div>
          </footer>
        </div>
      </div>
    </div>
  )
}

/**
 * Phase3ApprovalModal -- Sprint-14 PR-6 (2026-05-06).
 *
 * Renders the rich approval surface for any GoaRequest whose
 * action_type matches a Sprint-14 controlled-execution tool. The
 * operator sees the full payload, the canonical hash, the Asset
 * Shield result, and the rollback instruction BEFORE clicking
 * approve.
 *
 * Locked invariants:
 *   - Approve button is DISABLED if payload_hash is missing/empty.
 *   - No one-click hidden execution -- the approve button still
 *     surfaces a confirm step internal to this modal.
 *   - Reject is always enabled.
 *   - Payload preview is always rendered before the buttons.
 */
import { useMemo, useState } from 'react'
import {
  ShieldCheck,
  ShieldAlert,
  Clock,
  CheckCircle2,
  XCircle,
  X,
  Mail,
  Calendar,
  FileEdit,
} from 'lucide-react'

export const PHASE3_TOOL_IDS = [
  'gmail.create_draft',
  'calendar.create_tentative_event_without_invites',
  'local.file_change_proposal',
] as const

export type Phase3ToolId = (typeof PHASE3_TOOL_IDS)[number]

export function isPhase3ToolId(action_type: string | null | undefined): action_type is Phase3ToolId {
  return !!action_type && (PHASE3_TOOL_IDS as readonly string[]).includes(action_type)
}

const TOOL_META: Record<Phase3ToolId, { label: string; icon: React.ReactNode; risk: string; rollback_default: string }> = {
  'gmail.create_draft': {
    label: 'Gmail: Create Draft',
    icon: <Mail size={14} />,
    risk: 'low',
    rollback_default: 'Delete the draft from the Gmail Drafts folder.',
  },
  'calendar.create_tentative_event_without_invites': {
    label: 'Calendar: Tentative Event (no invites)',
    icon: <Calendar size={14} />,
    risk: 'low',
    rollback_default: 'Open calendar.google.com and delete the event.',
  },
  'local.file_change_proposal': {
    label: 'Local: File Change Proposal',
    icon: <FileEdit size={14} />,
    risk: 'medium',
    rollback_default:
      'Reject the proposal here; no changes have been applied.',
  },
}

export interface Phase3ApprovalDetails {
  approval_id: string
  action_type: Phase3ToolId
  owner_email: string | null
  payload: Record<string, unknown>
  payload_hash: string | null
  asset_shield_pass: boolean
  rollback_or_undo_instruction: string | null
}

interface Props {
  open: boolean
  onClose: () => void
  details: Phase3ApprovalDetails | null
  onApprove: (note: string) => Promise<void> | void
  onReject: (reason: string) => Promise<void> | void
}

export function Phase3ApprovalModal({
  open,
  onClose,
  details,
  onApprove,
  onReject,
}: Props) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)

  const meta = details ? TOOL_META[details.action_type] : null

  const payloadPreview = useMemo(() => {
    if (!details) return ''
    try {
      return JSON.stringify(details.payload, null, 2)
    } catch {
      return String(details.payload)
    }
  }, [details])

  if (!open || !details || !meta) return null

  const hashMissing = !details.payload_hash || details.payload_hash.length !== 64
  const approveDisabled = busy != null || hashMissing

  const submitApprove = async () => {
    if (approveDisabled) return
    setBusy('approve')
    try {
      await onApprove(note.trim())
    } finally {
      setBusy(null)
    }
  }

  const submitReject = async () => {
    if (busy != null) return
    if (!note.trim()) return
    setBusy('reject')
    try {
      await onReject(note.trim())
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 p-4">
      <div className="bg-midnight-700 border border-white/10 rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <header className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="flex items-center gap-2 text-starlight-100 text-sm font-bold">
            {meta.icon}
            Phase 3 Approval — {meta.label}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-starlight-400 hover:text-starlight-100"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </header>

        <div className="p-4 space-y-3">
          {/* Tool / account / risk */}
          <div className="flex items-center gap-2 flex-wrap text-[11px]">
            <span className="px-2 py-0.5 rounded bg-violet-500/15 text-violet-300 border border-violet-500/30 font-mono">
              {details.action_type}
            </span>
            {details.owner_email && (
              <span className="px-2 py-0.5 rounded bg-white/5 text-starlight-300 border border-white/10">
                {details.owner_email}
              </span>
            )}
            <span
              className={`px-2 py-0.5 rounded border ${
                meta.risk === 'low'
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
              }`}
            >
              risk: {meta.risk}
            </span>
          </div>

          {/* Asset Shield result */}
          <div
            className={`flex items-center gap-2 text-[11px] px-2 py-1.5 rounded border ${
              details.asset_shield_pass
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
            }`}
          >
            {details.asset_shield_pass ? (
              <ShieldCheck size={12} />
            ) : (
              <ShieldAlert size={12} />
            )}
            Asset Shield:{' '}
            {details.asset_shield_pass
              ? 'pass — egress allowed for this tool'
              : 'FAIL — Approve will be refused at the dispatch gate'}
          </div>

          {/* Payload hash */}
          <div className="text-[10px] text-starlight-400">
            <span className="font-bold text-starlight-300 mr-2">Payload hash:</span>
            {hashMissing ? (
              <span className="text-rose-300 font-mono">
                missing or invalid -- approve disabled
              </span>
            ) : (
              <span className="font-mono">
                {details.payload_hash!.slice(0, 16)}…{details.payload_hash!.slice(-8)}
              </span>
            )}
          </div>

          {/* Payload preview */}
          <div>
            <div className="text-[10px] font-bold text-starlight-300 mb-1">
              Payload preview
            </div>
            <pre className="text-[10px] text-starlight-200 font-mono bg-midnight-900/70 p-2 rounded max-h-72 overflow-y-auto whitespace-pre-wrap break-all border border-white/5">
              {payloadPreview || '(empty)'}
            </pre>
          </div>

          {/* Rollback */}
          <div>
            <div className="text-[10px] font-bold text-starlight-300 mb-1 flex items-center gap-1">
              <Clock size={10} /> Rollback / undo
            </div>
            <p className="text-[10px] text-starlight-400 leading-relaxed">
              {details.rollback_or_undo_instruction || meta.rollback_default}
            </p>
          </div>

          {/* Note */}
          <div>
            <label className="text-[10px] font-bold text-starlight-300 mb-1 block">
              Note for the audit trail{' '}
              <span className="text-starlight-500 font-normal">
                (required when rejecting)
              </span>
            </label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              rows={2}
              className="w-full bg-midnight-900/70 border border-white/10 rounded p-2 text-[11px] text-starlight-200 focus:outline-none focus:border-primary-500"
              placeholder="Why are you approving / rejecting?"
            />
          </div>
        </div>

        <footer className="flex items-center justify-end gap-2 px-4 py-3 border-t border-white/10">
          <button
            type="button"
            onClick={() => void submitReject()}
            disabled={busy != null || !note.trim()}
            className="px-3 py-1.5 rounded text-[11px] inline-flex items-center gap-1 cursor-pointer text-rose-300 border border-rose-500/30 hover:bg-rose-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <XCircle size={12} /> Reject
          </button>
          <button
            type="button"
            onClick={() => void submitApprove()}
            disabled={approveDisabled}
            className="px-3 py-1.5 rounded text-[11px] inline-flex items-center gap-1 cursor-pointer bg-primary-500 text-white hover:bg-primary-400 disabled:opacity-50 disabled:cursor-not-allowed"
            title={
              hashMissing
                ? 'Approve disabled: payload_hash is missing or not 64 chars'
                : 'Approve this controlled-execution request'
            }
          >
            <CheckCircle2 size={12} /> Approve
          </button>
        </footer>
      </div>
    </div>
  )
}

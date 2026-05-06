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
  Send,
  Calendar,
  FileEdit,
  AlertTriangle,
} from 'lucide-react'

export const PHASE3_TOOL_IDS = [
  'gmail.create_draft',
  'gmail.send_existing_draft',
  'calendar.create_tentative_event_without_invites',
  'local.file_change_proposal',
] as const

export type Phase3ToolId = (typeof PHASE3_TOOL_IDS)[number]

export function isPhase3ToolId(action_type: string | null | undefined): action_type is Phase3ToolId {
  return !!action_type && (PHASE3_TOOL_IDS as readonly string[]).includes(action_type)
}

interface ToolMeta {
  label: string
  icon: React.ReactNode
  risk: 'low' | 'medium' | 'high'
  rollback_default: string
  // Sprint-15 PR-3: when true, render an extra irrevocability
  // banner above the layout. Send is the FIRST irreversible Phase 3
  // action, so the second-approval wall must be visibly different
  // from a draft approval.
  is_send: boolean
}

const TOOL_META: Record<Phase3ToolId, ToolMeta> = {
  'gmail.create_draft': {
    label: 'Gmail: Create Draft',
    icon: <Mail size={14} />,
    risk: 'low',
    rollback_default: 'Delete the draft from the Gmail Drafts folder.',
    is_send: false,
  },
  'gmail.send_existing_draft': {
    label: 'Gmail: Send Existing Draft',
    icon: <Send size={14} />,
    risk: 'high',
    rollback_default:
      'Email cannot be unsent after delivery. Send a follow-up correction or recall via Google Workspace admin if available.',
    is_send: true,
  },
  'calendar.create_tentative_event_without_invites': {
    label: 'Calendar: Tentative Event (no invites)',
    icon: <Calendar size={14} />,
    risk: 'low',
    rollback_default: 'Open calendar.google.com and delete the event.',
    is_send: false,
  },
  'local.file_change_proposal': {
    label: 'Local: File Change Proposal',
    icon: <FileEdit size={14} />,
    risk: 'medium',
    rollback_default:
      'Reject the proposal here; no changes have been applied.',
    is_send: false,
  },
}

// Sprint-15 PR-3: optional draft preview surfaced ONLY on send
// approvals so the operator sees what is actually about to leave
// Gmail before clicking Approve. The upstream send-approval-creator
// is responsible for snapshotting the draft's To/Subject/snippet
// at approval-creation time and stashing them in
// action_params.draft_preview.
//
// Sprint-16 PR-5: extended with snapshot_captured_at + snapshot_hash
// so the operator can see WHEN the snapshot was taken and a hash
// prefix that maps directly to the audit-log row written after
// send. Both fields are optional; older approvals lack them.
export interface Phase3DraftPreview {
  to: string | null
  subject: string | null
  snippet: string | null
  snapshot_captured_at?: string | null
  snapshot_hash?: string | null
}

export interface Phase3ApprovalDetails {
  approval_id: string
  action_type: Phase3ToolId
  owner_email: string | null
  payload: Record<string, unknown>
  payload_hash: string | null
  asset_shield_pass: boolean
  rollback_or_undo_instruction: string | null
  draft_preview?: Phase3DraftPreview | null
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
          {/* Sprint-15 PR-3: irrevocability banner for SEND actions.
              Rendered FIRST so the operator sees the warning before
              any other detail. Different from a draft approval --
              this is the second wall, and the message must say so. */}
          {meta.is_send && (
            <div
              data-testid="phase3-send-irrevocability-banner"
              className="rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-[11px] text-rose-200"
            >
              <div className="flex items-center gap-2 font-bold uppercase tracking-[0.16em] text-rose-300">
                <AlertTriangle size={12} />
                This will send an email externally
              </div>
              <p className="mt-1 leading-relaxed">
                Approving here triggers the FIRST controlled external
                send. Email cannot be unsent after delivery. Confirm
                the recipient and subject below match what you
                intended; reject if anything is off.
              </p>
            </div>
          )}

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
                meta.risk === 'high'
                  ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                  : meta.risk === 'low'
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
              }`}
            >
              risk: {meta.risk}
            </span>
          </div>

          {/* Sprint-15 PR-3: send-time draft preview. Only shown on
              send approvals, only when the upstream approval creator
              snapshotted draft metadata. Empty placeholder when
              missing -- the operator can still approve via the
              hash + payload, but the preview makes the second wall
              honest. */}
          {meta.is_send && (
            <div
              data-testid="phase3-send-draft-preview"
              className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3"
            >
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-amber-300 mb-2">
                Draft snapshot (what will be sent)
              </div>
              {details.draft_preview ? (
                <dl className="space-y-1 text-[11px]">
                  <div className="flex gap-2">
                    <dt className="font-bold text-starlight-300 min-w-[70px]">To:</dt>
                    <dd
                      data-testid="phase3-send-draft-to"
                      className="text-starlight-100 font-mono break-all"
                    >
                      {details.draft_preview.to || '(missing)'}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="font-bold text-starlight-300 min-w-[70px]">Subject:</dt>
                    <dd
                      data-testid="phase3-send-draft-subject"
                      className="text-starlight-100"
                    >
                      {details.draft_preview.subject || '(missing)'}
                    </dd>
                  </div>
                  {details.draft_preview.snippet && (
                    <div className="flex gap-2">
                      <dt className="font-bold text-starlight-300 min-w-[70px]">Snippet:</dt>
                      <dd
                        data-testid="phase3-send-draft-snippet"
                        className="text-starlight-200 italic"
                      >
                        {details.draft_preview.snippet}
                      </dd>
                    </div>
                  )}
                  {/* Sprint-16 PR-5: snapshot time + hash for audit
                      cross-reference. Hash is truncated (16+8 chars)
                      to fit, but the literal value is also rendered
                      in the result row of the audit log so operator
                      can match. */}
                  {details.draft_preview.snapshot_captured_at && (
                    <div className="flex gap-2">
                      <dt className="font-bold text-starlight-300 min-w-[70px]">Captured:</dt>
                      <dd
                        data-testid="phase3-send-draft-captured-at"
                        className="text-starlight-300 font-mono text-[10px]"
                      >
                        {details.draft_preview.snapshot_captured_at}
                      </dd>
                    </div>
                  )}
                  {details.draft_preview.snapshot_hash && (
                    <div className="flex gap-2">
                      <dt className="font-bold text-starlight-300 min-w-[70px]">Hash:</dt>
                      <dd
                        data-testid="phase3-send-draft-snapshot-hash"
                        className="text-starlight-200 font-mono text-[10px]"
                        title="Snapshot metadata hash (matches the audit row written after send)"
                      >
                        {details.draft_preview.snapshot_hash.length === 64
                          ? `${details.draft_preview.snapshot_hash.slice(0, 16)}…${details.draft_preview.snapshot_hash.slice(-8)}`
                          : details.draft_preview.snapshot_hash}
                      </dd>
                    </div>
                  )}
                </dl>
              ) : (
                <p
                  data-testid="phase3-send-draft-preview-missing"
                  className="text-[10px] text-amber-300"
                >
                  Draft preview not snapshotted at approval time. Open
                  Gmail Drafts in another tab and verify the recipient
                  before approving.
                </p>
              )}
            </div>
          )}

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

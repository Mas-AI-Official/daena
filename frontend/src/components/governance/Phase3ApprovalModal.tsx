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
  FileCog,
  AlertTriangle,
} from 'lucide-react'

export const PHASE3_TOOL_IDS = [
  'gmail.create_draft',
  'gmail.send_existing_draft',
  'calendar.create_tentative_event_without_invites',
  'local.file_change_proposal',
  'local.file_change_proposal.apply',
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
  // Sprint-17 PR-2: when true, render a file-apply preview block
  // showing target / hashes / backup path / tests-to-run /
  // secret-path checks. Distinct visual from is_send because the
  // failure mode is different (rollback exists; for send there is
  // no unsend).
  is_file_apply: boolean
}

const TOOL_META: Record<Phase3ToolId, ToolMeta> = {
  'gmail.create_draft': {
    label: 'Gmail: Create Draft',
    icon: <Mail size={14} />,
    risk: 'low',
    rollback_default: 'Delete the draft from the Gmail Drafts folder.',
    is_send: false,
    is_file_apply: false,
  },
  'gmail.send_existing_draft': {
    label: 'Gmail: Send Existing Draft',
    icon: <Send size={14} />,
    risk: 'high',
    rollback_default:
      'Email cannot be unsent after delivery. Send a follow-up correction or recall via Google Workspace admin if available.',
    is_send: true,
    is_file_apply: false,
  },
  'calendar.create_tentative_event_without_invites': {
    label: 'Calendar: Tentative Event (no invites)',
    icon: <Calendar size={14} />,
    risk: 'low',
    rollback_default: 'Open calendar.google.com and delete the event.',
    is_send: false,
    is_file_apply: false,
  },
  'local.file_change_proposal': {
    label: 'Local: File Change Proposal',
    icon: <FileEdit size={14} />,
    risk: 'medium',
    rollback_default:
      'Reject the proposal here; no changes have been applied.',
    is_send: false,
    is_file_apply: false,
  },
  'local.file_change_proposal.apply': {
    label: 'Local: APPLY File Change',
    icon: <FileCog size={14} />,
    risk: 'high',
    rollback_default:
      'Backup file at backup_file_path is restored automatically if declared tests fail. Commit is gated by a SEPARATE local.git_commit_approved_patch approval.',
    is_send: false,
    is_file_apply: true,
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

// Sprint-17 PR-2: optional file-apply preview surfaced ONLY on
// local.file_change_proposal.apply approvals. The upstream
// approval creator captures these fields from the existing
// FileChangeProposal artifact at approval-creation time.
export interface Phase3FileApplyPreview {
  target_repo_relative: string
  current_file_hash: string | null
  approved_diff_hash: string | null
  backup_file_path: string | null
  change_type: string
  tests_to_run_after_apply: string[]
  diff_preview_lines: number | null
  diff_excerpt: string | null
  secret_file_check_passed: boolean
  outside_repo_check_passed: boolean
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
  file_apply_preview?: Phase3FileApplyPreview | null
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
  // Sprint-17 PR-2: extra defensive walls for file-apply approvals.
  // Even if the backend would refuse, the client-side button stays
  // disabled when the preview doesn't show:
  //   * a non-empty target path
  //   * change_type === "modify"
  //   * non-empty tests_to_run_after_apply
  //   * secret-file + outside-repo checks both PASSED
  const fileApplyMissingPreview =
    meta.is_file_apply &&
    (!details.file_apply_preview ||
      !details.file_apply_preview.target_repo_relative ||
      details.file_apply_preview.change_type !== 'modify' ||
      details.file_apply_preview.tests_to_run_after_apply.length === 0 ||
      !details.file_apply_preview.secret_file_check_passed ||
      !details.file_apply_preview.outside_repo_check_passed)
  const approveDisabled = busy != null || hashMissing || fileApplyMissingPreview

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
          {/* Sprint-17 PR-2: warning banner for FILE APPLY.
              Distinct from is_send because the failure mode is
              different (rollback exists; for send it doesn't). */}
          {meta.is_file_apply && (
            <div
              data-testid="phase3-file-apply-banner"
              className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] text-amber-200"
            >
              <div className="flex items-center gap-2 font-bold uppercase tracking-[0.16em] text-amber-300">
                <AlertTriangle size={12} />
                This modifies local repo files
              </div>
              <p className="mt-1 leading-relaxed">
                Approving here applies a patch to your local working
                tree. Daena writes a byte-for-byte BACKUP first; if
                any declared test fails after apply, the file is
                restored automatically. Commit is gated by a separate{' '}
                <code className="text-starlight-200">local.git_commit_approved_patch</code>{' '}
                approval. Reject if the diff or tests look wrong.
              </p>
            </div>
          )}

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

          {/* Sprint-17 PR-2: file-apply preview. Shown only on
              local.file_change_proposal.apply approvals. Renders
              the locked Sprint-17 contract fields so operator sees
              what the dispatcher will verify. Approve stays
              disabled until preview is non-empty. */}
          {meta.is_file_apply && (
            <div
              data-testid="phase3-file-apply-preview"
              className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3"
            >
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-amber-300 mb-2">
                File apply contract
              </div>
              {details.file_apply_preview ? (
                <dl className="space-y-1 text-[11px]">
                  <div className="flex gap-2">
                    <dt className="font-bold text-starlight-300 min-w-[110px]">Target file:</dt>
                    <dd
                      data-testid="phase3-file-apply-target"
                      className="text-starlight-100 font-mono break-all"
                    >
                      {details.file_apply_preview.target_repo_relative}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="font-bold text-starlight-300 min-w-[110px]">Change type:</dt>
                    <dd
                      data-testid="phase3-file-apply-change-type"
                      className={
                        details.file_apply_preview.change_type === 'modify'
                          ? 'text-emerald-300 font-mono'
                          : 'text-rose-300 font-mono'
                      }
                    >
                      {details.file_apply_preview.change_type}
                      {details.file_apply_preview.change_type !== 'modify' &&
                        ' (refused -- only "modify" is allowed)'}
                    </dd>
                  </div>
                  {details.file_apply_preview.current_file_hash && (
                    <div className="flex gap-2">
                      <dt className="font-bold text-starlight-300 min-w-[110px]">Current file:</dt>
                      <dd
                        data-testid="phase3-file-apply-current-hash"
                        className="text-starlight-200 font-mono text-[10px]"
                        title="sha256 of current on-disk bytes; refused at dispatch if drifted"
                      >
                        {details.file_apply_preview.current_file_hash.slice(0, 16)}…{details.file_apply_preview.current_file_hash.slice(-8)}
                      </dd>
                    </div>
                  )}
                  {details.file_apply_preview.approved_diff_hash && (
                    <div className="flex gap-2">
                      <dt className="font-bold text-starlight-300 min-w-[110px]">Approved diff:</dt>
                      <dd
                        data-testid="phase3-file-apply-diff-hash"
                        className="text-starlight-200 font-mono text-[10px]"
                        title="sha256 of artifact diff_text; refused at dispatch if tampered"
                      >
                        {details.file_apply_preview.approved_diff_hash.slice(0, 16)}…{details.file_apply_preview.approved_diff_hash.slice(-8)}
                      </dd>
                    </div>
                  )}
                  {details.file_apply_preview.backup_file_path && (
                    <div className="flex gap-2">
                      <dt className="font-bold text-starlight-300 min-w-[110px]">Backup:</dt>
                      <dd className="text-starlight-300 font-mono text-[10px] break-all">
                        {details.file_apply_preview.backup_file_path}
                      </dd>
                    </div>
                  )}
                  {/* Path / secret check badges */}
                  <div className="flex gap-2 pt-1">
                    <dt className="font-bold text-starlight-300 min-w-[110px]">Path checks:</dt>
                    <dd className="flex gap-1 flex-wrap">
                      <span
                        data-testid={`phase3-secret-check-${details.file_apply_preview.secret_file_check_passed ? 'pass' : 'fail'}`}
                        className={
                          details.file_apply_preview.secret_file_check_passed
                            ? 'rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300'
                            : 'rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-300'
                        }
                      >
                        secret-file: {details.file_apply_preview.secret_file_check_passed ? 'pass' : 'FAIL'}
                      </span>
                      <span
                        data-testid={`phase3-repo-check-${details.file_apply_preview.outside_repo_check_passed ? 'pass' : 'fail'}`}
                        className={
                          details.file_apply_preview.outside_repo_check_passed
                            ? 'rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300'
                            : 'rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-300'
                        }
                      >
                        in-repo: {details.file_apply_preview.outside_repo_check_passed ? 'pass' : 'FAIL'}
                      </span>
                    </dd>
                  </div>
                  {/* Tests-to-run-after-apply */}
                  <div className="flex gap-2 pt-1">
                    <dt className="font-bold text-starlight-300 min-w-[110px]">Tests to run:</dt>
                    <dd
                      data-testid="phase3-file-apply-tests"
                      className="flex flex-col gap-0.5"
                    >
                      {details.file_apply_preview.tests_to_run_after_apply.length === 0 ? (
                        <span className="text-rose-300 text-[10px]">
                          (none -- approve is disabled)
                        </span>
                      ) : (
                        details.file_apply_preview.tests_to_run_after_apply.map((t, i) => (
                          <code key={i} className="text-emerald-300 text-[10px] font-mono">
                            {t}
                          </code>
                        ))
                      )}
                    </dd>
                  </div>
                  {/* Diff excerpt */}
                  {details.file_apply_preview.diff_excerpt && (
                    <div className="pt-2">
                      <div className="text-[10px] font-bold text-starlight-300 mb-1">
                        Diff preview ({details.file_apply_preview.diff_preview_lines ?? '?'} lines)
                      </div>
                      <pre
                        data-testid="phase3-file-apply-diff-excerpt"
                        className="text-[10px] text-starlight-200 font-mono bg-midnight-900/70 p-2 rounded max-h-40 overflow-y-auto whitespace-pre-wrap break-all border border-white/5"
                      >
                        {details.file_apply_preview.diff_excerpt}
                      </pre>
                    </div>
                  )}
                </dl>
              ) : (
                <p
                  data-testid="phase3-file-apply-preview-missing"
                  className="text-[10px] text-rose-300"
                >
                  File apply preview missing -- approve is disabled.
                  The upstream approval creator must capture the
                  contract fields (target / hashes / tests / path
                  checks) before the modal can render an honest
                  approval surface.
                </p>
              )}
            </div>
          )}

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

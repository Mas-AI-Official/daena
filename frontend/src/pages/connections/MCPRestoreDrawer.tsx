/**
 * MCPRestoreDrawer -- list + restore Daena backup files.
 *
 * PR-CONN-MCP-INSTALL-RESTORE (2026-05-02). Counterpart to
 * MCPInstallDrawer: when Daena writes into a CLI's MCP config, it
 * also lays down a timestamped backup. This drawer lets the operator
 * roll back by picking one.
 *
 * Honesty:
 *   - File contents are NEVER fetched. The list shows filename +
 *     timestamp + size + valid_json only. Operator chooses; the
 *     backend reads + restores.
 *   - Restore ALWAYS creates a pre-restore backup of the CURRENT
 *     config first (server-side) so the operator can roll forward
 *     by re-restoring.
 *   - Malformed backups are listed with a red "JSON invalid" pill
 *     and the Restore button is disabled.
 *   - Path basenames only. Full filesystem paths are shown ONCE
 *     (the config_path label) but never inside the per-backup row.
 */

import { useEffect, useRef, useState } from "react"
import {
  AlertTriangle, ArrowLeft, CheckCircle2, Clock, FileWarning,
  Loader2, RotateCcw, X,
} from "lucide-react"

import {
  type BackupEntry,
  type BackupListReport,
  type BackupRestoreReport,
  type McpInstallTarget,
  listMcpBackups,
  restoreMcpBackup,
} from "@/hooks/useMarketplace"

interface MCPRestoreDrawerProps {
  target: McpInstallTarget
  targetDisplayName: string
  onClose: () => void
  onComplete?: (result: BackupRestoreReport) => void
}

type Step = "list" | "confirm" | "restoring" | "done"

export default function MCPRestoreDrawer({
  target, targetDisplayName, onClose, onComplete,
}: MCPRestoreDrawerProps) {
  const [step, setStep] = useState<Step>("list")
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  // PR-A11Y-PHASE32: overlay focus contract -- move focus into the panel on open,
  // restore to the opener on close. Nested under MCPInstallDrawer so capture/
  // restore is LIFO per overlay (WCAG 2.4.3 / 2.1.2 / WAI-ARIA dialog pattern).
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null
    const focusTimer = setTimeout(() => {
      const panel = panelRef.current
      if (panel && !panel.contains(document.activeElement)) panel.focus()
    }, 50)
    return () => { clearTimeout(focusTimer); previousFocusRef.current?.focus?.() }
  }, [])
  const [listing, setListing] = useState<BackupListReport | null>(null)
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [selected, setSelected] = useState<BackupEntry | null>(null)
  const [restoreResult, setRestoreResult] = useState<BackupRestoreReport | null>(null)
  const [restoreError, setRestoreError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setListLoading(true)
    setListError(null)
    void (async () => {
      const res = await listMcpBackups(target)
      if (cancelled) return
      setListLoading(false)
      if (res.ok && res.data) setListing(res.data)
      else setListError(res.error ?? "Failed to list backups")
    })()
    return () => { cancelled = true }
  }, [target])

  async function handleRestore() {
    if (!selected) return
    setStep("restoring")
    setRestoreError(null)
    const res = await restoreMcpBackup({
      target, backup_filename: selected.filename,
    })
    if (res.ok && res.data) {
      setRestoreResult(res.data)
      setStep("done")
      if (res.data.success) onComplete?.(res.data)
    } else {
      setRestoreError(res.error ?? "Restore failed")
      setStep("confirm")
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Restore MCP backup for ${targetDisplayName}`}
        tabIndex={-1}
        onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }}
        className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl focus:outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/5 p-5">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              Restore MCP backup
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-starlight-100">
              {targetDisplayName}
            </h2>
            <p className="text-xs text-starlight-400">
              Roll back to a previous version of this CLI's MCP config.
              Daena always writes a fresh pre-restore backup of the
              CURRENT state before overwriting.
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

        <div className="space-y-5 p-5">
          {step === "list" && (
            <ListBlock
              listing={listing}
              loading={listLoading}
              error={listError}
              selected={selected}
              onSelect={setSelected}
              onContinue={() => selected && setStep("confirm")}
              onClose={onClose}
            />
          )}

          {step === "confirm" && selected && (
            <ConfirmBlock
              selected={selected}
              listing={listing}
              error={restoreError}
              onBack={() => { setStep("list"); setRestoreError(null) }}
              onConfirm={() => void handleRestore()}
            />
          )}

          {step === "restoring" && (
            <div className="rounded-lg border border-white/5 bg-white/[0.02] py-6 text-center text-xs text-starlight-400">
              <Loader2 size={14} className="mr-2 inline animate-spin" />
              Writing pre-restore backup + atomic rename...
            </div>
          )}

          {step === "done" && restoreResult && (
            <DoneBlock result={restoreResult} onClose={onClose} />
          )}
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────
// Sub-blocks
// ──────────────────────────────────────────────────────────────────

function ListBlock({
  listing, loading, error, selected, onSelect, onContinue, onClose,
}: {
  listing: BackupListReport | null
  loading: boolean
  error: string | null
  selected: BackupEntry | null
  onSelect: (b: BackupEntry) => void
  onContinue: () => void
  onClose: () => void
}) {
  if (loading) {
    return (
      <div className="rounded-lg border border-white/5 bg-white/[0.02] py-6 text-center text-xs text-starlight-400">
        <Loader2 size={14} className="mr-2 inline animate-spin" />
        Listing backups...
      </div>
    )
  }
  if (error || !listing) {
    return (
      <FailureBlock message={error ?? "List unavailable"} onClose={onClose} />
    )
  }
  if (listing.failure_reason) {
    return (
      <FailureBlock
        message={listing.failure_reason}
        onClose={onClose}
        configPath={listing.config_path}
      />
    )
  }
  if (listing.backups.length === 0) {
    return (
      <Section title="No backups found">
        <p className="text-xs text-starlight-300">
          Daena hasn't written any backup files for{" "}
          <strong>{listing.target_display_name}</strong> yet. Backups
          are created automatically when you install or update an MCP
          plugin.
        </p>
        {listing.config_path && (
          <p className="mt-2 text-[11px] text-starlight-500">
            Looked next to: <code>{listing.config_path}</code>
          </p>
        )}
        <FooterRow>
          <button
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
          >
            Close
          </button>
        </FooterRow>
      </Section>
    )
  }
  return (
    <>
      <Section title="Pick a backup to restore">
        <p className="text-[11px] text-starlight-400">
          Newest backups first. The selected backup will be written
          over the current config; a fresh pre-restore backup is
          always created first.
        </p>
        {listing.config_path && (
          <p className="mt-1 text-[11px] text-starlight-500">
            Target config: <code>{listing.config_path}</code>
          </p>
        )}
        <ul className="mt-3 space-y-1.5">
          {listing.backups.map((b) => (
            <li key={b.filename}>
              <button
                onClick={() => onSelect(b)}
                disabled={!b.valid_json}
                className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                  selected?.filename === b.filename
                    ? "border-primary-500/60 bg-primary-500/10"
                    : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
                } disabled:cursor-not-allowed disabled:opacity-50`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 text-[11px] font-medium text-starlight-100">
                      <Clock size={11} className="text-starlight-500" />
                      {formatTimestamp(b.timestamp)}
                    </p>
                    <p className="mt-1 truncate font-mono text-[10px] text-starlight-500">
                      {b.filename}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1 text-[10px]">
                    <span className="text-starlight-400">
                      {formatBytes(b.size_bytes)}
                    </span>
                    {b.valid_json ? (
                      <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">
                        JSON ok
                      </span>
                    ) : (
                      <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-rose-200">
                        JSON invalid
                      </span>
                    )}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </Section>

      <FooterRow>
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
        >
          Cancel
        </button>
        <button
          onClick={onContinue}
          disabled={!selected || !selected.valid_json}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
        >
          Restore selected
          <RotateCcw size={11} />
        </button>
      </FooterRow>
    </>
  )
}

function ConfirmBlock({
  selected, listing, error, onBack, onConfirm,
}: {
  selected: BackupEntry
  listing: BackupListReport | null
  error: string | null
  onBack: () => void
  onConfirm: () => void
}) {
  return (
    <>
      <Section title="Confirm restore">
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
          <FileWarning size={12} className="mr-1.5 inline" />
          <strong>Daena will overwrite the current config.</strong> A
          fresh pre-restore backup of the live state is created first
          (atomic rename), so you can roll forward by re-restoring this
          drawer.
        </div>
        <div className="mt-3 space-y-1 text-[11px] text-starlight-300">
          <p>
            <span className="text-starlight-500">Target:</span>{" "}
            <strong>{listing?.target_display_name}</strong>
          </p>
          <p>
            <span className="text-starlight-500">Backup:</span>{" "}
            <code>{selected.filename}</code>
          </p>
          <p>
            <span className="text-starlight-500">Timestamp:</span>{" "}
            {formatTimestamp(selected.timestamp)}
          </p>
          <p>
            <span className="text-starlight-500">Size:</span>{" "}
            {formatBytes(selected.size_bytes)}
          </p>
        </div>
      </Section>
      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200">
          <AlertTriangle size={12} className="mr-1.5 inline" />
          {error}
        </div>
      )}
      <FooterRow>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
        >
          <ArrowLeft size={11} /> Back
        </button>
        <button
          onClick={onConfirm}
          className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/40 bg-rose-500/15 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-500/25"
        >
          Restore now
          <RotateCcw size={11} />
        </button>
      </FooterRow>
    </>
  )
}

function DoneBlock({
  result, onClose,
}: { result: BackupRestoreReport; onClose: () => void }) {
  const ok = result.success
  return (
    <>
      <Section title={ok ? "Restored" : "Restore failed"}>
        <div
          className={`rounded-lg border p-3 text-xs ${
            ok
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-200"
              : "border-rose-500/30 bg-rose-500/5 text-rose-200"
          }`}
        >
          {ok ? (
            <>
              <CheckCircle2 size={12} className="mr-1.5 inline" />
              <strong>{result.target_display_name} config restored.</strong>{" "}
              Live config now matches <code>{result.restored_from}</code>.
              The pre-restore backup is at:
              <pre className="mt-1.5 overflow-x-auto rounded bg-emerald-500/10 px-2 py-1 text-[10px] text-emerald-100">
                {result.pre_restore_backup}
              </pre>
            </>
          ) : (
            <>
              <AlertTriangle size={12} className="mr-1.5 inline" />
              <code>{result.failure_reason}</code>
            </>
          )}
        </div>
      </Section>
      <FooterRow>
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20"
        >
          Done
        </button>
      </FooterRow>
    </>
  )
}

function FailureBlock({
  message, onClose, configPath,
}: { message: string; onClose: () => void; configPath?: string | null }) {
  return (
    <>
      <Section title="Could not list backups">
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200">
          <AlertTriangle size={12} className="mr-1.5 inline" />
          <code>{message}</code>
          {configPath && (
            <p className="mt-2 text-[11px] text-rose-200/70">
              Resolved config path: <code>{configPath}</code>
            </p>
          )}
        </div>
      </Section>
      <FooterRow>
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
        >
          Close
        </button>
      </FooterRow>
    </>
  )
}

// ──────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString()
  } catch {
    return iso
  }
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
        {title}
      </h3>
      {children}
    </section>
  )
}

function FooterRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-white/5 pt-3">
      {children}
    </div>
  )
}

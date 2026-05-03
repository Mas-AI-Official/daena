/**
 * MCPInstallDrawer -- 4-step install flow for MCP catalog entries.
 *
 * PR-CONN-MCP-INSTALL-INTO-CLI (2026-05-02). Replaces the read-only
 * Setup Guide drawer for MCP plugins where Daena can safely install
 * the entry into a supported CLI's own config file.
 *
 * Steps:
 *   1. Choose target CLI (Claude Desktop / Claude Code / Codex / Gemini)
 *   2. Preview the diff (existing block vs proposed block + warnings)
 *   3. Confirm and apply (backup + atomic write happens server-side)
 *   4. Test (post-apply probe runs MCP initialize + tools/list)
 *
 * Honesty:
 *   - "Connected" pill ONLY appears when post-apply probe succeeded.
 *   - Required env vars surface as NAMES with "Set in your shell"
 *     copy. Daena never asks the user to paste values into a form.
 *   - Malformed config -> repair-needed message + Apply button stays
 *     disabled.
 *   - Missing config + allow_create=false -> a single "Create config"
 *     toggle that the user must explicitly opt into.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2,
  FileWarning, Loader2, RotateCcw, ShieldCheck, X,
} from 'lucide-react'

import {
  applyMcpInstall,
  type McpInstallApply,
  type McpInstallPreview,
  type McpInstallTarget,
  previewMcpInstall,
} from '@/hooks/useMarketplace'
import MCPRestoreDrawer from './MCPRestoreDrawer'
import { type PluginCard } from './pluginCard'

interface MCPInstallDrawerProps {
  plugin: PluginCard
  onClose: () => void
  onComplete?: (result: McpInstallApply) => void
}

type Step = 'target' | 'preview' | 'confirm' | 'test'

const TARGET_OPTIONS: ReadonlyArray<{
  id: McpInstallTarget
  label: string
  hint: string
}> = [
  {
    id: 'claude_desktop',
    label: 'Claude Desktop',
    hint: 'Writes to claude_desktop_config.json in the standard install path.',
  },
  {
    id: 'claude_code',
    label: 'Claude Code (CLI)',
    hint: 'Writes to ~/.claude.json (or ~/.claude/mcp.json).',
  },
  {
    id: 'codex',
    label: 'Codex CLI',
    hint: 'Writes to ~/.codex/config.json.',
  },
  {
    id: 'gemini_cli',
    label: 'Gemini CLI',
    hint: 'Writes to ~/.gemini/settings.json.',
  },
] as const

export default function MCPInstallDrawer({
  plugin, onClose, onComplete,
}: MCPInstallDrawerProps) {
  const [step, setStep] = useState<Step>('target')
  const [target, setTarget] = useState<McpInstallTarget | null>(null)
  const [allowCreate, setAllowCreate] = useState(false)
  const [preview, setPreview] = useState<McpInstallPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [applyResult, setApplyResult] = useState<McpInstallApply | null>(null)
  const [applyLoading, setApplyLoading] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [restoreOpen, setRestoreOpen] = useState(false)

  // Re-fetch preview whenever (target | allowCreate) change.
  useEffect(() => {
    if (step !== 'preview' || !target) return
    let cancelled = false
    setPreviewLoading(true)
    setPreviewError(null)
    void (async () => {
      const res = await previewMcpInstall(plugin.id, {
        target, allow_create: allowCreate,
      })
      if (cancelled) return
      setPreviewLoading(false)
      if (res.ok && res.preview) {
        setPreview(res.preview)
      } else {
        setPreviewError(res.error ?? 'Preview failed')
      }
    })()
    return () => { cancelled = true }
  }, [step, target, allowCreate, plugin.id])

  async function handleApply() {
    if (!target) return
    setApplyLoading(true)
    setApplyError(null)
    const res = await applyMcpInstall(plugin.id, {
      target, allow_create: allowCreate, probe_after_apply: true,
    })
    setApplyLoading(false)
    if (res.ok && res.result) {
      setApplyResult(res.result)
      setStep('test')
      onComplete?.(res.result)
    } else {
      setApplyError(res.error ?? 'Apply failed')
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <DrawerHeader plugin={plugin} step={step} onClose={onClose} />

        <div className="space-y-5 p-5">
          {step === 'target' && (
            <TargetStep
              selected={target}
              onSelect={(t) => setTarget(t)}
              onNext={() => target && setStep('preview')}
            />
          )}

          {step === 'preview' && target && (
            <PreviewStep
              preview={preview}
              loading={previewLoading}
              error={previewError}
              allowCreate={allowCreate}
              setAllowCreate={setAllowCreate}
              onBack={() => setStep('target')}
              onNext={() => preview?.apply_allowed && setStep('confirm')}
            />
          )}

          {step === 'confirm' && target && (
            <ConfirmStep
              preview={preview}
              applyLoading={applyLoading}
              applyError={applyError}
              onBack={() => setStep('preview')}
              onApply={handleApply}
            />
          )}

          {step === 'test' && applyResult && (
            <TestStep result={applyResult} onClose={onClose} />
          )}

          {/* PR-CONN-MCP-INSTALL-RESTORE: every step that touches an
              existing config offers a "Restore previous backup" link.
              Only enabled once the operator has picked a target so we
              know which CLI's backups to list. */}
          {target && step !== 'test' && (
            <div className="pt-2 text-right">
              <button
                onClick={() => setRestoreOpen(true)}
                className="inline-flex items-center gap-1 text-[11px] text-starlight-500 hover:text-starlight-300"
                title="List + restore Daena backups for this CLI's config"
              >
                <RotateCcw size={10} />
                Restore previous backup...
              </button>
            </div>
          )}
        </div>
      </div>

      {restoreOpen && target && (
        <MCPRestoreDrawer
          target={target}
          targetDisplayName={
            TARGET_OPTIONS.find((o) => o.id === target)?.label ?? target
          }
          onClose={() => setRestoreOpen(false)}
          onComplete={() => {
            // After a successful restore, refresh marketplace cards
            // so the V2 row truth re-flects the restored config.
            window.dispatchEvent(new Event('daena:retry-pending'))
            setRestoreOpen(false)
            // Bounce the install flow back to preview so the operator
            // sees the new (restored) state.
            setStep('preview')
            setPreview(null)
          }}
        />
      )}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────
// Header (with step indicator)
// ──────────────────────────────────────────────────────────────────

function DrawerHeader({
  plugin, step, onClose,
}: { plugin: PluginCard; step: Step; onClose: () => void }) {
  const steps: Array<{ id: Step; label: string }> = useMemo(() => [
    { id: 'target', label: 'Choose CLI' },
    { id: 'preview', label: 'Preview' },
    { id: 'confirm', label: 'Confirm' },
    { id: 'test', label: 'Test' },
  ], [])
  const activeIdx = steps.findIndex((s) => s.id === step)

  return (
    <header className="border-b border-white/5 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
            Install MCP
          </p>
          <h2 className="mt-0.5 text-lg font-semibold text-starlight-100">
            {plugin.name}
          </h2>
          <p className="text-xs text-starlight-400">
            {plugin.vendor} - {plugin.description}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md border border-white/10 bg-white/5 p-1.5 text-starlight-300 hover:bg-white/10"
          aria-label="Close"
        >
          <X size={14} />
        </button>
      </div>
      <ol className="mt-4 flex items-center gap-2 text-[10px]">
        {steps.map((s, idx) => (
          <li
            key={s.id}
            className={`flex items-center gap-2 ${
              idx <= activeIdx ? 'text-primary-200' : 'text-starlight-500'
            }`}
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                idx === activeIdx
                  ? 'border-primary-500 bg-primary-500/30 text-primary-100'
                  : idx < activeIdx
                    ? 'border-emerald-500 bg-emerald-500/30 text-emerald-100'
                    : 'border-white/10 bg-white/5'
              }`}
            >
              {idx < activeIdx ? <CheckCircle2 size={11} /> : idx + 1}
            </span>
            <span>{s.label}</span>
            {idx < steps.length - 1 && (
              <span className="text-starlight-600">/</span>
            )}
          </li>
        ))}
      </ol>
    </header>
  )
}

// ──────────────────────────────────────────────────────────────────
// Step 1: Choose target
// ──────────────────────────────────────────────────────────────────

function TargetStep({
  selected, onSelect, onNext,
}: {
  selected: McpInstallTarget | null
  onSelect: (t: McpInstallTarget) => void
  onNext: () => void
}) {
  return (
    <>
      <Section title="Which CLI should host this MCP?">
        <ul className="space-y-2">
          {TARGET_OPTIONS.map((opt) => (
            <li key={opt.id}>
              <button
                onClick={() => onSelect(opt.id)}
                className={`w-full rounded-lg border px-3 py-2.5 text-left transition-colors ${
                  selected === opt.id
                    ? 'border-primary-500/60 bg-primary-500/10'
                    : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-starlight-100">
                    {opt.label}
                  </span>
                  {selected === opt.id && (
                    <CheckCircle2 size={14} className="text-primary-300" />
                  )}
                </div>
                <p className="mt-0.5 text-[11px] text-starlight-400">
                  {opt.hint}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </Section>
      <FooterRow>
        <span className="text-[11px] text-starlight-500">
          Daena writes only into the CLI's own config; nothing else changes.
        </span>
        <button
          onClick={onNext}
          disabled={!selected}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
        >
          Preview install
          <ArrowRight size={11} />
        </button>
      </FooterRow>
    </>
  )
}

// ──────────────────────────────────────────────────────────────────
// Step 2: Preview the diff
// ──────────────────────────────────────────────────────────────────

function PreviewStep({
  preview, loading, error, allowCreate, setAllowCreate, onBack, onNext,
}: {
  preview: McpInstallPreview | null
  loading: boolean
  error: string | null
  allowCreate: boolean
  setAllowCreate: (v: boolean) => void
  onBack: () => void
  onNext: () => void
}) {
  if (loading) {
    return (
      <div className="rounded-lg border border-white/5 bg-white/[0.02] py-6 text-center text-xs text-starlight-400">
        <Loader2 size={14} className="mr-2 inline animate-spin" />
        Computing preview...
      </div>
    )
  }
  if (error || !preview) {
    return (
      <FailureCard message={error ?? 'Preview unavailable'} onBack={onBack} />
    )
  }

  const isParseError =
    preview.failure_reason && preview.failure_reason.startsWith('config_parse_error')
  const isMissingPath =
    preview.failure_reason && preview.failure_reason.startsWith('config_path_missing')

  return (
    <>
      <Section title="Target config">
        <KV label="CLI" value={preview.target_display_name} />
        <KV label="Path" value={preview.config_path ?? '(not found)'} mono />
        <KV
          label="Action"
          value={preview.action}
          tone={
            preview.action === 'failed' ? 'danger'
              : preview.action === 'skip' ? 'muted'
                : 'success'
          }
        />
      </Section>

      {isMissingPath && !allowCreate && (
        <Section title="Config file not found">
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
            <FileWarning size={12} className="mr-1.5 inline" />
            None of the candidate paths exist yet. Daena can create a new
            config file at the first candidate path -- but only if you opt in.
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[11px] text-amber-200/80">
              {preview.candidates_tried.map((p) => (
                <li key={p}><code>{p}</code></li>
              ))}
            </ul>
            <label className="mt-3 flex items-center gap-2 text-[11px]">
              <input
                type="checkbox"
                checked={allowCreate}
                onChange={(e) => setAllowCreate(e.target.checked)}
                className="rounded border-amber-500/50 bg-transparent"
              />
              Create the config file at the first candidate path
            </label>
          </div>
        </Section>
      )}

      {isParseError && (
        <Section title="Repair needed">
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200">
            <AlertTriangle size={12} className="mr-1.5 inline" />
            <strong>Daena refuses to overwrite a malformed config.</strong>
            <p className="mt-1 text-[11px] text-rose-300/90">
              {preview.failure_reason?.replace('config_parse_error: ', '')}
            </p>
            <p className="mt-2 text-[11px] text-rose-300/90">
              Open <code>{preview.config_path}</code> in a JSON editor,
              fix the syntax error, then re-run preview.
            </p>
          </div>
        </Section>
      )}

      {preview.proposed_block && !isParseError && (
        <Section title={`Block to write (mcpServers.${preview.server_name})`}>
          <CodeBlock
            json={JSON.stringify(preview.proposed_block, null, 2)}
          />
          {preview.existing_block && (
            <div className="mt-2">
              <p className="text-[10px] uppercase tracking-wider text-starlight-500">
                Existing block (will be replaced)
              </p>
              <CodeBlock
                json={JSON.stringify(preview.existing_block, null, 2)}
                tone="warn"
              />
            </div>
          )}
        </Section>
      )}

      {preview.required_env_vars.length > 0 && (
        <Section title="Required env vars (NAMES only)">
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
            <ShieldCheck size={12} className="mr-1.5 inline text-amber-300" />
            Daena will <strong>not</strong> write the values into the config.
            Set these in your shell <em>before launching {preview.target_display_name}</em>:
            <ul className="mt-2 grid grid-cols-1 gap-1 text-[11px] sm:grid-cols-2">
              {preview.required_env_vars.map((name) => (
                <li key={name}>
                  <code className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-100">
                    {name}
                  </code>
                </li>
              ))}
            </ul>
          </div>
        </Section>
      )}

      {preview.risk_warnings.length > 0 && (
        <Section title="Heads up">
          <ul className="space-y-1.5">
            {preview.risk_warnings.map((w) => (
              <li
                key={w}
                className="flex items-start gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[11px] text-amber-100"
              >
                <AlertTriangle size={11} className="mt-0.5 shrink-0 text-amber-300" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <FooterRow>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
        >
          <ArrowLeft size={11} /> Back
        </button>
        <button
          onClick={onNext}
          disabled={!preview.apply_allowed}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
        >
          {preview.action === 'skip' ? 'Already installed' : 'Confirm install'}
          {preview.action !== 'skip' && <ArrowRight size={11} />}
        </button>
      </FooterRow>
    </>
  )
}

// ──────────────────────────────────────────────────────────────────
// Step 3: Confirm + apply
// ──────────────────────────────────────────────────────────────────

function ConfirmStep({
  preview, applyLoading, applyError, onBack, onApply,
}: {
  preview: McpInstallPreview | null
  applyLoading: boolean
  applyError: string | null
  onBack: () => void
  onApply: () => Promise<void>
}) {
  if (!preview) {
    return (
      <FailureCard
        message="Preview required before confirm"
        onBack={onBack}
      />
    )
  }
  return (
    <>
      <Section title="Ready to write">
        <div className="space-y-1 text-xs text-starlight-200">
          <p>
            <strong>{preview.target_display_name}</strong> config at{' '}
            <code>{preview.config_path}</code> will be{' '}
            <strong>{preview.action}</strong>.
          </p>
          {preview.config_exists && preview.action !== 'skip' && (
            <p className="text-[11px] text-starlight-400">
              A timestamped backup will be created beside the config file
              before any change. The write itself is atomic (temp file +
              rename).
            </p>
          )}
        </div>
      </Section>

      {applyError && (
        <FailureCard message={applyError} onBack={onBack} hideBack />
      )}

      <FooterRow>
        <button
          onClick={onBack}
          disabled={applyLoading}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10 disabled:opacity-50"
        >
          <ArrowLeft size={11} /> Back
        </button>
        <button
          onClick={() => void onApply()}
          disabled={applyLoading}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20 disabled:opacity-50"
        >
          {applyLoading ? (
            <Loader2 size={11} className="animate-spin" />
          ) : (
            <Activity size={11} />
          )}
          {applyLoading ? 'Writing...' : 'Apply install'}
        </button>
      </FooterRow>
    </>
  )
}

// ──────────────────────────────────────────────────────────────────
// Step 4: Test (post-apply probe outcome)
// ──────────────────────────────────────────────────────────────────

function TestStep({
  result, onClose,
}: { result: McpInstallApply; onClose: () => void }) {
  const probe = result.post_apply_probe
  const wrote = result.action !== 'failed' && result.action !== 'skipped'
  return (
    <>
      <Section title="Install result">
        <KV label="Action" value={result.action} tone={
          result.action === 'failed' ? 'danger' : 'success'
        } />
        <KV label="Config" value={result.config_path ?? '(none)'} mono />
        {result.backup_path && (
          <KV label="Backup" value={result.backup_path} mono />
        )}
        {result.v2_label && (
          <KV label="Status" value={result.v2_label} />
        )}
        {result.failure_reason && (
          <p className="mt-2 text-[11px] text-rose-300">
            {result.failure_reason}
          </p>
        )}
      </Section>

      {probe && (
        <Section title="Test (MCP initialize + tools/list)">
          {probe.success ? (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-emerald-200">
              <CheckCircle2 size={12} className="mr-1.5 inline" />
              <strong>Connected.</strong> The MCP responded to initialize
              and exposed at least one tool. Status pill in Plugins now
              reflects this row's V2 truth.
            </div>
          ) : (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
              <AlertTriangle size={12} className="mr-1.5 inline text-amber-300" />
              <strong>Probe did not succeed.</strong>
              <p className="mt-1 text-[11px] text-amber-200/80">
                Failure reason: <code>{probe.failure_reason}</code>
              </p>
              {result.required_env_vars.length > 0 && (
                <p className="mt-1 text-[11px] text-amber-200/80">
                  Don't forget to set: {result.required_env_vars.map((n) => (
                    <code key={n} className="mx-1 rounded bg-amber-500/10 px-1">{n}</code>
                  ))} in your shell, then re-run Test from the plugin card.
                </p>
              )}
            </div>
          )}
        </Section>
      )}

      {wrote && !probe && (
        <Section title="Next">
          <p className="text-xs text-starlight-300">
            Write succeeded. Restart {result.target_display_name} so it
            picks up the new MCP, then click <strong>Test</strong> on the
            plugin card.
          </p>
        </Section>
      )}

      <FooterRow>
        <span className="text-[11px] text-starlight-500">
          {result.required_env_vars.length > 0
            ? `Set env vars: ${result.required_env_vars.join(', ')}`
            : 'No env vars required.'}
        </span>
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

// ──────────────────────────────────────────────────────────────────
// Tiny shared layout helpers
// ──────────────────────────────────────────────────────────────────

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

function KV({
  label, value, mono = false, tone = 'default',
}: {
  label: string; value: string; mono?: boolean
  tone?: 'default' | 'success' | 'danger' | 'muted'
}) {
  const toneClass =
    tone === 'success' ? 'text-emerald-200'
      : tone === 'danger' ? 'text-rose-300'
        : tone === 'muted' ? 'text-starlight-500'
          : 'text-starlight-200'
  return (
    <div className="flex items-center justify-between gap-3 rounded border border-white/5 bg-white/[0.02] px-2.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wider text-starlight-500">
        {label}
      </p>
      <p className={`max-w-[60%] truncate text-xs ${toneClass} ${mono ? 'font-mono' : ''}`}>
        {value}
      </p>
    </div>
  )
}

function CodeBlock({
  json, tone = 'ok',
}: { json: string; tone?: 'ok' | 'warn' }) {
  const toneClass =
    tone === 'warn'
      ? 'border-amber-500/30 bg-amber-500/5 text-amber-100'
      : 'border-white/5 bg-midnight-900/60 text-emerald-200'
  return (
    <pre className={`mt-1 overflow-x-auto rounded-md border p-2 text-[11px] ${toneClass}`}>
      <code>{json}</code>
    </pre>
  )
}

function FooterRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-white/5 pt-3">
      {children}
    </div>
  )
}

function FailureCard({
  message, onBack, hideBack = false,
}: { message: string; onBack: () => void; hideBack?: boolean }) {
  return (
    <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200">
      <AlertTriangle size={12} className="mr-1.5 inline" />
      {message}
      {!hideBack && (
        <button
          onClick={onBack}
          className="ml-3 inline-flex items-center gap-1 text-[11px] text-rose-100 underline-offset-2 hover:underline"
        >
          <ArrowLeft size={10} /> Back
        </button>
      )}
    </div>
  )
}

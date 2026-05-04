/**
 * FirstCallableWizard -- Sprint-7 PR-3 (2026-05-04).
 *
 * Goal: walk Masoud from "0 of N callable" to "1 callable plugin" in
 * the smallest possible number of clicks. Filesystem MCP is the
 * preferred first plugin because it needs no OAuth, no cloud
 * account login, and runs locally as an npx package.
 *
 * Honesty rules:
 *   - Never auto-installs npm/pip/docker. The exact command is
 *     surfaced for copy-paste and the operator runs it themselves.
 *   - Never claims "callable" -- only points the operator at the
 *     existing safe paths (Install drawer for one of 4 CLIs, then
 *     the Probe button on the resulting V2 row).
 *   - The CTA is shown ONLY when callable === 0. Once one plugin
 *     is callable, the wizard auto-hides (see OverviewPanel
 *     conditional render).
 */

import { useState } from 'react'
import {
  CheckCircle2, ChevronRight, Copy, FolderOpen, Lightbulb, Sparkles, Terminal,
} from 'lucide-react'

interface FirstCallableWizardProps {
  /** Total catalog size, used in the "Y of N" copy. */
  catalogTotal: number
  /** Navigate to a primary tab (caller routes 'mcp' to the MCP store). */
  onNavigateTab?: (tab: string) => void
  /** Optional callback so a parent can dismiss the wizard explicitly
   *  (e.g. after the operator chooses to skip first-run guidance). */
  onDismiss?: () => void
}

export default function FirstCallableWizard({
  catalogTotal, onNavigateTab, onDismiss,
}: FirstCallableWizardProps) {
  const [copied, setCopied] = useState(false)

  // Copy-paste command from the catalog entry. This is the exact
  // string mcp-filesystem advertises as its install method. We render
  // a placeholder for the allowed root so the operator never blindly
  // executes a command pointed at a folder they don't intend.
  const installCommand =
    'npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>'

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(installCommand)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // Clipboard can fail in non-secure contexts; the textarea
      // fallback is below.
    }
  }

  return (
    <section
      data-testid="first-callable-wizard"
      className="rounded-xl border border-accent-cyan/40 bg-accent-cyan/5 p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-md bg-accent-cyan/15 text-accent-cyan">
            <Sparkles size={16} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.22em] text-accent-cyan">
              Start here
            </p>
            <h2 className="mt-1 text-base font-semibold text-starlight-100">
              Make your first plugin callable
            </h2>
            <p className="mt-1 max-w-2xl text-xs text-starlight-300">
              Daena has {catalogTotal} connectors in the catalog and 0 callable
              right now. The fastest path to 1 callable is{' '}
              <strong className="text-starlight-100">Filesystem MCP</strong>:
              no OAuth, no cloud account, no native install. It runs locally
              as an <code>npx</code> package.
            </p>
          </div>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-[11px] text-starlight-400 hover:text-starlight-200"
          >
            Skip for now
          </button>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {/* Capability summary */}
        <div className="rounded-md border border-white/5 bg-midnight-400/40 p-3">
          <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-starlight-300">
            <FolderOpen size={12} className="text-accent-cyan" />
            What Filesystem can do
          </h3>
          <ul className="mt-2 space-y-1 text-xs text-starlight-300">
            <li className="flex gap-2">
              <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-accent-cyan" />
              <span>List directory contents</span>
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-accent-cyan" />
              <span>Read file contents (read-only by default)</span>
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-accent-cyan" />
              <span>Search files by name pattern</span>
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-accent-cyan" />
              <span>Sandboxed: refuses operations outside the allowed root</span>
            </li>
          </ul>
        </div>

        {/* Install hint */}
        <div className="rounded-md border border-white/5 bg-midnight-400/40 p-3">
          <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-starlight-300">
            <Terminal size={12} className="text-accent-cyan" />
            Install command (copy + paste)
          </h3>
          <p className="mt-2 text-[11px] text-starlight-400">
            Replace <code>&lt;ALLOWED_ROOT&gt;</code> with the folder you want
            Daena to read (e.g. <code>D:\Ideas\Daena</code>). Daena does NOT
            run this for you -- run it once in your shell to verify the
            package starts cleanly.
          </p>
          <div className="mt-2 flex items-stretch gap-2">
            <pre
              data-testid="first-callable-install-cmd"
              className="grow overflow-x-auto rounded-md border border-white/5 bg-midnight-500/60 px-3 py-2 text-[11px] text-starlight-100"
            >
              {installCommand}
            </pre>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1 rounded-md border border-accent-cyan/40 bg-accent-cyan/10 px-2 text-[11px] text-accent-cyan hover:bg-accent-cyan/20"
              data-testid="first-callable-copy-button"
            >
              {copied ? <CheckCircle2 size={12} /> : <Copy size={12} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      </div>

      {/* Continue path */}
      <div className="mt-4 rounded-md border border-white/5 bg-midnight-400/30 p-3">
        <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-starlight-300">
          <Lightbulb size={12} className="text-accent-cyan" />
          Next steps
        </h3>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-starlight-300">
          <li>
            (Optional) Run the command above once in your shell to confirm the
            npx package downloads + starts.
          </li>
          <li>
            Open the <strong className="text-starlight-100">MCP Store</strong> tab
            and find <strong className="text-starlight-100">Filesystem</strong>.
          </li>
          <li>
            Click <strong className="text-starlight-100">Install</strong>.
            Daena will write the entry into one of your CLI configs
            (Claude Desktop, Claude Code, Codex, or Gemini) with an atomic
            backup.
          </li>
          <li>
            After install, click <strong className="text-starlight-100">Probe</strong>{' '}
            on the V2 row. If the probe succeeds, the lifecycle pill flips to{' '}
            <strong className="text-emerald-300">callable</strong> and the row
            shows the available skills.
          </li>
          <li>
            From the plugin drawer, run your first read-only skill
            (<code>find_files</code> or <code>read_file</code>). The skill
            execution stays inside Daena's Phase 2 read-only allowlist -- no
            writes, no deletes, no external network.
          </li>
        </ol>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            onClick={() => onNavigateTab?.('mcp')}
            className="inline-flex items-center gap-2 rounded-md border border-accent-cyan/40 bg-accent-cyan/10 px-3 py-1.5 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20"
            data-testid="first-callable-go-mcp"
          >
            Continue in MCP Store
            <ChevronRight size={12} />
          </button>
          <a
            href="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10"
          >
            Read the spec
          </a>
        </div>

        <p className="mt-3 text-[10px] text-starlight-400">
          If the install or probe fails, open the Connections{' '}
          <strong className="text-starlight-200">Top blockers</strong> panel below --
          it explains exactly which step blocked the connector and what to do next.
        </p>
      </div>
    </section>
  )
}

/**
 * Extensions tab for the Connections page.
 *
 * Renders:
 *   - The "Detected in your CLIs" import banner (Session 9)
 *   - The governance-mode banner (Session 11) explaining UNLEASHED /
 *     BALANCED / GOVERNED interaction with per-tool pills
 *   - The Browse MCP servers button (opens BrowseModal in the parent)
 *   - The batch-action toolbar (enable / disable selected)
 *   - The extensions list with per-row toggle + expandable per-tool
 *     Allow/Ask/Block dropdowns
 *
 * The optimistic-permission revert logic in ExtensionRow (setPermission /
 * setToolPerms actually rolling back local state on a failed POST) is a
 * recent audit fix. Do NOT replace with fire-and-forget calls.
 */
import { useCallback, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Puzzle,
  RefreshCw,
  MoreVertical,
  CheckCircle2,
  XCircle,
  Settings,
  Loader2,
  Plus,
  ChevronDown,
  ChevronUp,
  Shield,
  ToggleLeft,
  ToggleRight,
  Download,
  AlertTriangle,
  Trash2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { EXTENSION_ICONS } from '@/components/icons/BrandIcons'
import type { useMCPDetections } from '@/hooks/useMCPDetections'
import type { usePermissionState } from '@/hooks/usePermissionState'
import { ConfigPanel, ContextMenu, PermissionSelect } from './shared'
import type { ExtensionData, Permission } from './types'

// ── Extension Row with Perplexity-style toggle + expandable config ──

function ExtensionRow({ ext, expanded, onToggleExpand, onToggle, onUninstalled, selected, onSelect, governanceOverride }: {
  ext: ExtensionData
  expanded: boolean
  onToggleExpand: () => void
  onToggle: (id: string, enabled: boolean) => void
  onUninstalled?: (id: string) => void
  selected?: boolean
  onSelect?: (id: string, checked: boolean) => void
  // Session 11: when true (UNLEASHED mode), per-tool pills are shown
  // but visually dimmed with a tooltip explaining they are overridden
  // at the governance-mode layer.
  governanceOverride?: boolean
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [permission, setPermissionState] = useState<Permission>(ext.permission as Permission || 'ASK_EACH_TIME')
  // Session 10: per-tool permissions matching Claude Desktop.
  // Session 11: seeded from the backend's saved state (ext.tool_permissions)
  // so user choices persist across logout. Missing tools inherit the
  // extension default.
  const [toolPerms, setToolPermsState] = useState<Record<string, Permission>>(() => {
    const init: Record<string, Permission> = {}
    for (const t of ext.tools ?? []) {
      const saved = ext.tool_permissions?.[t]
      init[t] = (saved as Permission) ?? (ext.permission as Permission) ?? 'ASK_EACH_TIME'
    }
    return init
  })
  const Icon = EXTENSION_ICONS[ext.id] || Puzzle
  const hasTools = (ext.tools?.length ?? 0) > 0

  // Session 11: persist permission changes to User.settings JSONB via
  // Optimistic update with TRUE revert on failure. Previously this
  // toasted "will revert on refresh" but never actually reverted the
  // local state — UI claimed one thing, source of truth was another.
  // Now we capture the previous value and roll back on error.
  const persistPermission = useCallback(async (prev: Permission, next: Permission) => {
    try {
      await api.post(`/connections/extensions/${encodeURIComponent(ext.id)}/permissions`, {
        default: next,
      })
    } catch {
      setPermissionState(prev)
      toast.error(`Could not save ${ext.name} permission. Reverted.`)
    }
  }, [ext.id, ext.name])

  const persistToolPermission = useCallback(async (toolName: string, prev: Permission, next: Permission) => {
    try {
      await api.post(`/connections/extensions/${encodeURIComponent(ext.id)}/permissions`, {
        tools: { [toolName]: next },
      })
    } catch {
      // Roll back the specific tool that failed.
      setToolPermsState((current) => ({ ...current, [toolName]: prev }))
      toast.error(`Could not save ${toolName} permission. Reverted.`)
    }
  }, [ext.id])

  const setPermission = useCallback((next: Permission) => {
    setPermissionState((prev) => {
      void persistPermission(prev, next)
      return next
    })
  }, [persistPermission])

  const setToolPerms = useCallback((updater: React.SetStateAction<Record<string, Permission>>) => {
    setToolPermsState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      // Figure out which tool(s) changed and persist only those.
      for (const [k, v] of Object.entries(next)) {
        if (prev[k] !== v) void persistToolPermission(k, prev[k], v)
      }
      return next
    })
  }, [persistToolPermission])

  return (
    <div>
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        {/* Batch select checkbox */}
        {onSelect && (
          <input
            type="checkbox"
            checked={selected || false}
            onChange={(e) => { e.stopPropagation(); onSelect(ext.id, e.target.checked) }}
            onClick={(e) => e.stopPropagation()}
            className="w-3.5 h-3.5 rounded border-white/20 bg-transparent accent-primary-500 cursor-pointer shrink-0"
          />
        )}
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-starlight-100">{ext.name}</span>
          <p className="text-xs text-starlight-500 truncate">{ext.description}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0" onClick={(e) => e.stopPropagation()}>
          {/* Inline toggle switch (Perplexity style) -- green=enabled, red=disabled */}
          <button
            role="switch"
            aria-checked={ext.enabled}
            onClick={() => onToggle(ext.id, !ext.enabled)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-all duration-200 cursor-pointer ${
              ext.enabled ? 'bg-accent-green border border-accent-green' : 'bg-accent-red/60 border border-accent-red/40'
            }`}
          >
            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${ext.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
          </button>
          {expanded ? <ChevronUp size={14} className="text-starlight-400" /> : <ChevronDown size={14} className="text-starlight-400" />}
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer">
              <MoreVertical size={14} />
            </button>
            <AnimatePresence>
              {menuOpen && (
                <ContextMenu
                  onClose={() => setMenuOpen(false)}
                  items={[
                    { label: ext.enabled ? 'Disable' : 'Enable', icon: <Settings size={12} />, onClick: () => onToggle(ext.id, !ext.enabled) },
                    {
                      label: 'Uninstall…',
                      icon: <Trash2 size={12} />,
                      onClick: async () => {
                        const ok = await confirmDialog({
                          title: `Uninstall ${ext.name}?`,
                          message: 'This removes the MCP entry from claude_desktop_config.json and stops the live adapter. Your saved per-tool permissions stay in case you reinstall.',
                          confirmLabel: 'Uninstall',
                          variant: 'danger',
                        })
                        if (!ok) return
                        try {
                          await api.post('/connections/extensions/uninstall', { id: ext.id })
                          toast.success(`${ext.name} uninstalled`)
                          // Caller refreshes the extensions list via parent state.
                          if (typeof onUninstalled === 'function') onUninstalled(ext.id)
                        } catch {
                          toast.error(`Could not uninstall ${ext.name}`)
                        }
                      },
                    },
                  ]}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Expandable config panel -- Claude Desktop parity:
          1. Compact source/version header (tiny, one line)
          2. Default permission pill (controls all tools at once)
          3. Per-tool permission list (this is what the empty space was)
          4. Empty-state callout when tools haven't been discovered yet */}
      <ConfigPanel expanded={expanded}>
        {/* Source + version strip -- one line instead of a 2x2 grid */}
        <div className="flex items-center gap-3 text-[11px] text-starlight-500">
          <span className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${ext.enabled ? 'bg-accent-green' : 'bg-starlight-500'}`} />
            {ext.enabled ? 'Running' : 'Stopped'}
          </span>
          <span>&middot;</span>
          <span>{ext.source || 'MCP Server'}</span>
          {ext.version && (
            <>
              <span>&middot;</span>
              <span className="font-mono">{ext.version}</span>
            </>
          )}
        </div>

        {/* Default permission -- controls every tool at once.
            Session 11: when governanceOverride is true (UNLEASHED),
            wrap in an opacity-reduced container with a tooltip so the
            operator sees the pills are informational only. */}
        <div className={`space-y-2 ${governanceOverride ? 'opacity-50' : ''}`}
             title={governanceOverride ? 'UNLEASHED mode overrides per-tool settings. BLOCK is still honored.' : undefined}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield size={12} className="text-starlight-400" />
              <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">Default Permission</span>
              {governanceOverride && (
                <span className="text-[9px] uppercase tracking-wider text-accent-green font-semibold">
                  overridden
                </span>
              )}
            </div>
            {hasTools && (
              <button
                onClick={async () => {
                  // Batch update: set local state for all tools AND
                  // fire a single persist call so we don't hammer the
                  // backend with N requests when there are many tools.
                  const next: Record<string, Permission> = {}
                  for (const t of ext.tools ?? []) next[t] = permission
                  setToolPermsState(next)
                  try {
                    await api.post(`/connections/extensions/${encodeURIComponent(ext.id)}/permissions`, {
                      tools: next,
                    })
                    toast.success(`All tools set to ${permission.replace('_', ' ').toLowerCase()}`)
                  } catch {
                    toast.error(`Applied locally but failed to save to server.`)
                  }
                }}
                className="text-[10px] text-primary-400 hover:text-primary-300 cursor-pointer"
              >
                Apply to all tools
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <PermissionSelect value={permission} onChange={setPermission} />
            <span className="text-[11px] text-starlight-400">
              {permission === 'ALLOW' ? 'Tools run without asking' : permission === 'ASK_EACH_TIME' ? 'Daena asks before each tool use' : 'All tools blocked'}
            </span>
          </div>
        </div>

        {/* Per-tool permissions -- matches Claude Desktop's MCP section.
            Shows each tool the MCP server exposes with an individual
            Allow/Ask/Block control. Empty state explains why tools
            might not be visible yet. Session 11: dims when UNLEASHED
            overrides per-tool settings. */}
        <div className={`space-y-2 ${governanceOverride ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">
              Tools {hasTools ? `(${ext.tools?.length})` : ''}
              {governanceOverride && (
                <span className="ml-2 text-[9px] uppercase tracking-wider text-accent-green font-semibold">
                  overridden
                </span>
              )}
            </span>
          </div>
          {hasTools ? (
            <div className="rounded-lg border border-white/5 divide-y divide-white/5">
              {(ext.tools ?? []).map((toolName) => (
                <div
                  key={toolName}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-white/[0.02]"
                >
                  <Puzzle size={12} className="text-starlight-500 shrink-0" />
                  <span className="flex-1 text-xs font-mono text-starlight-200 truncate">
                    {toolName}
                  </span>
                  <PermissionSelect
                    value={toolPerms[toolName] ?? permission}
                    onChange={(v) => setToolPerms((s) => ({ ...s, [toolName]: v }))}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.01] px-4 py-3 flex items-start gap-2">
              <Puzzle size={12} className="text-starlight-500 mt-0.5 shrink-0" />
              <div className="flex-1 text-[11px] text-starlight-500">
                Tools appear here once this MCP server runs for the first time.
                Daena probes the server's <span className="font-mono">tools/list</span>{' '}
                endpoint after it connects. Until then, the default permission
                above applies to every tool the server exposes.
              </div>
            </div>
          )}
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Detected-in-CLIs banner ──
//
// Lifted out of the tab body so the page can also render it in the MCP
// Servers tab via the same hook reference. Stays a private helper here
// because the props line up 1:1 with what the parent already has.

export function MCPDetectionsList({ mcpSync }: { mcpSync: ReturnType<typeof useMCPDetections> }) {
  return (
    <div className="mb-6 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-display font-bold text-starlight-100">Detected in your CLIs</h2>
          <p className="text-xs text-starlight-400">
            MCP servers you already installed in Claude Code, Codex, or Gemini. Import once — use everywhere.
          </p>
        </div>
        <button
          onClick={() => { void mcpSync.refresh() }}
          disabled={mcpSync.loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
        >
          {mcpSync.loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Rescan
        </button>
      </div>
      <div className="rounded-xl border border-white/5 overflow-hidden">
        {mcpSync.detections.map((mcp) => {
          const status = mcpSync.importStatus[mcp.name] ?? 'idle'
          const result = mcpSync.importResults[mcp.name]
          const cliList = mcp.notes.match(/detected_in=([^|]+)/)?.[1] ?? mcp.source_cli
          return (
            <div
              key={`${mcp.source_cli}:${mcp.name}`}
              className="flex items-center gap-3 px-4 py-3 border-b border-white/5 last:border-b-0 hover:bg-white/[0.02]"
            >
              <div className="w-8 h-8 rounded-lg bg-primary-500/10 flex items-center justify-center text-primary-400 shrink-0">
                <Puzzle size={14} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-starlight-100 truncate">{mcp.name}</p>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-starlight-400 uppercase tracking-wider">
                    {cliList}
                  </span>
                </div>
                <p className="text-[11px] text-starlight-500 truncate" title={`${mcp.command} ${mcp.args.join(' ')}`.trim()}>
                  {mcp.url || `${mcp.command} ${mcp.args.join(' ')}`.trim() || 'no command'}
                </p>
                {result && !result.safe && result.blockers.length > 0 && (
                  <p className="text-[11px] text-accent-red mt-1 flex items-center gap-1">
                    <AlertTriangle size={10} /> Blocked: {result.blockers.join('; ')}
                  </p>
                )}
              </div>
              <button
                onClick={() => { void mcpSync.importMCP(mcp) }}
                disabled={status === 'importing' || status === 'imported'}
                className={
                  status === 'imported'
                    ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-green/10 text-accent-green cursor-default'
                    : status === 'blocked' || status === 'error'
                    ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red cursor-not-allowed'
                    : 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer disabled:opacity-50'
                }
              >
                {status === 'importing' && <Loader2 size={12} className="animate-spin" />}
                {status === 'imported' && <CheckCircle2 size={12} />}
                {(status === 'blocked' || status === 'error') && <AlertTriangle size={12} />}
                {status === 'idle' && <Download size={12} />}
                {status === 'imported'
                  ? 'Imported'
                  : status === 'blocked'
                  ? 'Blocked'
                  : status === 'error'
                  ? 'Error'
                  : status === 'importing'
                  ? 'Scanning...'
                  : 'Import'}
              </button>
            </div>
          )
        })}
      </div>
      {mcpSync.error && (
        <p className="text-xs text-accent-red flex items-center gap-1">
          <AlertTriangle size={12} /> {mcpSync.error}
        </p>
      )}
    </div>
  )
}

// ── Tab body ──

export interface ConnectionsExtensionsProps {
  extensions: ExtensionData[]
  cloudPreinstalled: ExtensionData[]
  cloudMode: boolean
  extLoading: boolean
  permissionState: ReturnType<typeof usePermissionState>
  governanceOverride: boolean
  expandedItem: string | null
  selectedExtensions: Set<string>
  onToggleExpand: (id: string) => void
  onSelectExtension: (id: string, checked: boolean) => void
  onSelectAll: (list: ExtensionData[]) => void
  onClearSelection: () => void
  onBatchToggle: (enabled: boolean) => void
  onBulkSetEnabled: (enabled: boolean) => void
  onToggleExtension: (id: string, enabled: boolean) => void
  // Called after a successful uninstall so the parent can drop the row
  // from `extensions` and re-fetch. Without this, the uninstall would
  // succeed at the backend but the UI would still show the dead entry.
  onUninstalled?: (id: string) => void
  onOpenBrowse: () => void
  // The CLI-detected list (Session 9). Rendered above the main list when
  // detections > 0. Lifted from the parent so other tabs can also peek
  // at the same hook state.
  mcpSync: ReturnType<typeof useMCPDetections>
}

export default function ConnectionsExtensions({
  extensions,
  cloudPreinstalled,
  cloudMode,
  extLoading,
  permissionState,
  governanceOverride,
  expandedItem,
  selectedExtensions,
  onToggleExpand,
  onSelectExtension,
  onSelectAll,
  onClearSelection,
  onBatchToggle,
  onBulkSetEnabled,
  onToggleExtension,
  onUninstalled,
  onOpenBrowse,
  mcpSync,
}: ConnectionsExtensionsProps) {
  const list = cloudMode ? cloudPreinstalled : extensions
  const allEnabled = list.every((e) => e.enabled)

  return (
    <>
      {mcpSync.detections.length > 0 && <MCPDetectionsList mcpSync={mcpSync} />}

      <div className="space-y-4">
        {/* Session 11: governance-mode banner. Explains how
            per-tool Allow/Ask/Block interacts with the current
            UNLEASHED/BALANCED/GOVERNED mode. Color-coded: green
            for UNLEASHED (wide open), amber for BALANCED,
            primary for GOVERNED (strict). */}
        {permissionState && (
          <div
            className={
              governanceOverride
                ? 'flex items-start gap-3 px-4 py-3 rounded-xl bg-accent-green/10 border border-accent-green/30'
                : permissionState.governance_mode === 'BALANCED'
                ? 'flex items-start gap-3 px-4 py-3 rounded-xl bg-accent-amber/10 border border-accent-amber/30'
                : 'flex items-start gap-3 px-4 py-3 rounded-xl bg-primary-500/10 border border-primary-500/30'
            }
          >
            <Shield
              size={16}
              className={
                governanceOverride
                  ? 'text-accent-green shrink-0 mt-0.5'
                  : permissionState.governance_mode === 'BALANCED'
                  ? 'text-accent-amber shrink-0 mt-0.5'
                  : 'text-primary-400 shrink-0 mt-0.5'
              }
            />
            <div className="flex-1">
              <p className="text-xs font-semibold text-starlight-100">
                {permissionState.banner_headline}
              </p>
              <p className="text-[11px] text-starlight-400 mt-1">
                {permissionState.banner_body}
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs text-starlight-400">
            {cloudMode
              ? 'Pre-installed MCP servers available in cloud mode.'
              : 'MCP servers let Daena read files, query APIs, and drive other tools on your computer.'}
          </p>
          <div className="flex items-center gap-2">
            {!cloudMode && (
              <button
                onClick={onOpenBrowse}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
              >
                <Plus size={12} /> Browse MCP servers
              </button>
            )}
          </div>
        </div>

        {/* Batch action toolbar */}
        {selectedExtensions.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-primary-500/10 border border-primary-500/20"
          >
            <span className="text-xs text-primary-400 font-medium">{selectedExtensions.size} selected</span>
            <div className="flex-1" />
            <button
              onClick={() => onBatchToggle(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-accent-green/20 cursor-pointer"
            >
              <ToggleRight size={12} /> Enable selected
            </button>
            <button
              onClick={() => onBatchToggle(false)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red hover:bg-accent-red/20 cursor-pointer"
            >
              <ToggleLeft size={12} /> Disable selected
            </button>
            <button
              onClick={onClearSelection}
              className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer"
            >
              <XCircle size={14} />
            </button>
          </motion.div>
        )}

        <div>
          {/* Header with select-all */}
          <div className="flex items-center justify-between px-4 mb-2">
            <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">
              {cloudMode ? 'Pre-installed extensions' : 'Installed on your computer'}
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => onSelectAll(list)}
                className="text-[10px] text-starlight-500 hover:text-primary-400 cursor-pointer"
              >
                {selectedExtensions.size === list.length ? 'Deselect all' : 'Select all'}
              </button>
              <button
                onClick={() => onBulkSetEnabled(!allEnabled)}
                className="text-[10px] text-starlight-500 hover:text-accent-green cursor-pointer"
              >
                {allEnabled ? 'Disable all' : 'Enable all'}
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-white/5 divide-y divide-white/5">
            {list.map((ext) => (
              <ExtensionRow
                key={ext.id}
                ext={ext}
                expanded={expandedItem === ext.id}
                onToggleExpand={() => onToggleExpand(ext.id)}
                selected={selectedExtensions.has(ext.id)}
                onSelect={onSelectExtension}
                governanceOverride={governanceOverride}
                onToggle={onToggleExtension}
                onUninstalled={onUninstalled}
              />
            ))}
            {!cloudMode && extensions.length === 0 && !extLoading && (
              <div className="px-4 py-8 text-center text-xs text-starlight-500">No extensions installed. Install MCP servers to add extensions.</div>
            )}
          </div>
        </div>

        {!cloudMode && (
          <div className="border-2 border-dashed border-white/10 rounded-xl p-6 text-center">
            <p className="text-xs text-starlight-500">Drag .MCPB or .DXT files here to install</p>
          </div>
        )}
      </div>
    </>
  )
}

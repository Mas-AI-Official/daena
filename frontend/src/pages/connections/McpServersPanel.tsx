import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Download,
  Loader2,
  PackagePlus,
  RefreshCw,
  Search,
  Server,
  Wrench,
} from 'lucide-react'

import { getMcpBrandIcon } from '@/components/icons/BrandIcons'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { ExtensionData } from './types'

interface DetectedMcp {
  source_cli: string
  config_path: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  url: string
  notes: string
}

interface RegistryEntry {
  server_key: string
  display_name: string
  description: string
  command: string
  args: string[]
  package?: string | null
}

interface PluginSkill {
  id: string
  name: string
  description: string
}

interface PluginDefinition {
  id: string
  name: string
  subtitle: string
  category: string
  auth_kind: string
  skills: PluginSkill[]
  skill_count: number
  mcp_package?: string | null
  install_note?: string | null
}

interface RegistryResponse {
  success: boolean
  data: {
    count: number
    entries: RegistryEntry[]
  }
}

interface ExtensionsResponse {
  success: boolean
  data: ExtensionData[]
}

interface PluginCatalogResponse {
  success: boolean
  data: PluginDefinition[]
}

function shortCommand(command: string, args: string[] = []) {
  const text = [command, ...args].filter(Boolean).join(' ')
  return text || 'No command configured'
}

function sourceLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())
}

function probeMessage(raw: unknown): string {
  const text = String(raw || 'Probe failed').trim()
  if (!text || text.includes('unhandled errors in a TaskGroup')) {
    return 'MCP process failed during startup. Check command, args, package, and required env vars.'
  }
  return text
}

function McpIcon({ id }: { id: string }) {
  const Icon = getMcpBrandIcon(id)
  return <Icon size={22} />
}

export default function McpServersPanel() {
  const [detected, setDetected] = useState<DetectedMcp[]>([])
  const [registry, setRegistry] = useState<RegistryEntry[]>([])
  const [extensions, setExtensions] = useState<ExtensionData[]>([])
  const [catalog, setCatalog] = useState<PluginDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [probe, setProbe] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const results = await Promise.allSettled([
      api.get<DetectedMcp[]>('/mcp-sync/detected', { silent: false }),
      api.get<RegistryResponse>('/connections/mcp-registry', { silent: false }),
      api.get<ExtensionsResponse>('/connections/extensions', { silent: false }),
      api.get<PluginCatalogResponse>('/connections/plugin-catalog', { silent: false }),
    ])

    const [detectedR, registryR, extensionsR, catalogR] = results
    if (detectedR.status === 'fulfilled') setDetected(Array.isArray(detectedR.value.data) ? detectedR.value.data : [])
    if (registryR.status === 'fulfilled') setRegistry(registryR.value.data?.data?.entries ?? [])
    if (extensionsR.status === 'fulfilled') setExtensions(extensionsR.value.data?.data ?? [])
    if (catalogR.status === 'fulfilled') setCatalog(catalogR.value.data?.data ?? [])

    if (results.every((r) => r.status === 'rejected')) {
      const first = results[0]
      setError(first.status === 'rejected' && first.reason instanceof Error ? first.reason.message : 'MCP APIs unavailable')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const liveKeys = useMemo(() => new Set(registry.map((entry) => entry.server_key)), [registry])
  const livePackages = useMemo(() => new Set(registry.map((entry) => entry.package).filter(Boolean) as string[]), [registry])
  const mcpCatalog = useMemo(() => catalog.filter((plugin) => plugin.mcp_package), [catalog])

  const filteredDetected = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return detected
    return detected.filter((item) =>
      [item.name, item.source_cli, item.command, item.args.join(' '), item.config_path]
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [detected, query])

  const filteredRegistry = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return registry
    return registry.filter((item) =>
      [item.server_key, item.display_name, item.description, item.command, item.args.join(' '), item.package ?? '']
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [query, registry])

  const filteredCatalog = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return mcpCatalog
    return mcpCatalog.filter((item) =>
      [item.id, item.name, item.subtitle, item.mcp_package ?? '', item.skills.map((skill) => skill.name).join(' ')]
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [mcpCatalog, query])

  async function importDetected(item: DetectedMcp) {
    setBusy(`import:${item.name}`)
    try {
      const res = await api.post('/mcp-sync/import', item, { silent: false })
      const payload = res.data
      if (payload?.safe && payload?.registered) toast.success(`${item.name} imported into Daena MCP registry`)
      else if (payload?.safe) toast.error(`${item.name} passed scan but did not register`)
      else toast.error(`${item.name} blocked: ${(payload?.blockers ?? []).join(', ') || 'scan failed'}`)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'MCP import failed')
    } finally {
      setBusy(null)
    }
  }

  async function installCatalog(plugin: PluginDefinition) {
    if (!plugin.mcp_package) return
    setBusy(`install:${plugin.id}`)
    try {
      const res = await api.post('/connections/extensions/install', {
        id: plugin.id,
        name: plugin.name,
        description: plugin.subtitle,
        command: 'npx',
        args: ['-y', plugin.mcp_package],
      }, { silent: false })
      const data = res.data?.data
      if (data?.mcp_persisted) toast.success(`${plugin.name} MCP installed and persisted`)
      else toast.error(`${plugin.name} wrote config but did not persist in Daena registry`)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'MCP install failed')
    } finally {
      setBusy(null)
    }
  }

  async function probeServer(serverKey: string) {
    setBusy(`probe:${serverKey}`)
    try {
      const res = await api.post(`/connections/extensions/${serverKey}/probe-auth`, {}, { silent: false })
      const data = res.data?.data
      const message = data?.alive
        ? `Alive, ${data.tools_count ?? 0} tools${data.connected_as ? `, ${data.connected_as}` : ''}`
        : probeMessage(data?.error)
      setProbe((prev) => ({ ...prev, [serverKey]: message }))
      if (data?.alive) toast.success(`${serverKey} is callable`)
      else toast.error(`${serverKey} is not callable. See row details.`)
    } catch (err) {
      const msg = probeMessage(err instanceof Error ? err.message : 'Probe failed')
      setProbe((prev) => ({ ...prev, [serverKey]: msg }))
      toast.error(`${serverKey} probe failed. See row details.`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <SummaryTile label="Detected in CLI configs" value={detected.length} />
        <SummaryTile label="Registry rows" value={registry.length} />
        <SummaryTile label="Claude config rows" value={extensions.length} />
        <SummaryTile label="Installable MCPs" value={mcpCatalog.length} />
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-starlight-100">MCP servers</h2>
          <p className="text-[11px] text-starlight-500">
            Import reads CLI configs. Install writes Claude Desktop config and Daena MCP persistence.
          </p>
        </div>
        <div className="flex gap-2">
          <div className="relative w-full md:w-72">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-starlight-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search MCPs..."
              aria-label="Search MCP servers"
              className="glass-input w-full rounded-md py-2 pl-8 pr-3 text-xs text-starlight-200"
            />
          </div>
          <button
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-md border border-status-error/25 bg-status-error/5 px-3 py-2 text-xs text-status-error">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      <section className="space-y-2">
        <SectionHeading title="Daena MCP registry" subtitle="Rows Daena knows about. A row is callable only after Test succeeds." />
        {loading && registry.length === 0 ? (
          <LoadingLine label="Loading live MCP registry..." />
        ) : filteredRegistry.length > 0 ? (
          <div className="divide-y divide-white/5 rounded-lg border border-white/5 bg-midnight-400/20">
            {filteredRegistry.map((entry) => (
              <div key={entry.server_key} className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-white/5">
                  <McpIcon id={entry.server_key} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-starlight-100">{entry.display_name || entry.server_key}</span>
                    <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-starlight-400">
                      Registry row
                    </span>
                    {probe[entry.server_key] && (
                      <span className={`rounded-md border px-2 py-0.5 text-[10px] ${
                        probe[entry.server_key].startsWith('Alive')
                          ? 'border-status-success/25 bg-status-success/5 text-status-success'
                          : 'border-status-error/25 bg-status-error/5 text-status-error'
                      }`}>
                        {probe[entry.server_key].startsWith('Alive') ? 'Callable' : 'Not callable'}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 truncate font-mono text-[11px] text-starlight-500" title={shortCommand(entry.command, entry.args)}>
                    {shortCommand(entry.command, entry.args)}
                  </p>
                  {probe[entry.server_key] && <p className="mt-1 text-[11px] text-starlight-400">{probe[entry.server_key]}</p>}
                </div>
                <button
                  onClick={() => void probeServer(entry.server_key)}
                  disabled={busy === `probe:${entry.server_key}`}
                  className="inline-flex items-center justify-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-50"
                >
                  {busy === `probe:${entry.server_key}` ? <Loader2 size={13} className="animate-spin" /> : <Wrench size={13} />}
                  Test
                </button>
              </div>
            ))}
          </div>
        ) : (
          <EmptyLine label="No live MCP servers in Daena registry." />
        )}
      </section>

      <section className="space-y-2">
        <SectionHeading title="Detected from Claude/Codex/Gemini configs" subtitle="Read-only discovery. Import runs the install scanner before persisting." />
        {filteredDetected.length > 0 ? (
          <div className="divide-y divide-white/5 rounded-lg border border-white/5 bg-midnight-400/20">
            {filteredDetected.map((item) => {
              const live = liveKeys.has(item.name)
              return (
                <div key={`${item.source_cli}:${item.name}:${item.command}:${item.args.join(' ')}`} className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-white/5">
                    <McpIcon id={item.name} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-starlight-100">{item.name}</span>
                      <span className="rounded-md border border-accent-cyan/25 bg-accent-cyan/5 px-2 py-0.5 text-[10px] text-accent-cyan">
                        {sourceLabel(item.source_cli)}
                      </span>
                      {live && <span className="rounded-md border border-status-success/25 bg-status-success/5 px-2 py-0.5 text-[10px] text-status-success">Already live</span>}
                    </div>
                    <p className="mt-1 truncate font-mono text-[11px] text-starlight-500" title={shortCommand(item.command, item.args)}>
                      {shortCommand(item.command, item.args)}
                    </p>
                    <p className="mt-1 truncate text-[11px] text-starlight-600" title={item.config_path}>
                      {item.config_path}
                    </p>
                  </div>
                  <button
                    onClick={() => void importDetected(item)}
                    disabled={live || busy === `import:${item.name}`}
                    className="inline-flex items-center justify-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-xs text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-40"
                  >
                    {busy === `import:${item.name}` ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                    Import to Daena
                  </button>
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyLine label="No MCP servers detected in Claude, Codex, or Gemini config paths." />
        )}
      </section>

      <section className="space-y-2">
        <SectionHeading title="Installable MCP catalog" subtitle="Plugin definitions that include an MCP package." />
        {filteredCatalog.length > 0 ? (
          <div className="grid gap-2 lg:grid-cols-2">
            {filteredCatalog.map((plugin) => {
              const installed = Boolean(plugin.mcp_package && livePackages.has(plugin.mcp_package))
              return (
                <div key={plugin.id} className="rounded-lg border border-white/5 bg-midnight-400/20 p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-white/5">
                      <McpIcon id={plugin.id} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-starlight-100">{plugin.name}</span>
                        {installed && <span className="rounded-md border border-status-success/25 bg-status-success/5 px-2 py-0.5 text-[10px] text-status-success">Installed</span>}
                      </div>
                      <p className="mt-1 text-xs text-starlight-500">{plugin.subtitle}</p>
                      <p className="mt-2 truncate font-mono text-[11px] text-starlight-600" title={plugin.mcp_package || ''}>
                        npx -y {plugin.mcp_package}
                      </p>
                      {plugin.skills.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {plugin.skills.slice(0, 4).map((skill) => (
                            <span key={skill.id} className="rounded-md bg-white/5 px-2 py-1 text-[10px] text-starlight-400">
                              {skill.name}
                            </span>
                          ))}
                          {plugin.skills.length > 4 && (
                            <span className="rounded-md bg-white/5 px-2 py-1 text-[10px] text-starlight-500">
                              +{plugin.skills.length - 4} skills
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={() => void installCatalog(plugin)}
                      disabled={installed || busy === `install:${plugin.id}`}
                      className="inline-flex items-center gap-1.5 rounded-md border border-accent-amber/30 bg-accent-amber/10 px-3 py-1.5 text-xs text-accent-amber hover:bg-accent-amber/20 disabled:opacity-40"
                    >
                      {busy === `install:${plugin.id}` ? <Loader2 size={13} className="animate-spin" /> : <PackagePlus size={13} />}
                      Install MCP
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyLine label="No installable MCP package definitions found." />
        )}
      </section>

      {extensions.length > 0 && (
        <section className="space-y-2">
          <SectionHeading title="Claude Desktop config rows" subtitle="Rows read from Claude Desktop config after permission hydration." />
          <div className="grid gap-2 lg:grid-cols-2">
            {extensions.map((ext) => (
              <div key={ext.id} className="rounded-lg border border-white/5 bg-midnight-400/20 p-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/5">
                    <McpIcon id={ext.id} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-starlight-100">{ext.name}</span>
                      <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-starlight-400">{ext.permission}</span>
                    </div>
                    <p className="mt-1 text-xs text-starlight-500">{ext.description || ext.source || 'No description'}</p>
                  </div>
                  <Server size={14} className="text-starlight-500" />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-white/5 bg-midnight-400/20 px-3 py-2">
      <div className="text-lg font-semibold text-starlight-100">{value}</div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-starlight-500">{label}</div>
    </div>
  )
}

function SectionHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-starlight-100">{title}</h3>
      <p className="text-[11px] text-starlight-500">{subtitle}</p>
    </div>
  )
}

function LoadingLine({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-midnight-400/20 px-4 py-4 text-sm text-starlight-400">
      <Loader2 size={14} className="mr-2 inline animate-spin" />
      {label}
    </div>
  )
}

function EmptyLine({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/10 bg-midnight-400/10 px-4 py-6 text-sm text-starlight-500">
      {label}
    </div>
  )
}

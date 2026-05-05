/**
 * PluginsCatalogBrowser -- Codex/Claude-style app connector catalog.
 *
 * Contract:
 *   - Install opens the unified install dialog and then persists the
 *     resulting account connection through the backend.
 *   - Connect account re-opens the same install dialog for installed
 *     but unauthenticated connectors.
 *   - Connected is shown only when the backend instance status is CONNECTED.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  BookOpen,
  Briefcase,
  Code,
  KeyRound,
  Loader2,
  Package,
  Palette,
  Plug,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Unplug,
  UserCircle,
} from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { getBrandIcon } from '@/components/icons/BrandIcons'
import ConnectorInstallDialog from '@/components/connections/ConnectorInstallDialog'
import { useConnectorCatalog, type CatalogConnector } from '@/hooks/useConnectorCatalog'
import { CONNECTOR_MCP_EQUIVALENT } from './catalog'

interface InstanceRow {
  id: string
  connector_id: string
  status: string
  connected_at?: string
  account_identity?: string | null
}

interface InstancesResponse {
  data: InstanceRow[]
}

const CATEGORY_ICON: Record<string, typeof Code> = {
  Coding: Code,
  Productivity: Briefcase,
  Research: BookOpen,
  Lifestyle: Sparkles,
  Design: Palette,
}

function slugifyName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function connectorSlug(connector: CatalogConnector): string {
  return connector.slug || slugifyName(connector.name)
}

function normalizeAuth(authType: string | null | undefined): string {
  const value = String(authType || 'none').trim().toLowerCase()
  if (value === 'oauth2') return 'oauth'
  if (value === 'apikey') return 'api_key'
  return value
}

function authMethod(connector: CatalogConnector): string {
  const method = String(connector.auth?.method || '').trim().toLowerCase()
  if (method) return method
  const authType = normalizeAuth(connector.auth_type)
  if (authType === 'token' || authType === 'api_key') return 'api_token'
  if (authType === 'oauth') return 'oauth_managed'
  return authType || 'none'
}

function hasMcpServer(connector: CatalogConnector, slug: string): boolean {
  return Boolean(CONNECTOR_MCP_EQUIVALENT[slug]) ||
    Boolean(connector.mcp_servers && Object.keys(connector.mcp_servers).length > 0)
}

function isSkillOnlyConnector(connector: CatalogConnector, slug: string): boolean {
  return authMethod(connector) === 'none' && !hasMcpServer(connector, slug)
}

function skillOnlyReason(connector: CatalogConnector): string {
  const name = connector.name.toLowerCase()
  if (name.includes('macos') || name.includes('ios') || name.includes('xcode')) {
    return 'Skill pack only. Xcode/macOS tooling is not callable from this Windows Daena runtime.'
  }
  return 'Skill pack only. No backend connector, OAuth flow, MCP server, or callable Daena adapter is wired.'
}

function normalizeStatus(status: string | null | undefined): string {
  return String(status || '').trim().toUpperCase()
}

function isInstalled(instance?: InstanceRow): boolean {
  const status = normalizeStatus(instance?.status)
  return Boolean(instance) && status !== 'DISCONNECTED'
}

function isConnected(instance?: InstanceRow): boolean {
  return normalizeStatus(instance?.status) === 'CONNECTED'
}

function apiErrorMessage(err: unknown, fallback: string): string {
  const maybe = err as {
    response?: { data?: { detail?: string; error?: { message?: string }; message?: string } }
    message?: string
  }
  return (
    maybe?.response?.data?.detail ||
    maybe?.response?.data?.error?.message ||
    maybe?.response?.data?.message ||
    maybe?.message ||
    fallback
  )
}

function ConnectorIcon({ connector }: { connector: Pick<CatalogConnector, 'name' | 'category' | 'icon_url'> }) {
  if (connector.icon_url) {
    return <img src={connector.icon_url} alt="" width={22} height={22} className="rounded-sm" loading="lazy" />
  }
  const Brand = getBrandIcon(connector.name, 'connector')
  if (Brand) return <Brand size={22} className="text-accent-cyan" />
  const category = connector.category
  const Icon = (category && CATEGORY_ICON[category]) || Package
  return <Icon size={22} className="text-accent-cyan" />
}

// PR-CONNECTIONS-TRUTH-CLEANUP (2026-05-02): the V1 catalog uses the
// legacy ``_status_for_install`` heuristic (credentials present ==
// connected). The V2 panels use real probe results. We keep the V1
// pills but qualify "Connected" with a "(legacy)" suffix and a
// tooltip so an operator hovering the badge sees the heuristic source
// and is pointed at the V2 truth surface.
const LEGACY_STATUS_TOOLTIP =
  'Legacy V1 status: derived from credentials present, NOT from a real ' +
  'probe round-trip. See the All Connections (V2) tab for canonical ' +
  '"is this actually callable?" truth.'

function StatusBadge({ instance, authType }: { instance?: InstanceRow; authType: string }) {
  const status = normalizeStatus(instance?.status)
  if (!instance || status === 'DISCONNECTED') {
    return <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-starlight-400">Available</span>
  }
  if (status === 'CONNECTED') {
    return (
      <span
        title={LEGACY_STATUS_TOOLTIP}
        className="rounded-full border border-status-success/30 bg-status-success/10 px-2 py-0.5 text-[10px] text-status-success"
      >
        Connected (legacy)
      </span>
    )
  }
  if (status === 'INSTALLED') {
    return (
      <span
        title="Legacy V1 status: install record exists. Run a probe in the V2 panel to confirm callable."
        className="rounded-full border border-accent-amber/30 bg-accent-amber/10 px-2 py-0.5 text-[10px] text-accent-amber"
      >
        Installed
      </span>
    )
  }
  if (status === 'NEEDS_REAUTH') {
    return <span className="rounded-full border border-status-warning/30 bg-status-warning/10 px-2 py-0.5 text-[10px] text-status-warning">Needs reauth</span>
  }
  if (status === 'ERROR') {
    return <span className="rounded-full border border-status-error/30 bg-status-error/10 px-2 py-0.5 text-[10px] text-status-error">Error</span>
  }
  if (authType === 'none') {
    return (
      <span
        title="Skill-only connector: no install or auth required. Always reachable."
        className="rounded-full border border-status-success/30 bg-status-success/10 px-2 py-0.5 text-[10px] text-status-success"
      >
        Ready
      </span>
    )
  }
  return <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-starlight-400">{status || 'Unknown'}</span>
}

function SkillOnlyBadge() {
  return <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-starlight-400">Skill pack</span>
}

function CategoryFilter({
  value,
  onChange,
  categories,
  total,
}: {
  value: string | null
  onChange: (v: string | null) => void
  categories: { name: string; count: number }[]
  total: number
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        onClick={() => onChange(null)}
        className={`px-2.5 py-1 rounded-md text-[11px] font-medium border ${
          value === null
            ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30'
            : 'bg-white/5 text-starlight-400 border-white/10 hover:bg-white/10'
        }`}
      >
        All ({total})
      </button>
      {categories.map((cat) => (
        <button
          key={cat.name}
          onClick={() => onChange(cat.name)}
          className={`px-2.5 py-1 rounded-md text-[11px] font-medium border ${
            value === cat.name
              ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30'
              : 'bg-white/5 text-starlight-400 border-white/10 hover:bg-white/10'
          }`}
        >
          {cat.name} ({cat.count})
        </button>
      ))}
    </div>
  )
}

export default function PluginsCatalogBrowser() {
  const { connectors, version, loading, error, refresh } = useConnectorCatalog()
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [instances, setInstances] = useState<InstanceRow[]>([])
  const [instancesLoading, setInstancesLoading] = useState(true)
  const [busyConnectorId, setBusyConnectorId] = useState<string | null>(null)
  const [installSlug, setInstallSlug] = useState<string | null>(null)
  const [recommendedState, setRecommendedState] = useState<string | null>(null)
  const autoInstallAttempted = useRef(false)

  async function loadInstances() {
    setInstancesLoading(true)
    try {
      const res = await api.get<InstancesResponse>('/connections/instances?page_size=100')
      const list = Array.isArray(res.data?.data) ? res.data.data : []
      setInstances(list)
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to load installed connectors'))
    } finally {
      setInstancesLoading(false)
    }
  }

  useEffect(() => {
    void loadInstances()
  }, [])

  useEffect(() => {
    if (loading || error || instancesLoading || autoInstallAttempted.current) return
    if (connectors.length === 0 || instances.length > 0) return
    autoInstallAttempted.current = true
    void installRecommended(false)
  }, [connectors.length, error, instances.length, instancesLoading, loading])

  async function installRecommended(showToast = true) {
    setRecommendedState('Installing recommended connectors...')
    try {
      const res = await api.post<{ data: { count: number } }>(
        '/connections/instances/install-defaults',
        {},
        { silent: !showToast },
      )
      const count = res.data?.data?.count ?? 0
      setRecommendedState(`Recommended starter set installed: ${count} connectors`)
      if (showToast) toast.success(`Installed ${count} recommended connectors`)
      await loadInstances()
    } catch (err) {
      const msg = apiErrorMessage(err, 'Recommended install failed')
      setRecommendedState(`Recommended install failed: ${msg}`)
      if (showToast) toast.error(msg)
    }
  }

  async function disconnect(instance: InstanceRow, connectorName: string) {
    setBusyConnectorId(instance.connector_id)
    try {
      await api.post(`/connections/instances/${instance.id}/disconnect`, {}, { silent: false })
      toast.success(`${connectorName} disconnected`)
      await loadInstances()
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Disconnect failed'))
    } finally {
      setBusyConnectorId(null)
    }
  }

  const instanceByConnectorId = useMemo(() => {
    const map = new Map<string, InstanceRow>()
    for (const instance of instances) map.set(instance.connector_id, instance)
    return map
  }, [instances])

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const c of connectors) {
      const cat = c.category ?? 'Other'
      counts.set(cat, (counts.get(cat) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
  }, [connectors])

  const filtered = useMemo(() => {
    let result = connectors
    if (activeCategory) result = result.filter((c) => c.category === activeCategory)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.description ?? '').toLowerCase().includes(q) ||
          (c.category ?? '').toLowerCase().includes(q),
      )
    }
    return result
  }, [activeCategory, connectors, search])

  const connectorById = useMemo(() => {
    const map = new Map<string, CatalogConnector>()
    for (const connector of connectors) map.set(connector.id, connector)
    return map
  }, [connectors])

  const installedCount = instances.filter((i) => {
    const connector = connectorById.get(i.connector_id)
    const slug = connector ? connectorSlug(connector) : ''
    return Boolean(connector) && !isSkillOnlyConnector(connector!, slug) && isInstalled(i)
  }).length
  const connectedCount = instances.filter((i) => {
    const connector = connectorById.get(i.connector_id)
    const slug = connector ? connectorSlug(connector) : ''
    return Boolean(connector) && !isSkillOnlyConnector(connector!, slug) && isConnected(i)
  }).length

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-starlight-100">Plugins / App Connections</h2>
          <p className="text-[11px] text-starlight-500">
            {connectors.length} apps · {installedCount} installed · {connectedCount} connected
            {version && ` · catalog v${version}`}
          </p>
          {recommendedState && <p className="mt-1 text-[10px] text-starlight-500">{recommendedState}</p>}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {/* Sprint-7 acceptance fix (2026-05-04): this control lives in the
              Legacy V1 panel inside Advanced. The label used to read "Install
              recommended" with primary cyan styling, which made it look like
              the canonical install path. The canonical path is the V2
              MCPInstallDrawer in the Plugins tab. We mute the styling and
              relabel so an operator who lands here doesn't mistake it for the
              modern install. */}
          <button
            onClick={() => void installRecommended(true)}
            title="Legacy V1 install path. The modern install lives in the Plugins tab via the MCP install drawer."
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-400 hover:bg-white/10"
          >
            <ShieldCheck size={13} />
            Legacy install (not recommended)
          </button>
          <button
            onClick={() => {
              void refresh()
              void loadInstances()
            }}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
          >
            <RefreshCw size={13} />
            Refresh
          </button>
          <div className="relative sm:w-72">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-starlight-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search apps, skills, categories..."
              className="w-full glass-input rounded-lg py-1.5 pl-8 pr-3 text-xs text-starlight-200"
            />
          </div>
        </div>
      </div>

      <CategoryFilter value={activeCategory} onChange={setActiveCategory} categories={categoryCounts} total={connectors.length} />

      {loading && (
        <div className="flex items-center gap-2 rounded-lg border border-white/5 bg-midnight-400/30 px-4 py-3 text-xs text-starlight-400">
          <Loader2 size={13} className="animate-spin" />
          Loading connector catalog...
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-status-error/30 bg-status-error/5 p-3">
          <div className="flex items-start gap-2 text-xs text-status-error">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Catalog unavailable</p>
              <p className="mt-0.5 text-[11px] text-status-error/80">{error}</p>
              <button onClick={() => void refresh()} className="mt-2 text-[11px] text-accent-cyan hover:underline">
                Retry
              </button>
            </div>
          </div>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="rounded-lg border border-dashed border-white/10 bg-midnight-400/20 px-4 py-6 text-center">
          <p className="text-xs text-starlight-400">No connectors match {search ? `"${search}"` : 'this filter'}.</p>
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((connector) => {
            const instance = instanceByConnectorId.get(connector.id)
            const authType = normalizeAuth(connector.auth_type)
            const busy = busyConnectorId === connector.id
            const slug = connectorSlug(connector)
            const hasMcp = hasMcpServer(connector, slug)
            const skillOnly = isSkillOnlyConnector(connector, slug)
            const installed = !skillOnly && isInstalled(instance)
            const connected = !skillOnly && isConnected(instance)
            const skills = connector.skills?.length
              ? connector.skills.map((skill) => ({
                  name: skill.name,
                  description: skill.description || `Skill bundled with ${connector.name}.`,
                }))
              : connector.tools.map((tool) => ({
                  name: tool.name,
                  description: tool.description,
                }))
            const skillCount = connector.skill_count ?? skills.length

            return (
              <div
                key={connector.id}
                className="flex min-h-[188px] flex-col gap-3 rounded-lg border border-white/5 bg-midnight-400/30 p-3 transition-colors hover:border-white/10"
              >
                <div className="flex items-start gap-3">
                  <div className="rounded-md bg-white/5 p-2">
                    <ConnectorIcon connector={connector} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="truncate text-sm font-medium text-starlight-100">{connector.name}</div>
                      {skillOnly ? <SkillOnlyBadge /> : <StatusBadge instance={instance} authType={authType} />}
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] text-starlight-500">
                      <span>{connector.category ?? 'Other'}</span>
                      <span>·</span>
                      <span className="inline-flex items-center gap-1">
                        {authType === 'none' ? <ShieldCheck size={9} /> : <KeyRound size={9} />}
                        {authType === 'none' ? 'No auth' : authType.replace('_', ' ')}
                      </span>
                      {hasMcp && (
                        <>
                          <span>·</span>
                          <span className="text-accent-cyan">MCP available</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {connector.description && (
                  <p className="line-clamp-2 min-h-[32px] text-[11px] leading-relaxed text-starlight-400">{connector.description}</p>
                )}

                {connected && instance?.account_identity && (
                  <div className="flex items-center gap-1.5 rounded-md border border-status-success/20 bg-status-success/5 px-2 py-1.5 text-[10px] text-status-success">
                    <UserCircle size={11} />
                    <span className="truncate">Connected as {instance.account_identity}</span>
                  </div>
                )}

                {skillOnly && (
                  <div className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1.5 text-[10px] leading-relaxed text-starlight-500">
                    {skillOnlyReason(connector)}
                  </div>
                )}

                <div className="grid gap-1">
                  {skills.slice(0, 3).map((skill) => (
                    <div key={skill.name} className="rounded-md border border-white/5 bg-white/[0.03] px-2 py-1.5">
                      <div className="text-[10px] font-medium text-starlight-200">{skill.name}</div>
                      {skill.description && <div className="mt-0.5 line-clamp-1 text-[10px] text-starlight-500">{skill.description}</div>}
                    </div>
                  ))}
                  {skillCount > 3 && <div className="text-[10px] text-starlight-500">+{skillCount - 3} more skills</div>}
                </div>

                <div className="mt-auto flex items-center justify-between gap-2 pt-1">
                  <div className="text-[10px] text-starlight-500">
                    {skillCount} {skillCount === 1 ? 'skill' : 'skills'}
                    {connector.catalog_seeded === false ? ' - seeds on install' : ''}
                  </div>
                  <div className="flex items-center gap-1.5">
                    {skillOnly && (
                      <span className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-starlight-500">
                        Not installable
                      </span>
                    )}
                    {!skillOnly && !installed && (
                      <button
                        onClick={() => setInstallSlug(slug)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 rounded-md border border-accent-cyan/30 bg-accent-cyan/15 px-2.5 py-1 text-[10px] text-accent-cyan hover:bg-accent-cyan/25 disabled:opacity-50"
                      >
                        {busy ? <Loader2 size={10} className="animate-spin" /> : <Plug size={10} />}
                        {authMethod(connector) === 'api_token' ? 'Connect account' : 'Connect'}
                      </button>
                    )}
                    {!skillOnly && installed && !connected && authType !== 'none' && (
                      <button
                        onClick={() => setInstallSlug(slug)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 rounded-md border border-accent-amber/30 bg-accent-amber/10 px-2.5 py-1 text-[10px] text-accent-amber hover:bg-accent-amber/20 disabled:opacity-50"
                      >
                        <KeyRound size={10} />
                        Connect account
                      </button>
                    )}
                    {connected && instance && (
                      <button
                        onClick={() => void disconnect(instance, connector.name)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 rounded-md border border-status-error/20 bg-status-error/10 px-2 py-1 text-[10px] text-status-error hover:bg-status-error/20 disabled:opacity-50"
                      >
                        {busy ? <Loader2 size={10} className="animate-spin" /> : <Unplug size={10} />}
                        Disconnect
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <ConnectorInstallDialog
        slug={installSlug}
        open={installSlug !== null}
        onClose={() => setInstallSlug(null)}
        onConnected={() => {
          void loadInstances()
          void refresh()
        }}
      />

    </div>
  )
}

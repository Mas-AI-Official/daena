/**
 * useConnectorCatalog -- fetches the global connector catalog from the
 * backend so the Plugins tab no longer carries a hardcoded ~110 entry
 * CONNECTORS array. Pairs with GET /api/v1/connections/catalog which is
 * seeded at startup from backend/app/config/connector_catalog.json.
 *
 * Polling cadence is conservative on purpose: the catalog only changes
 * when an operator updates the JSON file or a fresh deploy ships, so a
 * 5-minute in-memory cache (matching the backend's TTL) is more than
 * enough. Callers can force a re-fetch via `refresh`.
 *
 * Honesty + persistence + visibility (CLAUDE.md rule 17): errors are
 * surfaced inline via the returned `error` field; we never silently
 * swap to a hardcoded fallback list. If the catalog is unreachable
 * the component renders an honest empty state with a retry affordance.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '@/lib/api'

export type ConnectorAuthMethod = 'oauth' | 'api_key' | 'token' | 'none'

export interface ConnectorTool {
  /** Stable tool id used by the governance gate. */
  name: string
  /** One-line description rendered in the skill card. */
  description: string
}

export interface CatalogConnector {
  /** Connector row UUID -- not used by the UI today, but the API
   *  returns it so future per-connector edits can target it. */
  id: string
  /** Display name (matches the legacy CONNECTORS[].name). */
  name: string
  /** Short subtitle shown on the row header. */
  description: string | null
  category: string | null
  auth_type: ConnectorAuthMethod | string
  icon_url: string | null
  tools: ConnectorTool[]
  config_schema: Record<string, unknown>
  slug?: string | null
  interface?: {
    displayName?: string
    shortDescription?: string
    longDescription?: string
    developerName?: string
    websiteURL?: string
    privacyPolicyURL?: string
    termsOfServiceURL?: string
    brandColor?: string
    capabilities?: string[]
    defaultPrompts?: string[] | string
    logoPath?: string
  }
  auth?: {
    method?: string
    token_settings_url?: string
    mcp_url?: string
  }
  skills?: Array<{
    id: string
    name: string
    description?: string
    source?: string
  }>
  skill_count?: number
  mcp_servers?: Record<string, { type?: string; url?: string; note?: string }>
  catalog_seeded?: boolean
}

export interface CatalogPayload {
  version: string
  connectors: CatalogConnector[]
}

interface ResponseBody {
  version: string
  connectors: CatalogConnector[]
}

interface UseConnectorCatalogReturn {
  connectors: CatalogConnector[]
  version: string
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const CACHE_TTL_MS = 5 * 60 * 1000

let _module_cache: { payload: CatalogPayload; expires_at: number } | null = null

export function useConnectorCatalog(): UseConnectorCatalogReturn {
  const [connectors, setConnectors] = useState<CatalogConnector[]>(
    () => _module_cache?.payload.connectors ?? [],
  )
  const [version, setVersion] = useState<string>(
    () => _module_cache?.payload.version ?? '',
  )
  const [loading, setLoading] = useState<boolean>(() => _module_cache === null)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const fetchOnce = useCallback(async (force = false): Promise<void> => {
    if (!force && _module_cache && Date.now() < _module_cache.expires_at) {
      if (!mounted.current) return
      setConnectors(_module_cache.payload.connectors)
      setVersion(_module_cache.payload.version)
      setLoading(false)
      setError(null)
      return
    }

    setLoading((prev) => (_module_cache === null ? true : prev))
    setError(null)
    try {
      const res = await api.get<ResponseBody>('/connections/catalog')
      const payload: CatalogPayload = {
        version: res.data?.version ?? 'unknown',
        connectors: Array.isArray(res.data?.connectors) ? res.data.connectors : [],
      }
      _module_cache = { payload, expires_at: Date.now() + CACHE_TTL_MS }
      if (!mounted.current) return
      setConnectors(payload.connectors)
      setVersion(payload.version)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load connector catalog'
      if (!mounted.current) return
      setError(msg)
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  const refresh = useCallback(async (): Promise<void> => {
    await fetchOnce(true)
  }, [fetchOnce])

  useEffect(() => {
    mounted.current = true
    void fetchOnce(false)
    return () => {
      mounted.current = false
    }
  }, [fetchOnce])

  return { connectors, version, loading, error, refresh }
}

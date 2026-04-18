/**
 * useMCPDetections: fetches CLI-installed MCP servers Daena detected and
 * provides a one-click Import that routes through the backend's install
 * scanner before registering the server.
 *
 * Maps to Session 8's backend detector + Session 9's API endpoints:
 *   GET  /api/v1/mcp-sync/detected
 *   POST /api/v1/mcp-sync/import
 *
 * The backend is the source of truth for safety and registration. The
 * hook only orchestrates the user-facing state: list, loading flag,
 * per-row import status, and a refresh.
 */
import { useCallback, useEffect, useState } from 'react'

import { api } from '@/lib/api'

export interface DetectedMCP {
  source_cli: string
  config_path: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  url: string
  notes: string
}

export interface ImportResult {
  safe: boolean
  registered: boolean
  name: string
  governance_tier: number
  blockers: string[]
  warnings: string[]
}

type ImportStatus = 'idle' | 'importing' | 'imported' | 'blocked' | 'error'

interface UseMCPDetectionsReturn {
  detections: DetectedMCP[]
  loading: boolean
  error: string | null
  importStatus: Record<string, ImportStatus>
  importResults: Record<string, ImportResult>
  refresh: () => Promise<void>
  importMCP: (mcp: DetectedMCP) => Promise<ImportResult | null>
}

export function useMCPDetections(): UseMCPDetectionsReturn {
  const [detections, setDetections] = useState<DetectedMCP[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importStatus, setImportStatus] = useState<Record<string, ImportStatus>>({})
  const [importResults, setImportResults] = useState<Record<string, ImportResult>>({})

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get<DetectedMCP[]>('/mcp-sync/detected')
      setDetections(res.data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load detected MCPs'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  const importMCP = useCallback(async (mcp: DetectedMCP): Promise<ImportResult | null> => {
    setImportStatus((s) => ({ ...s, [mcp.name]: 'importing' }))
    try {
      const res = await api.post<ImportResult>('/mcp-sync/import', {
        name: mcp.name,
        command: mcp.command,
        args: mcp.args,
        env: mcp.env,
        url: mcp.url,
      })
      const result = res.data
      setImportResults((r) => ({ ...r, [mcp.name]: result }))
      setImportStatus((s) => ({
        ...s,
        [mcp.name]: result.safe && result.registered ? 'imported' : 'blocked',
      }))
      return result
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Import failed'
      setError(msg)
      setImportStatus((s) => ({ ...s, [mcp.name]: 'error' }))
      return null
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return {
    detections,
    loading,
    error,
    importStatus,
    importResults,
    refresh,
    importMCP,
  }
}

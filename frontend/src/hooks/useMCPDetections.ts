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
 *
 * 2026-04-23 wiring fix: a successful import now (a) toasts visible
 * confirmation, (b) re-fetches the detection list so the imported
 * server falls out of the "detected, not imported" warning, and
 * (c) optionally calls a caller-supplied `onImported` callback so the
 * parent can refresh the MCP Servers registry. Before this fix the
 * backend would register context7 cleanly but every UI counter
 * stayed stale -- looked like "nothing happened" to the user.
 */
import { useCallback, useEffect, useState } from 'react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

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

export interface UseMCPDetectionsOptions {
  /**
   * Called once after a successful import (safe=true && registered=true).
   * Parent passes the MCP registry refresh so the MCP Servers tab,
   * header chip, and tab counter all reflect the newly imported
   * server immediately. Without this, the registry stays stale and
   * the import looks like a no-op even though the backend wrote it.
   */
  onImported?: (result: ImportResult) => void | Promise<void>
}

export function useMCPDetections(opts: UseMCPDetectionsOptions = {}): UseMCPDetectionsReturn {
  const { onImported } = opts
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
      const ok = result.safe && result.registered
      setImportStatus((s) => ({
        ...s,
        [mcp.name]: ok ? 'imported' : 'blocked',
      }))

      // Visible feedback. Before this commit the only signal was the
      // button text changing -- easy to miss when the cursor moved off.
      if (ok) {
        toast.success(`Imported ${mcp.name} (governance tier ${result.governance_tier})`)
        // Re-fetch detections so the imported entry leaves the
        // "detected, not imported" warning band.
        try {
          await refresh()
        } catch {
          /* ignore -- toast already confirmed the import */
        }
        // Tell the parent to refresh whatever else displays MCP state
        // (the registry that powers the MCP Servers tab + the header
        // chip on ConnectionsPage).
        if (onImported) {
          try {
            await onImported(result)
          } catch (cb_err) {
            // A failed onImported should not mask import success.
            console.warn('useMCPDetections.onImported callback failed', cb_err)
          }
        }
      } else if (result.blockers && result.blockers.length > 0) {
        toast.error(`${mcp.name} blocked: ${result.blockers.join('; ')}`)
      } else {
        toast.warning(`${mcp.name} did not register. ${result.warnings?.join(' ') ?? ''}`)
      }

      return result
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Import failed'
      setError(msg)
      toast.error(`Import ${mcp.name} failed: ${msg}`)
      setImportStatus((s) => ({ ...s, [mcp.name]: 'error' }))
      return null
    }
  }, [refresh, onImported])

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

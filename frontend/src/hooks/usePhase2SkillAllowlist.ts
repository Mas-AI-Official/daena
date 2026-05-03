/**
 * usePhase2SkillAllowlist -- caches the Phase 2 read-only skill
 * allowlist so SkillBundleSection chips know whether to surface
 * the "Run read-only skill" affordance.
 *
 * PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03).
 *
 * The allowlist is small (~15 entries) and stable per backend deploy.
 * One fetch per session is plenty -- callers receive a Map keyed by
 * "plugin_id:skill_id" for O(1) lookup.
 */

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Phase2AllowlistRow } from '@/pages/connections/SkillExecuteModal'

interface AllowlistResponse {
  phase: string
  execution_mode_default: string
  entries: Phase2AllowlistRow[]
}

let _cache: Map<string, Phase2AllowlistRow> | null = null
let _inflight: Promise<Map<string, Phase2AllowlistRow>> | null = null

async function fetchAllowlist(): Promise<Map<string, Phase2AllowlistRow>> {
  if (_cache) return _cache
  if (_inflight) return _inflight
  _inflight = (async () => {
    try {
      const res = await api.get<AllowlistResponse>('/connections/v2/skills/allowlist')
      const map = new Map<string, Phase2AllowlistRow>()
      for (const row of res.data.entries ?? []) {
        map.set(`${row.plugin_id}:${row.skill_id}`, row)
      }
      _cache = map
      return map
    } catch {
      // Fail closed -- empty map means no Run button surfaces.
      const empty = new Map<string, Phase2AllowlistRow>()
      _cache = empty
      return empty
    } finally {
      _inflight = null
    }
  })()
  return _inflight
}

export function usePhase2SkillAllowlist(): {
  loading: boolean
  lookup: (plugin_id: string, skill_id: string) => Phase2AllowlistRow | undefined
} {
  const [allowlist, setAllowlist] = useState<Map<string, Phase2AllowlistRow> | null>(_cache)

  useEffect(() => {
    if (_cache) return
    let cancelled = false
    void fetchAllowlist().then((m) => {
      if (!cancelled) setAllowlist(m)
    })
    return () => { cancelled = true }
  }, [])

  return {
    loading: allowlist === null,
    lookup: (plugin_id: string, skill_id: string) =>
      allowlist?.get(`${plugin_id}:${skill_id}`),
  }
}

/** Test-only helper to clear the module-level cache. */
export function _resetPhase2AllowlistCacheForTests(): void {
  _cache = null
  _inflight = null
}

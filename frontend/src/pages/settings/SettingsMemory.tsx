/**
 * Memory settings -- NBMF tier config, agent experience stats, purge controls.
 *
 * Shows:
 *   - 5 NBMF tiers with counts
 *   - Agent experience stats (quarantine, trust, validated)
 *   - Purge controls
 *   - Trust validation trigger
 */
import { useState, useEffect, useCallback } from 'react'
import { Card, Badge } from '@/components/common'
import { AlertTriangle, Database, Layers, Trash2, Brain, ShieldCheck, FlaskConical, RefreshCw, Search } from 'lucide-react'
import api from '@/lib/api'
import { toast } from '@/stores/toastStore'

const MEMORY_TIERS = [
  { tier: 0, name: 'Ephemeral', ttl: 'Session only', desc: 'Scratch pad, lost on session close' },
  { tier: 1, name: 'Working', ttl: '24 hours', desc: 'Short-term cross-session context' },
  { tier: 2, name: 'Persistent', ttl: '30 days', desc: 'User preferences and learned patterns' },
  { tier: 3, name: 'Archival', ttl: '1 year', desc: 'Long-term facts and history' },
  { tier: 4, name: 'Core', ttl: 'Permanent', desc: 'Identity, policies, hard directives' },
]

interface ServiceStatus {
  status?: string
  enabled?: boolean
  reason?: string
  vault_path?: string | null
  total_memories?: number
  per_tier_counts?: Record<string, number>
  experience_count?: number
  quarantined_count?: number
  avg_trust_score?: number
}

// PR-RAG-HONEST: the actual chat-recall algorithm (keyword Jaccard
// blend) is described here so the UI can surface what truly runs --
// not just that vector RAG is not configured.
interface RecallDescriptor {
  mode?: string
  embeddings_enabled?: boolean
  function_path?: string
  scoring?: Record<string, number>
  scope_priority?: string[]
  filters?: string[]
  tokenizer?: string
  default_top_k?: number
  reason?: string
}

interface MemoryStatusResponse {
  memory?: ServiceStatus
  rag?: ServiceStatus
  obsidian?: ServiceStatus
  recall?: RecallDescriptor
}

function statusVariant(status?: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'online' || status === 'available') return 'success'
  if (status === 'error' || status === 'unavailable') return 'danger'
  if (status === 'not_configured' || status === 'disabled') return 'warning'
  return 'info'
}

export function SettingsMemory() {
  const [totalMemories, setTotalMemories] = useState(0)
  const [tierCounts, setTierCounts] = useState<Record<number, number>>({ 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 })
  const [experienceCount, setExperienceCount] = useState(0)
  const [quarantinedCount, setQuarantinedCount] = useState(0)
  const [avgTrustScore, setAvgTrustScore] = useState(0)
  const [memoryStatus, setMemoryStatus] = useState<MemoryStatusResponse | null>(null)
  const [loadingStats, setLoadingStats] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [validating, setValidating] = useState(false)

  const fetchStats = useCallback(async () => {
    setLoadingStats(true)
    try {
      const res = await api.get('/memory/status')
      const data = res.data?.data
      const memory = data?.memory ?? data
      if (data) {
        setMemoryStatus(data)
      }
      if (memory) {
        setTotalMemories(memory.total_memories ?? 0)
        const counts: Record<number, number> = {}
        const perTier = memory.per_tier_counts ?? {}
        for (let t = 0; t <= 4; t++) {
          counts[t] = perTier[`T${t}`] ?? 0
        }
        setTierCounts(counts)
        setExperienceCount(memory.experience_count ?? 0)
        setQuarantinedCount(memory.quarantined_count ?? 0)
        setAvgTrustScore(memory.avg_trust_score ?? 0)
      }
      setLoadError(null)
    } catch (err) {
      setMemoryStatus(null)
      setLoadError(
        (err as { response?: { status?: number } })?.response?.status
          ? `Memory status endpoint returned ${(err as { response?: { status?: number } }).response?.status}.`
          : 'Memory/RAG/Obsidian status endpoint is unreachable.',
      )
    } finally {
      setLoadingStats(false)
    }
  }, [])

  useEffect(() => {
    void fetchStats()
  }, [fetchStats])

  const handleClearEphemeral = async () => {
    try {
      const res = await api.post('/memory/memories/clear-ephemeral')
      const count = res.data?.data?.archived_count ?? 0
      toast.success(`Cleared ${count} ephemeral/working memories`)
      await fetchStats()
    } catch {
      toast.error('Failed to clear ephemeral memories')
    }
  }

  const handleValidateExperiences = async () => {
    setValidating(true)
    try {
      const res = await api.post('/memory/experiences/validate')
      const data = res.data?.data ?? {}
      toast.success(
        `Validated: ${data.reviewed ?? 0} reviewed, ${data.promoted ?? 0} promoted, ${data.demoted ?? 0} demoted`
      )
      await fetchStats()
    } catch {
      toast.error('Failed to validate experiences')
    } finally {
      setValidating(false)
    }
  }

  const trustColor = avgTrustScore >= 0.7 ? 'text-accent-green' : avgTrustScore >= 0.4 ? 'text-accent-amber' : 'text-starlight-400'

  return (
    <div className="space-y-6">
      {/* Live Status */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
            <Database size={14} /> Memory / RAG / Obsidian Status
          </h3>
          <button
            onClick={() => void fetchStats()}
            disabled={loadingStats}
            className="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            <RefreshCw size={12} className={loadingStats ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
        {loadError && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-status-warning/10 border border-status-warning/30 flex items-start gap-2">
            <AlertTriangle size={14} className="text-status-warning shrink-0 mt-0.5" />
            <p className="text-xs text-starlight-300">{loadError}</p>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: 'NBMF Memory', item: memoryStatus?.memory, fallback: 'loading' },
            { label: 'RAG Retrieval', item: memoryStatus?.rag, fallback: 'unknown' },
            { label: 'Obsidian Vault', item: memoryStatus?.obsidian, fallback: 'unknown' },
          ].map(({ label, item, fallback }) => {
            const status = loadingStats ? fallback : item?.status ?? (loadError ? 'unavailable' : 'unknown')
            return (
              <div key={label} className="px-3 py-3 rounded-lg bg-midnight-800/40 border border-white/5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-starlight-200">{label}</p>
                  <Badge variant={statusVariant(status)} size="sm" dot>{status}</Badge>
                </div>
                <p className="text-[10px] text-starlight-500 mt-2">
                  {item?.reason || (loadingStats ? 'Checking backend status...' : 'No status detail returned.')}
                </p>
                {item?.vault_path && (
                  <p className="text-[10px] text-starlight-600 mt-1 truncate font-mono">{item.vault_path}</p>
                )}
              </div>
            )
          })}
        </div>
      </Card>

      {/* Recall Algorithm — PR-RAG-HONEST.
          Surfaces what chat recall ACTUALLY does (deterministic keyword
          Jaccard blend across tier, confidence, recency) so the operator
          can see the algorithm rather than guess from the absence of RAG. */}
      {memoryStatus?.recall && (
        <Card variant="glass" padding="lg">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
              <Search size={14} /> Recall Algorithm
            </h3>
            <Badge
              variant={memoryStatus.recall.embeddings_enabled ? 'info' : 'warning'}
              size="sm"
              dot
            >
              {memoryStatus.recall.embeddings_enabled ? 'embeddings' : 'no embeddings'}
            </Badge>
          </div>
          {memoryStatus.recall.reason && (
            <p className="text-[11px] text-starlight-400 mb-3 leading-relaxed">
              {memoryStatus.recall.reason}
            </p>
          )}
          {memoryStatus.recall.mode && (
            <div className="mb-3">
              <p className="text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Mode</p>
              <p className="text-xs font-mono text-starlight-200">{memoryStatus.recall.mode}</p>
            </div>
          )}
          {memoryStatus.recall.scoring && Object.keys(memoryStatus.recall.scoring).length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] text-starlight-500 uppercase tracking-wider mb-1.5">Scoring weights</p>
              <div className="space-y-1.5">
                {Object.entries(memoryStatus.recall.scoring).map(([component, weight]) => {
                  const pct = Math.round((weight ?? 0) * 100)
                  return (
                    <div key={component} className="flex items-center gap-2">
                      <span className="text-[11px] text-starlight-300 min-w-[10rem]">
                        {component.replace(/_/g, ' ')}
                      </span>
                      <div className="flex-1 h-1.5 rounded-full bg-midnight-800/60 overflow-hidden">
                        <div
                          className="h-full bg-accent-teal/60"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-mono text-starlight-400 min-w-[2.5rem] text-right">
                        {pct}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
            {memoryStatus.recall.scope_priority && memoryStatus.recall.scope_priority.length > 0 && (
              <div className="px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5">
                <p className="text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Scope priority</p>
                <p className="text-starlight-300 font-mono">
                  {memoryStatus.recall.scope_priority.join(' › ')}
                </p>
              </div>
            )}
            {memoryStatus.recall.filters && memoryStatus.recall.filters.length > 0 && (
              <div className="px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5">
                <p className="text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Filters</p>
                <p className="text-starlight-300 font-mono">
                  {memoryStatus.recall.filters.join(', ')}
                </p>
              </div>
            )}
            {memoryStatus.recall.tokenizer && (
              <div className="px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5 md:col-span-2">
                <p className="text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Tokenizer</p>
                <p className="text-starlight-300 leading-relaxed">{memoryStatus.recall.tokenizer}</p>
              </div>
            )}
            {memoryStatus.recall.function_path && (
              <div className="md:col-span-2">
                <p className="text-[9px] font-mono text-starlight-600 mt-1">
                  source: {memoryStatus.recall.function_path}
                  {memoryStatus.recall.default_top_k != null && (
                    <span className="ml-2">· default top_k={memoryStatus.recall.default_top_k}</span>
                  )}
                </p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* NBMF Tiers */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Layers size={14} /> NBMF Tiers
        </h3>
        <div className="space-y-2">
          {MEMORY_TIERS.map((t) => (
            <div key={t.tier} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
              <Badge
                variant={t.tier <= 1 ? 'default' : t.tier <= 2 ? 'info' : t.tier <= 3 ? 'purple' : 'warning'}
                size="sm"
              >
                T{t.tier}
              </Badge>
              <div className="flex-1">
                <span className="text-xs text-starlight-200 font-semibold">{t.name}</span>
                <p className="text-[10px] text-starlight-500">{t.desc}</p>
              </div>
              <span className="text-xs font-mono text-starlight-300 min-w-[2rem] text-right">
                {loadError ? '--' : tierCounts[t.tier]}
              </span>
              <span className="text-[10px] text-starlight-400 min-w-[5rem]">{t.ttl}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Storage Stats */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Database size={14} /> Storage Stats
        </h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className="text-lg font-display font-bold text-starlight-100">{loadError ? '--' : totalMemories}</p>
            <p className="text-[10px] text-starlight-500">Total Memories</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className="text-lg font-display font-bold text-starlight-100">{loadError ? '--' : tierCounts[0] + tierCounts[1]}</p>
            <p className="text-[10px] text-starlight-500">Ephemeral + Working</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className="text-lg font-display font-bold text-starlight-100">{loadError ? '--' : tierCounts[2] + tierCounts[3] + tierCounts[4]}</p>
            <p className="text-[10px] text-starlight-500">Persistent+</p>
          </div>
        </div>
      </Card>

      {/* Agent Experience (NBMF Learning) */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Brain size={14} /> Agent Experience (NBMF Learning)
        </h3>
        <p className="text-[11px] text-starlight-400 mb-3">
          Agents learn from decisions, skill outcomes, and patterns. New experiences enter quarantine (L2Q) and must pass trust validation before being used in future responses.
        </p>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className="text-lg font-display font-bold text-starlight-100">{loadError ? '--' : experienceCount}</p>
            <p className="text-[10px] text-starlight-500">Total Experiences</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-accent-amber/20">
            <div className="flex items-center gap-1.5">
              <ShieldCheck size={12} className="text-accent-amber" />
              <p className="text-lg font-display font-bold text-accent-amber">{loadError ? '--' : quarantinedCount}</p>
            </div>
            <p className="text-[10px] text-starlight-500">In Quarantine (L2Q)</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className={`text-lg font-display font-bold ${trustColor}`}>
              {loadError ? '--' : `${(avgTrustScore * 100).toFixed(0)}%`}
            </p>
            <p className="text-[10px] text-starlight-500">Avg Trust Score</p>
          </div>
        </div>
        <button
          onClick={handleValidateExperiences}
          disabled={validating || quarantinedCount === 0}
          className="px-3 py-1.5 rounded-lg text-xs bg-accent-teal/10 text-accent-teal hover:bg-accent-teal/20 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          <FlaskConical size={12} />
          {validating ? 'Validating...' : `Validate Quarantined (${quarantinedCount})`}
        </button>
      </Card>

      {/* Purge Controls */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Trash2 size={14} /> Purge Controls
        </h3>
        <div className="space-y-2 max-w-md">
          <p className="text-xs text-starlight-400">
            Clear ephemeral (T0) and working (T1) memories. Persistent and above require ADMIN+ role.
          </p>
          <button
            onClick={handleClearEphemeral}
            className="px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors cursor-pointer"
          >
            Clear Ephemeral Memories
          </button>
        </div>
      </Card>
    </div>
  )
}

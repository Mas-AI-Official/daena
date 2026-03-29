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
import { Database, Layers, Trash2, Brain, ShieldCheck, FlaskConical } from 'lucide-react'
import api from '@/lib/api'
import { toast } from '@/stores/toastStore'

const MEMORY_TIERS = [
  { tier: 0, name: 'Ephemeral', ttl: 'Session only', desc: 'Scratch pad, lost on session close' },
  { tier: 1, name: 'Working', ttl: '24 hours', desc: 'Short-term cross-session context' },
  { tier: 2, name: 'Persistent', ttl: '30 days', desc: 'User preferences and learned patterns' },
  { tier: 3, name: 'Archival', ttl: '1 year', desc: 'Long-term facts and history' },
  { tier: 4, name: 'Core', ttl: 'Permanent', desc: 'Identity, policies, hard directives' },
]

export function SettingsMemory() {
  const [totalMemories, setTotalMemories] = useState(0)
  const [tierCounts, setTierCounts] = useState<Record<number, number>>({ 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 })
  const [experienceCount, setExperienceCount] = useState(0)
  const [quarantinedCount, setQuarantinedCount] = useState(0)
  const [avgTrustScore, setAvgTrustScore] = useState(0)
  const [validating, setValidating] = useState(false)

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/memory/stats')
      const data = res.data?.data
      if (data) {
        setTotalMemories(data.total_memories ?? 0)
        const counts: Record<number, number> = {}
        const perTier = data.per_tier_counts ?? {}
        for (let t = 0; t <= 4; t++) {
          counts[t] = perTier[`T${t}`] ?? 0
        }
        setTierCounts(counts)
        setExperienceCount(data.experience_count ?? 0)
        setQuarantinedCount(data.quarantined_count ?? 0)
        setAvgTrustScore(data.avg_trust_score ?? 0)
      }
    } catch {
      // API not available, keep defaults
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

  const trustColor = avgTrustScore >= 0.7 ? 'text-accent-green' : avgTrustScore >= 0.4 ? 'text-accent-yellow' : 'text-starlight-400'

  return (
    <div className="space-y-6">
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
                {tierCounts[t.tier]}
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
            <p className="text-lg font-display font-bold text-starlight-100">{totalMemories}</p>
            <p className="text-[10px] text-starlight-500">Total Memories</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className="text-lg font-display font-bold text-starlight-100">{tierCounts[0] + tierCounts[1]}</p>
            <p className="text-[10px] text-starlight-500">Ephemeral + Working</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className="text-lg font-display font-bold text-starlight-100">{tierCounts[2] + tierCounts[3] + tierCounts[4]}</p>
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
            <p className="text-lg font-display font-bold text-starlight-100">{experienceCount}</p>
            <p className="text-[10px] text-starlight-500">Total Experiences</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-accent-yellow/20">
            <div className="flex items-center gap-1.5">
              <ShieldCheck size={12} className="text-accent-yellow" />
              <p className="text-lg font-display font-bold text-accent-yellow">{quarantinedCount}</p>
            </div>
            <p className="text-[10px] text-starlight-500">In Quarantine (L2Q)</p>
          </div>
          <div className="px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5">
            <p className={`text-lg font-display font-bold ${trustColor}`}>
              {(avgTrustScore * 100).toFixed(0)}%
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

/**
 * BenchmarkPage -- Intelligence benchmark dashboard.
 *
 * Proves Daena's 21-stage Laevateinn pipeline beats single-model inference.
 * Compares pipeline ON vs OFF across reasoning, security, factual,
 * adversarial, and multi-step challenges.
 *
 * Endpoints:
 *   POST /benchmark/intelligence        -- Run full benchmark
 *   GET  /benchmark/intelligence/:id     -- Get results
 *   GET  /benchmark/intelligence/challenges -- List challenges
 *   GET  /benchmark/full                 -- Existing full benchmark
 */
import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart3,
  Play,
  Trophy,
  Brain,
  Shield,
  Target,
  AlertTriangle,
  Layers,
  Loader2,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Minus,
  Zap,
  Clock,
  RefreshCw,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, EmptyState } from '@/components/common'
import { api } from '@/lib/api'

// ── Types ──

interface Challenge {
  id: string
  category: string
  question: string
  difficulty: 'easy' | 'medium' | 'hard' | 'extreme'
}

interface ChallengeResult {
  challenge_id: string
  category: string
  pipeline_on_score: number
  pipeline_off_score: number
  delta: number
  pipeline_on_latency_ms: number
  pipeline_off_latency_ms: number
}

interface BenchmarkResult {
  job_id: string
  status: 'running' | 'complete' | 'failed'
  total_challenges: number
  completed: number
  pipeline_on_avg: number
  pipeline_off_avg: number
  overall_delta: number
  per_category: Record<string, { on: number; off: number; delta: number }>
  results: ChallengeResult[]
  model_used: string
  total_duration_secs: number
}

// ── Category config ──

const CATEGORIES: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  reasoning: { icon: <Brain size={14} />, color: 'text-primary-400', label: 'Reasoning' },
  security: { icon: <Shield size={14} />, color: 'text-status-error', label: 'Security' },
  factual: { icon: <CheckCircle2 size={14} />, color: 'text-status-success', label: 'Factual' },
  adversarial: { icon: <AlertTriangle size={14} />, color: 'text-accent-amber', label: 'Adversarial' },
  multi_step: { icon: <Layers size={14} />, color: 'text-accent-cyan', label: 'Multi-Step' },
}

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: 'text-status-success',
  medium: 'text-accent-cyan',
  hard: 'text-accent-amber',
  extreme: 'text-status-error',
}

function ScoreBar({ score, max = 10, color }: { score: number; max?: number; color: string }) {
  const pct = Math.min(100, (score / max) * 100)
  return (
    <div className="h-2 bg-midnight-400 rounded-full overflow-hidden w-full">
      <motion.div
        className={`h-full rounded-full ${color}`}
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
    </div>
  )
}

function DeltaBadge({ delta }: { delta: number }) {
  if (delta > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-mono text-status-success">
        <TrendingUp size={10} /> +{delta.toFixed(1)}
      </span>
    )
  }
  if (delta < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-mono text-status-error">
        <TrendingUp size={10} className="rotate-180" /> {delta.toFixed(1)}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-mono text-starlight-500">
      <Minus size={10} /> 0
    </span>
  )
}

export function BenchmarkPage() {
  usePageTitle('Intelligence Benchmark')

  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [result, setResult] = useState<BenchmarkResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  // Load challenges
  useEffect(() => {
    api.get('/benchmark/intelligence/challenges')
      .then(({ data }) => setChallenges(data?.challenges || []))
      .catch(() => { /* Endpoint may not exist yet */ })
  }, [])

  // Start benchmark
  const startBenchmark = async () => {
    setRunning(true)
    setError('')
    setResult(null)
    try {
      const { data } = await api.post('/benchmark/intelligence')
      // Poll for results
      const poll = async () => {
        try {
          const { data: res } = await api.get(`/benchmark/intelligence/${data.job_id}`)
          setResult(res)
          if (res.status === 'running') {
            setTimeout(poll, 5000)
          } else {
            setRunning(false)
          }
        } catch {
          setRunning(false)
          setError('Failed to get benchmark results')
        }
      }
      setTimeout(poll, 3000)
    } catch (err: any) {
      setRunning(false)
      setError(err?.response?.data?.detail || 'Failed to start benchmark')
    }
  }

  const onAvg = result?.pipeline_on_avg ?? 0
  const offAvg = result?.pipeline_off_avg ?? 0
  const delta = result?.overall_delta ?? 0

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-3">
            <BarChart3 className="text-accent-amber" size={28} />
            Intelligence Benchmark
          </h1>
          <p className="text-sm text-starlight-400 mt-1">
            Pipeline ON vs OFF -- proving multi-model verification beats single-model inference
          </p>
        </div>
        <button
          onClick={startBenchmark}
          disabled={running}
          className="px-5 py-2.5 rounded-lg bg-accent-amber hover:bg-accent-amber/80 disabled:bg-accent-amber/30
                     text-midnight-900 font-semibold text-sm flex items-center gap-2 transition-colors
                     disabled:cursor-not-allowed cursor-pointer"
        >
          {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {running ? 'Running...' : 'Run Benchmark'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-status-error/10 border border-status-error/20 rounded-lg text-xs text-status-error flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Summary Cards */}
      {result && result.status === 'complete' && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <Card className="p-5 text-center">
              <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-2">Pipeline OFF</p>
              <p className="text-3xl font-bold font-mono text-starlight-400">{offAvg.toFixed(1)}</p>
              <p className="text-[10px] text-starlight-600 mt-1">Single model baseline</p>
            </Card>
            <Card className="p-5 text-center border-primary-500/30">
              <p className="text-[10px] uppercase tracking-wider text-primary-400 mb-2">Pipeline ON</p>
              <p className="text-3xl font-bold font-mono text-primary-400">{onAvg.toFixed(1)}</p>
              <p className="text-[10px] text-starlight-600 mt-1">21-stage Laevateinn</p>
            </Card>
            <Card className="p-5 text-center border-accent-amber/30">
              <p className="text-[10px] uppercase tracking-wider text-accent-amber mb-2">Intelligence Delta</p>
              <p className={`text-3xl font-bold font-mono ${delta > 0 ? 'text-status-success' : 'text-status-error'}`}>
                {delta > 0 ? '+' : ''}{delta.toFixed(1)}
              </p>
              <p className="text-[10px] text-starlight-600 mt-1">
                {delta > 0 ? 'Pipeline wins' : delta < 0 ? 'Baseline wins' : 'Tied'}
              </p>
            </Card>
            <Card className="p-5 text-center">
              <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-2">Challenges</p>
              <p className="text-3xl font-bold font-mono text-starlight-300">{result.total_challenges}</p>
              <p className="text-[10px] text-starlight-600 mt-1">
                <Clock size={10} className="inline mr-1" />{result.total_duration_secs}s total
              </p>
            </Card>
          </div>

          {/* Per-Category Breakdown */}
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-starlight-300">Category Breakdown</h2>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {Object.entries(result.per_category).map(([cat, scores]) => {
                const catInfo = CATEGORIES[cat] || { icon: <Zap size={14} />, color: 'text-starlight-400', label: cat }
                return (
                  <Card key={cat} className="p-4">
                    <div className={`flex items-center gap-2 mb-3 ${catInfo.color}`}>
                      {catInfo.icon}
                      <span className="text-xs font-semibold">{catInfo.label}</span>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <div className="flex justify-between text-[10px] mb-0.5">
                          <span className="text-starlight-500">OFF</span>
                          <span className="text-starlight-400 font-mono">{scores.off.toFixed(1)}</span>
                        </div>
                        <ScoreBar score={scores.off} color="bg-starlight-600" />
                      </div>
                      <div>
                        <div className="flex justify-between text-[10px] mb-0.5">
                          <span className="text-primary-400">ON</span>
                          <span className="text-primary-400 font-mono">{scores.on.toFixed(1)}</span>
                        </div>
                        <ScoreBar score={scores.on} color="bg-primary-500" />
                      </div>
                      <div className="text-center pt-1">
                        <DeltaBadge delta={scores.delta} />
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          </div>

          {/* Per-Challenge Results */}
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-starlight-300">Challenge Results</h2>
            <div className="space-y-1">
              {result.results.map((r, i) => {
                const catInfo = CATEGORIES[r.category] || { icon: <Zap size={14} />, color: 'text-starlight-400', label: r.category }
                const won = r.delta > 0
                return (
                  <div
                    key={r.challenge_id}
                    className="flex items-center gap-3 p-3 bg-midnight-200/40 rounded-lg border border-white/5"
                  >
                    <span className={catInfo.color}>{catInfo.icon}</span>
                    <span className="text-xs text-starlight-400 flex-1 truncate">
                      {challenges.find(c => c.id === r.challenge_id)?.question || r.challenge_id}
                    </span>
                    <span className="text-[10px] font-mono text-starlight-500 w-12 text-right">
                      {r.pipeline_off_score.toFixed(1)}
                    </span>
                    <span className="text-[10px] text-starlight-600">vs</span>
                    <span className={`text-[10px] font-mono w-12 text-right ${won ? 'text-primary-400' : 'text-starlight-400'}`}>
                      {r.pipeline_on_score.toFixed(1)}
                    </span>
                    <DeltaBadge delta={r.delta} />
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}

      {/* Running state */}
      {running && result && (
        <Card className="p-8 text-center">
          <Loader2 size={32} className="mx-auto text-primary-400 animate-spin mb-4" />
          <p className="text-sm text-starlight-300">
            Running benchmark... {result.completed}/{result.total_challenges} challenges complete
          </p>
          <div className="mt-3 max-w-xs mx-auto h-1.5 bg-midnight-400 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-primary-500 rounded-full"
              animate={{ width: `${result.total_challenges > 0 ? (result.completed / result.total_challenges) * 100 : 0}%` }}
            />
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!result && !running && (
        <Card className="p-12 text-center">
          <Trophy size={48} className="mx-auto text-accent-amber/40 mb-4" />
          <h3 className="text-lg font-semibold text-starlight-200 mb-2">Prove the Intelligence Delta</h3>
          <p className="text-sm text-starlight-500 max-w-md mx-auto mb-6">
            Run the same challenges through single-model inference and Daena's 21-stage pipeline.
            Measure the difference in correctness, reasoning depth, verification, and nuance.
          </p>
          <div className="flex justify-center gap-8 text-xs text-starlight-500">
            <div className="text-center">
              <p className="text-2xl font-bold text-starlight-400 mb-1">15+</p>
              <p>Challenge questions</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-primary-400 mb-1">5</p>
              <p>Categories</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-accent-amber mb-1">5</p>
              <p>Scoring axes</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

export default BenchmarkPage

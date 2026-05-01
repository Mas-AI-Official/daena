/**
 * ScanLauncher -- the page header, tier selector grid, and target
 * input form for kicking off a new scan.
 */
import {
  Shield,
  Target,
  Play,
  Loader2,
  AlertTriangle,
  Layers,
  Brain,
  DollarSign,
} from 'lucide-react'
import { Card } from '@/components/common'
import type { ScanTier } from './types'

interface Props {
  visibleTiers: ScanTier[]
  selectedTier: string
  onSelectTier: (id: string) => void
  target: string
  onTargetChange: (value: string) => void
  onStartScan: () => void
  loading: boolean
  error: string
}

export default function ScanLauncher({
  visibleTiers,
  selectedTier,
  onSelectTier,
  target,
  onTargetChange,
  onStartScan,
  loading,
  error,
}: Props) {
  return (
    <>
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-3">
          <Shield className="text-primary-400" size={28} />
          Security Intelligence
        </h1>
        <p className="text-sm text-starlight-400 mt-1">
          Intelligence-as-a-Service -- submit targets for multi-model verified security analysis
        </p>
      </div>

      {/* Tier Selector */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {visibleTiers.map(tier => (
          <button
            key={tier.id}
            disabled={tier.locked}
            onClick={() => onSelectTier(tier.id)}
            className={`
              relative p-4 rounded-xl border transition-all duration-200 text-left cursor-pointer
              ${selectedTier === tier.id
                ? 'bg-primary-500/10 border-primary-500/40 shadow-[var(--shadow-glow-sm)]'
                : tier.locked
                  ? 'bg-midnight-200/40 border-white/5 opacity-50 cursor-not-allowed'
                  : 'bg-midnight-200/60 border-white/5 hover:border-white/15'
              }
            `}
          >
            <div className={`flex items-center gap-2 mb-2 ${tier.color}`}>
              {tier.icon}
              <span className="font-semibold text-sm">{tier.id}</span>
            </div>
            <p className="text-xs font-medium text-starlight-100">{tier.name}</p>
            <p className="text-[10px] text-starlight-500 mt-0.5">{tier.description}</p>
            <div className="mt-2 flex items-center gap-1">
              <Layers size={10} className="text-starlight-500" />
              <span className="text-[10px] text-starlight-500">{tier.pipelineStages} stages</span>
            </div>
            <p className="text-xs font-mono text-accent-amber mt-1">{tier.price}</p>
          </button>
        ))}
      </div>

      {/* Scan Input */}
      <Card className="p-6">
        <div className="flex gap-3">
          <div className="flex-1">
            <div className="relative">
              <Target size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
              <input
                type="text"
                value={target}
                onChange={e => onTargetChange(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && onStartScan()}
                placeholder="Enter target: GitHub URL, file path, or paste code..."
                className="w-full pl-10 pr-4 py-3 rounded-lg bg-midnight-400/60 border border-white/10
                           text-sm text-starlight-100 placeholder:text-starlight-600
                           focus:outline-none focus:border-primary-500/50 focus:shadow-[var(--shadow-glow-sm)]
                           transition-all"
              />
            </div>
          </div>
          <button
            onClick={onStartScan}
            disabled={loading || !target.trim()}
            className="px-6 py-3 rounded-lg bg-primary-500 hover:bg-primary-400 disabled:bg-primary-500/30
                       text-white font-medium text-sm flex items-center gap-2 transition-colors
                       disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {loading ? 'Starting...' : 'Start Scan'}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-xs text-status-error flex items-center gap-1">
            <AlertTriangle size={12} /> {error}
          </p>
        )}

        {/* Selected tier details */}
        <div className="mt-4 flex items-center gap-4 text-xs text-starlight-500">
          <span className="flex items-center gap-1">
            <Layers size={12} />
            Tier: <span className="text-starlight-300 font-medium">{selectedTier}</span>
          </span>
          <span className="flex items-center gap-1">
            <Brain size={12} />
            Pipeline: <span className="text-starlight-300 font-medium">
              {visibleTiers.find(t => t.id === selectedTier)?.pipelineStages} stages
            </span>
          </span>
          <span className="flex items-center gap-1">
            <DollarSign size={12} />
            <span className="text-accent-amber font-medium">
              {visibleTiers.find(t => t.id === selectedTier)?.price}
            </span>
          </span>
        </div>
      </Card>
    </>
  )
}

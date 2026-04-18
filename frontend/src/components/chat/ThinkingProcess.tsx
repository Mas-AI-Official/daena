/**
 * ThinkingProcess: premium inline indicator for the AI pipeline.
 *
 * Auto-expands while active to show live pipeline stages cascading in.
 * Each stage has a context-appropriate icon, elapsed timer, and smooth
 * transitions. Collapses to a compact summary once complete.
 *
 * Design philosophy: users should SEE the AI working without clicking.
 * Transparency builds trust -- Daena's core brand identity.
 */
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronRight,
  BrainCircuit,
  Cpu,
  ShieldCheck,
  Zap,
  Search,
  Route,
  Users,
  Sparkles,
  ArrowRightLeft,
  Database,
  Wallet,
  Network,
  CheckCircle2,
  Loader2,
} from 'lucide-react'

/** A single reasoning step shown in the process timeline */
export interface ThinkingStep {
  label: string
  detail?: string
  status: 'done' | 'active' | 'pending' | 'error'
}

interface ThinkingProcessProps {
  content: string
  isActive: boolean
  modelUsed?: string
  governanceTier?: number
  steps?: ThinkingStep[]
}

const TIER_LABELS: Record<number, { label: string; color: string }> = {
  0: { label: 'Silent', color: 'text-starlight-400' },
  1: { label: 'Log', color: 'text-accent-cyan' },
  2: { label: 'Notify', color: 'text-status-warning' },
  3: { label: 'Approve', color: 'text-accent-amber' },
  4: { label: 'Council', color: 'text-accent-purple' },
}

/** Map stage labels to context-appropriate icons */
function getStageIcon(label: string) {
  const lower = label.toLowerCase()
  // Cognitive Engine (OODA-R) stages
  if (lower.includes('ooda') || lower.includes('observe') || lower.includes('orient'))
    return BrainCircuit
  if (lower.includes('strateg') || lower.includes('decide') || lower.includes('select'))
    return Route
  if (lower.includes('reflect') || lower.includes('learn')) return Sparkles
  if (lower.includes('loop') || lower.includes('detect')) return ArrowRightLeft
  if (lower.includes('cognitive')) return BrainCircuit
  // Standard pipeline stages
  if (lower.includes('understand') || lower.includes('analyz')) return Search
  if (lower.includes('governance') || lower.includes('polic')) return ShieldCheck
  if (lower.includes('consult') || lower.includes('cross-valid') || lower.includes('perspect'))
    return Users
  if (lower.includes('expert') || lower.includes('deep') || lower.includes('lens'))
    return Sparkles
  if (lower.includes('synth') || lower.includes('complete')) return CheckCircle2
  if (lower.includes('switch') || lower.includes('fallback') || lower.includes('retry'))
    return ArrowRightLeft
  if (lower.includes('memory') || lower.includes('knowledge')) return Database
  if (lower.includes('budget') || lower.includes('cost')) return Wallet
  if (lower.includes('subtask') || lower.includes('decompos') || lower.includes('swarm'))
    return Network
  return Zap
}

/** Elapsed time display for active stages */
function ElapsedTimer({ startTime }: { startTime: number }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [startTime])
  if (elapsed < 1) return null
  return (
    <span className="text-[9px] text-starlight-600 tabular-nums ml-auto">{elapsed}s</span>
  )
}

export function ThinkingProcess({
  content,
  isActive,
  modelUsed,
  governanceTier,
  steps,
}: ThinkingProcessProps) {
  const [userExpanded, setUserExpanded] = useState(false)
  const stageTimers = useRef<Map<string, number>>(new Map())

  // Track when each stage becomes active
  useEffect(() => {
    steps?.forEach((step) => {
      if (step.status === 'active' && !stageTimers.current.has(step.label)) {
        stageTimers.current.set(step.label, Date.now())
      }
    })
  }, [steps])

  if (!content && !isActive && !steps?.length) return null

  const tierInfo = governanceTier != null ? TIER_LABELS[governanceTier] : null
  const reachedCount = steps?.filter((s) => s.status !== 'pending').length || 0
  const totalCount = steps?.length || 0
  const hasSteps = totalCount > 0

  // Collapsed by default. User clicks to expand/collapse.
  const expanded = userExpanded

  return (
    <motion.div
      className="ml-[60px] mr-4 mb-1"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* Header line: click to toggle */}
      <button
        onClick={() => setUserExpanded(!userExpanded)}
        className="group flex items-center gap-2 py-1 text-[11px] w-full text-left cursor-pointer"
      >
        {isActive ? (
          <Loader2 size={13} className="animate-spin text-accent-cyan" />
        ) : (
          <CheckCircle2 size={13} className="text-status-success" />
        )}

        <span
          className={`font-medium ${isActive ? 'text-accent-cyan' : 'text-starlight-400'}`}
        >
          {isActive
            ? steps?.find((s) => s.status === 'active')?.label || 'Processing...'
            : `Completed in ${reachedCount} steps`}
        </span>

        {/* Model pill */}
        {modelUsed && !isActive && (
          <span className="inline-flex items-center gap-0.5 text-[9px] text-starlight-500 bg-white/5 px-1.5 py-0.5 rounded">
            <Cpu size={8} className="opacity-60" /> {modelUsed}
          </span>
        )}

        {/* Tier badge */}
        {tierInfo && (
          <span
            className={`inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded ${tierInfo.color} bg-white/5`}
          >
            <ShieldCheck size={8} /> T{governanceTier}
          </span>
        )}

        {/* Step progress when collapsed */}
        {!expanded && hasSteps && (
          <span className="text-[9px] text-starlight-600 ml-auto">
            {reachedCount}/{totalCount}
          </span>
        )}

        <motion.span
          className="text-starlight-600 group-hover:text-starlight-400 transition-colors ml-auto"
          animate={{ rotate: expanded ? 90 : 0 }}
          transition={{ duration: 0.15 }}
        >
          <ChevronRight size={11} />
        </motion.span>
      </button>

      {/* Expanded: cascading stage timeline */}
      <AnimatePresence>
        {expanded && hasSteps && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="pl-2 pb-2 ml-[5px]">
              {steps!.map((step, i) => {
                const Icon = getStageIcon(step.label)
                const stageStart = stageTimers.current.get(step.label)
                const isDone = step.status === 'done'
                const isStageActive = step.status === 'active'

                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: i * 0.05 }}
                    className="flex items-center gap-2 py-0.5"
                  >
                    {/* Timeline connector */}
                    <div className="flex flex-col items-center w-4">
                      {i > 0 && (
                        <div
                          className={`w-px h-2 ${
                            isDone || isStageActive
                              ? 'bg-accent-cyan/30'
                              : 'bg-white/5'
                          }`}
                        />
                      )}
                      <div
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          isDone
                            ? 'bg-status-success'
                            : isStageActive
                              ? 'bg-accent-cyan animate-pulse'
                              : 'bg-white/10'
                        }`}
                      />
                      {i < steps!.length - 1 && (
                        <div
                          className={`w-px h-2 ${
                            isDone ? 'bg-accent-cyan/30' : 'bg-white/5'
                          }`}
                        />
                      )}
                    </div>

                    {/* Stage icon */}
                    <Icon
                      size={11}
                      className={
                        isDone
                          ? 'text-status-success/70'
                          : isStageActive
                            ? 'text-accent-cyan'
                            : 'text-starlight-600'
                      }
                    />

                    {/* Label */}
                    <span
                      className={`text-[10px] ${
                        isDone
                          ? 'text-starlight-500'
                          : isStageActive
                            ? 'text-accent-cyan font-medium'
                            : 'text-starlight-600'
                      }`}
                    >
                      {step.label}
                    </span>

                    {/* Detail (model name, expandable) */}
                    {step.detail && isDone && (
                      <span className="text-[9px] text-starlight-600">{step.detail}</span>
                    )}

                    {/* Elapsed timer for active stage */}
                    {isStageActive && stageStart && <ElapsedTimer startTime={stageStart} />}
                  </motion.div>
                )
              })}
            </div>

            {/* Raw thinking content (collapsed by default) */}
            {content && (
              <details className="ml-[21px] mb-1">
                <summary className="text-[9px] text-starlight-600 cursor-pointer hover:text-starlight-400 select-none">
                  Raw pipeline log
                </summary>
                <pre className="text-[9px] font-mono text-starlight-500 whitespace-pre-wrap leading-relaxed max-h-24 overflow-y-auto mt-1 p-2 bg-white/[0.02] rounded">
                  {content}
                  {isActive && (
                    <motion.span
                      className="inline-block w-1 h-2.5 bg-accent-cyan ml-0.5 align-middle"
                      animate={{ opacity: [1, 0] }}
                      transition={{ duration: 0.6, repeat: Infinity }}
                    />
                  )}
                </pre>
              </details>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default ThinkingProcess

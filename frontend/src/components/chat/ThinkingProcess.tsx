/**
 * ThinkingProcess: compact inline indicator for the AI pipeline.
 * Shows a small status line by default. Expands to reveal step pills
 * and raw thinking content on click. Designed to sit above the AI
 * message bubble, not as a separate panel.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, BrainCircuit, Cpu, ShieldCheck, Zap } from 'lucide-react'

/** A single reasoning step shown in the process timeline */
export interface ThinkingStep {
  label: string
  detail?: string
  status: 'done' | 'active' | 'pending'
}

interface ThinkingProcessProps {
  content: string
  isActive: boolean
  /** Which model is handling this request */
  modelUsed?: string
  /** Governance tier applied (0-4) */
  governanceTier?: number
  /** Discrete reasoning steps (routing, generation, etc.) */
  steps?: ThinkingStep[]
}

const TIER_LABELS: Record<number, { label: string; color: string }> = {
  0: { label: 'Silent', color: 'text-starlight-400' },
  1: { label: 'Log', color: 'text-accent-cyan' },
  2: { label: 'Notify', color: 'text-status-warning' },
  3: { label: 'Approve', color: 'text-accent-amber' },
  4: { label: 'Council+Approve', color: 'text-accent-purple' },
}

export function ThinkingProcess({
  content,
  isActive,
  modelUsed,
  governanceTier,
  steps,
}: ThinkingProcessProps) {
  const [expanded, setExpanded] = useState(false)

  if (!content && !isActive && !steps?.length) return null

  const tierInfo = governanceTier != null ? TIER_LABELS[governanceTier] : null
  const hasDetails = !!(content || (steps && steps.length > 0))
  // Count done + active as "reached" so the user sees progress (e.g. 4/4 not 3/4)
  const reachedCount = steps?.filter(s => s.status !== 'pending').length || 0
  const totalCount = steps?.length || 0

  return (
    <motion.div
      className="ml-[60px] mr-4 mb-0.5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
    >
      {/* Compact status line: icon + label + model + tier + step count */}
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className={`group flex items-center gap-1.5 py-0.5 text-[10px] transition-colors ${
          hasDetails ? 'cursor-pointer' : 'cursor-default'
        }`}
      >
        <BrainCircuit
          size={11}
          className={isActive ? 'animate-pulse text-accent-cyan' : 'text-status-success'}
        />
        <span className={`font-medium ${isActive ? 'text-accent-cyan' : 'text-starlight-500'}`}>
          {isActive ? 'Processing' : 'Routed'}
        </span>

        {/* Model pill */}
        {modelUsed && (
          <span className="inline-flex items-center gap-0.5 text-[9px] text-starlight-500">
            <Cpu size={8} className="opacity-60" /> {modelUsed}
          </span>
        )}

        {/* Tier badge */}
        {tierInfo && (
          <span className={`inline-flex items-center gap-0.5 text-[9px] ${tierInfo.color}`}>
            <ShieldCheck size={8} className="opacity-70" /> T{governanceTier}
          </span>
        )}

        {/* Step count when collapsed */}
        {!expanded && totalCount > 0 && (
          <span className="text-[9px] text-starlight-600">
            {reachedCount}/{totalCount} steps
          </span>
        )}

        {hasDetails && (
          <motion.span
            className="text-starlight-600 group-hover:text-starlight-400 transition-colors"
            animate={{ rotate: expanded ? 90 : 0 }}
            transition={{ duration: 0.15 }}
          >
            <ChevronRight size={10} />
          </motion.span>
        )}
      </button>

      {/* Expandable: step pills + raw thinking content */}
      <AnimatePresence>
        {expanded && hasDetails && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="pl-4 pb-1.5 border-l border-white/5 ml-[5px]">
              {/* Step pills */}
              {steps && steps.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1">
                  {steps.map((step, i) => (
                    <span
                      key={i}
                      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] ${
                        step.status === 'done'
                          ? 'bg-status-success/10 text-status-success'
                          : step.status === 'active'
                            ? 'bg-accent-cyan/15 text-accent-cyan animate-pulse'
                            : 'bg-white/5 text-starlight-500'
                      }`}
                    >
                      <Zap size={7} />
                      {step.label}
                      {step.detail && (
                        <span className="text-starlight-600">{step.detail}</span>
                      )}
                    </span>
                  ))}
                </div>
              )}

              {/* Raw thinking content */}
              {content && (
                <div className="max-h-32 overflow-y-auto">
                  <pre className="text-[10px] font-mono text-starlight-500 whitespace-pre-wrap leading-relaxed">
                    {content}
                    {isActive && (
                      <motion.span
                        className="inline-block w-1 h-2.5 bg-accent-cyan ml-0.5 align-middle"
                        animate={{ opacity: [1, 0] }}
                        transition={{ duration: 0.6, repeat: Infinity }}
                      />
                    )}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default ThinkingProcess

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, ShieldAlert, ShieldCheck, ShieldOff, Siren } from 'lucide-react'
import type { GovernanceSlider as GovernanceLevel } from '@/types/api'

interface GovernanceSliderProps {
  value: GovernanceLevel
  onChange: (value: GovernanceLevel) => void
  compact?: boolean
}

const LEVELS: GovernanceLevel[] = ['YOLO', 'LIGHT', 'STANDARD', 'STRICT', 'PARANOID']

interface LevelMeta {
  label: string
  icon: React.ReactNode
  color: string
  bgColor: string
  borderColor: string
  glowColor: string
  description: string
}

const LEVEL_META: Record<GovernanceLevel, LevelMeta> = {
  YOLO: {
    label: 'YOLO',
    icon: <ShieldOff size={14} />,
    color: 'text-status-success',
    bgColor: 'bg-status-success/20',
    borderColor: 'border-status-success/40',
    glowColor: 'shadow-[0_0_12px_rgba(0,214,143,0.3)]',
    description: 'Minimal — logs HIGH+ risk only',
  },
  LIGHT: {
    label: 'Light',
    icon: <Shield size={14} />,
    color: 'text-accent-cyan',
    bgColor: 'bg-accent-cyan/20',
    borderColor: 'border-accent-cyan/40',
    glowColor: 'shadow-[0_0_12px_rgba(6,182,212,0.3)]',
    description: 'Log mode — logs MEDIUM+ risk',
  },
  STANDARD: {
    label: 'Standard',
    icon: <ShieldCheck size={14} />,
    color: 'text-primary-400',
    bgColor: 'bg-primary-500/20',
    borderColor: 'border-primary-500/40',
    glowColor: 'shadow-[0_0_12px_rgba(0,112,243,0.3)]',
    description: 'Balanced — logs LOW+ risk, notifies',
  },
  STRICT: {
    label: 'Strict',
    icon: <ShieldAlert size={14} />,
    color: 'text-status-warning',
    bgColor: 'bg-status-warning/20',
    borderColor: 'border-status-warning/40',
    glowColor: 'shadow-[0_0_12px_rgba(255,176,32,0.3)]',
    description: 'Requires approvals for MEDIUM+',
  },
  PARANOID: {
    label: 'Paranoid',
    icon: <Siren size={14} />,
    color: 'text-status-error',
    bgColor: 'bg-status-error/20',
    borderColor: 'border-status-error/40',
    glowColor: 'shadow-[0_0_12px_rgba(255,71,87,0.3)]',
    description: 'Council + approve everything',
  },
}

export function GovernanceSlider({ value, onChange, compact }: GovernanceSliderProps) {
  const [hovered, setHovered] = useState<GovernanceLevel | null>(null)
  const activeIndex = LEVELS.indexOf(value)
  const meta = LEVEL_META[value]
  const hoveredMeta = hovered ? LEVEL_META[hovered] : null

  if (compact) {
    return (
      <div className="relative">
        <button
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
            border transition-all duration-300 cursor-pointer
            ${meta.bgColor} ${meta.color} ${meta.borderColor} ${meta.glowColor}
          `}
          onClick={() => {
            const next = LEVELS[(activeIndex + 1) % LEVELS.length]
            onChange(next)
          }}
        >
          {meta.icon}
          <span className="font-mono">{meta.label}</span>
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Slider track */}
      <div className="flex items-center gap-0.5 bg-midnight-400/50 rounded-lg p-0.5">
        {LEVELS.map((level, i) => {
          const m = LEVEL_META[level]
          const isActive = level === value
          return (
            <button
              key={level}
              onClick={() => onChange(level)}
              onMouseEnter={() => setHovered(level)}
              onMouseLeave={() => setHovered(null)}
              className={`
                relative flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium
                transition-all duration-300 cursor-pointer
                ${isActive
                  ? `${m.bgColor} ${m.color} border ${m.borderColor} ${m.glowColor}`
                  : 'text-starlight-400 hover:text-starlight-200 border border-transparent'
                }
              `}
            >
              {m.icon}
              <span className="font-mono hidden xl:inline">{m.label}</span>
            </button>
          )
        })}
      </div>

      {/* Description tooltip */}
      <AnimatePresence mode="wait">
        {(hovered || value) && (
          <motion.p
            key={hovered || value}
            className={`text-[10px] font-mono ${(hoveredMeta || meta).color} pl-1`}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 0.7, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            {(hoveredMeta || meta).description}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}

export default GovernanceSlider

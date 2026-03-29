/**
 * NeuralOrb — Daena's animated avatar.
 * Compact orb with orbital dots, rotating dashed ring, and mode-synced palettes.
 * Ported visual elements from legacy full-screen NeuralOrb + MiniNeuralOrb.
 *   CMD = blue, EXE = gold, Council = purple, Quintessence = white, Error = red.
 */
import { motion } from 'framer-motion'
import type { ChatMode, RoutingMode } from '@/types/api'

type OrbState = 'idle' | 'thinking' | 'speaking' | 'error'
type OrbMode = 'CMD' | 'EXE' | 'COUNCIL' | 'QUINTESSENCE'

interface NeuralOrbProps {
  state?: OrbState
  size?: number
  className?: string
  chatMode?: ChatMode
  routingMode?: RoutingMode
}

const MODE_PALETTES: Record<OrbMode, { from: string; to: string; shadow: string; accent: string }> = {
  CMD:          { from: '#0070f3', to: '#00a8ff', shadow: 'rgba(0,112,243,0.4)', accent: '#60a5fa' },
  EXE:          { from: '#eab308', to: '#fcd34d', shadow: 'rgba(234,179,8,0.4)', accent: '#fbbf24' },
  COUNCIL:      { from: '#8b5cf6', to: '#a855f7', shadow: 'rgba(139,92,246,0.4)', accent: '#c084fc' },
  QUINTESSENCE: { from: '#e2e8f0', to: '#f8f9fa', shadow: 'rgba(226,232,240,0.4)', accent: '#f1f5f9' },
}

const ERROR_PALETTE = { from: '#ff4757', to: '#f97316', shadow: 'rgba(255,71,87,0.4)', accent: '#fb7185' }

function resolveOrbMode(chatMode?: ChatMode, routingMode?: RoutingMode): OrbMode {
  if (routingMode === 'QUINTESSENCE') return 'QUINTESSENCE'
  if (routingMode === 'COUNCIL') return 'COUNCIL'
  if (chatMode === 'EXE') return 'EXE'
  return 'CMD'
}

export function NeuralOrb({
  state = 'idle',
  size = 40,
  className = '',
  chatMode,
  routingMode,
}: NeuralOrbProps) {
  const isActive = state === 'thinking' || state === 'speaking'
  const isError = state === 'error'
  const palette = isError ? ERROR_PALETTE : MODE_PALETTES[resolveOrbMode(chatMode, routingMode)]

  const dotSize = Math.max(2, size * 0.06)
  const orbitR = size * 0.42

  return (
    <div
      className={`relative flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Deep background glow */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, ${palette.from}20, transparent 70%)`,
          filter: `blur(${size * 0.2}px)`,
        }}
        animate={{
          scale: isActive ? [1, 1.4, 1] : [1, 1.15, 1],
          opacity: isActive ? [0.4, 0.8, 0.4] : [0.2, 0.4, 0.2],
        }}
        transition={{ duration: isActive ? 1.5 : 4, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Outer glow ring */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, ${palette.from}30, ${palette.to}10)`,
          boxShadow: `0 0 ${isActive ? 24 : 14}px ${palette.shadow}`,
        }}
        animate={{
          scale: isActive ? [1, 1.2, 1] : [1, 1.08, 1],
          opacity: isActive ? [0.6, 1, 0.6] : [0.4, 0.6, 0.4],
        }}
        transition={{
          duration: state === 'thinking' ? 1.2 : 3,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Rotating dashed ring (from legacy MiniNeuralOrb) */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.85,
          height: size * 0.85,
          border: `1px dashed ${palette.accent}40`,
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: isActive ? 4 : 15, repeat: Infinity, ease: 'linear' }}
      />

      {/* Inner orb — gradient sphere */}
      <motion.div
        className="relative rounded-full"
        style={{
          width: size * 0.55,
          height: size * 0.55,
          background: `linear-gradient(135deg, ${palette.from}, ${palette.to})`,
          boxShadow: `inset 0 -2px 4px ${palette.from}40, 0 0 8px ${palette.shadow}`,
        }}
        animate={{
          scale: state === 'speaking' ? [1, 1.12, 0.94, 1.06, 1] : [1, 1.04, 1],
        }}
        transition={{
          duration: state === 'speaking' ? 0.8 : 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      />

      {/* Core highlight dot */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.14,
          height: size * 0.14,
          background: `radial-gradient(circle, white 30%, ${palette.accent}80)`,
        }}
        animate={{ opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      />

      {/* 4 orbital dots (from legacy MiniNeuralOrb) */}
      {[0, 90, 180, 270].map((angle) => (
        <motion.div
          key={angle}
          className="absolute rounded-full"
          style={{
            width: dotSize,
            height: dotSize,
            backgroundColor: palette.accent,
            left: '50%',
            top: '50%',
            marginLeft: -dotSize / 2,
            marginTop: -dotSize / 2,
          }}
          animate={{
            x: [
              Math.cos((angle * Math.PI) / 180) * orbitR,
              Math.cos(((angle + 360) * Math.PI) / 180) * orbitR,
            ],
            y: [
              Math.sin((angle * Math.PI) / 180) * orbitR,
              Math.sin(((angle + 360) * Math.PI) / 180) * orbitR,
            ],
            opacity: isActive ? [0.6, 1, 0.6] : [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: isActive ? 3 : 8,
            repeat: Infinity,
            ease: 'linear',
          }}
        />
      ))}
    </div>
  )
}

export default NeuralOrb

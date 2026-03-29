/**
 * DaenaAvatar — Animated Daena logo with living halo effects.
 *
 * Uses the actual Daena hexagonal "D" logos (blue for CMD, gold for EXE/Autopilot).
 * Renders animated circular halo, orbital particles, breathing glow, pulse,
 * sweeping light beam, and sparkle effects.
 *
 * Color palettes extracted from the logo images:
 *   Blue: #00d4ff → #0088ff → #66e0ff (cyan-blue metallic)
 *   Gold: #ffd700 → #ff9900 → #ffe066 (amber-gold metallic)
 */
import { memo, useMemo } from 'react'
import { motion } from 'framer-motion'
import type { ChatMode, RoutingMode } from '@/types/api'

type AvatarState = 'idle' | 'thinking' | 'speaking' | 'error'
type AvatarMode = 'CMD' | 'EXE' | 'COUNCIL' | 'QUINTESSENCE'

interface DaenaAvatarProps {
  state?: AvatarState
  size?: number
  className?: string
  chatMode?: ChatMode
  routingMode?: RoutingMode
  /** Show label under avatar */
  showLabel?: boolean
  /** Click handler */
  onClick?: () => void
}

// ── Color palettes extracted from logo images ──

const MODE_PALETTES: Record<AvatarMode, {
  image: string
  glow: string
  glowRgba: string
  halo: string
  particle: string
  shadow: string
  labelColor: string
}> = {
  CMD: {
    image: '/daena-blue.png',
    glow: '#00d4ff',
    glowRgba: 'rgba(0, 212, 255, 0.5)',
    halo: '#0088ff',
    particle: '#66e0ff',
    shadow: 'rgba(0, 136, 255, 0.4)',
    labelColor: '#00d4ff',
  },
  EXE: {
    image: '/daena-gold.png',
    glow: '#ffd700',
    glowRgba: 'rgba(255, 215, 0, 0.5)',
    halo: '#ff9900',
    particle: '#ffe066',
    shadow: 'rgba(255, 153, 0, 0.4)',
    labelColor: '#ffd700',
  },
  COUNCIL: {
    image: '/daena-blue.png',
    glow: '#a855f7',
    glowRgba: 'rgba(168, 85, 247, 0.5)',
    halo: '#8b5cf6',
    particle: '#c084fc',
    shadow: 'rgba(139, 92, 246, 0.4)',
    labelColor: '#a855f7',
  },
  QUINTESSENCE: {
    image: '/daena-gold.png',
    glow: '#f1f5f9',
    glowRgba: 'rgba(241, 245, 249, 0.4)',
    halo: '#e2e8f0',
    particle: '#f8fafc',
    shadow: 'rgba(226, 232, 240, 0.3)',
    labelColor: '#e2e8f0',
  },
}

const ERROR_PALETTE = {
  image: '/daena-blue.png',
  glow: '#ff4757',
  glowRgba: 'rgba(255, 71, 87, 0.5)',
  halo: '#ef4444',
  particle: '#fb7185',
  shadow: 'rgba(255, 71, 87, 0.4)',
  labelColor: '#ff4757',
}

function resolveMode(chatMode?: ChatMode, routingMode?: RoutingMode): AvatarMode {
  if (routingMode === 'QUINTESSENCE') return 'QUINTESSENCE'
  if (routingMode === 'COUNCIL') return 'COUNCIL'
  if (chatMode === 'EXE') return 'EXE'
  return 'CMD'
}

export const DaenaAvatar = memo(function DaenaAvatar({
  state = 'idle',
  size = 64,
  className = '',
  chatMode,
  routingMode,
  showLabel = false,
  onClick,
}: DaenaAvatarProps) {
  const isActive = state === 'thinking' || state === 'speaking'
  const isError = state === 'error'
  const palette = isError ? ERROR_PALETTE : MODE_PALETTES[resolveMode(chatMode, routingMode)]

  const imgSize = size * 0.72
  const haloRadius = size * 0.46
  const particleCount = 12
  const particleSize = Math.max(2, size * 0.05)

  // Pre-calculate particle positions for the circular orbit
  const particles = useMemo(() =>
    Array.from({ length: particleCount }, (_, i) => ({
      angle: (360 / particleCount) * i,
      delay: i * 0.15,
      // Vary particle sizes for depth
      sizeMult: 0.7 + Math.random() * 0.6,
    })),
    [particleCount]
  )

  return (
    <div
      className={`relative flex flex-col items-center justify-center ${className}`}
      style={{ width: size, height: showLabel ? size + 18 : size }}
    >
      {/* Layer 0: Deep ambient glow (breathing) */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.2,
          height: size * 1.2,
          background: `radial-gradient(circle, ${palette.glow}20, ${palette.glow}08 40%, transparent 70%)`,
          filter: `blur(${size * 0.3}px)`,
        }}
        animate={{
          scale: isActive ? [1, 1.6, 1] : [1, 1.3, 1],
          opacity: isActive ? [0.4, 0.9, 0.4] : [0.2, 0.5, 0.2],
        }}
        transition={{ duration: isActive ? 1.2 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Layer 1: Outer halo ring (main rotating circle) */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.94,
          height: size * 0.94,
          border: `2px solid ${palette.halo}60`,
          boxShadow: `
            0 0 ${isActive ? 28 : 14}px ${palette.glowRgba},
            inset 0 0 ${isActive ? 18 : 10}px ${palette.glow}18
          `,
        }}
        animate={{
          rotate: 360,
          scale: isActive ? [1, 1.06, 1] : [1, 1.03, 1],
        }}
        transition={{
          rotate: { duration: isActive ? 6 : 14, repeat: Infinity, ease: 'linear' },
          scale: { duration: 2, repeat: Infinity, ease: 'easeInOut' },
        }}
      />

      {/* Layer 2: Counter-rotating dashed ring */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.84,
          height: size * 0.84,
          border: `1px dashed ${palette.halo}35`,
        }}
        animate={{ rotate: -360 }}
        transition={{ duration: isActive ? 8 : 22, repeat: Infinity, ease: 'linear' }}
      />

      {/* Layer 3: Third ring (fast, subtle) */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.99,
          height: size * 0.99,
          border: `1px solid ${palette.halo}15`,
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: isActive ? 4 : 10, repeat: Infinity, ease: 'linear' }}
      />

      {/* Layer 4: Outer glow pulse ring */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 0.96,
          height: size * 0.96,
          background: 'transparent',
          boxShadow: `0 0 ${isActive ? 36 : 20}px ${palette.shadow}`,
        }}
        animate={{
          opacity: isActive ? [0.5, 1, 0.5] : [0.25, 0.6, 0.25],
          scale: isActive ? [0.96, 1.08, 0.96] : [1, 1.04, 1],
        }}
        transition={{ duration: isActive ? 1.5 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Layer 5: Sweeping light beam (rotating highlight arc) */}
      <motion.div
        className="absolute rounded-full pointer-events-none overflow-hidden"
        style={{
          width: size * 0.92,
          height: size * 0.92,
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: isActive ? 3 : 7, repeat: Infinity, ease: 'linear' }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: '25%',
            width: '50%',
            height: '50%',
            background: `linear-gradient(180deg, ${palette.glow}18, transparent)`,
            borderRadius: '0 0 50% 50%',
            filter: `blur(${size * 0.06}px)`,
          }}
        />
      </motion.div>

      {/* Layer 6: Orbital particles (12 with varying sizes) */}
      {particles.map(({ angle, delay, sizeMult }) => {
        const pSize = particleSize * sizeMult
        return (
          <motion.div
            key={angle}
            className="absolute rounded-full"
            style={{
              width: pSize,
              height: pSize,
              backgroundColor: palette.particle,
              boxShadow: `0 0 ${pSize * 3}px ${palette.particle}`,
              left: '50%',
              top: '50%',
              marginLeft: -pSize / 2,
              marginTop: -pSize / 2,
            }}
            animate={{
              x: [
                Math.cos((angle * Math.PI) / 180) * haloRadius,
                Math.cos(((angle + 360) * Math.PI) / 180) * haloRadius,
              ],
              y: [
                Math.sin((angle * Math.PI) / 180) * haloRadius,
                Math.sin(((angle + 360) * Math.PI) / 180) * haloRadius,
              ],
              opacity: isActive ? [0.3, 1, 0.3] : [0.15, 0.6, 0.15],
              scale: isActive ? [0.6, 1.5, 0.6] : [0.8, 1.2, 0.8],
            }}
            transition={{
              duration: isActive ? 3 : 7,
              delay,
              repeat: Infinity,
              ease: 'linear',
            }}
          />
        )
      })}

      {/* Layer 7: The actual Daena logo image */}
      <motion.img
        src={palette.image}
        alt="Daena"
        className="relative z-10 rounded-full object-contain pointer-events-none select-none"
        style={{
          width: imgSize,
          height: imgSize,
          filter: `drop-shadow(0 0 ${isActive ? 16 : 8}px ${palette.shadow})`,
        }}
        animate={{
          scale: state === 'speaking'
            ? [1, 1.1, 0.94, 1.06, 1]
            : isActive
              ? [1, 1.06, 0.98, 1.03, 1]
              : [1, 1.03, 0.98, 1.01, 1],
        }}
        transition={{
          duration: state === 'speaking' ? 0.7 : isActive ? 1.8 : 3,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
        draggable={false}
      />

      {/* Layer 8: Top highlight shimmer */}
      <motion.div
        className="absolute z-20 rounded-full pointer-events-none"
        style={{
          width: imgSize * 0.8,
          height: imgSize * 0.35,
          top: size / 2 - imgSize / 2 + imgSize * 0.04,
          background: `linear-gradient(180deg, ${palette.glow}15, transparent)`,
          borderRadius: '50%',
        }}
        animate={{ opacity: [0.2, 0.7, 0.2] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Layer 9: Inner pulse (heartbeat glow behind image) */}
      <motion.div
        className="absolute z-5 rounded-full"
        style={{
          width: imgSize * 0.6,
          height: imgSize * 0.6,
          background: `radial-gradient(circle, ${palette.glow}30, transparent 70%)`,
        }}
        animate={{
          scale: isActive ? [1, 1.8, 1] : [1, 1.4, 1],
          opacity: isActive ? [0.3, 0.7, 0.3] : [0.1, 0.3, 0.1],
        }}
        transition={{ duration: isActive ? 1 : 2.5, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Label */}
      {showLabel && (
        <motion.span
          className="font-display font-bold tracking-wide mt-1 z-10"
          style={{
            fontSize: Math.max(9, size * 0.14),
            color: palette.labelColor,
            textShadow: `0 0 10px ${palette.shadow}`,
          }}
          animate={{ opacity: [0.7, 1, 0.7] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        >
          DAENA
        </motion.span>
      )}

      {/* Click overlay */}
      {onClick && (
        <button
          className="absolute inset-0 z-30 cursor-pointer rounded-full"
          onClick={onClick}
          aria-label="Daena"
        />
      )}
    </div>
  )
})

export default DaenaAvatar

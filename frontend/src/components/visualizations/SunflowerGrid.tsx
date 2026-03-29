/**
 * SunflowerGrid — Honeycomb visualization for department agents.
 * Golden-angle spiral positioning with hexagonal clip-path nodes.
 * Ported from legacy with Daena design system integration.
 */
import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { DaenaAvatar } from '@/components/chat/DaenaAvatar'
import { useUiStore } from '@/stores/uiStore'
import { HIVE_HEX_COLORS } from '@/styles/designTokens'

export interface HiveSectorNode {
  id: string
  label: string
  total: number
  active: number
  error: number
  performance: number
  departmentId?: string
  color?: string
  icon?: React.ReactNode
}

interface SunflowerGridProps {
  nodes: HiveSectorNode[]
  onNodeClick?: (node: HiveSectorNode) => void
  onCenterClick?: () => void
  maxSizePx?: number
}

const GOLDEN_ANGLE_RAD = Math.PI * (3 - Math.sqrt(5))
const HEX_CLIP_PATH = 'polygon(25% 6%, 75% 6%, 95% 50%, 75% 94%, 25% 94%, 5% 50%)'

const HIVE_COLORS = HIVE_HEX_COLORS

// 10-node ring layout (percentages from center, decagon)
const RING_LAYOUT_10 = [
  { x: 0, y: -36 },
  { x: 21, y: -29 },
  { x: 34, y: -11 },
  { x: 34, y: 11 },
  { x: 21, y: 29 },
  { x: 0, y: 36 },
  { x: -21, y: 29 },
  { x: -34, y: 11 },
  { x: -34, y: -11 },
  { x: -21, y: -29 },
]

function buildLayoutPoints(count: number): { x: number; y: number }[] {
  if (count <= 0) return []
  if (count === 10) return RING_LAYOUT_10

  // Fallback: golden-angle spiral
  const points: { x: number; y: number }[] = []
  for (let i = 0; i < count; i++) {
    const angle = -Math.PI / 2 + GOLDEN_ANGLE_RAD * i
    const radius = 28 + Math.sqrt(i + 1) * 8
    points.push({
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    })
  }
  return points
}

export function SunflowerGrid({
  nodes,
  onNodeClick,
  onCenterClick,
  maxSizePx = 520,
}: SunflowerGridProps) {
  const layoutPoints = useMemo(() => buildLayoutPoints(nodes.length), [nodes.length])
  const { chatMode, routingMode, autopilotActive } = useUiStore()
  const totalAgents = useMemo(() => nodes.reduce((sum, n) => sum + n.total, 0), [nodes])
  const avgPerf = useMemo(() => {
    const weighted = nodes.reduce((sum, n) => sum + n.performance * Math.max(1, n.total), 0)
    return totalAgents > 0 ? weighted / totalAgents : 0
  }, [nodes, totalAgents])

  return (
    <div className="relative flex items-center justify-center w-full">
      <div
        className="relative aspect-square overflow-visible"
        style={{ maxWidth: `${maxSizePx}px`, width: '100%' }}
      >
        {/* Background with concentric rings */}
        <div className="absolute inset-0 overflow-hidden rounded-3xl border border-white/10 bg-[radial-gradient(circle_at_center,rgba(30,64,175,0.18),rgba(15,23,42,0.46)_54%,rgba(2,6,23,0.96)_92%)]">
          <div className="absolute inset-0 bg-[linear-gradient(130deg,rgba(14,165,233,0.06),rgba(45,212,191,0.04),rgba(2,6,23,0))]" />
          <div className="absolute left-1/2 top-1/2 h-[72%] w-[72%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent-cyan/15" />
          <div className="absolute left-1/2 top-1/2 h-[50%] w-[50%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent-cyan/20" />
        </div>

        {/* Center — Daena Avatar */}
        <div
          className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
          style={{ width: 140, height: 160 }}
        >
          <DaenaAvatar
            state={autopilotActive ? 'thinking' : 'idle'}
            size={110}
            chatMode={chatMode}
            routingMode={routingMode}
            onClick={() => onCenterClick?.()}
          />
          <div className="text-center -mt-1">
            <span className="text-[11px] text-accent-amber font-semibold">{totalAgents} Agents</span>
            <span className="text-[10px] text-status-success ml-2">{avgPerf.toFixed(1)}%</span>
          </div>
        </div>

        {/* Hex nodes */}
        {nodes.map((node, i) => {
          const point = layoutPoints[i] || { x: 0, y: 0 }
          const color = node.color || HIVE_COLORS[i % HIVE_COLORS.length]
          const borderColor = `${color}dd`
          const shadowColor = `${color}55`

          return (
            <motion.button
              key={node.id}
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onNodeClick?.(node)
              }}
              className="absolute -translate-x-1/2 -translate-y-1/2 text-center transition-transform
                         hover:scale-[1.06] z-30 cursor-pointer"
              style={{
                left: `calc(50% + ${point.x}%)`,
                top: `calc(50% + ${point.y}%)`,
              }}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.06, type: 'spring', stiffness: 200 }}
              title={`Open ${node.label}`}
            >
              <div
                className="p-2 text-white"
                style={{
                  width: 140,
                  height: 120,
                  clipPath: HEX_CLIP_PATH,
                  border: `1px solid ${borderColor}`,
                  boxShadow: `0 12px 24px -12px ${shadowColor}`,
                  background: `linear-gradient(170deg, ${color}cc, rgba(15,23,42,0.92))`,
                }}
              >
                <div className="h-full w-full flex flex-col items-center justify-center gap-0.5">
                  {node.icon && <span className="mb-0.5">{node.icon}</span>}
                  <span className="text-[10px] font-semibold leading-tight">{node.label}</span>
                  <span className="text-[10px] font-semibold">{node.total} agents</span>
                  <span
                    className={`text-[8px] uppercase tracking-wider ${
                      node.error > 0 ? 'text-status-error' : 'text-status-success'
                    }`}
                  >
                    {node.error > 0 ? `${node.error} alerts` : `${node.active} active`}
                  </span>
                  <span className="text-[7px] text-accent-cyan/80">
                    {Math.round(node.performance)}% eff
                  </span>
                </div>
              </div>
            </motion.button>
          )
        })}

        {/* Footer badge */}
        <div className="absolute left-1/2 bottom-2 z-40 -translate-x-1/2 px-3 py-1 rounded-full border border-white/10 bg-midnight-950/60 text-[10px] uppercase tracking-widest text-starlight-300">
          Sunflower Hive · Live
        </div>
      </div>
    </div>
  )
}

export default SunflowerGrid

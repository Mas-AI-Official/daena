/**
 * SunflowerHive — hex hive visualization with Daena orb at center.
 * 10 department hexagons arranged in a decagonal ring around a central orb.
 * Ported visual design from legacy SunflowerGrid.
 *
 * Patent-pending: Sunflower-Honeycomb Architecture.
 */
import { memo } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { DaenaAvatar } from '@/components/chat/DaenaAvatar'
import { useUiStore } from '@/stores/uiStore'
import { DEPARTMENT_COLORS, type DepartmentColor } from '@/styles/designTokens'

// ── Hex ring positions (pre-calculated decagon, offset from center) ──

const RING_POSITIONS = [
  { x: 0, y: -120 },     // top
  { x: 71, y: -97 },     // upper-right
  { x: 114, y: -37 },    // right-upper
  { x: 114, y: 37 },     // right-lower
  { x: 71, y: 97 },      // lower-right
  { x: 0, y: 120 },      // bottom
  { x: -71, y: 97 },     // lower-left
  { x: -114, y: 37 },    // left-lower
  { x: -114, y: -37 },   // left-upper
  { x: -71, y: -97 },    // upper-left
]

const HEX_CLIP = 'polygon(25% 6%, 75% 6%, 95% 50%, 75% 94%, 25% 94%, 5% 50%)'

/** Ordered department color lookup from centralized tokens. */
const DEPT_NAMES = ['Engineering', 'Product', 'Marketing', 'Sales', 'Finance', 'Operations', 'Research', 'Legal & Compliance', 'Skill Governance', 'Security Operations']
const DEPT_COLORS = DEPT_NAMES.map((name) => {
  const c = DEPARTMENT_COLORS[name]
  return { bg: c.bgRgba, border: c.borderRgba, text: c.textHex }
})

export interface HiveDepartment {
  id: string
  name: string
  agentCount: number
  activeCount: number
  efficiency: number
}

interface SunflowerHiveProps {
  departments: HiveDepartment[]
  size?: number
}

export const SunflowerHive = memo(function SunflowerHive({
  departments,
  size = 400,
}: SunflowerHiveProps) {
  const navigate = useNavigate()
  const { chatMode, routingMode, autopilotActive } = useUiStore()
  const scale = size / 400 // base size is 400px

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      {/* Background concentric circles */}
      <div
        className="absolute rounded-full border border-accent-cyan/10"
        style={{ width: size * 0.9, height: size * 0.9 }}
      />
      <div
        className="absolute rounded-full border border-accent-cyan/15"
        style={{ width: size * 0.6, height: size * 0.6 }}
      />

      {/* Connection lines from center to each hex */}
      <svg
        className="absolute inset-0 pointer-events-none"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
      >
        {departments.slice(0, 10).map((_, i) => {
          const pos = RING_POSITIONS[i]
          const cx = size / 2
          const cy = size / 2
          return (
            <line
              key={i}
              x1={cx}
              y1={cy}
              x2={cx + pos.x * scale}
              y2={cy + pos.y * scale}
              stroke="rgba(6,182,212,0.08)"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
          )
        })}
      </svg>

      {/* Department hexagons */}
      {departments.slice(0, 10).map((dept, i) => {
        const pos = RING_POSITIONS[i]
        const color = DEPT_COLORS[i % DEPT_COLORS.length]
        const hexW = 100 * scale
        const hexH = 88 * scale

        return (
          <motion.button
            key={dept.id}
            className="absolute flex flex-col items-center justify-center cursor-pointer group"
            style={{
              width: hexW,
              height: hexH,
              left: size / 2 + pos.x * scale - hexW / 2,
              top: size / 2 + pos.y * scale - hexH / 2,
              clipPath: HEX_CLIP,
              background: `linear-gradient(170deg, ${color.bg}, rgba(15,23,42,0.92))`,
              boxShadow: `0 8px 20px -10px ${color.border}`,
            }}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.06, duration: 0.3 }}
            whileHover={{ scale: 1.06 }}
            onClick={() => navigate(`/departments/${dept.id}`)}
            title={`${dept.name}: ${dept.activeCount}/${dept.agentCount} active, ${dept.efficiency}% efficiency`}
            aria-label={`${dept.name} department`}
          >
            <span
              className="text-[9px] font-semibold leading-tight text-center px-2 truncate w-full"
              style={{ color: color.text, fontSize: Math.max(8, 9 * scale) }}
            >
              {dept.name}
            </span>
            <span
              className="text-starlight-400 mt-0.5"
              style={{ fontSize: Math.max(7, 8 * scale) }}
            >
              {dept.agentCount} agents
            </span>
            <span
              className="text-starlight-500 mt-0.5"
              style={{ fontSize: Math.max(7, 7 * scale) }}
            >
              {dept.efficiency}%
            </span>
          </motion.button>
        )
      })}

      {/* Central Daena Avatar (logo-based) */}
      <motion.div
        className="absolute z-10"
        style={{
          left: size / 2 - 50 * scale,
          top: size / 2 - 50 * scale,
          width: 100 * scale,
          height: 100 * scale,
        }}
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.3, duration: 0.4, type: 'spring' }}
        whileHover={{ scale: 1.08 }}
      >
        <DaenaAvatar
          state={autopilotActive ? 'thinking' : 'idle'}
          size={Math.round(90 * scale)}
          chatMode={chatMode}
          routingMode={routingMode}
          showLabel
          onClick={() => navigate('/chat')}
        />
      </motion.div>
    </div>
  )
})

export default SunflowerHive

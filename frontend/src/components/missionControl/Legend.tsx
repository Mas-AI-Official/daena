import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { GOV_GOLD, GOV_TEAL, KIND_COLORS, HIVE_HEX_COLORS } from '@/styles/designTokens'

/**
 * Legend for Mission Control. The force-graph hides labels at wide zoom (LOD),
 * so without a key the org reads as anonymous dots. This decodes the encoding:
 * which shape is which tier, that agents/workstreams INHERIT their department
 * color (so color == "which core owns this"), and what the spokes between cores
 * mean. Collapsible so it never competes with the graph; defaults open because
 * the readability gap is the whole reason it exists.
 */

const DEPT_SWATCH = `conic-gradient(${HIVE_HEX_COLORS.slice(0, 5).join(', ')}, ${HIVE_HEX_COLORS[0]})`
const FACULTY = KIND_COLORS.faculty

function Hex({ color }: { color: string }) {
  // Flat-top hexagon, the signature shape for the gold governance tier.
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
      <polygon points="6,3 18,3 23,12 18,21 6,21 1,12" fill={color} />
    </svg>
  )
}

function Dot({ color, hollow }: { color: string; hollow?: boolean }) {
  return (
    <span
      className="inline-block h-3 w-3 rounded-full"
      style={
        hollow
          ? { border: `2px solid ${color}`, background: 'transparent' }
          : { background: color }
      }
    />
  )
}

function GradientDot() {
  return <span className="inline-block h-3 w-3 rounded-full" style={{ background: DEPT_SWATCH }} />
}

function Spoke({ color, width }: { color: string; width: number }) {
  return <span className="inline-block w-4 rounded-full" style={{ height: width, background: color }} />
}

function Row({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-3.5 w-4 items-center justify-center">{swatch}</span>
      <span className="text-[11px] leading-tight text-white/70">{label}</span>
    </div>
  )
}

function Section({ title }: { title: string }) {
  return (
    <div className="mt-2 mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/35 first:mt-0">
      {title}
    </div>
  )
}

export default function Legend() {
  const [open, setOpen] = useState(true)

  return (
    <div className="absolute left-4 top-4 z-20 w-[230px] rounded-lg border border-white/10 bg-black/70 backdrop-blur">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-medium text-white/80 transition-colors hover:text-white"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Legend
      </button>
      {open ? (
        <div className="space-y-1 px-3 pb-3">
          <Section title="Tiers" />
          <Row swatch={<Hex color={GOV_GOLD} />} label="Daena — governance core" />
          <Row swatch={<Hex color={FACULTY} />} label="Faculty — Daena's 6 capabilities" />
          <Row swatch={<GradientDot />} label="Department — colored per core" />
          <Row swatch={<Dot color="#9aa4b2" />} label="Agent — inherits dept color" />
          <Row swatch={<Dot color="#9aa4b2" hollow />} label="Workstream / Session" />

          <Section title="Resources" />
          <Row swatch={<Dot color={KIND_COLORS.project} />} label="Project" />
          <Row swatch={<Dot color={KIND_COLORS.mcp_server} />} label="MCP server" />
          <Row swatch={<Dot color={KIND_COLORS.skill} />} label="Skill" />
          <Row swatch={<Dot color={KIND_COLORS.tool} />} label="Tool" />

          <Section title="Links" />
          <Row swatch={<Spoke color={GOV_GOLD} width={4} />} label="Daena governs department" />
          <Row swatch={<Spoke color="rgba(255,255,255,0.45)" width={2} />} label="Employs / owns" />

          <Section title="Selection" />
          <Row swatch={<Dot color={GOV_TEAL} hollow />} label="Selected / search match" />
        </div>
      ) : null}
    </div>
  )
}

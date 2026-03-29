/**
 * Design Tokens -- centralized color palettes and animation constants.
 *
 * Components that need hardcoded hex values (SVG, canvas, inline styles)
 * should import from here instead of embedding raw color strings.
 *
 * CSS variables live in globals.css @theme block; this file is for JS-side usage.
 */

// ── Department Colors (used by SunflowerGrid, SunflowerHive, DepartmentsPage) ──

export interface DepartmentColor {
  /** Primary hex color */
  hex: string
  /** Background rgba (15% opacity) */
  bgRgba: string
  /** Border rgba (30% opacity) */
  borderRgba: string
  /** Text color hex */
  textHex: string
}

export const DEPARTMENT_COLORS: Record<string, DepartmentColor> = {
  Engineering:           { hex: '#0070f3', bgRgba: 'rgba(0,112,243,0.15)',   borderRgba: 'rgba(0,112,243,0.3)',   textHex: '#0070f3' },
  Product:               { hex: '#8b5cf6', bgRgba: 'rgba(139,92,246,0.15)',  borderRgba: 'rgba(139,92,246,0.3)',  textHex: '#8b5cf6' },
  Marketing:             { hex: '#22c55e', bgRgba: 'rgba(34,197,94,0.15)',   borderRgba: 'rgba(34,197,94,0.3)',   textHex: '#22c55e' },
  Sales:                 { hex: '#06b6d4', bgRgba: 'rgba(6,182,212,0.15)',   borderRgba: 'rgba(6,182,212,0.3)',   textHex: '#06b6d4' },
  Finance:               { hex: '#eab308', bgRgba: 'rgba(234,179,8,0.15)',   borderRgba: 'rgba(234,179,8,0.3)',   textHex: '#eab308' },
  Operations:            { hex: '#f97316', bgRgba: 'rgba(249,115,22,0.15)',  borderRgba: 'rgba(249,115,22,0.3)',  textHex: '#f97316' },
  Research:              { hex: '#3b82f6', bgRgba: 'rgba(59,130,246,0.15)',  borderRgba: 'rgba(59,130,246,0.3)',  textHex: '#3b82f6' },
  'Legal & Compliance':  { hex: '#ef4444', bgRgba: 'rgba(239,68,68,0.15)',   borderRgba: 'rgba(239,68,68,0.3)',   textHex: '#ef4444' },
  'Skill Governance':    { hex: '#d946ef', bgRgba: 'rgba(217,70,239,0.15)',  borderRgba: 'rgba(217,70,239,0.3)',  textHex: '#d946ef' },
  'Security Operations': { hex: '#f472b6', bgRgba: 'rgba(244,114,182,0.15)', borderRgba: 'rgba(244,114,182,0.3)', textHex: '#f472b6' },
} as const

/** Ordered array of hex colors for indexed access (e.g., hive node coloring). */
export const HIVE_HEX_COLORS = [
  '#0070f3', '#8b5cf6', '#22c55e', '#06b6d4', '#eab308',
  '#f97316', '#3b82f6', '#ef4444', '#d946ef', '#f472b6',
] as const

// ── Orb/Avatar Mode Palettes ──

export interface ModePalette {
  from: string
  to: string
  shadow: string
  accent: string
}

export const ORB_MODE_PALETTES: Record<string, ModePalette> = {
  CMD:          { from: '#0070f3', to: '#00a8ff', shadow: 'rgba(0,112,243,0.4)',  accent: '#60a5fa' },
  EXE:          { from: '#eab308', to: '#fcd34d', shadow: 'rgba(234,179,8,0.4)',  accent: '#fbbf24' },
  COUNCIL:      { from: '#8b5cf6', to: '#a855f7', shadow: 'rgba(139,92,246,0.4)', accent: '#c084fc' },
  QUINTESSENCE: { from: '#e2e8f0', to: '#f8f9fa', shadow: 'rgba(226,232,240,0.4)', accent: '#f1f5f9' },
} as const

export const ORB_ERROR_PALETTE: ModePalette = {
  from: '#ff4757', to: '#f97316', shadow: 'rgba(255,71,87,0.4)', accent: '#fb7185',
}

// ── Animation Durations (ms) ──

export const ANIMATION = {
  /** Fast micro-interaction (hover, toggle) */
  fast: 150,
  /** Standard transition (modal, panel) */
  normal: 250,
  /** Slow entrance (page, large panel) */
  slow: 400,
  /** Breathing/idle animations */
  breathe: 3000,
  /** Active/thinking animations */
  active: 1500,
} as const

// ── Background Constants ──

export const BACKGROUNDS = {
  /** Primary background */
  midnight: '#020408',
  /** Card background */
  card: '#161B26',
  /** Input background */
  input: 'rgba(2,4,8,0.5)',
  /** Glass overlay */
  glass: 'rgba(11,15,23,0.6)',
  /** Standard border */
  border: 'rgba(255,255,255,0.08)',
  /** Hover border */
  borderHover: 'rgba(255,255,255,0.12)',
} as const

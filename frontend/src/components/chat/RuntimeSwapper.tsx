/**
 * RuntimeSwapper (Phase 8): chat header dropdown for switching
 * between execution runtimes (Claude Code, Codex, Gemini CLI, Ollama, etc.).
 *
 * Shows current runtime, health status, capability stars, and
 * an "Auto" option that lets Daena choose per message.
 */
import { useState, useRef, useEffect, memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown,
  Cpu,
  Settings,
  Sparkles,
  Wifi,
  WifiOff,
  AlertTriangle,
  Zap,
} from 'lucide-react'
import type { RuntimeInfo, RuntimeStatus } from '@/types/api'

// ── Status display helpers ──

const STATUS_DOT_CLASS: Record<RuntimeStatus, string> = {
  online: 'runtime-dot-online',
  offline: 'runtime-dot-offline',
  rate_limited: 'runtime-dot-limited',
  error: 'runtime-dot-error',
  not_installed: 'runtime-dot-offline',
}

const STATUS_LABEL: Record<RuntimeStatus, string> = {
  online: 'Online',
  offline: 'Offline',
  rate_limited: 'Rate Limited',
  error: 'Error',
  not_installed: 'Not Installed',
}

function capabilityStars(score: number): string {
  const filled = Math.round(score / 2) // 0-10 -> 0-5 stars
  return '\u2605'.repeat(filled) + '\u2606'.repeat(5 - filled)
}

function bestCapability(caps: Record<string, number>): string {
  let best = ''
  let max = 0
  for (const [key, val] of Object.entries(caps)) {
    if (key === 'cost_per_1k_tokens') continue
    if (val > max) {
      max = val
      best = key.replace(/_/g, ' ')
    }
  }
  return best
}

// ── Default runtimes (in-memory demo data) ──

const DEFAULT_RUNTIMES: RuntimeInfo[] = [
  {
    id: 'claude_code',
    name: 'Claude Code (Anthropic)',
    status: 'online',
    capabilities: { complex_reasoning: 9.5, code_generation: 9.5, code_editing: 9.0 },
    cost_per_1k_tokens: 0.015,
    is_free: false,
  },
  {
    id: 'codex',
    name: 'Codex (OpenAI)',
    status: 'online',
    capabilities: { code_generation: 9.5, bulk_operations: 8.0, code_editing: 8.5 },
    cost_per_1k_tokens: 0.01,
    is_free: false,
  },
  {
    id: 'gemini_cli',
    name: 'Gemini CLI (Google)',
    status: 'not_installed',
    capabilities: { web_research: 8.0, data_analysis: 8.5, simple_chat: 7.5 },
    cost_per_1k_tokens: 0.005,
    is_free: false,
  },
  {
    id: 'grok_cli',
    name: 'Grok (xAI)',
    status: 'not_installed',
    capabilities: { web_research: 8.5, simple_chat: 7.0, data_analysis: 6.5 },
    cost_per_1k_tokens: 0.01,
    is_free: false,
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    status: 'online',
    capabilities: { simple_chat: 7.0, code_generation: 6.0, data_analysis: 5.5 },
    cost_per_1k_tokens: 0,
    is_free: true,
  },
]

// ── RuntimeSwapper component ──

interface RuntimeSwapperProps {
  selectedRuntime: string | null
  onSelectRuntime: (runtimeId: string | null) => void
  runtimes?: RuntimeInfo[]
  className?: string
}

export const RuntimeSwapper = memo(function RuntimeSwapper({
  selectedRuntime,
  onSelectRuntime,
  runtimes = DEFAULT_RUNTIMES,
  className = '',
}: RuntimeSwapperProps) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    if (open) document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open])

  const active = runtimes.find((r) => r.id === selectedRuntime)
  const isAuto = selectedRuntime === null
  const displayName = isAuto ? 'Auto' : (active?.name ?? 'Unknown')

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Trigger button.
         Label prefix "Mind:" was added 2026-04-16 to disambiguate
         this control (which picks the Primary Mind runtime -- Claude
         Code / Codex / Gemini CLI / Ollama) from the per-message
         model dropdown in ChatInput (which picks a specific model
         within the selected runtime). Two separate controls, two
         separate uiStore fields (selectedRuntime vs selectedModel).
         Before this label, both showed "Auto" and operators confused
         them. */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-midnight-300/60 border border-white/5 hover:border-white/10 hover:bg-midnight-400/60 transition-all text-sm"
        title="Primary Mind: which runtime orchestrates the answer"
      >
        {isAuto ? (
          <Sparkles size={14} className="text-accent-amber" />
        ) : (
          <Cpu size={14} className="text-primary-400" />
        )}
        <span className="text-starlight-500 text-xs mr-0.5">Mind:</span>
        <span className="text-starlight-200">{displayName}</span>
        {active && (
          <span className={`runtime-dot ${STATUS_DOT_CLASS[active.status]}`} />
        )}
        <ChevronDown
          size={14}
          className={`text-starlight-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 mt-2 w-72 rounded-xl bg-midnight-200 border border-white/10 shadow-2xl z-50 overflow-hidden"
          >
            {/* Auto option */}
            <button
              onClick={() => { onSelectRuntime(null); setOpen(false) }}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors
                ${isAuto ? 'bg-primary-500/10 border-l-2 border-primary-500' : 'border-l-2 border-transparent'}`}
            >
              <Sparkles size={16} className="text-accent-amber" />
              <div className="flex-1">
                <p className="text-sm font-medium text-starlight-100">Auto</p>
                <p className="text-[10px] text-starlight-400">Let Daena choose per message</p>
              </div>
              {isAuto && <Zap size={14} className="text-primary-400" />}
            </button>

            <div className="border-t border-white/5" />

            {/* Runtime list -- only show ONLINE runtimes */}
            {runtimes.filter((r) => r.status === 'online').map((runtime) => {
              const isSelected = selectedRuntime === runtime.id
              const best = bestCapability(runtime.capabilities)

              return (
                <button
                  key={runtime.id}
                  onClick={() => {
                    onSelectRuntime(runtime.id)
                    setOpen(false)
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-white/[0.03] cursor-pointer
                    ${isSelected ? 'bg-primary-500/10 border-l-2 border-primary-500' : 'border-l-2 border-transparent'}`}
                >
                  <Cpu size={16} className="text-primary-400" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-starlight-200 truncate">{runtime.name}</span>
                      <span className={`runtime-dot ${STATUS_DOT_CLASS[runtime.status]}`} />
                    </div>
                    {best && (
                      <p className="text-[10px] text-starlight-400 mt-0.5">
                        {capabilityStars(runtime.capabilities[Object.keys(runtime.capabilities).find(
                          (k) => k.replace(/_/g, ' ') === best
                        ) ?? ''] ?? 0)}{' '}
                        {best}
                        {runtime.is_free && (
                          <span className="ml-1.5 text-status-success">(free)</span>
                        )}
                      </p>
                    )}
                  </div>
                </button>
              )
            })}

            {/* Manage link removed -- use Connections page instead */}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
})

export default RuntimeSwapper

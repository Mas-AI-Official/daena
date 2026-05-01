/**
 * Tiny presentational primitives shared by every Connections sub-tab.
 *   - PermissionSelect: Allow / Ask each time / Block dropdown
 *   - ConfigPanel: animated expand/collapse wrapper for row config
 *   - ContextMenu: three-dot floating menu
 *
 * Pure presentational, no data fetching, no business logic.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, ChevronDown } from 'lucide-react'
import type { Permission } from './types'

// ── Permission Select (Allow / Ask each time / Block) ──

export function PermissionSelect({ value, onChange }: { value: Permission; onChange: (v: Permission) => void }) {
  const [open, setOpen] = useState(false)
  // Session 10: Claude Desktop parity -- pills are bigger and higher
  // contrast so "Ask" reads at a glance. Old opacities (5% bg, 30%
  // border) were too dim on midnight-500; at 12% / 50% they match
  // Claude Desktop's permission pills.
  const colors: Record<Permission, { text: string; bg: string; border: string; dot: string }> = {
    ALLOW: { text: 'text-accent-green', bg: 'bg-accent-green/12', border: 'border-accent-green/50', dot: 'bg-accent-green' },
    ASK_EACH_TIME: { text: 'text-accent-amber', bg: 'bg-accent-amber/12', border: 'border-accent-amber/50', dot: 'bg-accent-amber' },
    BLOCK: { text: 'text-accent-red', bg: 'bg-accent-red/12', border: 'border-accent-red/50', dot: 'bg-accent-red' },
  }
  const labels: Record<Permission, string> = { ALLOW: 'Allow', ASK_EACH_TIME: 'Ask', BLOCK: 'Block' }
  const options: Permission[] = ['ALLOW', 'ASK_EACH_TIME', 'BLOCK']
  const c = colors[value]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-md border cursor-pointer transition-colors hover:brightness-110 ${c.text} ${c.bg} ${c.border}`}
      >
        <span className={`w-2 h-2 rounded-full ${c.dot}`} />
        {labels[value]}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.1 }}
              className="absolute right-0 top-full mt-1 w-28 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
            >
              {options.map((opt) => {
                const oc = colors[opt]
                return (
                  <button
                    key={opt}
                    onClick={() => { onChange(opt); setOpen(false) }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-[11px] font-medium text-left transition-colors cursor-pointer hover:bg-white/5 ${
                      value === opt ? oc.text : 'text-starlight-300'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${oc.dot}`} />
                    {labels[opt]}
                    {value === opt && <CheckCircle2 size={11} className="ml-auto" />}
                  </button>
                )
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Expandable Config Panel wrapper ──

export function ConfigPanel({ expanded, children }: { expanded: boolean; children: React.ReactNode }) {
  return (
    <AnimatePresence>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="overflow-hidden"
        >
          <div className="px-4 pb-4 pt-1 ml-14 border-t border-white/5 space-y-3">
            {children}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ── Three-dot menu ──

export function ContextMenu({ items, onClose }: { items: { label: string; icon: React.ReactNode; onClick: () => void; danger?: boolean }[]; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="absolute right-0 top-full mt-1 w-48 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
      >
        {items.map((item) => (
          <button
            key={item.label}
            onClick={() => { item.onClick(); onClose() }}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors cursor-pointer ${
              item.danger ? 'text-accent-red hover:bg-accent-red/10' : 'text-starlight-300 hover:bg-white/5'
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </motion.div>
    </>
  )
}

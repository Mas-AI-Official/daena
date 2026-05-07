/**
 * SlashCommands -- autocomplete menu for / commands in chat input.
 *
 * When user types "/" as the first character, shows a filtered list
 * of available commands. Arrow keys navigate, Enter selects.
 */
import { useState, useEffect, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HelpCircle,
  Settings,
  Plug,
  Brain,
  Zap,
  Shield,
  ShieldAlert,
  Heart,
  Database,
  DollarSign,
  Store,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useUiStore } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'

interface SlashCommand {
  command: string
  description: string
  icon: typeof HelpCircle
  action: () => void
}

export function useSlashCommands() {
  const navigate = useNavigate()
  const { setChatMode } = useUiStore()

  const commands: SlashCommand[] = useMemo(
    () => [
      {
        command: '/help',
        description: 'Show available commands',
        icon: HelpCircle,
        action: () => toast.info('Type / to see all commands. Type /settings to open settings.'),
      },
      {
        command: '/settings',
        description: 'Open settings',
        icon: Settings,
        action: () => navigate('/settings'),
      },
      {
        command: '/connect',
        description: 'Manage runtime connections',
        icon: Plug,
        action: () => navigate('/connections'),
      },
      {
        command: '/mode cmd',
        description: 'Switch to CMD (chat) mode',
        icon: Brain,
        action: () => { setChatMode('CMD'); toast.success('Switched to CMD mode') },
      },
      {
        command: '/mode exe',
        description: 'Switch to EXE (execute) mode',
        icon: Zap,
        action: () => { setChatMode('EXE'); toast.success('Switched to EXE mode') },
      },
      {
        command: '/governance',
        description: 'Set governance level',
        icon: Shield,
        action: () => navigate('/settings/governance'),
      },
      {
        command: '/heartbeat',
        description: 'Show Daena Heartbeat status',
        icon: Heart,
        action: () => navigate('/settings/heartbeat'),
      },
      {
        command: '/audit',
        description: 'Show recent audit entries',
        icon: Shield,
        action: () => navigate('/governance/audit'),
      },
      {
        command: '/cost',
        description: 'Open billing and usage',
        icon: DollarSign,
        action: () => navigate('/settings/billing'),
      },
      {
        command: '/marketplace',
        description: 'Open skills registry',
        icon: Store,
        action: () => navigate('/skills'),
      },
      {
        command: '/memory',
        description: 'View stored memories',
        icon: Database,
        action: () => navigate('/settings/memory'),
      },
      {
        command: '/scan',
        description: 'Trigger a security scan on a URL',
        icon: ShieldAlert,
        action: () => toast.info('Type /scan followed by a URL, then send to start a scan.'),
      },
    ],
    [navigate, setChatMode],
  )

  return commands
}

interface SlashCommandMenuProps {
  input: string
  onSelect: (command: SlashCommand) => void
  onClose: () => void
  visible: boolean
}

export function SlashCommandMenu({ input, onSelect, onClose, visible }: SlashCommandMenuProps) {
  const commands = useSlashCommands()
  const [selectedIndex, setSelectedIndex] = useState(0)

  const filtered = useMemo(() => {
    if (!input.startsWith('/')) return []
    const query = input.toLowerCase()
    return commands.filter((cmd) => cmd.command.startsWith(query))
  }, [input, commands])

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [filtered.length])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible || filtered.length === 0) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((i) => (i + 1) % filtered.length)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length)
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        onSelect(filtered[selectedIndex])
      } else if (e.key === 'Escape') {
        onClose()
      }
    },
    [visible, filtered, selectedIndex, onSelect, onClose],
  )

  useEffect(() => {
    if (visible) {
      window.addEventListener('keydown', handleKeyDown)
      return () => window.removeEventListener('keydown', handleKeyDown)
    }
  }, [visible, handleKeyDown])

  if (!visible || filtered.length === 0) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 8 }}
        className="absolute bottom-full left-0 right-0 mb-2 max-h-64 overflow-y-auto glass-card rounded-xl border border-white/10 shadow-2xl z-50"
      >
        <div className="p-1.5">
          {filtered.map((cmd, i) => {
            const Icon = cmd.icon
            return (
              <button
                key={cmd.command}
                onClick={() => onSelect(cmd)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors cursor-pointer ${
                  i === selectedIndex
                    ? 'bg-primary-500/15 text-starlight-100'
                    : 'text-starlight-300 hover:bg-white/5'
                }`}
              >
                <Icon size={14} className="text-starlight-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-mono">{cmd.command}</span>
                  <span className="text-[10px] text-starlight-500 ml-2">{cmd.description}</span>
                </div>
              </button>
            )
          })}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

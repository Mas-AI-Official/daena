import { memo, useCallback, useState, useEffect, useRef } from 'react'
import { Bell, Search, Brain, BrainCircuit, Zap, X, Menu, Heart, Mic, MicOff, AudioLines, AudioWaveform } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useUiStore, persistUiPref, hydrateNotificationsFromBackend } from '@/stores/uiStore'
import { useToastStore } from '@/stores/toastStore'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useSecurityModeStore } from '@/stores/securityModeStore'
import { CommandPalette } from '@/components/common/CommandPalette'
import { ConnectionStatusIndicator } from '@/components/common/ConnectionStatusIndicator'
import { useVoice } from '@/providers/VoiceProvider'
// RuntimeSwapper was re-mounted here in Session 2 (2026-04-16) and
// removed in Session 9 (2026-04-17) after operator audit: it duplicated
// the Mind Control tab on /connections + the per-message Model dropdown
// in ChatInput. Primary Mind selection now lives in Connections > Mind
// Control for setup, and ChatInput "Model:" handles per-message picks.
// RuntimeSwapper.tsx archived 2026-06-17 -> .archive/dead_orphan_components_20260617/ (revive = founder call).
import type { ChatMode, RoutingMode, GovernanceMode } from '@/types/api'

/** Fire a PATCH to sync a session-level field to the backend (fire-and-forget). */
function syncSession(fields: Record<string, unknown>) {
  const { activeSessionId, updateSession } = useChatStore.getState()
  if (activeSessionId) {
    updateSession(activeSessionId, fields)
  }
}

export const Header = memo(function Header() {
  const {
    chatMode,
    setChatMode,
    routingMode,
    setRoutingMode,
    thinkingVisible,
    toggleThinking,
    governanceMode,
    setGovernanceMode,
    autopilotActive,
    toggleAutopilot,
    notifications,
  } = useUiStore()
  const { user, logout } = useAuthStore()
  const registry = useModelRegistryStore((s) => s.registry)
  const unreadCount = notifications.length
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)
  const removeNotification = useUiStore((s) => s.removeNotification)
  const clearNotifications = useUiStore((s) => s.clearNotifications)

  // Close notification panel on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    if (notifOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [notifOpen])

  // Phase 11 PR-S2: hydrate the bell from /notifications on mount so
  // persisted rows survive a browser refresh. Once-only; future
  // additions arrive via the in-memory addNotification path (toast)
  // or a dedicated SSE channel (future PR-S2 follow-up).
  useEffect(() => {
    void hydrateNotificationsFromBackend(20)
  }, [])

  // Global Ctrl+K / Cmd+K shortcut
  useEffect(() => {
    const handleGlobalKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
    }
    document.addEventListener('keydown', handleGlobalKey)
    return () => document.removeEventListener('keydown', handleGlobalKey)
  }, [])

  // Wrapped toggle handlers that also sync to backend session
  const handleChatMode = useCallback((mode: ChatMode) => {
    setChatMode(mode)
    syncSession({ mode })
    persistUiPref('default_chat_mode', mode)
  }, [setChatMode])

  const handleRoutingMode = useCallback((mode: RoutingMode) => {
    setRoutingMode(mode)
    syncSession({ routing_mode: mode })
    persistUiPref('default_routing_mode', mode)
  }, [setRoutingMode])

  const handleThinkToggle = useCallback(() => {
    const newVal = !useUiStore.getState().thinkingVisible
    toggleThinking()
    syncSession({ think_mode: newVal })
    persistUiPref('persist_thinking', newVal)
  }, [toggleThinking])

  const handleAutopilotToggle = useCallback(() => {
    const newVal = !useUiStore.getState().autopilotActive
    toggleAutopilot()
    syncSession({ autopilot: newVal })
    persistUiPref('autopilot_active', newVal)
    useToastStore.getState().addToast(
      newVal
        ? { type: 'success', message: 'AGI Mode activated -- non-critical actions auto-approved' }
        : { type: 'info', message: 'AGI Mode deactivated' },
    )
  }, [toggleAutopilot])

  const handleGovernanceCycle = useCallback(() => {
    const modes: GovernanceMode[] = ['UNLEASHED', 'BALANCED', 'GOVERNED']
    const idx = modes.indexOf(governanceMode)
    const next = modes[(idx + 1) % modes.length]
    setGovernanceMode(next)
    syncSession({ governance_mode: next })
    persistUiPref('default_governance_mode', next)
  }, [governanceMode, setGovernanceMode])

  return (
    <header className="h-16 bg-midnight-200/95 border-b border-white/5 flex items-center justify-between px-2 sm:px-4 shrink-0 z-40"
      style={{ backdropFilter: 'blur(8px)' }}
    >
      {/* Left: Simplified controls (4 items) */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Mobile hamburger */}
        <button
          onClick={() => useUiStore.getState().toggleMobileSidebar()}
          className="p-2 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer sm:hidden"
          aria-label="Toggle navigation menu"
        >
          <Menu size={20} />
        </button>

        {/* Execution Mode: CMD / EXE */}
        <div className="flex items-center gap-1 bg-midnight-400/50 rounded-lg p-0.5">
          <button
            onClick={() => handleChatMode('CMD')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all cursor-pointer ${
              chatMode === 'CMD'
                ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                : 'text-starlight-400 hover:text-starlight-200'
            }`}
          >
            CMD
          </button>
          <button
            onClick={() => handleChatMode('EXE')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all cursor-pointer ${
              chatMode === 'EXE'
                ? 'bg-accent-amber/20 text-accent-amber border border-accent-amber/30'
                : 'text-starlight-400 hover:text-starlight-200'
            }`}
          >
            EXE
          </button>
        </div>

        {/* Routing Mode: STD / QE pills (Council removed -- Quintessence is strictly better) */}
        <div className="hidden md:flex items-center gap-1 bg-midnight-400/50 rounded-lg p-0.5">
          {(['STANDARD', 'QUINTESSENCE'] as const).map((mode) => {
            const tooltip = mode === 'QUINTESSENCE'
              ? 'Expert-guided multi-model synthesis (DCP experts always active)'
              : 'Single best model, fast routing'
            return (
              <div key={mode} className="relative group">
                <button
                  onClick={() => handleRoutingMode(mode)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                    routingMode === mode
                      ? mode === 'QUINTESSENCE'
                        ? 'bg-accent-purple/20 text-accent-purple border border-accent-purple/30'
                        : 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'text-starlight-400 hover:text-starlight-200'
                  }`}
                >
                  {mode === 'QUINTESSENCE' ? 'QE' : 'STD'}
                </button>
                <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-2 py-1 rounded bg-midnight-100 text-[10px] text-starlight-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-white/10 shadow-lg z-50">
                  {tooltip}
                </div>
              </div>
            )
          })}
        </div>

        {/* Think toggle */}
        <button
          onClick={handleThinkToggle}
          className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            thinkingVisible
              ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
              : 'text-starlight-400 hover:text-starlight-200 border border-transparent'
          }`}
        >
          <BrainCircuit size={14} />
          Think
        </button>

        {/* Governance mode badge (clickable: cycle UNLEASHED > BALANCED > GOVERNED) + slider */}
        <div className="hidden lg:block w-px h-6 bg-white/10" />
        <div className="hidden lg:flex items-center gap-2">
          <button
            onClick={handleGovernanceCycle}
            title="Click to cycle governance mode"
            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider cursor-pointer transition-all ${
            governanceMode === 'UNLEASHED'
              ? 'bg-status-error/20 text-status-error border border-status-error/30 hover:bg-status-error/30 shadow-[0_0_12px_rgba(255,71,87,0.15)]'
              : governanceMode === 'BALANCED'
              ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30 hover:bg-accent-cyan/30'
              : 'bg-starlight-400/10 text-starlight-400 border border-white/10 hover:bg-white/10'
          }`}>
            {governanceMode}
          </button>
        </div>
      </div>

      {/* Right: AGI toggle, Heartbeat, Search, notifications, user */}
      <div className="flex items-center gap-3">
        {/* AGI Autopilot Toggle */}
        <button
          onClick={handleAutopilotToggle}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
            autopilotActive
              ? 'bg-status-success/20 text-status-success border border-status-success/30 shadow-[0_0_12px_rgba(34,197,94,0.15)]'
              : 'text-starlight-500 hover:text-starlight-300 border border-white/10 hover:border-white/20'
          }`}
        >
          <Zap size={14} className={autopilotActive ? 'animate-pulse' : ''} />
          {autopilotActive ? 'AGI ACTIVE' : 'AGI OFF'}
        </button>

        {/* Voice / Conversational mode toggle */}
        <VoiceToggle />

        {/* Connection-health dot -- surfaces backend fetch failures from
            errorStore (fed unconditionally by the axios interceptor). Returns
            null while healthy; lights degraded/down when fetches fail in a 60s
            window. Restores the global error surface ADR-001 mandates -- the
            component existed but was never mounted (Rule-17 fix, Phase 7). */}
        <ConnectionStatusIndicator />

        {/* Heartbeat indicator */}
        <HeartbeatIndicator />

        {/* Elevated mode indicator (discrete; no label; founder-only flow) */}
        <ElevatedModeIndicator />

        <div className="w-px h-6 bg-white/10" />

        <button
          aria-label="Search"
          onClick={() => setPaletteOpen(true)}
          className="p-2 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
        >
          <Search size={18} />
        </button>

        <div className="relative" ref={notifRef}>
          <button
            aria-label="Notifications"
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative p-2 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-status-error text-white text-[9px] font-bold flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          <AnimatePresence>
            {notifOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.97 }}
                transition={{ duration: 0.12 }}
                className="absolute top-full right-0 mt-2 w-72 sm:w-80 z-50
                           bg-midnight-400/95 backdrop-blur-md border border-white/10
                           rounded-xl shadow-xl overflow-hidden"
              >
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
                  <h3 className="text-xs font-display font-semibold text-starlight-200">
                    Notifications
                  </h3>
                  {notifications.length > 0 && (
                    <button
                      onClick={clearNotifications}
                      className="text-[10px] text-starlight-500 hover:text-starlight-200 cursor-pointer"
                    >
                      Clear all
                    </button>
                  )}
                </div>
                <div className="max-h-[300px] overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-xs text-starlight-500">
                      No notifications
                    </div>
                  ) : (
                    notifications.map((n) => (
                      <div
                        key={n.id}
                        className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition-colors border-b border-white/5 last:border-b-0"
                      >
                        <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
                          n.type === 'error' ? 'bg-status-error'
                          : n.type === 'warning' ? 'bg-status-warning'
                          : n.type === 'success' ? 'bg-status-success'
                          : 'bg-primary-400'
                        }`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-starlight-200">{n.title}</p>
                          <p className="text-[11px] text-starlight-500 truncate">{n.message}</p>
                        </div>
                        <button
                          onClick={() => removeNotification(n.id)}
                          className="p-0.5 text-starlight-600 hover:text-starlight-300 cursor-pointer shrink-0"
                          aria-label="Dismiss notification"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* User avatar moved to sidebar bottom (Perplexity-style) */}
      </div>
      {/* Command palette (Ctrl+K) */}
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </header>
  )
})

/** Voice toggle -- enables full voice conversation (listen + speak).
 * ON: single SpeechRecognition + ElevenLabs/browser TTS.
 * OFF: stops mic and TTS, clears floating indicator.
 */
function VoiceToggle() {
  const { isActive, isListening, isSpeaking, toggle } = useVoice()

  return (
    <button
      onClick={toggle}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
        isActive
          ? 'bg-accent-purple/20 text-accent-purple border border-accent-purple/30'
          : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/5'
      }`}
      title={
        isActive
          ? isSpeaking
            ? 'Daena is speaking...'
            : isListening
              ? 'Listening... (click to stop)'
              : 'Voice ON (click to stop)'
          : 'Enable voice conversation'
      }
    >
      {isActive
        ? <AudioLines size={14} className="animate-pulse" />
        : <AudioWaveform size={14} />}
      <span className="hidden sm:inline">{isActive ? 'Voice' : ''}</span>
    </button>
  )
}

/** Heartbeat pulsing dot indicator -- shows daemon status in header. */
function HeartbeatIndicator() {
  const [status, setStatus] = useState<'running' | 'paused' | 'stopped'>('stopped')

  useEffect(() => {
    let mounted = true
    let delay = 30000
    let timer: ReturnType<typeof setTimeout>
    const check = async () => {
      try {
        const token = useAuthStore.getState().token
        if (!token) return
        const res = await fetch('/api/v1/heartbeat/status', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok && mounted) {
          const data = await res.json()
          setStatus(data.data?.state || 'stopped')
        }
        delay = 30000 // Reset on success
      } catch {
        delay = Math.min(delay * 2, 120000) // Backoff to 2min max
      }
      if (mounted) timer = setTimeout(check, delay)
    }
    void check()
    return () => { mounted = false; clearTimeout(timer) }
  }, [])

  if (status === 'stopped') return null

  const isActive = status === 'running'
  return (
    <div
      className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-mono"
      title={`Heartbeat: ${status}`}
    >
      <Heart
        size={12}
        className={isActive ? 'text-accent-red animate-pulse' : 'text-starlight-500'}
        fill={isActive ? 'currentColor' : 'none'}
      />
      <span className={isActive ? 'text-starlight-300' : 'text-starlight-500'}>
        {isActive ? 'LIVE' : 'PAUSED'}
      </span>
    </div>
  )
}

/** Elevated mode indicator.
 *
 * Shows a small gold lightning icon when the elevated security mode
 * singleton is active. No text label. Tooltip is the only user-facing
 * hint. Polls /security/mode/state every 30s to keep in sync with
 * server-side state (handles auto-activation at startup and manual
 * deactivation from any tab).
 */
function ElevatedModeIndicator() {
  const active = useSecurityModeStore((s) => s.state.active)
  const fetchState = useSecurityModeStore((s) => s.fetchState)
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (!token) return
    void fetchState()
    const id = setInterval(() => { void fetchState() }, 30000)
    return () => clearInterval(id)
  }, [token, fetchState])

  if (!active) return null

  return (
    <div
      className="flex items-center justify-center p-1.5 rounded-lg"
      title={
        "Full-spectrum security mode active (founder).\n" +
        "This is separate from CMD/EXE action mode:\n" +
        "  EXE = Daena executes tools vs just plans.\n" +
        "  Elevated = Offensive security primitives + T5 Founder scan tier unlocked."
      }
      aria-label="Elevated security mode active"
    >
      <Zap size={14} className="text-accent-amber animate-pulse" />
    </div>
  )
}

export default Header

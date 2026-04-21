/**
 * UI store — sidebar state, mode switches, notifications, theme.
 */
import { create } from 'zustand'
import type { ChatMode, RoutingMode, GovernanceMode } from '@/types/api'
import type { InteractivePromptData } from '@/components/chat/InteractivePrompt'

export interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: number
}

interface UiState {
  // Layout
  sidebarOpen: boolean
  sidebarWidth: number
  historySidebarOpen: boolean
  // Company-wide / peer-signals pane on the right of ChatPage &
  // DepartmentChatPage. Collapsed by default so the chat stays big;
  // toggle lives next to the message composer.
  peerSignalsPaneOpen: boolean
  mobileSidebarOpen: boolean

  // Mode switches
  chatMode: ChatMode
  routingMode: RoutingMode
  governanceMode: GovernanceMode

  // Toggles
  darkMode: boolean
  thinkingVisible: boolean
  persistThinking: boolean
  conversationalMode: boolean
  speechEnabled: boolean
  voiceListening: boolean
  volume: number

  // Autopilot (AGI Mode)
  autopilotActive: boolean

  // LLM routing preferences
  localFirstRouting: boolean
  costAwareRouting: boolean

  // DaenaBot
  daenaBotEnabled: boolean
  screenshotCapture: boolean

  // Developer
  debugMode: boolean
  verboseLogging: boolean

  // Model selector
  selectedModel: string | null

  // Runtime swapper (V2)
  selectedRuntime: string | null

  // Execution view (V2)
  executionViewVisible: boolean

  // Voice auto-read (V2)
  autoReadResponses: boolean

  // Interactive prompts (agent-to-user)
  activePrompt: InteractivePromptData | null
  promptQueue: InteractivePromptData[]

  // Notifications
  notifications: Notification[]

  // Actions
  addPrompt: (prompt: InteractivePromptData) => void
  dismissPrompt: () => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  toggleHistorySidebar: () => void
  togglePeerSignalsPane: () => void
  setChatMode: (mode: ChatMode) => void
  setGovernanceMode: (mode: GovernanceMode) => void
  setRoutingMode: (mode: RoutingMode) => void
  toggleDarkMode: () => void
  toggleThinking: () => void
  togglePersistThinking: () => void
  toggleConversational: () => void
  toggleSpeech: () => void
  setVoiceListening: (listening: boolean) => void
  setVolume: (v: number) => void
  toggleAutopilot: () => void
  toggleLocalFirstRouting: () => void
  toggleCostAwareRouting: () => void
  toggleDaenaBot: () => void
  toggleScreenshotCapture: () => void
  toggleDebugMode: () => void
  toggleVerboseLogging: () => void
  setSelectedModel: (model: string | null) => void
  setSelectedRuntime: (runtime: string | null) => void
  toggleExecutionView: () => void
  setAutoReadResponses: (enabled: boolean) => void
  setMobileSidebarOpen: (open: boolean) => void
  toggleMobileSidebar: () => void
  addNotification: (n: Omit<Notification, 'id' | 'timestamp'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  sidebarWidth: 256,
  // History sidebar default is persisted per-user in localStorage.
  // Default is OPEN so chat history (sessions list) is visible the
  // moment you open /chat. The earlier Perplexity-style "start
  // collapsed" hid 20+ sessions from founders by default. The
  // toggle button still collapses it, and the choice persists.
  historySidebarOpen: localStorage.getItem('daena:historySidebarOpen') === 'false' ? false : true,
  peerSignalsPaneOpen: false, // starts collapsed so chat stays big
  mobileSidebarOpen: false,
  chatMode: (localStorage.getItem('daena:chatMode') as ChatMode) || 'CMD',
  governanceMode: (localStorage.getItem('daena:governanceMode') as GovernanceMode) || 'GOVERNED',
  routingMode: (localStorage.getItem('daena:routingMode') as RoutingMode) || 'STANDARD',
  darkMode: localStorage.getItem('daena:darkMode') !== 'false',
  thinkingVisible: localStorage.getItem('daena:thinkingVisible') !== 'false',
  persistThinking: localStorage.getItem('daena:persistThinking') !== 'false',
  conversationalMode: false,
  speechEnabled: false,
  voiceListening: false,
  volume: 0.7,
  autopilotActive: localStorage.getItem('daena:autopilotActive') === 'true',
  localFirstRouting: true,
  costAwareRouting: true,
  daenaBotEnabled: true,
  screenshotCapture: true,
  activePrompt: null,
  promptQueue: [],
  debugMode: false,
  verboseLogging: false,
  selectedModel: null,
  selectedRuntime: null,
  executionViewVisible: localStorage.getItem('daena:executionView') !== 'false',
  autoReadResponses: false,
  notifications: [],

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleHistorySidebar: () => set((s) => {
    const next = !s.historySidebarOpen
    try { localStorage.setItem('daena:historySidebarOpen', String(next)) } catch {}
    return { historySidebarOpen: next }
  }),
  togglePeerSignalsPane: () => set((s) => ({ peerSignalsPaneOpen: !s.peerSignalsPaneOpen })),
  setChatMode: (mode) => { localStorage.setItem('daena:chatMode', mode); set({ chatMode: mode }) },
  setGovernanceMode: (mode) => { localStorage.setItem('daena:governanceMode', mode); set({ governanceMode: mode }) },
  setRoutingMode: (mode) => { localStorage.setItem('daena:routingMode', mode); set({ routingMode: mode }) },
  toggleDarkMode: () => set((s) => {
    const next = !s.darkMode
    localStorage.setItem('daena:darkMode', String(next))
    const html = document.documentElement
    if (next) {
      html.classList.remove('light')
      html.style.colorScheme = 'dark'
    } else {
      html.classList.add('light')
      html.style.colorScheme = 'light'
    }
    return { darkMode: next }
  }),
  toggleThinking: () => set((s) => {
    const next = !s.thinkingVisible
    localStorage.setItem('daena:thinkingVisible', String(next))
    return { thinkingVisible: next }
  }),
  togglePersistThinking: () => set((s) => { const next = !s.persistThinking; localStorage.setItem('daena:persistThinking', String(next)); return { persistThinking: next } }),
  toggleConversational: () => set((s) => ({ conversationalMode: !s.conversationalMode })),
  toggleSpeech: () => set((s) => ({ speechEnabled: !s.speechEnabled })),
  setVoiceListening: (listening) => set({ voiceListening: listening }),
  setVolume: (v) => set({ volume: Math.max(0, Math.min(1, v)) }),
  toggleAutopilot: () => set((s) => { const next = !s.autopilotActive; localStorage.setItem('daena:autopilotActive', String(next)); return { autopilotActive: next } }),
  toggleLocalFirstRouting: () => set((s) => ({ localFirstRouting: !s.localFirstRouting })),
  toggleCostAwareRouting: () => set((s) => ({ costAwareRouting: !s.costAwareRouting })),
  toggleDaenaBot: () => set((s) => ({ daenaBotEnabled: !s.daenaBotEnabled })),
  toggleScreenshotCapture: () => set((s) => ({ screenshotCapture: !s.screenshotCapture })),
  toggleDebugMode: () => set((s) => ({ debugMode: !s.debugMode })),
  toggleVerboseLogging: () => set((s) => ({ verboseLogging: !s.verboseLogging })),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setSelectedRuntime: (runtime) => set({ selectedRuntime: runtime }),
  toggleExecutionView: () => set((s) => {
    const next = !s.executionViewVisible
    localStorage.setItem('daena:executionView', String(next))
    return { executionViewVisible: next }
  }),
  setAutoReadResponses: (enabled) => set({ autoReadResponses: enabled }),

  setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),
  toggleMobileSidebar: () => set((s) => ({ mobileSidebarOpen: !s.mobileSidebarOpen })),

  // Interactive prompts
  addPrompt: (prompt) =>
    set((s) => {
      if (s.activePrompt) {
        // Queue if one is already showing
        return { promptQueue: [...s.promptQueue, prompt] }
      }
      return { activePrompt: prompt }
    }),
  dismissPrompt: () =>
    set((s) => {
      const [next, ...rest] = s.promptQueue
      return { activePrompt: next || null, promptQueue: rest }
    }),

  addNotification: (n) =>
    set((s) => ({
      notifications: [
        ...s.notifications,
        { ...n, id: crypto.randomUUID(), timestamp: Date.now() },
      ],
    })),
  removeNotification: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
  clearNotifications: () => set({ notifications: [] }),
}))

// Apply dark/light mode class on initial load based on localStorage
if (typeof window !== 'undefined') {
  const isDark = localStorage.getItem('daena:darkMode') !== 'false'
  const html = document.documentElement
  if (!isDark) {
    html.classList.add('light')
    html.style.colorScheme = 'light'
  } else {
    html.classList.remove('light')
    html.style.colorScheme = 'dark'
  }
  // Expose store on window for wake word listener (non-React code)
  ;(window as unknown as Record<string, unknown>).__daenaUiStore = useUiStore
}

// ── Settings persistence helpers ──

let _persistTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Hydrate Zustand store from backend user preferences.
 * Call once on app load after auth is confirmed.
 */
export async function hydrateUiFromBackend(): Promise<void> {
  try {
    const { api } = await import('@/lib/api')
    const res = await api.get('/settings/user')
    const data = res.data?.data
    if (!data) return
    const store = useUiStore.getState()
    const updates: Partial<Record<string, unknown>> = {}
    if (data.dark_mode != null) {
      updates.darkMode = data.dark_mode
      const html = document.documentElement
      if (data.dark_mode) {
        html.classList.remove('light')
        html.style.colorScheme = 'dark'
      } else {
        html.classList.add('light')
        html.style.colorScheme = 'light'
      }
    }
    // Never hydrate conversationalMode or voiceListening from backend:
    // SpeechRecognition cannot auto-start without a user gesture.
    // Voice must always start OFF and require a click to activate.
    if (data.sidebar_collapsed != null) updates.sidebarOpen = !data.sidebar_collapsed
    if (data.default_chat_mode) { updates.chatMode = data.default_chat_mode; localStorage.setItem('daena:chatMode', data.default_chat_mode) }
    if (data.default_routing_mode) { updates.routingMode = data.default_routing_mode; localStorage.setItem('daena:routingMode', data.default_routing_mode) }
    if (data.default_governance_mode) { updates.governanceMode = data.default_governance_mode; localStorage.setItem('daena:governanceMode', data.default_governance_mode) }
    if (data.local_first_routing != null) updates.localFirstRouting = data.local_first_routing
    if (data.cost_aware_routing != null) updates.costAwareRouting = data.cost_aware_routing
    if (data.debug_mode != null) updates.debugMode = data.debug_mode
    if (data.verbose_logging != null) updates.verboseLogging = data.verbose_logging
    if (data.autopilot_active != null) { updates.autopilotActive = data.autopilot_active; localStorage.setItem('daena:autopilotActive', String(data.autopilot_active)) }
    if (data.persist_thinking != null) { updates.persistThinking = data.persist_thinking; localStorage.setItem('daena:persistThinking', String(data.persist_thinking)) }
    // conversationalMode excluded: see comment above
    if (data.auto_read_responses != null) updates.autoReadResponses = data.auto_read_responses
    if (data.default_runtime && data.default_runtime !== 'auto') updates.selectedRuntime = data.default_runtime
    useUiStore.setState(updates as Partial<typeof store>)
  } catch {
    // Non-critical -- use defaults
  }
}

/**
 * Debounced persist of a single UI preference to the backend.
 * Batches rapid changes into one PUT request after 500ms.
 */
export function persistUiPref(key: string, value: unknown): void {
  if (_persistTimer) clearTimeout(_persistTimer)
  _persistTimer = setTimeout(async () => {
    try {
      const { api } = await import('@/lib/api')
      await api.put('/settings/user', { [key]: value })
    } catch {
      // Non-critical
    }
  }, 500)
}

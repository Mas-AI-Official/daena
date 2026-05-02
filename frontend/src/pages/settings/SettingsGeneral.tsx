/**
 * General settings -- session defaults, appearance, data import.
 *
 * Profile editing (display name, password, OAuth, avatar) lives at
 * /account (canonical). PR-SETTINGS-CLEANUP (2026-05-02) removed the
 * inline display_name editor + Save button from this tab to eliminate
 * the dual-source-of-truth (Atlas F.2) and replaced it with a
 * read-only summary that links to /account. Reason: an editor that
 * lives in two places makes operators uncertain which one is the
 * canonical write site, and a duplicated PUT /settings/user call site
 * is one more thing to keep in sync when the schema changes.
 */
import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Download, ChevronRight, User as UserIcon } from 'lucide-react'
import { Card, Badge, Switch } from '@/components/common'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore, persistUiPref } from '@/stores/uiStore'
import { useBackendHealthStore } from '@/stores/backendHealthStore'
import { toast } from '@/stores/toastStore'
import api from '@/lib/api'

export function SettingsGeneral() {
  const { user } = useAuthStore()
  const { chatMode, setChatMode, routingMode, setRoutingMode, persistThinking, togglePersistThinking, darkMode, toggleDarkMode, autopilotActive, toggleAutopilot } = useUiStore()
  const backendHealthStatus = useBackendHealthStore((s) => s.status)
  const backendBlocksAutopilot = backendHealthStatus === 'down' || backendHealthStatus === 'degraded'
  const [importData, setImportData] = useState('')

  const handleDarkModeToggle = useCallback((_checked: boolean) => {
    toggleDarkMode()
    // After toggle, persist the NEW value
    persistUiPref('dark_mode', useUiStore.getState().darkMode)
  }, [toggleDarkMode])

  const handleChatModeChange = (mode: 'CMD' | 'EXE') => {
    setChatMode(mode)
    persistUiPref('default_chat_mode', mode)
  }

  const handleRoutingChange = (mode: 'STANDARD' | 'QUINTESSENCE') => {
    setRoutingMode(mode)
    persistUiPref('default_routing_mode', mode)
  }

  return (
    <div className="space-y-6">
      {/* Profile (read-only summary; canonical editor lives at /account) */}
      <Card variant="glass" padding="lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-display font-semibold text-starlight-100">Profile</h3>
          <Link
            to="/account"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] text-primary-400 border border-primary-500/20 hover:bg-primary-500/10 transition-colors"
            title="Profile editing (display name, password, OAuth, avatar) lives at /account."
          >
            <UserIcon size={10} /> Manage in Account <ChevronRight size={10} />
          </Link>
        </div>
        <div className="space-y-3 max-w-md text-xs">
          <div className="flex items-center justify-between">
            <span className="text-starlight-500">Display name</span>
            <span className="text-starlight-200">{user?.display_name || '-'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-starlight-500">Email</span>
            <span className="text-starlight-200">{user?.email || '-'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-starlight-500">Role</span>
            <Badge variant="purple" size="sm">{user?.role || 'VIEWER'}</Badge>
          </div>
        </div>
      </Card>

      {/* Session Defaults */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4">Session Defaults</h3>
        <div className="space-y-3 max-w-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Default Chat Mode</p>
              <p className="text-xs text-starlight-500">CMD (no side effects) or EXE (tool execution)</p>
            </div>
            <div className="flex items-center gap-1 bg-midnight-400/50 rounded-lg p-0.5">
              {(['CMD', 'EXE'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => handleChatModeChange(mode)}
                  className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-all cursor-pointer ${
                    chatMode === mode
                      ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'text-starlight-400 hover:text-starlight-200'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Default Routing</p>
              <p className="text-xs text-starlight-500">Standard, Council, or Quintessence</p>
            </div>
            <div className="flex items-center gap-1 bg-midnight-400/50 rounded-lg p-0.5">
              {(['STANDARD', 'QUINTESSENCE'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => handleRoutingChange(mode)}
                  className={`px-2 py-1 rounded-md text-[10px] font-medium transition-all cursor-pointer ${
                    routingMode === mode
                      ? mode === 'QUINTESSENCE'
                        ? 'bg-accent-purple/20 text-accent-purple border border-accent-purple/30'
                        : 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'text-starlight-400 hover:text-starlight-200'
                  }`}
                >
                  {mode === 'QUINTESSENCE' ? 'QE' : 'STD'}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Persist Thinking Process</p>
              <p className="text-xs text-starlight-500">Keep the reasoning steps visible after response delivery (expandable)</p>
            </div>
            <Switch checked={persistThinking} onChange={() => { togglePersistThinking(); persistUiPref('persist_thinking', !persistThinking) }} label="" size="sm" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">AGI Mode (Autopilot)</p>
              <p className="text-xs text-starlight-500">
                When ON, Daena auto-approves non-critical actions. Quintessence + Skills + Expert DCPs orchestrate autonomously.
                Only Hard Law violations pause for approval.
              </p>
            </div>
            <Switch
              checked={!backendBlocksAutopilot && autopilotActive}
              onChange={() => {
                if (backendBlocksAutopilot) return
                toggleAutopilot()
                persistUiPref('autopilot_active', !autopilotActive)
              }}
              label=""
              size="sm"
              disabled={backendBlocksAutopilot}
            />
          </div>
          {backendBlocksAutopilot && (
            <div className="rounded-lg border border-status-error/20 bg-status-error/5 px-3 py-2 text-xs text-starlight-300">
              Autopilot is blocked while backend health is failing.
            </div>
          )}
        </div>
      </Card>

      {/* Appearance */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4">Appearance</h3>
        <div className="space-y-4 max-w-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Dark Mode</p>
              <p className="text-xs text-starlight-500">Daena is designed dark-first. Light mode is experimental.</p>
            </div>
            <Switch checked={darkMode} onChange={handleDarkModeToggle} label="" size="sm" />

          </div>
        </div>
      </Card>

      {/* Import Your Data */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-2 flex items-center gap-2">
          <Download size={14} /> Import Your Data
        </h3>
        <p className="text-xs text-starlight-400 mb-4">
          Bring your context from other AI assistants. Copy the prompt below, paste it into your previous provider, and import the response here.
        </p>

        {/* Step 1: Copy the extraction prompt */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-starlight-300">
            <span className="w-5 h-5 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center text-[10px] font-bold">1</span>
            Copy this prompt and paste it into ChatGPT, Gemini, or your previous AI assistant:
          </div>
          <div className="relative">
            <pre className="text-[10px] text-starlight-300 bg-midnight-900/60 border border-white/10 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">
{`Please provide a comprehensive summary of everything you know about me from our conversations. Include:

1. **Personal Profile**: My name, role, company, location, and professional background
2. **Work Context**: Projects I'm working on, technologies I use, my team structure
3. **Preferences**: How I like to communicate, coding style preferences, tools I prefer
4. **Goals & Priorities**: What I'm trying to achieve, current focus areas, deadlines
5. **Key Decisions**: Important decisions I've made, architectural choices, business strategies
6. **Recurring Topics**: Subjects I frequently discuss, ongoing concerns, areas of expertise
7. **Communication Style**: How formal/informal I am, preferred response length, do I like explanations or just answers

Format this as a structured document I can import into a new AI assistant. Be thorough -- include everything you remember about my preferences, work patterns, and context. This helps me avoid re-explaining everything.`}
            </pre>
            <button
              onClick={() => {
                const prompt = `Please provide a comprehensive summary of everything you know about me from our conversations. Include:\n\n1. **Personal Profile**: My name, role, company, location, and professional background\n2. **Work Context**: Projects I'm working on, technologies I use, my team structure\n3. **Preferences**: How I like to communicate, coding style preferences, tools I prefer\n4. **Goals & Priorities**: What I'm trying to achieve, current focus areas, deadlines\n5. **Key Decisions**: Important decisions I've made, architectural choices, business strategies\n6. **Recurring Topics**: Subjects I frequently discuss, ongoing concerns, areas of expertise\n7. **Communication Style**: How formal/informal I am, preferred response length, do I like explanations or just answers\n\nFormat this as a structured document I can import into a new AI assistant. Be thorough -- include everything you remember about my preferences, work patterns, and context. This helps me avoid re-explaining everything.`
                navigator.clipboard.writeText(prompt)
                toast.success('Extraction prompt copied to clipboard!')
              }}
              className="absolute top-2 right-2 px-2 py-1 rounded-lg text-[10px] bg-primary-500/20 text-primary-400 hover:bg-primary-500/30 cursor-pointer border border-primary-500/20"
            >
              Copy Prompt
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs text-starlight-300 mt-4">
            <span className="w-5 h-5 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center text-[10px] font-bold">2</span>
            Paste the response here or upload as a file:
          </div>
          <textarea
            placeholder="Paste the response from your previous AI assistant here..."
            className="w-full glass-input px-4 py-3 rounded-xl text-xs text-starlight-200 placeholder:text-starlight-500 min-h-[100px] resize-y"
            onChange={(e) => setImportData(e.target.value)}
            value={importData}
          />
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const input = document.createElement('input')
                input.type = 'file'
                input.accept = '.txt,.md,.json'
                input.onchange = async (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0]
                  if (!file) return
                  const text = await file.text()
                  setImportData(text)
                  toast.success(`Loaded ${file.name}`)
                }
                input.click()
              }}
              className="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 border border-white/10 hover:bg-white/10 cursor-pointer"
            >
              Upload File
            </button>
            <button
              onClick={async () => {
                if (!importData.trim()) return
                try {
                  await api.post('/memory/memories', {
                    content: importData,
                    content_type: 'FACT',
                    tier: 2,
                    scope: 'USER',
                    confidence: 0.8,
                    tags: ['imported', 'user-context', 'migration'],
                    source: 'user_import',
                  })
                  toast.success('Your data has been imported into Daena memory!')
                  setImportData('')
                } catch {
                  toast.error('Import failed. Please try again.')
                }
              }}
              disabled={!importData.trim()}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-500/20 text-primary-400 border border-primary-500/20 hover:bg-primary-500/30 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Import to Daena
            </button>
          </div>
        </div>
      </Card>

      {/* Voice settings moved to dedicated Voice tab */}
    </div>
  )
}

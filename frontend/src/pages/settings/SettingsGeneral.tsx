/**
 * General settings -- profile, session defaults, appearance (dark/light).
 */
import { useState, useEffect, useCallback } from 'react'
import { Card, Input, Button, Badge, Switch } from '@/components/common'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore, persistUiPref } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'
import api from '@/lib/api'

export function SettingsGeneral() {
  const { user } = useAuthStore()
  const { chatMode, setChatMode, routingMode, setRoutingMode, persistThinking, togglePersistThinking, darkMode, toggleDarkMode, autopilotActive, toggleAutopilot } = useUiStore()
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [saving, setSaving] = useState(false)

  const handleDarkModeToggle = useCallback((_checked: boolean) => {
    toggleDarkMode()
    // After toggle, persist the NEW value
    persistUiPref('dark_mode', useUiStore.getState().darkMode)
  }, [toggleDarkMode])

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const res = await api.get('/settings/user')
        const name = res.data?.data?.display_name
        if (name) setDisplayName(name)
      } catch (err) {
        console.error('Profile load failed, using auth store value:', err)
      }
    }
    loadProfile()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/settings/user', { display_name: displayName })
      toast.success('Display name updated')
    } catch {
      toast.error('Failed to save display name')
    } finally {
      setSaving(false)
    }
  }

  const handleChatModeChange = (mode: 'CMD' | 'EXE') => {
    setChatMode(mode)
    persistUiPref('default_chat_mode', mode)
  }

  const handleRoutingChange = (mode: 'STANDARD' | 'COUNCIL' | 'QUINTESSENCE') => {
    setRoutingMode(mode)
    persistUiPref('default_routing_mode', mode)
  }

  return (
    <div className="space-y-6">
      {/* Profile */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4">Profile</h3>
        <div className="space-y-4 max-w-md">
          <Input
            label="Display Name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
          <div>
            <label className="block text-xs text-starlight-400 mb-1">Email</label>
            <p className="text-sm text-starlight-200">{user?.email || '--'}</p>
          </div>
          <div>
            <label className="block text-xs text-starlight-400 mb-1">Role</label>
            <Badge variant="purple" size="sm">{user?.role || 'VIEWER'}</Badge>
          </div>
          <Button variant="primary" size="sm" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
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
              {(['STANDARD', 'COUNCIL', 'QUINTESSENCE'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => handleRoutingChange(mode)}
                  className={`px-2 py-1 rounded-md text-[10px] font-medium transition-all cursor-pointer ${
                    routingMode === mode
                      ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'text-starlight-400 hover:text-starlight-200'
                  }`}
                >
                  {mode === 'QUINTESSENCE' ? 'QE' : mode.slice(0, 3)}
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
              checked={autopilotActive}
              onChange={() => { toggleAutopilot(); persistUiPref('autopilot_active', !autopilotActive) }}
              label=""
              size="sm"
            />
          </div>
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

      {/* Voice settings moved to dedicated Voice tab */}
    </div>
  )
}

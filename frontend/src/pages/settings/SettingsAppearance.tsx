/**
 * Appearance settings — theme, font size, accent color, sidebar behavior.
 */
import { useState, useEffect } from 'react'
import { Card, Switch } from '@/components/common'
import { useUiStore, persistUiPref } from '@/stores/uiStore'
import { Moon, Sun, Type, Sidebar as SidebarIcon, Palette } from 'lucide-react'

const ACCENT_COLORS = [
  { name: 'Cosmos Blue', value: '#0070F3' },
  { name: 'Violet', value: '#8B5CF6' },
  { name: 'Emerald', value: '#10B981' },
  { name: 'Amber', value: '#F59E0B' },
  { name: 'Rose', value: '#F43F5E' },
]

export function SettingsAppearance() {
  const { sidebarOpen, toggleSidebar, darkMode, toggleDarkMode } = useUiStore()
  const [fontSize, setFontSize] = useState(() => localStorage.getItem('daena-font-size') || 'md')

  useEffect(() => {
    localStorage.setItem('daena-font-size', fontSize)
  }, [fontSize])

  const handleThemeToggle = (_checked: boolean) => {
    toggleDarkMode()
    persistUiPref('dark_mode', useUiStore.getState().darkMode)
  }

  return (
    <div className="space-y-6">
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          {darkMode ? <Moon size={14} /> : <Sun size={14} />} Theme
        </h3>
        <div className="space-y-3 max-w-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Dark Mode</p>
              <p className="text-xs text-starlight-500">{darkMode ? 'Dark theme active' : 'Light theme active'}</p>
            </div>
            <Switch checked={darkMode} onChange={handleThemeToggle} label="" size="sm" />
          </div>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Palette size={14} /> Accent Color
        </h3>
        <div className="flex gap-3">
          {ACCENT_COLORS.map((c) => (
            <button
              key={c.value}
              title={c.name}
              className="w-8 h-8 rounded-full border-2 transition-all hover:scale-110 cursor-pointer"
              style={{
                backgroundColor: c.value,
                borderColor: c.value === '#0070F3' ? 'white' : 'transparent',
              }}
            />
          ))}
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Type size={14} /> Typography
        </h3>
        <div className="space-y-3 max-w-md">
          <div className="flex items-center justify-between">
            <p className="text-sm text-starlight-200">Font Size</p>
            <select
              value={fontSize}
              onChange={(e) => setFontSize(e.target.value)}
              className="glass-input px-2 py-1 rounded text-xs text-starlight-200 bg-midnight-400/50 border border-white/10 cursor-pointer"
            >
              <option value="sm">Small</option>
              <option value="md">Medium</option>
              <option value="lg">Large</option>
            </select>
          </div>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <SidebarIcon size={14} /> Layout
        </h3>
        <div className="space-y-3 max-w-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Collapsed Sidebar</p>
              <p className="text-xs text-starlight-500">Narrow sidebar by default</p>
            </div>
            <Switch
              checked={!sidebarOpen}
              onChange={() => { toggleSidebar(); persistUiPref('sidebar_collapsed', sidebarOpen) }}
              label=""
              size="sm"
            />
          </div>
        </div>
      </Card>
    </div>
  )
}

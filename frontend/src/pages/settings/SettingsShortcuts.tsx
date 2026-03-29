/**
 * SettingsShortcuts -- Keyboard shortcuts reference tab.
 */
import { Keyboard } from 'lucide-react'
import { Card } from '@/components/common'

const SHORTCUT_GROUPS = [
  {
    title: 'Global',
    shortcuts: [
      { keys: 'Ctrl+K', action: 'Command palette' },
      { keys: 'Ctrl+N', action: 'New chat' },
      { keys: '/', action: 'Slash commands (in chat)' },
      { keys: 'Ctrl+Shift+E', action: 'Toggle Execute mode' },
      { keys: 'Ctrl+,', action: 'Open settings' },
      { keys: 'Escape', action: 'Close modal/panel' },
    ],
  },
  {
    title: 'Chat',
    shortcuts: [
      { keys: 'Enter', action: 'Send message' },
      { keys: 'Shift+Enter', action: 'New line' },
      { keys: 'Ctrl+Shift+V', action: 'Paste as plain text' },
      { keys: 'Up arrow', action: 'Edit last message' },
    ],
  },
  {
    title: 'Navigation',
    shortcuts: [
      { keys: 'Ctrl+1', action: 'Go to Chat' },
      { keys: 'Ctrl+2', action: 'Go to Dashboard' },
      { keys: 'Ctrl+3', action: 'Go to Projects' },
      { keys: 'Ctrl+4', action: 'Go to Tasks' },
    ],
  },
]

function KeyBadge({ keys }: { keys: string }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {keys.split('+').map((key, i) => (
        <span key={i}>
          {i > 0 && <span className="text-starlight-600 mx-0.5">+</span>}
          <kbd className="px-1.5 py-0.5 rounded bg-midnight-700/80 border border-white/10 text-[10px] font-mono text-starlight-300">
            {key}
          </kbd>
        </span>
      ))}
    </span>
  )
}

export function SettingsShortcuts() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-display font-bold text-starlight-100">Keyboard Shortcuts</h2>
        <p className="text-xs text-starlight-400 mt-0.5">Navigate Daena without leaving the keyboard.</p>
      </div>

      {SHORTCUT_GROUPS.map((group) => (
        <section key={group.title} className="space-y-3">
          <h3 className="text-xs font-semibold text-starlight-300 uppercase tracking-wider flex items-center gap-1.5">
            <Keyboard size={12} className="text-starlight-500" />
            {group.title}
          </h3>
          <Card variant="glass" padding="none">
            {group.shortcuts.map((s, i) => (
              <div
                key={s.keys}
                className={`flex items-center justify-between px-4 py-2.5 ${
                  i < group.shortcuts.length - 1 ? 'border-b border-white/5' : ''
                }`}
              >
                <span className="text-xs text-starlight-300">{s.action}</span>
                <KeyBadge keys={s.keys} />
              </div>
            ))}
          </Card>
        </section>
      ))}

      <p className="text-xs text-starlight-500">
        Shortcuts are currently fixed defaults.
      </p>
    </div>
  )
}

export default SettingsShortcuts

/**
 * Voice settings -- browser-native TTS/STT configuration, ElevenLabs premium key.
 */
import { Card } from '@/components/common'

export function SettingsVoice() {
  return (
    <div className="space-y-6">
      {/* Browser Speech */}
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4">Voice</h3>
        <div className="space-y-4 max-w-md">
          <p className="text-xs text-starlight-400">
            Uses browser-native speech (free, no API key). For premium voices, add an ElevenLabs key below.
          </p>
          <div>
            <label className="block text-xs text-starlight-400 mb-1">ElevenLabs API Key (optional)</label>
            <input
              type="password"
              placeholder="sk_..."
              className="glass-input w-full px-3 py-2 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600"
              onChange={(e) => {
                const val = e.target.value.trim()
                if (val) localStorage.setItem('daena:elevenlabs_key', val)
                else localStorage.removeItem('daena:elevenlabs_key')
              }}
              defaultValue={localStorage.getItem('daena:elevenlabs_key') || ''}
            />
            <p className="text-[10px] text-starlight-500 mt-1">Stored locally. Never sent to Daena servers.</p>
          </div>
        </div>
      </Card>
    </div>
  )
}

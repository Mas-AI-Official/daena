/**
 * SettingsModelsRuntimes -- unified Models & Runtimes tab.
 * Merges: LLM settings + Connections/Runtimes into one place.
 *
 * Sections:
 * 1. Local Models (Ollama)
 * 2. CLI Runtimes (Claude Code, Codex, Gemini)
 * 3. API Keys (fallback)
 * 4. Auto Routing config
 */
import { useEffect, useState, useCallback } from 'react'
import { Terminal, Key, RefreshCw, Check, X, Loader2, Eye, EyeOff } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { Card, Badge } from '@/components/common'

interface RuntimeInfo {
  runtime_id: string
  display_name: string
  installed: boolean
  status: string
  subscription: { status: string; plan_name: string | null; is_authenticated: boolean } | null
}

const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic', envHint: 'ANTHROPIC_API_KEY' },
  { id: 'openai', label: 'OpenAI', envHint: 'OPENAI_API_KEY' },
  { id: 'google_gemini', label: 'Google Gemini', envHint: 'GEMINI_API_KEY' },
  { id: 'perplexity', label: 'Perplexity', envHint: 'PERPLEXITY_API_KEY' },
]

function ApiKeyRow({ provider }: { provider: typeof PROVIDERS[0] }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [showKey, setShowKey] = useState(false)

  const handleSave = async () => {
    if (!value.trim()) return
    setSaving(true)
    try {
      await api.post('/dynamic-models/provision', {
        provider_name: provider.id,
        api_key: value.trim(),
      })
      toast.success(`${provider.label} key saved and models discovered`)
      setSaved(true)
      setEditing(false)
      setValue('')
    } catch {
      toast.error(`Failed to provision ${provider.label}. Check your API key.`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <Key size={12} className="text-starlight-500" />
        <span className="text-xs text-starlight-300">{provider.label}</span>
        {saved && <Check size={10} className="text-accent-green" />}
      </div>
      {editing ? (
        <div className="flex items-center gap-1.5">
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="sk-..."
              autoFocus
              className="glass-input w-48 px-2 py-1 rounded text-xs text-starlight-200 placeholder:text-starlight-600 pr-7"
            />
            <button
              onClick={() => setShowKey(!showKey)}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-starlight-500 hover:text-starlight-300 cursor-pointer"
            >
              {showKey ? <EyeOff size={10} /> : <Eye size={10} />}
            </button>
          </div>
          <button
            onClick={handleSave}
            disabled={saving || !value.trim()}
            className="p-1 rounded bg-accent-green/10 text-accent-green hover:bg-accent-green/20 disabled:opacity-50 cursor-pointer"
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
          </button>
          <button
            onClick={() => { setEditing(false); setValue('') }}
            className="p-1 rounded bg-white/5 text-starlight-500 hover:bg-white/10 cursor-pointer"
          >
            <X size={12} />
          </button>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="text-[10px] text-primary-400 hover:text-primary-300 cursor-pointer"
        >
          {saved ? 'Change key' : 'Add key'}
        </button>
      )}
    </div>
  )
}

function ApiKeysSection() {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-display font-semibold text-starlight-100">API Keys</h3>
        <p className="text-xs text-starlight-400 mt-0.5">Optional fallback when CLI runtimes are unavailable.</p>
      </div>
      <Card variant="glass" padding="md" className="space-y-1">
        {PROVIDERS.map(p => <ApiKeyRow key={p.id} provider={p} />)}
      </Card>
    </section>
  )
}

export function SettingsModelsRuntimes() {
  const [runtimes, setRuntimes] = useState<RuntimeInfo[]>([])
  const [loading, setLoading] = useState(true)
  const fetchRuntimes = useCallback(async () => {
    try {
      const res = await api.get('/runtimes')
      if (res.data?.data?.runtimes) setRuntimes(res.data.data.runtimes)
    } catch { /* graceful */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchRuntimes() }, [fetchRuntimes])

  const ollamaRuntime = runtimes.find(r => r.runtime_id === 'ollama')

  // Fetch live model list from the chat model registry
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  useEffect(() => {
    api.get('/chat/model-registry').then(res => {
      const models = res.data?.data?.models ?? []
      setOllamaModels(
        models
          .filter((m: { provider: string }) => m.provider === 'OLLAMA')
          .map((m: { model_id: string }) => m.model_id)
      )
    }).catch(() => {})
  }, [])

  return (
    <div className="space-y-8">
      {/* Section 1: Local Models */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">Local Models (Ollama)</h3>
          <p className="text-xs text-starlight-400 mt-0.5">Free, private, runs on your machine. No API keys needed.</p>
        </div>
        <Card variant="glass" padding="md" className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal size={14} className="text-accent-green" />
              <span className="text-xs text-starlight-200">Ollama</span>
              {ollamaRuntime?.status === 'online' ? (
                <Badge variant="success" size="sm">Online</Badge>
              ) : (
                <Badge variant="default" size="sm">Offline</Badge>
              )}
            </div>
            <button onClick={fetchRuntimes} className="text-[10px] text-starlight-500 hover:text-starlight-300 flex items-center gap-1 cursor-pointer">
              <RefreshCw size={10} /> Refresh
            </button>
          </div>
          <p className="text-[10px] text-starlight-500">
            {ollamaModels.length > 0
              ? `${ollamaModels.length} models installed: ${ollamaModels.join(', ')}.`
              : 'Checking installed models...'
            }
          </p>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-xs text-starlight-300 cursor-pointer">
              <input type="checkbox" defaultChecked className="w-3.5 h-3.5 rounded border-white/20 bg-transparent text-primary-500" />
              Auto-update models weekly
            </label>
          </div>
        </Card>
      </section>

      {/* CLI Runtimes moved to Connections page (Runtimes tab) */}

      {/* Section 3: API Keys */}
      <ApiKeysSection />

      {/* Section 4: Auto Routing */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">Auto Routing</h3>
          <p className="text-xs text-starlight-400 mt-0.5">How Daena picks the best model for each task.</p>
        </div>
        <Card variant="glass" padding="md" className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-starlight-300">Cost optimization</span>
            <label className="relative w-10 h-5 cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-10 h-5 rounded-full bg-white/10 peer-checked:bg-accent-green/30 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-starlight-500 peer-checked:bg-accent-green peer-checked:translate-x-5 transition-all" />
            </label>
          </div>
          <p className="text-[10px] text-starlight-500">Route simple tasks to cheaper models automatically.</p>

          <div className="pt-2 border-t border-white/5">
            <span className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Fallback chain</span>
            <p className="text-xs text-starlight-400 mt-1">Claude Code &rarr; Codex &rarr; Gemini &rarr; Ollama &rarr; API keys</p>
          </div>
        </Card>
      </section>
    </div>
  )
}

export default SettingsModelsRuntimes

/**
 * SettingsModelsRuntimes -- the single Models & Runtimes tab.
 *
 * CONSOLIDATION 2026-06-18: this tab now is the unified surface its
 * name always promised. The former standalone "LLM Providers" Settings
 * tab (SettingsLLM) is composed in below rather than living as a second,
 * overlapping tab. SettingsLLM is reused as-is (not copied) so the
 * backend-enforced routing toggles (model_router PR-S3, 2026-06-01) keep
 * their exact wiring. The former in-tab API-key form (which posted to
 * /dynamic-models/provision with no health check and no never-echo) was
 * removed in favour of a pointer to the canonical, validate-before-persist
 * Account > Provider Keys surface.
 *
 * Sections:
 * 1. Local Models (Ollama) runtime status
 * 2. Providers, routing, and cost  (composed SettingsLLM)
 * 3. Provider API keys  (pointer to Account > Provider Keys)
 * 4. Fallback chain
 */
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Terminal, Key, RefreshCw, AlertTriangle, ArrowRight } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, Badge } from '@/components/common'
import { BrainReadinessPanel } from '@/components/common/BrainReadinessPanel'
import { MorningReadinessPanel } from '@/components/common/MorningReadinessPanel'
import { SettingsLLM } from './SettingsLLM'

interface RuntimeInfo {
  runtime_id: string
  display_name: string
  installed: boolean
  status: string
  subscription: { status: string; plan_name: string | null; is_authenticated: boolean } | null
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
      {/* Sprint-12A PR-4: brain readiness panel.
          Honest snapshot of which brain Daena will use right now.
          Read-only; no paid call fires from here. */}
      <BrainReadinessPanel />

      {/* Sprint-MORNING PR-4: ecosystem readiness panel.
          Single read-only call to /system/morning-readiness covering
          CLIs, local LLMs, API keys, and detected MCPs. */}
      <MorningReadinessPanel />

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
          <div className="flex items-start gap-2 rounded-md border border-accent-amber/20 bg-accent-amber/5 px-3 py-2">
            <AlertTriangle size={13} className="mt-0.5 shrink-0 text-accent-amber" />
            <p className="text-[10px] text-starlight-400">
              Model auto-update is not wired to a backend scheduler in this build, so the previous checkbox was removed from the active control path.
            </p>
          </div>
        </Card>
      </section>

      {/* CLI Runtimes moved to Connections page (Runtimes tab) */}

      {/* Section 2: Providers, routing, and cost.
          CONSOLIDATION 2026-06-18: composed from the former standalone
          "LLM Providers" tab. Reused as-is so the backend-enforced
          local-first / cost-aware routing toggles keep their exact
          model_router PR-S3 wiring. This is what folds two overlapping
          Settings tabs into this one Models & Runtimes surface. */}
      <SettingsLLM />

      {/* Section 3: Provider API keys.
          Rule-2 de-duplication 2026-06-18: the canonical key-entry surface
          is Account > Provider Keys (POST /account/provider-keys --
          validate-before-persist via a provider health check, never echoes
          a saved value, 7 providers). The inferior in-tab form removed from
          here posted to the older /dynamic-models/provision with no health
          check and only 4 hardcoded providers; its code is preserved in git
          history. We point at the canonical surface rather than duplicate it. */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">API Keys</h3>
          <p className="text-xs text-starlight-400 mt-0.5">Upstream provider keys are entered and rotated on the Account page.</p>
        </div>
        <Card variant="glass" padding="md">
          <Link
            to="/account#provider-keys"
            className="flex items-center justify-between gap-3 group cursor-pointer"
          >
            <div className="flex items-center gap-3">
              <Key size={16} className="shrink-0 text-starlight-500 group-hover:text-primary-400" />
              <div>
                <p className="text-xs text-starlight-200 group-hover:text-starlight-100">Provider Keys</p>
                <p className="text-[10px] text-starlight-500">
                  Add or rotate Anthropic, OpenAI, Gemini and more. Keys are health-checked before they are saved and never echoed back.
                </p>
              </div>
            </div>
            <ArrowRight size={14} className="shrink-0 text-starlight-500 group-hover:text-primary-400" />
          </Link>
        </Card>
      </section>

      {/* Section 4: Fallback chain.
          The routing toggles now live in the composed providers section
          above and ARE enforced (model_router PR-S3 honors them); the prior
          "frontend-only / not yet verified" note here was stale and was
          removed. */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">Fallback chain</h3>
          <p className="text-xs text-starlight-400 mt-0.5">Order Daena tries runtimes when the preferred provider is unavailable.</p>
        </div>
        <Card variant="glass" padding="md">
          <p className="text-xs text-starlight-400">Claude Code &rarr; Codex &rarr; Gemini &rarr; Ollama &rarr; API keys</p>
        </Card>
      </section>
    </div>
  )
}

export default SettingsModelsRuntimes

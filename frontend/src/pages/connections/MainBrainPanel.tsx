import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ComponentType } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Crown,
  Globe,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Terminal,
  Zap,
} from 'lucide-react'

import {
  AnthropicIcon,
  GoogleGeminiIcon,
  OllamaIcon,
  OpenAIIcon,
  RUNTIME_ICONS,
} from '@/components/icons/BrandIcons'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'
import type { RuntimeData } from './types'

interface ApiProvider {
  provider: string
  status: string
  display_name: string
  model_count?: number
  last_error_at?: number
  last_error_msg?: string
}

interface RuntimesPayload {
  success: boolean
  data: {
    runtimes: RuntimeData[]
    primary_runtime?: string | null
    warming?: boolean
    cloud_mode?: boolean
    api_providers?: ApiProvider[]
  }
}

const PROVIDER_ICON: Record<string, ComponentType<{ size?: number; className?: string }>> = {
  ANTHROPIC: AnthropicIcon,
  OPENAI: OpenAIIcon,
  GEMINI: GoogleGeminiIcon,
  OLLAMA: OllamaIcon,
}

function providerId(provider: string) {
  return provider.trim().toUpperCase()
}

function providerLabel(provider: ApiProvider) {
  return provider.display_name || provider.provider
}

function isRuntimeUsable(runtime: RuntimeData) {
  return runtime.installed && runtime.status === 'online' && (runtime.subscription?.is_authenticated ?? true)
}

function statusTone(status: string, ok: boolean) {
  if (ok) return 'border-status-success/25 bg-status-success/5 text-status-success'
  if (status === 'degraded') return 'border-accent-amber/25 bg-accent-amber/5 text-accent-amber'
  return 'border-status-error/25 bg-status-error/5 text-status-error'
}

function formatError(provider: ApiProvider) {
  if (!provider.last_error_msg) return ''
  if (!provider.last_error_at) return provider.last_error_msg
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - provider.last_error_at))
  return `${provider.last_error_msg} (${seconds < 60 ? `${seconds}s` : `${Math.round(seconds / 60)}m`} ago)`
}

export default function MainBrainPanel() {
  const [runtimes, setRuntimes] = useState<RuntimeData[]>([])
  const [providers, setProviders] = useState<ApiProvider[]>([])
  const [primary, setPrimary] = useState<string>('claude_code')
  const [warming, setWarming] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [experimentalOverride, setExperimentalOverride] = useState(false)

  // Phase 5 PR 2: V2 truth -- only callable=true CLI runtimes can be
  // pinned as Main Brain when USE_CONNECTION_REGISTRY_V2 is on (unless
  // founder opts in to experimentalOverride). Index by slug so the row
  // renderer can look up the V2 truth quickly.
  const { rows: v2Rows } = useConnectionsV2('cli_runtime')
  const v2BySlug = useMemo(() => {
    const out: Record<string, (typeof v2Rows)[number]> = {}
    for (const r of v2Rows) out[r.slug] = r
    return out
  }, [v2Rows])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get<RuntimesPayload>('/runtimes', { silent: false })
      const data = res.data?.data
      setRuntimes(Array.isArray(data?.runtimes) ? data.runtimes : [])
      setProviders(Array.isArray(data?.api_providers) ? data.api_providers : [])
      setPrimary(data?.primary_runtime || 'claude_code')
      setWarming(Boolean(data?.warming))
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Runtime registry unavailable'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const currentName = useMemo(() => {
    const runtime = runtimes.find((r) => r.runtime_id === primary)
    if (runtime) return runtime.display_name
    const provider = providers.find((p) => providerId(p.provider) === primary)
    if (provider) return providerLabel(provider)
    return primary
  }, [primary, providers, runtimes])

  async function choose(id: string, name: string) {
    setBusy(id)
    try {
      const res = await api.put(
        '/runtimes/primary',
        { runtime_id: id, experimental_override: experimentalOverride },
        { silent: false },
      )
      if (res.data?.success === false) {
        const msg = res.data?.error?.message || 'Main Brain update rejected'
        const code = res.data?.error?.code
        if (code === 'runtime_not_callable') {
          toast.error(
            `${name} is not callable. Run a probe first or enable Experimental Override.`,
          )
        } else {
          toast.error(msg)
        }
        return
      }
      setPrimary(res.data?.data?.primary_runtime || id)
      const overrode = res.data?.data?.experimental_override_used
      toast.success(
        overrode
          ? `${name} pinned as Main Brain (experimental override -- audit logged)`
          : `${name} is now Main Brain`,
      )
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to set Main Brain')
    } finally {
      setBusy(null)
    }
  }

  async function testRuntime(runtime: RuntimeData) {
    setBusy(`test:${runtime.runtime_id}`)
    try {
      const res = await api.post(`/runtimes/${runtime.runtime_id}/test`, {}, { silent: false })
      const payload = res.data?.data
      if (payload?.test_passed) toast.success(`${runtime.display_name} test passed`)
      else toast.error(payload?.summary || `${runtime.display_name} test failed`)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Runtime test failed')
    } finally {
      setBusy(null)
    }
  }

  if (loading && runtimes.length === 0 && providers.length === 0) {
    return (
      <div className="rounded-lg border border-white/5 bg-midnight-400/30 px-4 py-6 text-sm text-starlight-400">
        <Loader2 size={16} className="mr-2 inline animate-spin" />
        Loading Main Brain registry...
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-accent-amber/20 bg-accent-amber/5 px-4 py-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-accent-amber">
              <Crown size={14} />
              Main Brain
            </div>
            <div className="mt-1 text-lg font-semibold text-starlight-100">{currentName}</div>
            <p className="mt-1 text-xs text-starlight-500">
              Saved as <span className="font-mono text-starlight-300">{primary}</span>
            </p>
          </div>
          <button
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-starlight-200 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
        {warming && (
          <div className="mt-3 rounded-md border border-accent-cyan/20 bg-accent-cyan/5 px-3 py-2 text-xs text-accent-cyan">
            Runtime discovery is still warming. This page is showing the latest cached registry state.
          </div>
        )}
        {error && (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-status-error/25 bg-status-error/5 px-3 py-2 text-xs text-status-error">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            {error}
          </div>
        )}
      </div>

      <section className="space-y-2">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-starlight-100">CLI and local runtimes</h2>
            <p className="text-[11px] text-starlight-500">
              When V2 is on, only runtimes whose last probe proved callable=true
              can be set as Main Brain. Use Experimental Override to pin one
              that hasn't been probed yet (audit-logged).
            </p>
          </div>
          <label className="inline-flex items-center gap-2 text-[11px] text-starlight-300">
            <input
              type="checkbox"
              checked={experimentalOverride}
              onChange={(e) => setExperimentalOverride(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-white/20 bg-white/5"
            />
            Experimental Override
          </label>
        </div>
        <div className="divide-y divide-white/5 rounded-lg border border-white/5 bg-midnight-400/20">
          {runtimes.map((runtime) => {
            const Icon = RUNTIME_ICONS[runtime.runtime_id] || Terminal
            const usable = isRuntimeUsable(runtime)
            const isPrimary = primary === runtime.runtime_id
            const v2 = v2BySlug[runtime.runtime_id]
            const v2Callable = v2?.truth?.callable?.value === true
            const v2Failure =
              v2?.truth?.callable?.failure_reason ||
              v2?.truth?.authenticated?.failure_reason ||
              v2?.truth?.reachable?.failure_reason
            const v2LastProbe = v2?.truth?.callable?.at || v2?.truth?.reachable?.at
            // Disable rule: if V2 has the row AND callable=false AND
            // the operator hasn't toggled the override, the button is
            // visibly blocked. Backend gate is the source of truth;
            // this is just UX.
            const v2Blocked = !!v2 && !v2Callable && !experimentalOverride
            return (
              <div key={runtime.runtime_id} className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-white/5">
                  <Icon size={22} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-starlight-100">{runtime.display_name}</span>
                    {isPrimary && <span className="rounded-md bg-accent-amber/10 px-2 py-0.5 text-[10px] text-accent-amber">Main Brain</span>}
                    <span className={`rounded-md border px-2 py-0.5 text-[10px] ${statusTone(runtime.status, usable)}`}>
                      {usable ? 'Ready' : runtime.installed ? 'Needs auth/check' : 'Not installed'}
                    </span>
                    {v2 && (
                      <span
                        className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] ${
                          v2Callable
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                        }`}
                        title={
                          v2Callable
                            ? `V2 last proved callable at ${v2.truth.callable.at}`
                            : 'V2 has not proved callable yet'
                        }
                      >
                        <ShieldCheck size={10} />
                        V2 {v2Callable ? 'callable' : 'not callable'}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-starlight-500">
                    {runtime.subscription?.user_display || runtime.subscription?.plan_name || runtime.status || 'Unknown status'}
                  </div>
                  {v2 && v2Failure && !v2Callable && (
                    <div className="mt-1 text-xs text-rose-300">
                      V2 failure: {v2Failure}
                    </div>
                  )}
                  {v2 && v2LastProbe && (
                    <div className="mt-0.5 text-[10px] text-starlight-500">
                      V2 last probe: {new Date(v2LastProbe).toLocaleString()}
                    </div>
                  )}
                  {!v2 && (
                    <div className="mt-1 text-[10px] text-starlight-500">
                      No V2 row yet — selection allowed (legacy probe path)
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  <button
                    onClick={() => void testRuntime(runtime)}
                    disabled={!runtime.installed || busy === `test:${runtime.runtime_id}`}
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-200 hover:bg-white/10 disabled:opacity-40"
                  >
                    {busy === `test:${runtime.runtime_id}` ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                    Test
                  </button>
                  <button
                    onClick={() => void choose(runtime.runtime_id, runtime.display_name)}
                    disabled={!usable || isPrimary || busy === runtime.runtime_id || v2Blocked}
                    title={v2Blocked ? 'V2 says not callable. Probe first or enable Experimental Override.' : undefined}
                    className="inline-flex items-center gap-1.5 rounded-md border border-accent-amber/30 bg-accent-amber/10 px-3 py-1.5 text-xs text-accent-amber hover:bg-accent-amber/20 disabled:opacity-40"
                  >
                    {busy === runtime.runtime_id ? <Loader2 size={13} className="animate-spin" /> : <Crown size={13} />}
                    Set Main Brain
                  </button>
                </div>
              </div>
            )
          })}
          {runtimes.length === 0 && (
            <div className="px-4 py-6 text-sm text-starlight-500">No CLI or local runtimes detected.</div>
          )}
        </div>
      </section>

      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold text-starlight-100">Configured API providers</h2>
          <p className="text-[11px] text-starlight-500">Provider keys are still managed in Settings. This list only chooses routing priority.</p>
        </div>
        <div className="divide-y divide-white/5 rounded-lg border border-white/5 bg-midnight-400/20">
          {providers.map((provider) => {
            const id = providerId(provider.provider)
            const Icon = PROVIDER_ICON[id] || Globe
            const ok = provider.status === 'connected'
            const isPrimary = primary === id
            return (
              <div key={id} className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-white/5">
                  <Icon size={22} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-starlight-100">{providerLabel(provider)}</span>
                    {isPrimary && <span className="rounded-md bg-accent-amber/10 px-2 py-0.5 text-[10px] text-accent-amber">Main Brain</span>}
                    <span className={`rounded-md border px-2 py-0.5 text-[10px] ${statusTone(provider.status, ok)}`}>
                      {ok ? 'Configured' : 'Degraded'}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-starlight-500">
                    {formatError(provider) || `${provider.model_count ?? 0} models discovered`}
                  </div>
                </div>
                <button
                  onClick={() => void choose(id, providerLabel(provider))}
                  disabled={!ok || isPrimary || busy === id}
                  className="inline-flex items-center justify-center gap-1.5 rounded-md border border-accent-amber/30 bg-accent-amber/10 px-3 py-1.5 text-xs text-accent-amber hover:bg-accent-amber/20 disabled:opacity-40"
                >
                  {busy === id ? <Loader2 size={13} className="animate-spin" /> : <Crown size={13} />}
                  Set Main Brain
                </button>
              </div>
            )
          })}
          {providers.length === 0 && (
            <div className="px-4 py-6 text-sm text-starlight-500">
              No configured API providers returned by backend.
            </div>
          )}
        </div>
      </section>

      <div className="flex items-center gap-2 rounded-lg border border-white/5 bg-midnight-400/20 px-4 py-3 text-xs text-starlight-500">
        <CheckCircle2 size={14} className="text-status-success" />
        Main Brain persists to <span className="font-mono text-starlight-300">User.settings.primary_runtime</span>.
      </div>
    </div>
  )
}

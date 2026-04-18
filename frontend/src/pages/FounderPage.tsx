/**
 * FounderPage — founder-only runtime and routing diagnostics.
 */
import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Crown,
  Shield,
  Activity,
  Brain,
  Database,
  Lock,
  AlertTriangle,
  RefreshCw,
  Server,
  Cpu,
  Settings2,
  RotateCcw,
  Save,
  Plus,
  X,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Shimmer } from '@/components/common'
import { toast } from '@/stores/toastStore'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import type {
  ApiResponse,
  FounderRoutingPolicy,
  FounderRoutingPreview,
  FounderRoutingTelemetry,
  RoutingMode,
} from '@/types/api'

const HARD_LAWS = [
  { id: 1, law: 'Never bypass human approval for Tier 3+ actions', enforced: true },
  { id: 2, law: 'Never expose credentials or secrets in outputs', enforced: true },
  { id: 3, law: 'Never modify governance rules without FOUNDER role', enforced: true },
  { id: 4, law: 'Never delete data without explicit user consent', enforced: true },
  { id: 5, law: 'Never impersonate a human identity', enforced: true },
  { id: 6, law: 'Never execute recursive self-modification', enforced: true },
  { id: 7, law: 'Never bypass DaenaBot governance layer', enforced: true },
  { id: 8, law: 'Never share user data between tenants', enforced: true },
  { id: 9, law: 'Never override hard-coded safety limits', enforced: true },
]

const PREVIEW_SEED = 'Review a backend latency regression and propose the best local model path.'

const routingModeOptions: RoutingMode[] = ['STANDARD', 'QUINTESSENCE']

function truthVariant(value: boolean): 'success' | 'danger' {
  return value ? 'success' : 'danger'
}

function providerVariant(
  selectable: boolean,
  reachable: boolean,
): 'success' | 'warning' | 'danger' {
  if (selectable) return 'success'
  if (reachable) return 'warning'
  return 'danger'
}

export function FounderPage() {
  usePageTitle('Control Panel')
  const { user } = useAuthStore()
  const [telemetry, setTelemetry] = useState<FounderRoutingTelemetry | null>(null)
  const [preview, setPreview] = useState<FounderRoutingPreview | null>(null)
  const [previewMessage, setPreviewMessage] = useState(PREVIEW_SEED)
  const [previewRoutingMode, setPreviewRoutingMode] = useState<RoutingMode>('STANDARD')
  const [previewThinkMode, setPreviewThinkMode] = useState(false)
  const [loading, setLoading] = useState(true)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Policy editor state
  const [policy, setPolicy] = useState<FounderRoutingPolicy | null>(null)
  const [policyLoading, setPolicyLoading] = useState(false)
  const [policySaving, setPolicySaving] = useState(false)
  const [newBlockedModel, setNewBlockedModel] = useState('')
  const [newPreferredIntent, setNewPreferredIntent] = useState('CODING')
  const [newPreferredModel, setNewPreferredModel] = useState('')

  const fetchPolicy = useCallback(async () => {
    setPolicyLoading(true)
    try {
      const { data } = await api.get<ApiResponse<FounderRoutingPolicy>>('/founder/routing/policy')
      setPolicy(data.data)
    } catch (err) {
      console.error('Failed to load founder routing policy:', err)
      setPolicy(null)
    } finally {
      setPolicyLoading(false)
    }
  }, [])

  const savePolicy = async () => {
    if (!policy) return
    setPolicySaving(true)
    try {
      const { data } = await api.put<ApiResponse<FounderRoutingPolicy>>(
        '/founder/routing/policy',
        {
          preferred_models: policy.preferred_models,
          provider_priority: policy.provider_priority,
          cost_ceiling: policy.cost_ceiling,
          blocked_models: policy.blocked_models,
          blocked_providers: policy.blocked_providers,
          default_model: policy.default_model,
          enforce_local_only: policy.enforce_local_only,
        },
      )
      setPolicy(data.data)
      toast.success('Routing policy saved')
    } catch {
      toast.error('Failed to save routing policy')
    } finally {
      setPolicySaving(false)
    }
  }

  const resetPolicy = async () => {
    setPolicySaving(true)
    try {
      const { data } = await api.post<ApiResponse<FounderRoutingPolicy>>(
        '/founder/routing/policy/reset',
      )
      setPolicy(data.data)
      toast.success('Routing policy reset to defaults')
    } catch {
      toast.error('Failed to reset routing policy')
    } finally {
      setPolicySaving(false)
    }
  }

  const fetchTelemetry = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get<ApiResponse<FounderRoutingTelemetry>>('/founder/routing/telemetry')
      setTelemetry(data.data)
    } catch (fetchError) {
      console.error(fetchError)
      setError('Founder routing telemetry is unavailable in the current runtime.')
      setTelemetry(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchTelemetry()
    void fetchPolicy()
  }, [fetchPolicy])

  const runPreview = async () => {
    setPreviewLoading(true)
    setError(null)
    try {
      const { data } = await api.post<ApiResponse<FounderRoutingPreview>>(
        '/founder/routing/preview',
        {
          message: previewMessage,
          routing_mode: previewRoutingMode,
          chat_mode: 'CMD',
          think_mode: previewThinkMode,
        },
      )
      setPreview(data.data)
    } catch (previewError) {
      console.error(previewError)
      setError('Routing preview failed.')
      setPreview(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  if (user?.role !== 'FOUNDER') {
    return (
      <div className="h-full flex items-center justify-center">
        <Card variant="glass" padding="lg" className="max-w-sm text-center">
          <Lock size={40} className="text-accent-red mx-auto mb-3" />
          <h2 className="text-lg font-display font-bold text-starlight-100 mb-1">Access Denied</h2>
          <p className="text-sm text-starlight-400">
            The Founder Control Panel requires the FOUNDER role.
          </p>
        </Card>
      </div>
    )
  }

  const runtime = telemetry?.runtime ?? {}
  const guardrailIssues = Array.isArray(runtime['guardrail_issues'])
    ? runtime['guardrail_issues'] as string[]
    : []
  const rawProviderKeys = (
    runtime['provider_keys'] && typeof runtime['provider_keys'] === 'object'
      ? runtime['provider_keys']
      : {}
  ) as Record<string, unknown>
  // Values may be strings ("configured") or objects ({configured: true, source: "env"})
  const providerKeys: Record<string, string> = {}
  for (const [k, v] of Object.entries(rawProviderKeys)) {
    if (typeof v === 'string') providerKeys[k] = v
    else if (v && typeof v === 'object' && 'configured' in v) {
      providerKeys[k] = (v as Record<string, unknown>).configured ? 'configured' : 'missing'
    } else providerKeys[k] = String(v)
  }
  const registry = telemetry?.registry
  const stats = registry
    ? [
        { label: 'Healthy Providers', value: String(registry.summary.healthy_provider_count), icon: Server, color: 'text-accent-green' },
        { label: 'Selectable Models', value: String(registry.summary.selectable_model_count), icon: Brain, color: 'text-accent-cyan' },
        { label: 'Installed Local Models', value: String(registry.summary.installed_model_count), icon: Database, color: 'text-primary-400' },
        { label: 'Recent LLM Routes', value: String(telemetry?.trace_summary.total_routes ?? 0), icon: Activity, color: 'text-accent-amber' },
        { label: 'Routing Fallbacks', value: String(telemetry?.trace_summary.fallback_count ?? 0), icon: AlertTriangle, color: 'text-accent-red' },
        { label: 'Mode Downgrades', value: String(telemetry?.trace_summary.downgraded_mode_count ?? 0), icon: Cpu, color: 'text-accent-purple' },
        { label: 'Default Model', value: registry.default_model, icon: Brain, color: 'text-starlight-300' },
        { label: 'Guardrail Issues', value: String(guardrailIssues.length), icon: Shield, color: guardrailIssues.length ? 'text-accent-red' : 'text-accent-green' },
      ]
    : []

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        <motion.div
          className="flex items-center justify-between gap-3"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-accent-amber/15">
              <Crown size={22} className="text-accent-amber" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100">Founder Routing Panel</h1>
              <p className="text-sm text-starlight-400">Live runtime truth, provider state, and routing diagnostics</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void fetchTelemetry()} isLoading={loading}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </motion.div>

        {error && (
          <Card variant="glass" padding="md" className="border border-status-error/20">
            <div className="flex items-center gap-2 text-status-error text-sm">
              <AlertTriangle size={14} />
              <span>{error}</span>
            </div>
          </Card>
        )}

        {loading ? (
          <Shimmer count={4} layout="detail" />
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {stats.map((s, i) => {
                const Icon = s.icon
                return (
                  <motion.div
                    key={s.label}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                  >
                    <Card variant="glass" padding="md">
                      <div className="flex items-center gap-2 mb-1">
                        <Icon size={12} className={s.color} />
                        <span className="text-[10px] text-starlight-500">{s.label}</span>
                      </div>
                      <p className="text-lg font-display font-bold text-starlight-100 break-words">{s.value}</p>
                    </Card>
                  </motion.div>
                )
              })}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <Card variant="glass" padding="lg">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
                    <Server size={14} /> Runtime Truth
                  </h3>
                  <Badge variant={guardrailIssues.length ? 'danger' : 'success'} size="sm">
                    {guardrailIssues.length ? 'Warnings Present' : 'No Guardrail Warnings'}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg border border-white/5 bg-midnight-800/40 p-3">
                    <p className="text-starlight-500 mb-1">Environment</p>
                    <p className="text-starlight-100 font-medium">{String(runtime['app_env'] ?? 'unknown')}</p>
                  </div>
                  <div className="rounded-lg border border-white/5 bg-midnight-800/40 p-3">
                    <p className="text-starlight-500 mb-1">Unsafe Dev Features</p>
                    <Badge variant={Boolean(runtime['allows_unsafe_dev_features']) ? 'warning' : 'success'}>
                      {String(runtime['allows_unsafe_dev_features'])}
                    </Badge>
                  </div>
                  <div className="rounded-lg border border-white/5 bg-midnight-800/40 p-3">
                    <p className="text-starlight-500 mb-1">Debug</p>
                    <Badge variant={Boolean(runtime['debug']) ? 'warning' : 'success'}>
                      {String(runtime['debug'])}
                    </Badge>
                  </div>
                  <div className="rounded-lg border border-white/5 bg-midnight-800/40 p-3">
                    <p className="text-starlight-500 mb-1">Disable Auth</p>
                    <Badge variant={Boolean(runtime['disable_auth']) ? 'danger' : 'success'}>
                      {String(runtime['disable_auth'])}
                    </Badge>
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  <p className="text-[11px] uppercase tracking-wide text-starlight-500">Provider Key State</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(providerKeys).map(([provider, status]) => (
                      <Badge
                        key={provider}
                        variant={
                          status === 'configured'
                            ? 'success'
                            : status === 'placeholder'
                              ? 'warning'
                              : 'danger'
                        }
                        size="sm"
                      >
                        {provider}: {status}
                      </Badge>
                    ))}
                  </div>
                </div>
                {guardrailIssues.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {guardrailIssues.map((issue) => (
                      <div
                        key={issue}
                        className="rounded-lg border border-status-error/20 bg-status-error/5 px-3 py-2 text-xs text-starlight-300"
                      >
                        {issue}
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <Card variant="glass" padding="lg">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
                    <Brain size={14} /> Routing Mode Truth
                  </h3>
                  <Badge variant="info" size="sm">
                    Registry-backed
                  </Badge>
                </div>
                <div className="space-y-3">
                  {registry && Object.entries(registry.routing_modes).map(([mode, truth]) => (
                    <div
                      key={mode}
                      className="rounded-lg border border-white/5 bg-midnight-800/40 px-3 py-3"
                    >
                      <div className="flex items-center justify-between gap-3 mb-1">
                        <p className="text-sm font-semibold text-starlight-100">{mode}</p>
                        <Badge variant={truthVariant(truth.truthful)} size="sm">
                          {truth.truthful ? 'Truthful' : 'Disabled / Degraded'}
                        </Badge>
                      </div>
                      <p className="text-xs text-starlight-400">{truth.reason}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <Card variant="glass" padding="lg">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
                    <Database size={14} /> Provider Registry State
                  </h3>
                  <Badge variant="cyan" size="sm">
                    {registry?.providers.length ?? 0} providers
                  </Badge>
                </div>
                <div className="space-y-3">
                  {registry?.providers.map((provider) => (
                    <div
                      key={provider.provider}
                      className="rounded-lg border border-white/5 bg-midnight-800/40 px-3 py-3"
                    >
                      <div className="flex items-center justify-between gap-3 mb-1">
                        <div>
                          <p className="text-sm font-semibold text-starlight-100">{provider.display_name}</p>
                          <p className="text-[11px] text-starlight-500">{provider.kind} • {provider.model_count} models</p>
                        </div>
                        <Badge
                          variant={providerVariant(provider.selectable, provider.reachable)}
                          size="sm"
                        >
                          {provider.health}
                        </Badge>
                      </div>
                      <p className="text-xs text-starlight-400">{provider.reason}</p>
                    </div>
                  ))}
                </div>
              </Card>

              <Card variant="glass" padding="lg">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
                    <Activity size={14} /> Recent Routing Decisions
                  </h3>
                  <Badge variant="amber" size="sm">
                    {telemetry?.trace_summary.total_routes ?? 0} recent traces
                  </Badge>
                </div>
                <div className="space-y-3 max-h-[30rem] overflow-y-auto pr-1">
                  {telemetry?.recent_routes.length ? telemetry.recent_routes.map((route) => (
                    <div
                      key={route.id}
                      className="rounded-lg border border-white/5 bg-midnight-800/40 px-3 py-3 space-y-2"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="cyan" size="sm">{route.provider || 'unknown provider'}</Badge>
                        <Badge variant="default" size="sm">{route.model || 'unknown model'}</Badge>
                        <Badge
                          variant={route.requested_mode === route.applied_mode ? 'success' : 'warning'}
                          size="sm"
                        >
                          {route.requested_mode} → {route.applied_mode}
                        </Badge>
                        {route.intent && <Badge variant="purple" size="sm">{route.intent}</Badge>}
                      </div>
                      <p className="text-xs text-starlight-300">{route.selection_reason || 'No selection reason recorded.'}</p>
                      {route.mode_reason && (
                        <p className="text-xs text-accent-amber">{route.mode_reason}</p>
                      )}
                      <div className="flex flex-wrap gap-3 text-[11px] text-starlight-500">
                        <span>Source: {route.routing_source || 'unknown'}</span>
                        <span>Latency: {route.latency_ms ?? 'n/a'} ms</span>
                        <span>{new Date(route.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  )) : (
                    <div className="rounded-lg border border-white/5 bg-midnight-800/40 px-3 py-4 text-xs text-starlight-400">
                      No persisted LLM routing traces are available yet for this tenant.
                    </div>
                  )}
                </div>
              </Card>
            </div>

            <Card variant="glass" padding="lg">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
                  <Cpu size={14} /> Routing Preview
                </h3>
                <Badge variant="info" size="sm">
                  No LLM call
                </Badge>
              </div>
              <div className="space-y-4">
                <textarea
                  value={previewMessage}
                  onChange={(event) => setPreviewMessage(event.target.value)}
                  className="w-full min-h-28 rounded-lg border border-white/10 bg-midnight-900/70 px-3 py-3 text-sm text-starlight-100 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  placeholder="Enter a message to preview routing."
                />
                <div className="flex flex-wrap items-center gap-3">
                  <select
                    value={previewRoutingMode}
                    onChange={(event) => setPreviewRoutingMode(event.target.value as RoutingMode)}
                    className="rounded-lg border border-white/10 bg-midnight-900/70 px-3 py-2 text-sm text-starlight-100 focus:outline-none"
                  >
                    {routingModeOptions.map((mode) => (
                      <option key={mode} value={mode}>{mode}</option>
                    ))}
                  </select>
                  <label className="inline-flex items-center gap-2 text-sm text-starlight-300">
                    <input
                      type="checkbox"
                      checked={previewThinkMode}
                      onChange={(event) => setPreviewThinkMode(event.target.checked)}
                      className="rounded border-white/20 bg-midnight-900/70"
                    />
                    Think-mode preview
                  </label>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void runPreview()}
                    isLoading={previewLoading}
                    disabled={!previewMessage.trim()}
                  >
                    Preview Route
                  </Button>
                </div>

                {preview && (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <div className="rounded-lg border border-white/5 bg-midnight-800/40 p-4 space-y-3">
                      <p className="text-sm font-semibold text-starlight-100">Query Understanding</p>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="purple" size="sm">{preview.query_understanding.intent}</Badge>
                        <Badge variant="cyan" size="sm">{preview.query_understanding.complexity_label}</Badge>
                        <Badge variant="amber" size="sm">{preview.query_understanding.risk_level}</Badge>
                        <Badge variant="default" size="sm">
                          Suggested: {preview.query_understanding.suggested_mode}
                        </Badge>
                      </div>
                      <p className="text-xs text-starlight-400">
                        Confidence {preview.query_understanding.confidence.toFixed(2)} • Tier {preview.query_understanding.governance_tier} • {preview.query_understanding.processing_time_ms} ms
                      </p>
                      <p className="text-xs text-starlight-300">
                        Suggested providers: {preview.query_understanding.suggested_providers.join(', ') || 'none'}
                      </p>
                      {preview.query_understanding.clarifying_question && (
                        <p className="text-xs text-accent-amber">{preview.query_understanding.clarifying_question}</p>
                      )}
                    </div>
                    <div className="rounded-lg border border-white/5 bg-midnight-800/40 p-4 space-y-3">
                      <p className="text-sm font-semibold text-starlight-100">Routing Decision</p>
                      <div className="flex flex-wrap gap-2">
                        <Badge
                          variant={preview.routing.requested_mode === preview.routing.applied_mode ? 'success' : 'warning'}
                          size="sm"
                        >
                          {preview.routing.requested_mode} → {preview.routing.applied_mode}
                        </Badge>
                        <Badge variant="cyan" size="sm">
                          {String(preview.routing.primary.model_id || 'unknown model')}
                        </Badge>
                        <Badge variant="default" size="sm">
                          {String(preview.routing.primary.provider || 'unknown provider')}
                        </Badge>
                      </div>
                      <p className="text-xs text-starlight-300">{preview.routing.selection_reason || 'No selection reason returned.'}</p>
                      {preview.routing.mode_reason && (
                        <p className="text-xs text-accent-amber">{preview.routing.mode_reason}</p>
                      )}
                      <p className="text-xs text-starlight-400">
                        Provider strategy: {preview.routing.provider_strategy || 'unknown'} • {preview.routing.routing_time_ms} ms
                      </p>
                      {preview.routing.top_candidates.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[11px] uppercase tracking-wide text-starlight-500">Top Candidates</p>
                          {preview.routing.top_candidates.slice(0, 3).map((candidate, index) => (
                            <div
                              key={`${String(candidate.model_id)}-${index}`}
                              className="rounded-md border border-white/5 bg-midnight-900/60 px-3 py-2 text-xs text-starlight-300"
                            >
                              {String(candidate.model_id)} • {String(candidate.provider)} • score {Number(candidate.score ?? 0).toFixed(3)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            <Card variant="glass" padding="lg">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
                  <Settings2 size={14} /> Routing Policy Overrides
                </h3>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => void resetPolicy()} disabled={policySaving}>
                    <RotateCcw size={12} className="mr-1" /> Reset
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => void savePolicy()} isLoading={policySaving}>
                    <Save size={12} className="mr-1" /> Save
                  </Button>
                </div>
              </div>

              {policyLoading ? (
                <Shimmer count={3} layout="detail" />
              ) : policy ? (
                <div className="space-y-5">
                  {/* Preferred Models per Intent */}
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-starlight-500 mb-2">Preferred Model per Intent</p>
                    <div className="space-y-2">
                      {Object.entries(policy.preferred_models).map(([intent, model]) => (
                        <div key={intent} className="flex items-center gap-2 rounded-lg border border-white/5 bg-midnight-800/40 px-3 py-2">
                          <Badge variant="purple" size="sm">{intent}</Badge>
                          <span className="text-xs text-starlight-200 flex-1">{model}</span>
                          <button
                            onClick={() => {
                              const updated = { ...policy.preferred_models }
                              delete updated[intent]
                              setPolicy({ ...policy, preferred_models: updated })
                            }}
                            className="text-starlight-500 hover:text-accent-red transition-colors cursor-pointer"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                      <div className="flex items-center gap-2">
                        <select
                          value={newPreferredIntent}
                          onChange={(e) => setNewPreferredIntent(e.target.value)}
                          className="rounded-lg border border-white/10 bg-midnight-900/70 px-2 py-1.5 text-xs text-starlight-100 focus:outline-none"
                        >
                          {['SIMPLE', 'SEARCH', 'CODING', 'ANALYSIS', 'CREATIVE', 'MULTI_STEP'].map((i) => (
                            <option key={i} value={i}>{i}</option>
                          ))}
                        </select>
                        <input
                          value={newPreferredModel}
                          onChange={(e) => setNewPreferredModel(e.target.value)}
                          placeholder="model id (e.g. deepseek-r1:14b)"
                          className="flex-1 rounded-lg border border-white/10 bg-midnight-900/70 px-2 py-1.5 text-xs text-starlight-100 focus:outline-none"
                        />
                        <button
                          onClick={() => {
                            if (newPreferredModel.trim()) {
                              setPolicy({
                                ...policy,
                                preferred_models: { ...policy.preferred_models, [newPreferredIntent]: newPreferredModel.trim() },
                              })
                              setNewPreferredModel('')
                            }
                          }}
                          className="p-1.5 rounded-lg border border-white/10 hover:border-primary-500/30 text-starlight-400 hover:text-primary-400 transition-colors cursor-pointer"
                        >
                          <Plus size={12} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Blocked Models */}
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-starlight-500 mb-2">Blocked Models</p>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {policy.blocked_models.map((m) => (
                        <Badge key={m} variant="danger" size="sm">
                          {m}
                          <button
                            onClick={() => setPolicy({ ...policy, blocked_models: policy.blocked_models.filter((x) => x !== m) })}
                            className="ml-1 hover:text-white cursor-pointer"
                          >
                            <X size={10} />
                          </button>
                        </Badge>
                      ))}
                      {policy.blocked_models.length === 0 && (
                        <span className="text-xs text-starlight-500">None blocked</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        value={newBlockedModel}
                        onChange={(e) => setNewBlockedModel(e.target.value)}
                        placeholder="model id to block"
                        className="flex-1 rounded-lg border border-white/10 bg-midnight-900/70 px-2 py-1.5 text-xs text-starlight-100 focus:outline-none"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && newBlockedModel.trim()) {
                            setPolicy({ ...policy, blocked_models: [...policy.blocked_models, newBlockedModel.trim()] })
                            setNewBlockedModel('')
                          }
                        }}
                      />
                      <button
                        onClick={() => {
                          if (newBlockedModel.trim()) {
                            setPolicy({ ...policy, blocked_models: [...policy.blocked_models, newBlockedModel.trim()] })
                            setNewBlockedModel('')
                          }
                        }}
                        className="p-1.5 rounded-lg border border-white/10 hover:border-primary-500/30 text-starlight-400 hover:text-primary-400 transition-colors cursor-pointer"
                      >
                        <Plus size={12} />
                      </button>
                    </div>
                  </div>

                  {/* Cost Ceiling + Local Only */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-wide text-starlight-500 mb-2">Cost Ceiling (USD/req)</p>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={policy.cost_ceiling ?? ''}
                        onChange={(e) => setPolicy({ ...policy, cost_ceiling: e.target.value ? parseFloat(e.target.value) : null })}
                        placeholder="No limit"
                        className="w-full rounded-lg border border-white/10 bg-midnight-900/70 px-2 py-1.5 text-xs text-starlight-100 focus:outline-none"
                      />
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-wide text-starlight-500 mb-2">Enforce Local Only</p>
                      <label className="inline-flex items-center gap-2 text-xs text-starlight-300">
                        <input
                          type="checkbox"
                          checked={policy.enforce_local_only}
                          onChange={(e) => setPolicy({ ...policy, enforce_local_only: e.target.checked })}
                          className="rounded border-white/20 bg-midnight-900/70"
                        />
                        Only allow local Ollama models
                      </label>
                    </div>
                  </div>

                  {/* Default Model Override */}
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-starlight-500 mb-2">Default Fallback Model Override</p>
                    <input
                      value={policy.default_model ?? ''}
                      onChange={(e) => setPolicy({ ...policy, default_model: e.target.value || null })}
                      placeholder="System default (llama3.1:latest)"
                      className="w-full rounded-lg border border-white/10 bg-midnight-900/70 px-2 py-1.5 text-xs text-starlight-100 focus:outline-none"
                    />
                  </div>

                  {policy.updated_at && (
                    <p className="text-[10px] text-starlight-500">
                      Last updated: {new Date(policy.updated_at).toLocaleString()}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-starlight-400 py-4">No custom routing policy set. Using system defaults.</p>
              )}
            </Card>

            <Card variant="glass" padding="lg">
              <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
                <Lock size={14} className="text-accent-red" /> 9 Immutable Hard Laws
              </h3>
              <div className="space-y-2">
                {HARD_LAWS.map((l) => (
                  <div
                    key={l.id}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5"
                  >
                    <span className="text-accent-red font-bold text-xs w-5">{l.id}.</span>
                    <span className="text-xs text-starlight-300 flex-1">{l.law}</span>
                    <Badge variant="danger" size="sm">
                      <Shield size={8} className="mr-0.5" /> Enforced
                    </Badge>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-starlight-500 mt-3">
                Hard laws are compiled into the system binary. They cannot be modified, disabled, or overridden
                through any interface, including this panel.
              </p>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

export default FounderPage

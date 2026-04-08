/**
 * LLM settings -- model providers, routing config, cost tracking.
 */
import { useEffect, useState } from 'react'
import { Card, Badge, Switch } from '@/components/common'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useUiStore, persistUiPref } from '@/stores/uiStore'
import { api } from '@/lib/api'
import { Brain, DollarSign, Zap, CheckCircle2 } from 'lucide-react'

interface RuntimeSubscription {
  provider: string
  plan_name: string
  is_authenticated: boolean
}

export function SettingsLLM() {
  const {
    localFirstRouting,
    toggleLocalFirstRouting,
    costAwareRouting,
    toggleCostAwareRouting,
  } = useUiStore()
  const registry = useModelRegistryStore((s) => s.registry)
  const registryLoading = useModelRegistryStore((s) => s.loading)
  const registryError = useModelRegistryStore((s) => s.error)
  const fetchRegistry = useModelRegistryStore((s) => s.fetchRegistry)
  const [costs, setCosts] = useState({ session_cost: 0, daily_cost: 0, monthly_cost: 0 })
  const [subscriptions, setSubscriptions] = useState<RuntimeSubscription[]>([])
  const handleLocalFirstToggle = () => {
    const next = !localFirstRouting
    toggleLocalFirstRouting()
    persistUiPref('local_first_routing', next)
  }
  const handleCostAwareToggle = () => {
    const next = !costAwareRouting
    toggleCostAwareRouting()
    persistUiPref('cost_aware_routing', next)
  }

  useEffect(() => {
    void fetchRegistry()
  }, [fetchRegistry])

  useEffect(() => {
    api.get('/runtimes/subscriptions')
      .then((res) => {
        const payload = res.data?.data ?? res.data
        if (Array.isArray(payload)) {
          setSubscriptions(payload)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    api.get('/billing/overview')
      .then((res) => {
        const payload = res.data?.data ?? res.data
        if (!payload) return
        setCosts({
          session_cost: payload.session_cost ?? 0,
          daily_cost: payload.daily_cost ?? 0,
          monthly_cost: payload.monthly_cost ?? 0,
        })
      })
      .catch(() => {})
  }, [])

  // Build a lookup: provider name (lowercase) -> subscription info
  const subByProvider = new Map<string, RuntimeSubscription>()
  for (const sub of subscriptions) {
    subByProvider.set(sub.provider.toLowerCase(), sub)
  }
  const authenticatedCount = subscriptions.filter((s) => s.is_authenticated).length

  return (
    <div className="space-y-6">
      {/* Connected Providers summary */}
      {authenticatedCount > 0 && (
        <Card variant="glass" padding="lg">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-status-success/10 border border-status-success/20 flex items-center justify-center">
              <CheckCircle2 size={18} className="text-status-success" />
            </div>
            <div>
              <h3 className="text-sm font-display font-semibold text-starlight-100">
                {authenticatedCount} Connected Provider{authenticatedCount !== 1 ? 's' : ''}
              </h3>
              <p className="text-xs text-starlight-400">
                {subscriptions.filter((s) => s.is_authenticated).map((s) => s.provider).join(', ')} connected via subscription
              </p>
            </div>
          </div>
        </Card>
      )}

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Brain size={14} /> Model Providers
        </h3>
        <div className="space-y-3">
          <p className="text-[10px] text-starlight-500 px-1">
            Source of truth: <code>/api/v1/chat/model-registry</code>
          </p>
          {registryLoading && !registry && (
            <p className="text-xs text-starlight-500 px-1">
              Loading live provider and model registry...
            </p>
          )}
          {registryError && (
            <p className="text-xs text-status-error px-1">{registryError}</p>
          )}
          {(registry?.providers ?? []).map((provider) => {
            const providerModels = (registry?.models ?? []).filter(
              (model) => model.provider === provider.provider,
            )
            const matchedSub = subByProvider.get(provider.provider.toLowerCase())
            const hasSubscription = matchedSub?.is_authenticated === true
            const stateVariant = hasSubscription
              ? 'success'
              : provider.selectable
                ? 'success'
                : provider.reachable && provider.model_count > 0
                  ? 'success'
                  : provider.reachable
                    ? 'warning'
                    : provider.configured
                      ? 'danger'
                      : 'default'

            return (
              <div
                key={provider.provider}
                className="flex items-center gap-4 px-3 py-3 rounded-lg bg-midnight-800/40 border border-white/5"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm text-starlight-200 font-semibold">
                      {provider.display_name}
                    </span>
                    <Badge variant={provider.kind === 'local' ? 'success' : 'info'} size="sm">
                      {provider.kind === 'local' ? 'Local' : 'Cloud'}
                    </Badge>
                    {hasSubscription ? (
                      <Badge variant="success" size="sm">
                        Connected via {matchedSub.plan_name}
                      </Badge>
                    ) : provider.reachable && provider.model_count > 0 && !provider.configured ? (
                      <Badge variant="success" size="sm">
                        Connected via subscription
                      </Badge>
                    ) : (
                      <Badge variant={stateVariant} size="sm">
                        {provider.reason}
                      </Badge>
                    )}
                  </div>
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {providerModels.length > 0 ? providerModels.map((model) => (
                      <span
                        key={model.model_id}
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${
                          model.selectable
                            ? 'text-starlight-500 bg-midnight-700/60 border-white/5'
                            : 'text-status-error bg-status-error/5 border-status-error/20'
                        }`}
                      >
                        {model.display_name}
                      </span>
                    )) : (
                      <span className="text-[10px] text-starlight-500">
                        No models discovered
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-starlight-500 mt-1">
                    Configured: {provider.configured ? 'Yes' : 'No'} · Reachable: {provider.reachable ? 'Yes' : 'No'} · Models: {provider.model_count}
                  </p>
                </div>
                <Badge variant={stateVariant} size="sm">
                  {provider.health}
                </Badge>
              </div>
            )
          })}
          <p className="text-[10px] text-starlight-500 px-1">
            Provider availability is runtime truth. Unconfigured or unreachable providers stay visible instead of being assumed active.
          </p>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-2 flex items-center gap-2">
          <Zap size={14} /> Cost Optimization & Routing
        </h3>
        <p className="text-xs text-starlight-500 mb-4">Control how Daena routes queries to minimize cost while maintaining quality.</p>
        <div className="space-y-3 max-w-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Local-First Routing</p>
              <p className="text-xs text-starlight-500">Route 70%+ queries through Ollama</p>
            </div>
            <Switch checked={localFirstRouting} onChange={handleLocalFirstToggle} label="" size="sm" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Cost-Aware Routing</p>
              <p className="text-xs text-starlight-500">Prefer cheaper models when quality is sufficient</p>
            </div>
            <Switch checked={costAwareRouting} onChange={handleCostAwareToggle} label="" size="sm" />
          </div>
        </div>
        {registry && (
          <div className="mt-4 space-y-2">
            <p className="text-[10px] text-starlight-500">
              Default Ollama model: <code>{registry.default_model}</code>
            </p>
            <p className="text-[10px] text-starlight-500">
              Council: <span className={registry.routing_modes.COUNCIL.truthful ? 'text-status-success' : 'text-starlight-500'}>{registry.routing_modes.COUNCIL.truthful ? 'active' : 'inactive'}</span> · {registry.routing_modes.COUNCIL.reason}
            </p>
            <p className="text-[10px] text-starlight-500">
              Quintessence: <span className={registry.routing_modes.QUINTESSENCE.truthful ? 'text-status-success' : 'text-starlight-500'}>{registry.routing_modes.QUINTESSENCE.truthful ? 'active' : 'inactive'}</span> · {registry.routing_modes.QUINTESSENCE.reason}
            </p>
          </div>
        )}
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <DollarSign size={14} /> Cost Tracking
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'This Session', value: `$${costs.session_cost.toFixed(2)}` },
            { label: 'Today', value: `$${costs.daily_cost.toFixed(2)}` },
            { label: 'This Month', value: `$${costs.monthly_cost.toFixed(2)}` },
          ].map((s) => (
            <div key={s.label} className="text-center px-3 py-3 rounded-lg bg-midnight-800/40 border border-white/5">
              <p className="text-lg font-display font-bold text-starlight-100">{s.value}</p>
              <p className="text-[10px] text-starlight-500">{s.label}</p>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-starlight-500 mt-2 px-1">
          Cost data populated after LLM calls with real pricing. Local Ollama calls are free.
        </p>
      </Card>
    </div>
  )
}

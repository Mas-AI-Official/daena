/**
 * Developer settings -- debug toggles, environment readout, deferred
 * Webhooks panel.
 *
 * PR-SETTINGS-CLEANUP (2026-05-02) removed the mock API Keys block
 * from this tab (it had no real CRUD, just a fake masked placeholder
 * with a Coming-Soon button) and replaced it with a link to /account
 * which is the canonical home for API key management (Atlas F.3).
 * Webhooks block kept but marked as Coming Soon since no webhook
 * dispatcher exists in the backend (Atlas I.3 - DEAD).
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Switch, Badge, Input, Button } from '@/components/common'
import { useUiStore, persistUiPref } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'
import { api } from '@/lib/api'
import { Code, Key, Webhook, Bug, ChevronRight, ChevronDown } from 'lucide-react'

interface SettingsResponse {
  app_env?: string
  developer_mode?: boolean
  [key: string]: unknown
}

interface HealthResponse {
  version?: string
  [key: string]: unknown
}

export function SettingsDeveloper() {
  const {
    debugMode,
    toggleDebugMode,
    verboseLogging,
    toggleVerboseLogging,
  } = useUiStore()

  const [appEnv, setAppEnv] = useState<string>('loading...')
  const [developerMode, setDeveloperMode] = useState<boolean>(false)
  const [version, setVersion] = useState<string>('loading...')
  const [showRoadmap, setShowRoadmap] = useState<boolean>(false)
  const handleDebugToggle = () => {
    const next = !debugMode
    toggleDebugMode()
    persistUiPref('debug_mode', next)
  }
  const handleVerboseToggle = () => {
    const next = !verboseLogging
    toggleVerboseLogging()
    persistUiPref('verbose_logging', next)
  }

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        // Phase 10b G5 fix: trailing slash matches the SettingsOverview
        // route (GET /settings/) instead of bouncing through a 307 that
        // axios used to swallow as a 404 in the OpenAPI diff.
        const { data } = await api.get<{ data?: SettingsResponse } & SettingsResponse>('/settings/')
        const settings = data.data || data
        if (settings.app_env) setAppEnv(settings.app_env)
        else setAppEnv('unknown')
        if (settings.developer_mode !== undefined) setDeveloperMode(settings.developer_mode)
      } catch {
        setAppEnv('unavailable')
      }
    }

    const fetchVersion = async () => {
      try {
        const { data } = await api.get<HealthResponse>('/health')
        setVersion(data.version || '0.1.0-alpha')
      } catch {
        setVersion('0.1.0-alpha')
      }
    }

    fetchSettings()
    fetchVersion()
  }, [])

  return (
    <div className="space-y-6">
      <Card variant="glass" padding="lg">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
            <Key size={14} /> API Keys
          </h3>
          <Link
            to="/account"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] text-primary-400 border border-primary-500/20 hover:bg-primary-500/10 transition-colors"
            title="API key management (create / list / revoke) lives at /account."
          >
            <Key size={10} /> Manage in Account <ChevronRight size={10} />
          </Link>
        </div>
        <p className="text-xs text-starlight-400 max-w-md">
          API keys for programmatic access to Daena now live on the
          Account page. Create, copy, and revoke keys there.
        </p>
      </Card>

      <Card variant="glass" padding="lg">
        <button
          onClick={() => setShowRoadmap((v) => !v)}
          className="flex w-full items-center justify-between text-left"
          aria-expanded={showRoadmap}
        >
          <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
            {showRoadmap ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Roadmap (not active yet)
          </h3>
          <Badge variant="warning" size="sm">Webhooks · Debug Mode · Verbose Logging</Badge>
        </button>
        {showRoadmap && (
          <div className="mt-4 space-y-6 border-t border-white/5 pt-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-display font-semibold text-starlight-100 flex items-center gap-2">
                  <Webhook size={14} /> Webhooks
                </h4>
                <Badge variant="warning" size="sm">Coming soon</Badge>
              </div>
              <p
                className="text-[10px] text-starlight-500 mb-3"
                title="Atlas I.3 + Phase 10b §3: no webhook dispatcher exists in backend."
              >
                Webhook dispatcher pending. Saved values would not fire today.
              </p>
              <div className="space-y-3 max-w-md opacity-60 pointer-events-none select-none" aria-disabled="true">
                <Input
                  label="Webhook URL"
                  value=""
                  placeholder="https://your-server.com/webhook"
                  onChange={() => {}}
                />
                <div className="flex gap-3 text-xs text-starlight-400">
                  <label className="flex items-center gap-1">
                    <input type="checkbox" className="rounded" disabled /> Task complete
                  </label>
                  <label className="flex items-center gap-1">
                    <input type="checkbox" className="rounded" disabled /> Approval needed
                  </label>
                  <label className="flex items-center gap-1">
                    <input type="checkbox" className="rounded" disabled /> Errors
                  </label>
                </div>
                <div title="Coming in next release">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="opacity-60 cursor-not-allowed"
                    disabled
                    onClick={() => toast.info('Webhook configuration coming in next release')}
                  >
                    Save Webhook
                  </Button>
                </div>
              </div>
            </div>
            <div className="border-t border-white/5 pt-4">
              <h4 className="text-xs font-display font-semibold text-starlight-100 mb-3 flex items-center gap-2">
                <Bug size={14} /> Debug
              </h4>
              <div className="space-y-3 max-w-md">
                <div
                  className="flex items-center justify-between"
                  title="Phase 10C-D: setting persists, but no debug-overlay component reads debugMode yet."
                >
                  <div>
                    <p className="text-sm text-starlight-200">
                      Debug Mode
                      <Badge variant="warning" size="sm" className="ml-2 align-middle">Coming soon</Badge>
                    </p>
                    <p className="text-xs text-starlight-500">Show raw API responses and timing. (Persists; no consumer reads it yet.)</p>
                  </div>
                  <Switch checked={debugMode} onChange={handleDebugToggle} label="" size="sm" disabled />
                </div>
                <div
                  className="flex items-center justify-between"
                  title="Phase 10C-D: setting persists, but no logger setup reads verboseLogging."
                >
                  <div>
                    <p className="text-sm text-starlight-200">
                      Verbose Logging
                      <Badge variant="warning" size="sm" className="ml-2 align-middle">Coming soon</Badge>
                    </p>
                    <p className="text-xs text-starlight-500">Log all agent decisions to console. (Persists; no consumer reads it yet.)</p>
                  </div>
                  <Switch checked={verboseLogging} onChange={handleVerboseToggle} label="" size="sm" disabled />
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Code size={14} /> Environment
        </h3>
        <div className="space-y-1 font-mono text-xs">
          {[
            { key: 'API_URL', val: window.location.origin + '/api' },
            { key: 'WS_URL', val: window.location.origin.replace('http', 'ws') + '/ws' },
            { key: 'VERSION', val: version },
            { key: 'APP_ENV', val: appEnv },
            // Phase 10C-D: this is the SYSTEM-level developer_mode (from
            // /settings/, controls archive vs hard-delete per CLAUDE.md
            // rule 2). Distinct from any per-user JSONB key — collision
            // with users.settings.developer_mode is documented in
            // PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md §4.3 and will
            // be renamed in Phase 11 PR-S6.
            { key: 'DEVELOPER_MODE (system)', val: String(developerMode) },
          ].map((e) => (
            <div key={e.key} className="flex gap-2 px-2 py-1 rounded bg-midnight-800/40">
              <span className="text-accent-cyan">{e.key}</span>
              <span className="text-starlight-500">=</span>
              <span className="text-starlight-300">{e.val}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

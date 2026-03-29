/**
 * Developer settings — API keys, webhooks, debug mode.
 */
import { useEffect, useState } from 'react'
import { Card, Switch, Badge, Input, Button } from '@/components/common'
import { useUiStore, persistUiPref } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'
import { api } from '@/lib/api'
import { Code, Key, Webhook, Bug } from 'lucide-react'

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
        const { data } = await api.get<{ data: SettingsResponse }>('/settings')
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
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Key size={14} /> API Keys
        </h3>
        <div className="space-y-3 max-w-md">
          <p className="text-xs text-starlight-400">
            Generate API keys for programmatic access to Daena services.
          </p>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5">
            <code className="text-xs text-starlight-300 flex-1 font-mono">dk_••••••••••••••••</code>
            <Badge variant="success" size="sm">Active</Badge>
          </div>
          <div title="Coming in next release">
            <Button
              variant="ghost"
              size="sm"
              className="opacity-60 cursor-not-allowed"
              onClick={() => toast.info('API key generation coming in next release')}
            >
              Generate New Key
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Webhook size={14} /> Webhooks
        </h3>
        <div className="space-y-3 max-w-md">
          <Input
            label="Webhook URL"
            value=""
            placeholder="https://your-server.com/webhook"
            onChange={() => {}}
          />
          <div className="flex gap-3 text-xs text-starlight-400">
            <label className="flex items-center gap-1">
              <input type="checkbox" className="rounded" /> Task complete
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" className="rounded" /> Approval needed
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" className="rounded" /> Errors
            </label>
          </div>
          <div title="Coming in next release">
            <Button
              variant="ghost"
              size="sm"
              className="opacity-60 cursor-not-allowed"
              onClick={() => toast.info('Webhook configuration coming in next release')}
            >
              Save Webhook
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Bug size={14} /> Debug
        </h3>
        <div className="space-y-3 max-w-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Debug Mode</p>
              <p className="text-xs text-starlight-500">Show raw API responses and timing</p>
            </div>
            <Switch checked={debugMode} onChange={handleDebugToggle} label="" size="sm" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Verbose Logging</p>
              <p className="text-xs text-starlight-500">Log all agent decisions to console</p>
            </div>
            <Switch checked={verboseLogging} onChange={handleVerboseToggle} label="" size="sm" />
          </div>
        </div>
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
            { key: 'DEVELOPER_MODE', val: String(developerMode) },
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

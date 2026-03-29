/**
 * Connections settings — quick connector status overview, link to full page.
 */
import { Card, Badge } from '@/components/common'
import { Plug, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

export function SettingsConnections() {
  return (
    <div className="space-y-6">
      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Plug size={14} /> Connector Overview
        </h3>
        <p className="text-xs text-starlight-400 mb-4">
          Manage your connected services and per-tool permissions from the full Connections page.
        </p>
        <Link
          to="/connections"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-colors"
        >
          <ExternalLink size={14} />
          Open Connections Manager
        </Link>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4">Default Permissions</h3>
        <div className="space-y-3 max-w-md">
          {[
            { label: 'New connector tools', value: 'ASK_EACH_TIME' },
            { label: 'OAuth re-auth window', value: '30 days' },
            { label: 'API key rotation', value: 'Manual' },
          ].map((s) => (
            <div key={s.label} className="flex items-center justify-between">
              <span className="text-sm text-starlight-200">{s.label}</span>
              <Badge variant="info" size="sm">{s.value}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

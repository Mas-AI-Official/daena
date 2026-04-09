/**
 * OrgConnectors -- Organization-level connector policies.
 * Equivalent to Perplexity's /account/org/connectors
 */
import { Plug, Shield, Globe } from 'lucide-react'

export function OrgConnectors() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Connectors</h1>
        <p className="text-sm text-starlight-400 mt-1">Organization-level connector policies and defaults</p>
      </div>

      <div className="space-y-4 max-w-lg">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Shield size={14} /> Default permissions
        </h3>
        <p className="text-xs text-starlight-500">
          Set organization-wide default permissions for connectors. Members can override these with personal preferences.
        </p>

        {[
          { label: 'New connectors default', value: 'Ask each time' },
          { label: 'MCP server tools', value: 'Ask each time' },
          { label: 'External API calls', value: 'Block' },
        ].map((item) => (
          <div key={item.label} className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5">
            <span className="text-sm text-starlight-300">{item.label}</span>
            <select className="text-xs bg-midnight-400 border border-white/10 rounded px-2 py-1 text-starlight-300">
              <option>Allow</option>
              <option>Ask each time</option>
              <option>Block</option>
            </select>
          </div>
        ))}

        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 pt-4">
          <Globe size={14} /> Approved connectors
        </h3>
        <p className="text-xs text-starlight-500">
          Connectors approved for use across the organization.
          Visit the Connections page to manage individual connector configurations.
        </p>
      </div>

      <button className="px-6 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors cursor-pointer">
        Save policies
      </button>
    </div>
  )
}

export default OrgConnectors

/**
 * AccountConnectors -- Personal connector preferences.
 * Links to the main /connections page for full management.
 */
import { useNavigate } from 'react-router-dom'
import { Plug, ExternalLink, Shield } from 'lucide-react'

export function AccountConnectors() {
  const navigate = useNavigate()

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Connectors</h1>
        <p className="text-sm text-starlight-400 mt-1">Your personal connector preferences and permissions</p>
      </div>

      {/* Link to full connections page */}
      <button
        onClick={() => navigate('/connections')}
        className="flex items-center gap-3 p-4 rounded-xl bg-midnight-300/30 border border-white/5 hover:border-primary-500/20 transition-all cursor-pointer max-w-lg w-full text-left"
      >
        <Plug size={20} className="text-accent-purple" />
        <div className="flex-1">
          <p className="text-sm font-medium text-starlight-100">Manage all connections</p>
          <p className="text-xs text-starlight-500">Runtimes, MCP servers, and external services</p>
        </div>
        <ExternalLink size={14} className="text-starlight-400" />
      </button>

      {/* Personal permissions overview */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Shield size={14} /> Your permissions
        </h3>
        <p className="text-xs text-starlight-500 max-w-lg">
          Personal connector permissions override organization defaults. Visit the Connections page
          to configure per-tool Allow/Ask/Block permissions.
        </p>
      </div>
    </div>
  )
}

export default AccountConnectors

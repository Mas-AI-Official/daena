/**
 * Service setup modal (Session 10 -- rewritten)
 *
 * When the user clicks "Connect with Google" and the backend says OAuth
 * isn't configured, this modal explains the choice clearly:
 *
 *   PRIMARY PATH: Install the community MCP server (one click). The
 *   MCP server handles its own OAuth -- Daena doesn't need Client ID.
 *   This is what Claude Desktop does for the same connectors.
 *
 *   ADVANCED PATH: Register your own OAuth app at Google Cloud (or the
 *   provider), paste Client ID + Secret. For power users who want a
 *   private OAuth app under their own identity.
 *
 *   FUTURE PATH: Daena hosted broker at broker.daena.mas-ai.co -- no
 *   setup at all. Requires MAS-AI to register OAuth apps with each
 *   provider and deploy the broker service.
 *
 * Closing the door on the "paste credentials as a blind first step"
 * pattern that was confusing operators.
 */
import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Plug,
  Puzzle,
  XCircle,
  Loader2,
  Plus,
  ChevronUp,
  ChevronDown,
  Save,
  ExternalLink,
  Shield,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { CONNECTOR_MCP_EQUIVALENT } from './catalog'

export default function OAuthSetupModal({
  connectorId,
  connectorName,
  missingField,
  onClose,
  onSaved,
}: {
  connectorId: string
  connectorName: string
  missingField: string
  onClose: () => void
  onSaved: () => void
}) {
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const secretField = missingField.replace('_CLIENT_ID', '_CLIENT_SECRET')

  const mcp = CONNECTOR_MCP_EQUIVALENT[connectorId]

  const handleInstallMCP = async () => {
    if (!mcp) return
    setInstalling(true)
    try {
      // Forward the real command + args (e.g. ``npx -y
      // @modelcontextprotocol/server-gdrive``) so the backend writes
      // a working entry to claude_desktop_config.json. Previously we
      // only sent the internal id ("mcp-google-drive") and the
      // server wrote ``npx -y mcp-google-drive`` -- which is not a
      // real npm package, so the install silently produced a broken
      // config.
      await api.post('/connections/extensions/install', {
        id: `mcp-${connectorId}`,
        name: mcp.name,
        description: mcp.auth_note,
        command: mcp.command,
        args: mcp.args,
      })
      toast.success(
        `${mcp.name} installed. The MCP server will prompt you to sign in when you first use a ${connectorName} tool.`,
        10_000,
      )
      onSaved()
    } catch {
      toast.error(
        `Failed to install ${mcp.name}. Check your internet connection and try again.`,
      )
    } finally {
      setInstalling(false)
    }
  }

  const handleSave = async () => {
    if (!clientId.trim() || !clientSecret.trim()) {
      toast.error('Both Client ID and Client Secret are required')
      return
    }
    setSaving(true)
    try {
      await api.post('/settings/oauth-credentials', {
        connector_id: connectorId,
        client_id_field: missingField,
        client_id: clientId.trim(),
        client_secret_field: secretField,
        client_secret: clientSecret.trim(),
      })
      onSaved()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Save failed'
      toast.error(`Failed to save credentials: ${msg}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-[560px] max-w-[92vw] max-h-[90vh] overflow-y-auto rounded-2xl bg-midnight-500 border border-white/10 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-primary-500/10 flex items-center justify-center text-primary-400 shrink-0">
            <Plug size={20} />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-display font-bold text-starlight-100">
              Connect {connectorName}
            </h2>
            <p className="text-xs text-starlight-400 mt-1">
              Choose how you want to authenticate. Install the MCP server for a one-click
              setup, or bring your own OAuth app for full control.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer"
          >
            <XCircle size={18} />
          </button>
        </div>

        {/* PRIMARY: Install the MCP server */}
        {mcp ? (
          <div className="mb-3 p-4 rounded-xl bg-primary-500/10 border border-primary-500/30">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-9 h-9 rounded-lg bg-primary-500/20 flex items-center justify-center text-primary-400 shrink-0">
                <Puzzle size={18} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-starlight-100">
                    Install {mcp.name}
                  </p>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-green/20 text-accent-green font-semibold uppercase tracking-wider">
                    Recommended
                  </span>
                </div>
                <p className="text-[12px] text-starlight-400 mt-1">{mcp.auth_note}</p>
                <p className="text-[11px] text-starlight-500 mt-2 font-mono">
                  {mcp.command} {mcp.args.join(' ')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleInstallMCP}
                disabled={installing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-primary-500 text-white hover:bg-primary-400 disabled:opacity-50 cursor-pointer"
              >
                {installing ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                {installing ? 'Installing...' : `Install ${mcp.name}`}
              </button>
              <a
                href={mcp.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs text-starlight-400 hover:text-primary-400 hover:bg-white/5 cursor-pointer"
              >
                View source <ExternalLink size={11} />
              </a>
            </div>
          </div>
        ) : (
          <div className="mb-3 p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="flex items-start gap-2 text-xs text-starlight-400">
              <Puzzle size={14} className="shrink-0 mt-0.5 text-starlight-500" />
              <div>
                No official MCP server catalogued for {connectorName} yet. Use the
                advanced path below, or{' '}
                <a
                  href="https://github.com/modelcontextprotocol/servers"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                >
                  browse community MCP servers <ExternalLink size={10} />
                </a>
                {' '}and add one via Browse MCP servers.
              </div>
            </div>
          </div>
        )}

        {/* Hosted broker (future) - demoted to secondary info line */}
        <div className="mb-4 flex items-start gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
          <Shield size={12} className="text-accent-green mt-0.5 shrink-0" />
          <p className="text-[11px] text-starlight-400 leading-relaxed">
            <span className="font-semibold text-accent-green">Coming soon:</span>{' '}
            Daena hosted OAuth broker at <span className="font-mono">broker.daena.mas-ai.co</span>.
            Zero setup, just click Connect.
          </p>
        </div>

        {/* ADVANCED: manual OAuth configuration (collapsed by default) */}
        <div className="border-t border-white/5 pt-4">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-xs text-starlight-400 hover:text-starlight-200 cursor-pointer mb-3"
          >
            {showAdvanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            Advanced: use my own OAuth app
          </button>

          {showAdvanced && (
            <div className="space-y-3">
              <p className="text-[11px] text-starlight-500 leading-relaxed">
                For power users: register your own OAuth app at the provider and paste the
                Client ID + Secret below. Daena will use YOUR OAuth app instead of an MCP
                server.{' '}
                {connectorId.startsWith('google') && (
                  <a
                    href="https://console.cloud.google.com/apis/credentials"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                  >
                    Open Google Cloud Console <ExternalLink size={10} />
                  </a>
                )}
                {connectorId === 'github' && (
                  <a
                    href="https://github.com/settings/developers"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                  >
                    Open GitHub OAuth apps <ExternalLink size={10} />
                  </a>
                )}
                {connectorId === 'slack' && (
                  <a
                    href="https://api.slack.com/apps"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                  >
                    Open Slack apps <ExternalLink size={10} />
                  </a>
                )}
              </p>
              <div>
                <label className="text-[10px] font-semibold text-starlight-400 uppercase tracking-wider">
                  {missingField}
                </label>
                <input
                  type="text"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="Paste your OAuth Client ID"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-midnight-400 border border-white/5 text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
                />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-starlight-400 uppercase tracking-wider">
                  {secretField}
                </label>
                <input
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  placeholder="Paste your OAuth Client Secret"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-midnight-400 border border-white/5 text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
                />
              </div>
              <p className="text-[10px] text-starlight-500">
                Stored in Daena&apos;s local vault. Never logged, never sent to third parties
                besides {connectorName} itself during consent.
              </p>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  onClick={handleSave}
                  disabled={saving || !clientId.trim() || !clientSecret.trim()}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-200 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                  {saving ? 'Saving...' : 'Save & Enable'}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-white/5">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-xs text-starlight-400 hover:bg-white/5 cursor-pointer"
          >
            Close
          </button>
        </div>
      </motion.div>
    </div>
  )
}

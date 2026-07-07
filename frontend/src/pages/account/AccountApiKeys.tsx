/**
 * AccountApiKeys -- API key management for external access to Daena.
 * Create, list (masked), copy, and revoke API keys.
 */
import { useCallback, useEffect, useState } from 'react'
import { Code, Plus, Key, ExternalLink, Copy, Trash2, Check, AlertTriangle, Eye, EyeOff } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'

interface ApiKeyItem {
  id: string
  name: string
  key_prefix: string
  is_active: boolean
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export function AccountApiKeys() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [justCreatedKey, setJustCreatedKey] = useState<string | null>(null)
  const [showRawKey, setShowRawKey] = useState(false)
  const [revoking, setRevoking] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchKeys = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await api.get('/api-keys')
      setKeys(res.data)
    } catch {
      setKeys([])
      setLoadError('We could not load your API keys. Retry to refresh.')
      toast.error('Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchKeys() }, [fetchKeys])

  const handleCreate = async () => {
    if (!newKeyName.trim()) return
    setCreating(true)
    try {
      const res = await api.post('/api-keys', { name: newKeyName.trim() })
      setJustCreatedKey(res.data.raw_key)
      setShowRawKey(true)
      setNewKeyName('')
      setShowCreate(false)
      toast.success('API key created')
      void fetchKeys()
    } catch {
      toast.error('Failed to create API key')
    } finally {
      setCreating(false)
    }
  }

  const handleRevoke = async (key: ApiKeyItem) => {
    const ok = await confirmDialog({
      title: 'Revoke this API key?',
      message: `Any integration using "${key.name}" will immediately stop working. This cannot be undone -- you would need to create a new key and update every consumer.`,
      confirmLabel: 'Revoke key',
      variant: 'danger',
    })
    if (!ok) return
    setRevoking(key.id)
    try {
      await api.delete(`/api-keys/${key.id}`)
      toast.success('API key revoked')
      void fetchKeys()
    } catch {
      toast.error('Failed to revoke key')
    } finally {
      setRevoking(null)
    }
  }

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const activeKeys = keys.filter(k => k.is_active)
  const revokedKeys = keys.filter(k => !k.is_active)

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-xl font-display font-semibold text-starlight-100">API Platform</h3>
        <p className="text-sm text-starlight-400 mt-1">Manage API keys for programmatic access to Daena</p>
      </div>

      {/* API info card */}
      <div className="p-6 rounded-xl bg-gradient-to-br from-primary-500/10 to-accent-purple/10 border border-primary-500/20 max-w-2xl">
        <div className="flex items-start gap-3">
          <Code size={20} className="text-primary-400 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-starlight-100">Daena API</h4>
            <p className="text-xs text-starlight-400 mt-1">
              Access Daena's governance pipeline, chat, and agent capabilities programmatically.
              API keys authenticate requests to all /api/v1/* endpoints.
            </p>
            <p className="text-[10px] text-starlight-500 mt-2">
              Include your key as: <code className="px-1 py-0.5 rounded bg-midnight-400/50 text-primary-300">Authorization: Bearer dna_...</code>
            </p>
          </div>
        </div>
      </div>

      {/* Just-created key banner */}
      {justCreatedKey && (
        <div className="p-4 rounded-xl bg-status-success/10 border border-status-success/20 max-w-2xl">
          <div className="flex items-start gap-3">
            <AlertTriangle size={16} className="text-status-warning mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-starlight-100">Save your API key now</p>
              <p className="text-[10px] text-starlight-400 mt-0.5">This key will only be shown once. Copy it and store it securely.</p>
              <div className="mt-2 flex items-center gap-2">
                <code className="flex-1 px-3 py-2 rounded-lg bg-midnight-400/80 text-xs font-mono text-primary-300 break-all">
                  {showRawKey ? justCreatedKey : justCreatedKey.slice(0, 12) + '\u2022'.repeat(32)}
                </code>
                <button
                  onClick={() => setShowRawKey(!showRawKey)}
                  className="p-2 rounded-lg hover:bg-white/5 text-starlight-400 cursor-pointer"
                  title={showRawKey ? 'Hide' : 'Reveal'}
                >
                  {showRawKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
                <button
                  onClick={() => void copyToClipboard(justCreatedKey)}
                  className="p-2 rounded-lg hover:bg-white/5 text-starlight-400 cursor-pointer"
                  title={copied ? 'Copied' : 'Copy'}
                >
                  {copied ? <Check size={14} className="text-status-success" /> : <Copy size={14} />}
                </button>
                {/* PR-A11Y-PHASE84 (SC 4.1.3 Status Messages): the copy button's
                    icon swap is silent to screen readers. Announce success via a
                    polite live region -- mirrors ConnectionStatusIndicator's
                    sr-only pattern (no founder-gated <LiveRegion> primitive). */}
                <span className="sr-only" aria-live="polite" aria-atomic="true">
                  {copied ? 'API key copied to clipboard' : ''}
                </span>
              </div>
              <button
                onClick={() => setJustCreatedKey(null)}
                className="mt-2 text-[10px] text-starlight-500 hover:text-starlight-300 cursor-pointer"
              >
                I've saved it, dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API keys list */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium text-starlight-200">
            Your API keys {activeKeys.length > 0 && <span className="text-starlight-500">({activeKeys.length})</span>}
          </h4>
          {!showCreate && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-500/20 text-primary-400 text-xs font-medium hover:bg-primary-500/30 transition-colors cursor-pointer"
            >
              <Plus size={12} /> Create new key
            </button>
          )}
        </div>

        {/* Create form */}
        {showCreate && (
          <div className="p-4 rounded-xl bg-midnight-300/30 border border-white/5 max-w-2xl flex items-end gap-3">
            <div className="flex-1">
              <label htmlFor="apikey-name" className="text-[10px] text-starlight-500 uppercase tracking-wide">Key name</label>
              <input
                id="apikey-name"
                type="text"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
                placeholder="e.g. Production Backend, CI/CD Pipeline"
                className="mt-1 w-full px-3 py-2 rounded-lg bg-midnight-400/50 border border-white/10 text-sm text-starlight-100 placeholder:text-starlight-600 focus:border-primary-500/50 focus:outline-none"
                autoFocus
              />
            </div>
            <button
              onClick={() => void handleCreate()}
              disabled={creating || !newKeyName.trim()}
              className="px-4 py-2 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button
              onClick={() => { setShowCreate(false); setNewKeyName('') }}
              className="px-3 py-2 rounded-lg text-xs text-starlight-400 hover:bg-white/5 cursor-pointer"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Keys table */}
        {loading ? (
          <div className="space-y-2 max-w-2xl">
            {[1, 2].map(i => (
              <div key={i} className="h-14 rounded-lg bg-midnight-300/30 animate-pulse" />
            ))}
          </div>
        ) : loadError ? (
          <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 overflow-hidden max-w-2xl">
            <div className="px-6 py-8 text-center">
              <AlertTriangle size={24} className="mx-auto text-rose-300 mb-3" />
              <p className="text-sm text-rose-200">{loadError}</p>
              <button
                onClick={() => void fetchKeys()}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-500/30 text-xs text-rose-200 hover:bg-rose-500/10 cursor-pointer"
              >
                Retry
              </button>
            </div>
          </div>
        ) : activeKeys.length === 0 ? (
          <div className="rounded-lg border border-white/5 overflow-hidden max-w-2xl">
            <div className="px-6 py-8 text-center">
              <Key size={24} className="mx-auto text-starlight-500 mb-3" />
              <p className="text-sm text-starlight-400">No API keys yet</p>
              <p className="text-xs text-starlight-500 mt-1">Create a key to start using the Daena API</p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-white/5 overflow-hidden max-w-2xl">
            <table className="w-full">
              <thead>
                <tr className="bg-midnight-300/20 border-b border-white/5">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-starlight-400">Name</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-starlight-400">Key</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-starlight-400">Created</th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-starlight-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {activeKeys.map(k => (
                  <tr key={k.id} className="border-b border-white/5 last:border-b-0">
                    <td className="px-4 py-3">
                      <p className="text-sm text-starlight-100">{k.name}</p>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-xs font-mono text-starlight-400">{k.key_prefix}{'*'.repeat(8)}</code>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-starlight-500">
                        {new Date(k.created_at).toLocaleDateString()}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => void handleRevoke(k)}
                        disabled={revoking === k.id}
                        className="p-1.5 rounded hover:bg-status-error/10 text-starlight-500 hover:text-status-error transition-colors cursor-pointer"
                        title="Revoke key"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Revoked keys */}
        {revokedKeys.length > 0 && (
          <div className="mt-6 space-y-2">
            <h4 className="text-xs font-medium text-starlight-500">Revoked keys</h4>
            <div className="space-y-1 max-w-2xl">
              {revokedKeys.map(k => (
                <div key={k.id} className="flex items-center justify-between px-4 py-2 rounded-lg bg-midnight-300/20 opacity-50">
                  <span className="text-xs text-starlight-400">{k.name}</span>
                  <span className="text-[10px] text-starlight-600">
                    Revoked {k.revoked_at ? new Date(k.revoked_at).toLocaleDateString() : ''}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Documentation link */}
      <div className="flex items-center gap-2 text-xs text-starlight-500">
        <ExternalLink size={12} />
        <span>API reference: send any /api/v1/* endpoint with Bearer auth. Full docs in progress.</span>
      </div>
    </div>
  )
}

export default AccountApiKeys

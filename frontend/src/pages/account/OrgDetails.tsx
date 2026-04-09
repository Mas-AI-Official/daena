/**
 * OrgDetails -- Organization name, plan tier, stats.
 * Wired to GET/PATCH /api/v1/org/details.
 */
import { useCallback, useEffect, useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { Building, Crown, Globe, Users, Check, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

interface OrgData {
  id: string
  name: string
  slug: string
  plan: string
  created_at: string | null
  member_count: number
}

export function OrgDetails() {
  const { user } = useAuthStore()
  const [org, setOrg] = useState<OrgData | null>(null)
  const [loading, setLoading] = useState(true)
  const [editName, setEditName] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const fetchOrg = useCallback(async () => {
    try {
      const res = await api.get('/org/details')
      setOrg(res.data)
      setEditName(res.data.name)
    } catch {
      // Graceful -- show static fallback
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchOrg() }, [fetchOrg])

  const handleSave = async () => {
    if (!editName.trim() || editName === org?.name) return
    setSaving(true)
    try {
      const res = await api.patch('/org/details', { name: editName.trim() })
      setOrg(res.data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      toast.success('Organization updated')
    } catch {
      toast.error('Failed to update organization')
    } finally {
      setSaving(false)
    }
  }

  const planColors: Record<string, string> = {
    FREE: 'text-starlight-400',
    PRO: 'text-accent-amber',
    ENTERPRISE: 'text-accent-purple',
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Organization</h1>
        <p className="text-sm text-starlight-400 mt-1">Manage your organization settings</p>
      </div>

      {loading ? (
        <div className="space-y-4 max-w-lg">
          <div className="h-24 rounded-xl bg-midnight-300/30 animate-pulse" />
          <div className="h-16 rounded-lg bg-midnight-300/30 animate-pulse" />
        </div>
      ) : (
        <>
          {/* Org card */}
          <div className="p-6 rounded-xl bg-midnight-300/30 border border-white/5 max-w-lg space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-accent-amber/20 to-accent-purple/20 border border-white/10 flex items-center justify-center">
                <Building size={20} className="text-accent-amber" />
              </div>
              <div>
                <p className="text-sm font-medium text-starlight-100">{org?.name || user?.tenant_name || 'Organization'}</p>
                <p className="text-xs text-starlight-500">{org?.slug || 'org'}</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-midnight-400/30">
                <Crown size={14} className={planColors[org?.plan || 'FREE'] || 'text-starlight-400'} />
                <p className="text-sm font-semibold text-starlight-100 mt-1">{org?.plan || 'Free'}</p>
                <p className="text-[10px] text-starlight-500">Plan</p>
              </div>
              <div className="p-3 rounded-lg bg-midnight-400/30">
                <Users size={14} className="text-accent-cyan" />
                <p className="text-sm font-semibold text-starlight-100 mt-1">{org?.member_count || 1}</p>
                <p className="text-[10px] text-starlight-500">Members</p>
              </div>
              <div className="p-3 rounded-lg bg-midnight-400/30">
                <Globe size={14} className="text-primary-400" />
                <p className="text-sm font-semibold text-starlight-100 mt-1 truncate">mas-ai.co</p>
                <p className="text-[10px] text-starlight-500">Domain</p>
              </div>
            </div>

            {org?.created_at && (
              <p className="text-[10px] text-starlight-600">
                Created {new Date(org.created_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Org name edit */}
          <div className="space-y-2 max-w-lg">
            <label className="text-sm font-medium text-starlight-200">Organization name</label>
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleSave()}
              className="w-full px-3 py-2 rounded-lg bg-midnight-300/50 border border-white/10 text-sm text-starlight-100 focus:border-primary-500/50 focus:outline-none transition-colors"
            />
          </div>

          <button
            onClick={() => void handleSave()}
            disabled={saving || !editName.trim() || editName === org?.name}
            className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 disabled:opacity-50 transition-colors cursor-pointer"
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : saved ? (
              <Check size={14} />
            ) : null}
            {saving ? 'Saving...' : saved ? 'Saved' : 'Save changes'}
          </button>
        </>
      )}
    </div>
  )
}

export default OrgDetails

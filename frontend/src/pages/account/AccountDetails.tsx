/**
 * AccountDetails -- Profile management: display name, email, avatar, password, OAuth connections.
 */
import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { User, Mail, Shield, Camera, Key } from 'lucide-react'

export function AccountDetails() {
  const { user } = useAuthStore()
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/settings/user', { display_name: displayName })
      toast.success('Profile updated')
    } catch {
      toast.error('Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Account</h1>
        <p className="text-sm text-starlight-400 mt-1">Manage your personal account settings</p>
      </div>

      {/* Avatar */}
      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary-500 to-accent-purple flex items-center justify-center text-2xl font-bold text-white">
            {user?.display_name?.charAt(0)?.toUpperCase() || 'D'}
          </div>
          <button className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-midnight-300 border border-white/10 flex items-center justify-center text-starlight-400 hover:text-starlight-100 transition-colors cursor-pointer">
            <Camera size={12} />
          </button>
        </div>
        <div>
          <p className="text-sm font-medium text-starlight-100">{user?.display_name || 'User'}</p>
          <p className="text-xs text-starlight-500">{user?.role || 'USER'}</p>
        </div>
      </div>

      {/* Display Name */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <User size={14} /> Display Name
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="w-full max-w-md px-3 py-2 rounded-lg bg-midnight-300/50 border border-white/10 text-sm text-starlight-100 focus:border-primary-500/50 focus:outline-none transition-colors"
        />
      </div>

      {/* Email */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Mail size={14} /> Email
        </label>
        <p className="text-sm text-starlight-300 px-3 py-2 rounded-lg bg-midnight-300/30 border border-white/5 max-w-md">
          {user?.email || 'Not set'}
        </p>
        {user?.email_verified && (
          <p className="text-xs text-status-success flex items-center gap-1">
            <Shield size={10} /> Verified
          </p>
        )}
      </div>

      {/* Password */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Key size={14} /> Password
        </label>
        <button className="px-4 py-2 rounded-lg bg-midnight-300/50 border border-white/10 text-sm text-starlight-300 hover:text-starlight-100 hover:border-white/20 transition-colors cursor-pointer">
          Change password
        </button>
      </div>

      {/* OAuth Connections */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-starlight-200">Connected accounts</h3>
        <div className="space-y-2 max-w-md">
          {['Google', 'GitHub'].map((provider) => (
            <div key={provider} className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5">
              <span className="text-sm text-starlight-300">{provider}</span>
              <button className="text-xs text-primary-400 hover:text-primary-300 transition-colors cursor-pointer">
                {user?.oauth_provider === provider.toLowerCase() ? 'Connected' : 'Connect'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Save */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="px-6 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors disabled:opacity-50 cursor-pointer"
      >
        {saving ? 'Saving...' : 'Save changes'}
      </button>
    </div>
  )
}

export default AccountDetails

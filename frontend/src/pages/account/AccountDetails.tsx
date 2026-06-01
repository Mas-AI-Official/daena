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

      {/* Password
        *
        * ADR-001 honesty (2026-06-01): the Change Password button was a
        * dead control - clicking it did nothing (no onClick handler, no
        * backend route to call). Disabled + Coming Soon label until the
        * /auth/change-password flow ships. Founder workaround in the
        * meantime: use the password reset email flow (/forgot-password).
        */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Key size={14} /> Password
        </label>
        <button
          disabled
          title="Use the password reset email flow at /forgot-password until in-app change ships."
          className="px-4 py-2 rounded-lg bg-midnight-300/30 border border-white/5 text-sm text-starlight-500 cursor-not-allowed flex items-center gap-2"
        >
          Change password
          <span className="text-[10px] uppercase tracking-wider text-starlight-600 px-1.5 py-0.5 rounded bg-midnight-400/60">
            Coming soon
          </span>
        </button>
      </div>

      {/* OAuth Connections
        *
        * ADR-001 honesty (2026-06-01): the prior version of this panel
        * hardcoded the 'Google' and 'GitHub' rows even when the user had
        * never connected them - the only real signal was a string compare
        * against user.oauth_provider, so the Connect buttons did nothing.
        * Replaced with an honest reference to the /connections page (where
        * real OAuth instances are managed, lifecycle-tracked, and tested).
        */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-starlight-200">Connected accounts</h3>
        <p className="text-xs text-starlight-500 max-w-md">
          {user?.oauth_provider
            ? `Signed in via ${user.oauth_provider}.`
            : 'No OAuth provider linked to this account.'}
          {' '}
          Manage all OAuth connections from the
          {' '}
          <a
            href="/connections"
            className="text-primary-400 hover:text-primary-300 underline underline-offset-2"
          >
            Connections page
          </a>
          .
        </p>
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

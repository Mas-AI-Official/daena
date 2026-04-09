/**
 * OrgMembers -- Team member management with role assignment.
 * Wired to GET /api/v1/org/members, PATCH role, DELETE deactivate.
 */
import { useCallback, useEffect, useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { Users, Plus, Shield, Crown, Trash2, ChevronDown, Loader2, UserX } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

interface Member {
  id: string
  email: string
  display_name: string | null
  role: string
  is_active: boolean
  last_login: string | null
  created_at: string | null
}

const ROLE_BADGES: Record<string, { label: string; color: string; icon: typeof Crown }> = {
  FOUNDER: { label: 'Founder', color: 'text-accent-amber', icon: Crown },
  ADMIN: { label: 'Admin', color: 'text-accent-purple', icon: Shield },
  MEMBER: { label: 'Member', color: 'text-starlight-400', icon: Users },
  VIEWER: { label: 'Viewer', color: 'text-starlight-500', icon: Users },
}

export function OrgMembers() {
  const { user } = useAuthStore()
  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)
  const [roleDropdown, setRoleDropdown] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)

  const fetchMembers = useCallback(async () => {
    try {
      const res = await api.get('/org/members')
      setMembers(res.data)
    } catch {
      // Graceful
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchMembers() }, [fetchMembers])

  const handleRoleChange = async (memberId: string, newRole: string) => {
    setRoleDropdown(null)
    try {
      await api.patch(`/org/members/${memberId}/role`, { role: newRole })
      toast.success('Role updated')
      void fetchMembers()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update role'
      toast.error(msg)
    }
  }

  const handleRemove = async (memberId: string) => {
    setRemoving(memberId)
    try {
      await api.delete(`/org/members/${memberId}`)
      toast.success('Member deactivated')
      void fetchMembers()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to remove member'
      toast.error(msg)
    } finally {
      setRemoving(null)
    }
  }

  const activeMembers = members.filter(m => m.is_active)
  const inactiveMembers = members.filter(m => !m.is_active)
  const isAdmin = user?.role === 'FOUNDER' || user?.role === 'ADMIN'

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-display font-semibold text-starlight-100">Members</h1>
          <p className="text-sm text-starlight-400 mt-1">
            Manage who has access to your organization
            {activeMembers.length > 0 && (
              <span className="text-starlight-500"> -- {activeMembers.length} active</span>
            )}
          </p>
        </div>
        {isAdmin && (
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary-500/20 text-primary-400 text-xs font-medium hover:bg-primary-500/30 transition-colors cursor-pointer">
            <Plus size={12} /> Invite member
          </button>
        )}
      </div>

      {/* Members table */}
      {loading ? (
        <div className="space-y-2 max-w-2xl">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 rounded-lg bg-midnight-300/30 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-white/5 overflow-hidden max-w-2xl">
          <table className="w-full">
            <thead>
              <tr className="bg-midnight-300/20 border-b border-white/5">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-starlight-400">Member</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-starlight-400">Role</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-starlight-400">Last active</th>
                {isAdmin && (
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-starlight-400">Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {activeMembers.map(m => {
                const badge = ROLE_BADGES[m.role] || ROLE_BADGES.MEMBER
                const BadgeIcon = badge.icon
                const isSelf = m.id === String(user?.id || '')
                const isFounder = m.role === 'FOUNDER'

                return (
                  <tr key={m.id} className="border-b border-white/5 last:border-b-0 hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-accent-purple flex items-center justify-center text-xs font-bold text-white shrink-0">
                          {(m.display_name || m.email).charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm text-starlight-100 truncate">
                            {m.display_name || m.email.split('@')[0]}
                            {isSelf && <span className="text-[10px] text-starlight-500 ml-1">(you)</span>}
                          </p>
                          <p className="text-[10px] text-starlight-500 truncate">{m.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="relative">
                        {isAdmin && !isFounder && !isSelf ? (
                          <button
                            onClick={() => setRoleDropdown(roleDropdown === m.id ? null : m.id)}
                            className={`flex items-center gap-1 text-xs ${badge.color} hover:bg-white/5 px-2 py-1 rounded cursor-pointer`}
                          >
                            <BadgeIcon size={10} />
                            {badge.label}
                            <ChevronDown size={10} />
                          </button>
                        ) : (
                          <span className={`flex items-center gap-1 text-xs ${badge.color}`}>
                            <BadgeIcon size={10} /> {badge.label}
                          </span>
                        )}

                        {/* Role dropdown */}
                        {roleDropdown === m.id && (
                          <div className="absolute top-full left-0 mt-1 z-10 bg-midnight-300 border border-white/10 rounded-lg shadow-xl py-1 min-w-[120px]">
                            {['ADMIN', 'MEMBER', 'VIEWER'].map(role => (
                              <button
                                key={role}
                                onClick={() => void handleRoleChange(m.id, role)}
                                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-white/5 cursor-pointer ${
                                  m.role === role ? 'text-primary-400' : 'text-starlight-300'
                                }`}
                              >
                                {ROLE_BADGES[role]?.label || role}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-starlight-500">
                        {m.last_login
                          ? new Date(m.last_login).toLocaleDateString()
                          : 'Never'}
                      </p>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        {!isFounder && !isSelf && (
                          <button
                            onClick={() => void handleRemove(m.id)}
                            disabled={removing === m.id}
                            className="p-1.5 rounded hover:bg-status-error/10 text-starlight-500 hover:text-status-error transition-colors cursor-pointer"
                            title="Deactivate member"
                          >
                            {removing === m.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Inactive members */}
      {inactiveMembers.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-starlight-400 flex items-center gap-2">
            <UserX size={14} /> Deactivated members
          </h3>
          <div className="space-y-1 max-w-2xl">
            {inactiveMembers.map(m => (
              <div key={m.id} className="flex items-center justify-between px-4 py-2 rounded-lg bg-midnight-300/20 opacity-50">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-midnight-400 flex items-center justify-center text-[10px] text-starlight-500">
                    {(m.display_name || m.email).charAt(0).toUpperCase()}
                  </div>
                  <span className="text-xs text-starlight-400">{m.display_name || m.email}</span>
                </div>
                <span className="text-[10px] text-starlight-600">{m.role}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default OrgMembers

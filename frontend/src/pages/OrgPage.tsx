/**
 * OrgPage -- Organization (tenant) management surface.
 *
 * The ENTERPRISE seat-management view: org details, team members, and an
 * org-level spend rollup. Consumes app/api/v1/org.py:
 *   GET    /org/details              -- name, slug, plan, member_count
 *   PATCH  /org/details              -- rename (ADMIN+)
 *   GET    /org/members             -- roster
 *   POST   /org/members             -- invite a seat (ADMIN+)
 *   PATCH  /org/members/{id}/role    -- change role (ADMIN+)
 *   DELETE /org/members/{id}         -- deactivate (ADMIN+)
 *   GET    /org/billing             -- spend, tokens, per-member breakdown
 *
 * Honesty (Rule 17): Daena has no transactional email path, so an invite
 * returns a one-time temporary password and email_sent=false. The UI surfaces
 * that password for the admin to share securely -- it never shows a fake
 * "invitation sent" state. Admin-only controls render only for ADMIN/FOUNDER
 * (the roles require_role("ADMIN") actually grants), so a viewer never sees a
 * button that would 403. Per-component inline error state, no toast-only.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Building2,
  ChevronLeft,
  Settings as SettingsIcon,
  AlertCircle,
  Loader2,
  UserPlus,
  Copy,
  ShieldCheck,
  UserMinus,
  KeyRound,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { useAuthStore } from '@/stores/authStore'
import { usePageTitle } from '@/hooks/usePageTitle'

// --- Types (mirror org.py response models) ---

interface OrgDetails {
  id: string
  name: string
  slug: string
  plan: string
  created_at: string | null
  member_count: number
}

interface OrgMember {
  id: string
  email: string
  display_name: string | null
  role: string
  is_active: boolean
  last_login: string | null
  created_at: string | null
}

interface InviteResult {
  member: OrgMember
  temporary_password: string
  email_sent: boolean
  message: string
}

interface MemberSpend {
  name: string
  email: string
  spend_usd: number
}

interface OrgBilling {
  total_spend_usd: number
  total_tokens: number
  active_members: number
  spend_by_member: MemberSpend[]
}

// Roles require_role("ADMIN") actually grants (UserRole level >= ADMIN). Gating
// the controls on exactly these avoids rendering a button that would 403.
const ADMIN_ROLES = ['ADMIN', 'FOUNDER']
// Roles PATCH /members/{id}/role accepts (org.py UpdateMemberRoleRequest).
const ASSIGNABLE_ROLES = ['VIEWER', 'MEMBER', 'ADMIN']

function extractDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  const message = (detail as { message?: string } | undefined)?.message
  return typeof message === 'string' ? message : fallback
}

function fmtDate(iso: string | null): string {
  if (!iso) return '--'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '--' : d.toLocaleDateString()
}

function fmtUsd(n: number): string {
  return `$${(n || 0).toFixed(2)}`
}

function ErrorBox({ message, role }: { message: string; role?: string }) {
  return (
    <div role={role} className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">
      <AlertCircle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

function SectionLoader() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-4 w-48 rounded bg-white/5" />
      <div className="h-4 w-64 rounded bg-white/[0.03]" />
      <div className="h-4 w-40 rounded bg-white/[0.03]" />
    </div>
  )
}

export function OrgPage() {
  usePageTitle('Organization')
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const isAdmin = ADMIN_ROLES.includes((user?.role || '').toUpperCase())
  const currentUserId = user?.user_id || ''

  // Org details
  const [details, setDetails] = useState<OrgDetails | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(true)
  const [detailsError, setDetailsError] = useState<string | null>(null)
  const [nameDraft, setNameDraft] = useState('')
  const [savingName, setSavingName] = useState(false)

  // Members
  const [members, setMembers] = useState<OrgMember[] | null>(null)
  const [membersLoading, setMembersLoading] = useState(true)
  const [membersError, setMembersError] = useState<string | null>(null)
  const [pendingMemberId, setPendingMemberId] = useState<string | null>(null)

  // Invite
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('MEMBER')
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null)

  // Billing rollup
  const [billing, setBilling] = useState<OrgBilling | null>(null)
  const [billingLoading, setBillingLoading] = useState(true)
  const [billingError, setBillingError] = useState<string | null>(null)

  const loadDetails = useCallback(async () => {
    setDetailsLoading(true)
    setDetailsError(null)
    try {
      const res = await api.get<OrgDetails>('/org/details')
      setDetails(res.data)
      setNameDraft(res.data.name)
    } catch (err) {
      setDetailsError(extractDetail(err, 'Could not load organization details'))
    } finally {
      setDetailsLoading(false)
    }
  }, [])

  const loadMembers = useCallback(async () => {
    setMembersLoading(true)
    setMembersError(null)
    try {
      const res = await api.get<OrgMember[]>('/org/members')
      setMembers(res.data)
    } catch (err) {
      setMembersError(extractDetail(err, 'Could not load team members'))
    } finally {
      setMembersLoading(false)
    }
  }, [])

  const loadBilling = useCallback(async () => {
    setBillingLoading(true)
    setBillingError(null)
    try {
      const res = await api.get<OrgBilling>('/org/billing')
      setBilling(res.data)
    } catch (err) {
      setBillingError(extractDetail(err, 'Could not load billing summary'))
    } finally {
      setBillingLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDetails()
    loadMembers()
    loadBilling()
  }, [loadDetails, loadMembers, loadBilling])

  const saveName = useCallback(async () => {
    const next = nameDraft.trim()
    if (!next || next === details?.name) return
    setSavingName(true)
    try {
      const res = await api.patch<OrgDetails>('/org/details', { name: next })
      setDetails(res.data)
      setNameDraft(res.data.name)
      toast.success('Organization name updated')
    } catch (err) {
      const msg = extractDetail(err, 'Could not update name')
      setDetailsError(msg)
      toast.error(msg)
    } finally {
      setSavingName(false)
    }
  }, [nameDraft, details])

  const invite = useCallback(async () => {
    const email = inviteEmail.trim()
    if (!email) return
    setInviting(true)
    setInviteError(null)
    setInviteResult(null)
    try {
      const res = await api.post<InviteResult>('/org/members', { email, role: inviteRole })
      setInviteResult(res.data)
      setInviteEmail('')
      toast.success('Member seat created')
      loadMembers()
      loadBilling()
    } catch (err) {
      setInviteError(extractDetail(err, 'Could not create the member'))
    } finally {
      setInviting(false)
    }
  }, [inviteEmail, inviteRole, loadMembers, loadBilling])

  const changeRole = useCallback(
    async (member: OrgMember, role: string) => {
      if (role === member.role) return
      setPendingMemberId(member.id)
      try {
        await api.patch(`/org/members/${member.id}/role`, { role })
        toast.success(`Role updated to ${role}`)
        loadMembers()
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 404) {
          // The member was removed by another admin while this row was on screen.
          // Reconcile the stale roster instead of leaving a live-looking ghost row.
          toast.error('This member was already removed. Refreshing the list.')
          loadMembers()
        } else {
          const msg = extractDetail(err, 'Could not change role')
          setMembersError(msg)
          toast.error(msg)
        }
      } finally {
        setPendingMemberId(null)
      }
    },
    [loadMembers],
  )

  const deactivate = useCallback(
    async (member: OrgMember) => {
      const ok = await confirmDialog({
        title: 'Deactivate this member?',
        message: `${member.display_name || member.email} will immediately lose access to this organization. You can re-invite them later as a new seat.`,
        confirmLabel: 'Deactivate',
        variant: 'danger',
      })
      if (!ok) return
      setPendingMemberId(member.id)
      try {
        await api.delete(`/org/members/${member.id}`)
        toast.success('Member deactivated')
        loadMembers()
        loadBilling()
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 404) {
          // Another admin already deactivated this member; reconcile the stale
          // roster and spend rollup rather than leaving a ghost row that looks live.
          toast.error('This member was already removed. Refreshing the list.')
          loadMembers()
          loadBilling()
        } else {
          const msg = extractDetail(err, 'Could not deactivate member')
          setMembersError(msg)
          toast.error(msg)
        }
      } finally {
        setPendingMemberId(null)
      }
    },
    [loadMembers, loadBilling],
  )

  const copyTempPassword = useCallback(async () => {
    if (!inviteResult) return
    try {
      await navigator.clipboard.writeText(inviteResult.temporary_password)
      toast.success('Temporary password copied')
    } catch {
      toast.error('Copy failed -- select and copy it manually')
    }
  }, [inviteResult])

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <button
              onClick={() => navigate('/chat')}
              className="inline-flex items-center gap-1.5 text-xs text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer mb-2"
            >
              <ChevronLeft size={12} /> Home
            </button>
            <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
              <Building2 size={22} className="text-primary-500" />
              {details?.name || 'Organization'}
            </h1>
            <p className="text-sm text-starlight-400">
              Manage your team, seats, and organization details.
            </p>
          </div>
          <button
            onClick={() => navigate('/settings')}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs text-starlight-400 border border-white/10 hover:border-white/20 hover:text-starlight-200 transition-colors cursor-pointer"
          >
            <SettingsIcon size={12} /> All Settings
          </button>
        </motion.div>

        {/* Org Details */}
        <section>
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">
            Organization details
          </h2>
          {detailsLoading ? (
            <SectionLoader />
          ) : detailsError ? (
            <ErrorBox message={detailsError} role="alert" />
          ) : details ? (
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
              <div>
                <label className="block text-xs text-starlight-400 mb-1.5">Name</label>
                {isAdmin ? (
                  <div className="flex items-center gap-2">
                    <input
                      aria-label="Organization name"
                      value={nameDraft}
                      onChange={(e) => setNameDraft(e.target.value)}
                      maxLength={255}
                      className="flex-1 rounded-lg border border-white/10 bg-midnight-400/40 px-3 py-2 text-sm text-starlight-100 outline-none focus:border-primary-500/50"
                    />
                    <button
                      onClick={saveName}
                      disabled={savingName || !nameDraft.trim() || nameDraft.trim() === details.name}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {savingName && <Loader2 size={14} className="animate-spin" />}
                      Save
                    </button>
                  </div>
                ) : (
                  <p className="text-sm text-starlight-100">{details.name}</p>
                )}
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-xs text-starlight-400 mb-1">Plan</div>
                  <span className="inline-flex items-center rounded-md bg-primary-500/15 px-2 py-0.5 text-xs font-medium text-primary-300">
                    {details.plan}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-starlight-400 mb-1">Members</div>
                  <div className="text-starlight-100">{details.member_count}</div>
                </div>
                <div>
                  <div className="text-xs text-starlight-400 mb-1">Created</div>
                  <div className="text-starlight-100">{fmtDate(details.created_at)}</div>
                </div>
              </div>
              <div className="text-xs text-starlight-500">
                Slug: <span className="font-mono text-starlight-400">{details.slug}</span>
              </div>
            </div>
          ) : null}
        </section>

        {/* Team Members */}
        <section className="pt-4 border-t border-white/5">
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">
            Team members
          </h2>

          {/* Invite (admin only) */}
          {isAdmin && (
            <div className="mb-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <div className="flex flex-wrap items-end gap-2">
                <div className="flex-1 min-w-[180px]">
                  <label htmlFor="org-invite-email" className="block text-xs text-starlight-400 mb-1.5">Invite by email</label>
                  <input
                    id="org-invite-email"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="teammate@company.com"
                    autoComplete="off"
                    className="w-full rounded-lg border border-white/10 bg-midnight-400/40 px-3 py-2 text-sm text-starlight-100 outline-none focus:border-primary-500/50"
                  />
                </div>
                <div>
                  <label htmlFor="org-invite-role" className="block text-xs text-starlight-400 mb-1.5">Role</label>
                  <select
                    id="org-invite-role"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="rounded-lg border border-white/10 bg-midnight-400/40 px-3 py-2 text-sm text-starlight-100 outline-none focus:border-primary-500/50"
                  >
                    <option value="MEMBER">Member</option>
                    <option value="ADMIN">Admin</option>
                  </select>
                </div>
                <button
                  onClick={invite}
                  disabled={inviting || !inviteEmail.trim()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {inviting ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
                  Invite
                </button>
              </div>

              {inviteError && (
                <div className="mt-3">
                  <ErrorBox message={inviteError} />
                </div>
              )}

              {/* Honest invite result: no email path, surface the temp password. */}
              {inviteResult && (
                <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-amber-200">
                    <KeyRound size={15} />
                    Seat created for {inviteResult.member.email}
                  </div>
                  <p className="mt-1.5 text-xs text-amber-100/80">{inviteResult.message}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <code className="flex-1 truncate rounded-md bg-midnight-400/60 px-2.5 py-1.5 font-mono text-sm text-starlight-100">
                      {inviteResult.temporary_password}
                    </code>
                    <button
                      onClick={copyTempPassword}
                      className="inline-flex items-center gap-1.5 rounded-md border border-white/15 px-2.5 py-1.5 text-xs text-starlight-200 transition-colors hover:border-white/30"
                    >
                      <Copy size={13} /> Copy
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {membersLoading ? (
            <SectionLoader />
          ) : membersError ? (
            <ErrorBox message={membersError} role="alert" />
          ) : members && members.length > 0 ? (
            <div className="overflow-hidden rounded-xl border border-white/10">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/[0.02] text-left text-xs text-starlight-400">
                    <th className="px-3 py-2 font-medium">Member</th>
                    <th className="px-3 py-2 font-medium">Role</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">Last login</th>
                    {isAdmin && <th className="px-3 py-2" />}
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => {
                    const isSelf = m.id === currentUserId
                    const isFounder = m.role.toUpperCase() === 'FOUNDER'
                    const locked = isSelf || isFounder
                    const busy = pendingMemberId === m.id
                    const roleOptions = ASSIGNABLE_ROLES.includes(m.role)
                      ? ASSIGNABLE_ROLES
                      : [m.role, ...ASSIGNABLE_ROLES]
                    return (
                      <tr key={m.id} className="border-b border-white/5 last:border-0">
                        <td className="px-3 py-2.5">
                          <div className="text-starlight-100">{m.display_name || m.email.split('@')[0]}</div>
                          <div className="text-xs text-starlight-500">{m.email}</div>
                        </td>
                        <td className="px-3 py-2.5">
                          {isAdmin && !locked ? (
                            <select
                              aria-label={`Role for ${m.display_name || m.email}`}
                              value={m.role}
                              disabled={busy}
                              onChange={(e) => changeRole(m, e.target.value)}
                              className="rounded-md border border-white/10 bg-midnight-400/40 px-2 py-1 text-xs text-starlight-100 outline-none focus:border-primary-500/50 disabled:opacity-50"
                            >
                              {roleOptions.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-starlight-300">
                              {isFounder && <ShieldCheck size={12} className="text-primary-400" />}
                              {m.role}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          {m.is_active ? (
                            <span className="inline-flex items-center rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center rounded-md bg-white/5 px-2 py-0.5 text-xs text-starlight-500">
                              Inactive
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-starlight-400">{fmtDate(m.last_login)}</td>
                        {isAdmin && (
                          <td className="px-3 py-2.5 text-right">
                            {!locked && m.is_active && (
                              <button
                                onClick={() => deactivate(m)}
                                disabled={busy}
                                title="Deactivate member"
                                className="inline-flex items-center gap-1 rounded-md border border-rose-500/30 px-2 py-1 text-xs text-rose-300 transition-colors hover:bg-rose-500/10 disabled:opacity-40"
                              >
                                {busy ? <Loader2 size={12} className="animate-spin" /> : <UserMinus size={12} />}
                                Remove
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
          ) : (
            <p className="text-sm text-starlight-400">No members yet.</p>
          )}

          {!isAdmin && (
            <p className="mt-2 text-xs text-starlight-500">
              Inviting and managing members requires an admin role.
            </p>
          )}
        </section>

        {/* Usage and Spend */}
        <section className="pt-4 border-t border-white/5">
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">
            Usage and spend
          </h2>
          {billingLoading ? (
            <SectionLoader />
          ) : billingError ? (
            <ErrorBox message={billingError} />
          ) : billing ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="text-xs text-starlight-400">Total spend</div>
                  <div className="mt-1 text-lg font-semibold text-starlight-100">
                    {fmtUsd(billing.total_spend_usd)}
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="text-xs text-starlight-400">Total tokens</div>
                  <div className="mt-1 text-lg font-semibold text-starlight-100">
                    {billing.total_tokens.toLocaleString()}
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="text-xs text-starlight-400">Active members</div>
                  <div className="mt-1 text-lg font-semibold text-starlight-100">
                    {billing.active_members}
                  </div>
                </div>
              </div>

              {billing.spend_by_member.length > 0 && (
                <div className="overflow-hidden rounded-xl border border-white/10">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10 bg-white/[0.02] text-left text-xs text-starlight-400">
                        <th className="px-3 py-2 font-medium">Member</th>
                        <th className="px-3 py-2 text-right font-medium">Spend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billing.spend_by_member.map((s) => (
                        <tr key={s.email} className="border-b border-white/5 last:border-0">
                          <td className="px-3 py-2.5">
                            <div className="text-starlight-100">{s.name}</div>
                            <div className="text-xs text-starlight-500">{s.email}</div>
                          </td>
                          <td className="px-3 py-2.5 text-right text-starlight-200">
                            {fmtUsd(s.spend_usd)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}

export default OrgPage

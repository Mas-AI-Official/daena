/**
 * SettingsNotifications -- notification preferences tab.
 * All toggles persist to backend via PUT /settings/user JSONB.
 *
 * Phase 11 PR-S2 (2026-05-01): backend now consumes the per-event
 * notif_* flags via NotificationService. Five per-event toggles flip
 * from "Coming soon" to "Enforced by backend." Sound / Email / Daily
 * Digest stay disabled because there is no delivery channel for them
 * yet (no audio pipeline, no SMTP, no scheduler-driven digest job).
 */
import { useState, useEffect } from 'react'
import { Bell, Volume2, Mail, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Card, Switch, Badge } from '@/components/common'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { persistUiPref } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'

export function SettingsNotifications() {
  const userEmail = useAuthStore((s) => s.user?.email || '')
  const [desktop, setDesktop] = useState(true)
  const [taskComplete, setTaskComplete] = useState(true)
  const [budgetAlert, setBudgetAlert] = useState(true)
  const [heartbeat, setHeartbeat] = useState(true)
  const [govReject, setGovReject] = useState(true)
  const [runtimeDisc, setRuntimeDisc] = useState(true)
  const [sound, setSound] = useState(false)
  const [emailEnabled, setEmailEnabled] = useState(false)
  const [dailyDigest, setDailyDigest] = useState(false)
  const [sendingTest, setSendingTest] = useState(false)
  const emailConfigured = false

  // Hydrate from backend on mount
  useEffect(() => {
    api.get('/settings/user').then(res => {
      const d = res.data?.data
      if (!d) return
      if (d.notif_desktop != null) setDesktop(d.notif_desktop)
      if (d.notif_task_complete != null) setTaskComplete(d.notif_task_complete)
      if (d.notif_budget_alert != null) setBudgetAlert(d.notif_budget_alert)
      if (d.notif_heartbeat != null) setHeartbeat(d.notif_heartbeat)
      if (d.notif_gov_reject != null) setGovReject(d.notif_gov_reject)
      if (d.notif_runtime_disconnect != null) setRuntimeDisc(d.notif_runtime_disconnect)
      if (d.notif_sound != null) setSound(d.notif_sound)
      if (d.notif_email != null) setEmailEnabled(d.notif_email)
      if (d.notif_daily_digest != null) setDailyDigest(d.notif_daily_digest)
    }).catch(() => {})
  }, [])

  const [permStatus, setPermStatus] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  )

  const requestPermission = async () => {
    if (typeof Notification === 'undefined') return
    const result = await Notification.requestPermission()
    setPermStatus(result)
    if (result === 'granted') {
      new Notification('Daena Notifications Enabled', {
        body: 'You will now receive desktop notifications for important events.',
        icon: '/daena-blue.png',
      })
    }
  }

  const toggle = (key: string, current: boolean, setter: (v: boolean) => void) => {
    setter(!current)
    persistUiPref(key, !current)
  }

  /**
   * Phase 11 PR-S2: real backend test.
   *
   * 1. POST /api/v1/notifications/test → backend creates a system_info
   *    row in `notifications` table (unconditionally — system_info
   *    bypasses per-event flags so the user sees confirmation that
   *    the plumbing works).
   * 2. Push the row into the in-memory uiStore so it shows in the
   *    bell immediately (no need to wait for next dropdown open).
   * 3. If the user has granted browser permission AND notif_desktop
   *    is on, also fire an OS notification.
   * 4. Toast on success / failure.
   */
  const handleSendTest = async () => {
    setSendingTest(true)
    try {
      const res = await api.post('/notifications/test', {
        title: 'Test from Daena',
        message: 'Notifications are working correctly!',
        severity: 'info',
      })
      const row = res.data?.data
      // Push into the bell store so it shows immediately.
      const { useUiStore } = await import('@/stores/uiStore')
      useUiStore.setState((s) => ({
        notifications: [
          {
            id: row?.id ?? crypto.randomUUID(),
            type: 'info',
            title: row?.title ?? 'Test from Daena',
            message: row?.message ?? 'Notifications are working correctly!',
            timestamp: row?.created_at
              ? new Date(row.created_at).getTime()
              : Date.now(),
          },
          ...s.notifications,
        ],
      }))
      // Fire OS notification only if the user has both granted
      // permission AND the master desktop toggle is on. (Master toggle
      // is a client-side gate; per-event toggles affect only what the
      // backend persists.)
      if (desktop && permStatus === 'granted') {
        new Notification('Test from Daena', {
          body: 'Notifications are working correctly!',
          icon: '/daena-blue.png',
        })
      }
      toast.success('Test notification sent. Check the bell in the header.')
    } catch {
      toast.error('Failed to send test notification.')
    } finally {
      setSendingTest(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Desktop */}
      <section className="space-y-3">
        <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
          <Bell size={14} className="text-primary-400" />
          Desktop Notifications
        </h3>
        <Card variant="glass" padding="md" className="space-y-3">
          <div
            className="flex items-center justify-between"
            title="Master gate: controls whether the browser asks for OS notification permission and whether the Send Test button fires an OS notification. Per-event toggles below now have a real backend consumer (Phase 11 PR-S2)."
          >
            <div>
              <p className="text-sm text-starlight-200">Enable desktop notifications</p>
              <p className="text-[10px] text-starlight-500">Show system notifications for important events. (Master gate is client-side; in-app rows are governed by per-event toggles below.)</p>
            </div>
            <Switch checked={desktop} onChange={() => toggle('notif_desktop', desktop, setDesktop)} label="" size="sm" />
          </div>
          {desktop && permStatus !== 'granted' && (
            <div className="mt-2 px-3 py-2 rounded-lg bg-accent-amber/10 border border-accent-amber/20 flex items-center justify-between">
              <p className="text-[10px] text-accent-amber">Browser notifications need permission to work.</p>
              <button
                onClick={requestPermission}
                className="text-[10px] font-medium text-accent-amber hover:text-accent-amber/80 underline cursor-pointer"
              >
                Grant Permission
              </button>
            </div>
          )}
          {desktop && permStatus === 'granted' && (
            <div className="mt-2 px-3 py-2 rounded-lg bg-status-success/10 border border-status-success/20">
              <p className="text-[10px] text-status-success flex items-center gap-1">
                <CheckCircle2 size={10} /> Desktop notifications are active
              </p>
            </div>
          )}
          {desktop && (
            <div
              className="pl-4 border-l border-white/10 space-y-3 mt-1"
              title="Phase 11 PR-S2 / PR-S2.1: per-event toggles gate in-app row creation. NotificationService.emit reads users.settings.notif_<type> and skips writing the row when the matching flag is False. Three event types have real emitters today; two have the gate but no emitter source yet (Backlog P1-03; PR-NOTIF-FANOUT)."
            >
              <p className="text-[10px] text-status-success flex items-center gap-1.5">
                <Badge variant="success" size="sm">Enforced by backend</Badge>
                In-app rows for these events land in the bell. OS notifications still require browser permission above.
              </p>
              <div
                className="flex items-center justify-between"
                title="Real emitter: chat_orchestrator emits notif_task_complete on Workstream / task COMPLETE."
              >
                <p className="text-xs text-starlight-300">Task completion</p>
                <Switch checked={taskComplete} onChange={() => toggle('notif_task_complete', taskComplete, setTaskComplete)} label="" size="sm" />
              </div>
              <div
                className="flex items-center justify-between"
                title="Real emitter: cost_guard fires budget_alert when spend crosses threshold (PR-S2.1)."
              >
                <p className="text-xs text-starlight-300">Budget alerts</p>
                <Switch checked={budgetAlert} onChange={() => toggle('notif_budget_alert', budgetAlert, setBudgetAlert)} label="" size="sm" />
              </div>
              <div
                className="flex items-center justify-between"
                title="Backlog P1-03: gate is wired (NotificationService respects the flag) but no service emits with type=heartbeat today; per-tenant fan-out pending PR-NOTIF-FANOUT."
              >
                <div className="flex items-center gap-2">
                  <p className="text-xs text-starlight-300">Daena Heartbeat findings</p>
                  <Badge variant="warning" size="sm">Source pending</Badge>
                </div>
                <Switch checked={heartbeat} onChange={() => toggle('notif_heartbeat', heartbeat, setHeartbeat)} label="" size="sm" />
              </div>
              <div
                className="flex items-center justify-between"
                title="Real emitter: governance/SecurityGate emits notif_gov_reject when an action is BLOCKED (PR-S2)."
              >
                <p className="text-xs text-starlight-300">Governance rejections</p>
                <Switch checked={govReject} onChange={() => toggle('notif_gov_reject', govReject, setGovReject)} label="" size="sm" />
              </div>
              <div
                className="flex items-center justify-between"
                title="Backlog P1-03: gate is wired but the runtime health tracker is a process-wide singleton with no per-tenant scope; no service emits notif_runtime_disconnect today. PR-NOTIF-FANOUT closes this."
              >
                <div className="flex items-center gap-2">
                  <p className="text-xs text-starlight-300">Runtime disconnection</p>
                  <Badge variant="warning" size="sm">Source pending</Badge>
                </div>
                <Switch checked={runtimeDisc} onChange={() => toggle('notif_runtime_disconnect', runtimeDisc, setRuntimeDisc)} label="" size="sm" />
              </div>
            </div>
          )}
        </Card>
      </section>

      {/* Sound */}
      <section className="space-y-3">
        <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
          <Volume2 size={14} className="text-primary-400" />
          Sound
        </h3>
        <Card variant="glass" padding="md">
          <div
            className="flex items-center justify-between"
            title="Phase 11 PR-S2: sound preference persists, but no audio delivery channel is wired (NotificationService is in-app row only). Coming when an audio surface ships."
          >
            <div>
              <p className="text-sm text-starlight-200">
                Notification sound
                <Badge variant="warning" size="sm" className="ml-2 align-middle">Coming soon</Badge>
              </p>
              <p className="text-[10px] text-starlight-500">Play a sound when notifications arrive. (Toggle persists; audio delivery channel pending.)</p>
            </div>
            <Switch checked={sound} onChange={() => toggle('notif_sound', sound, setSound)} label="" size="sm" disabled />
          </div>
        </Card>
      </section>

      {/* Email */}
      <section className="space-y-3">
        <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
          <Mail size={14} className="text-primary-400" />
          Email Notifications
        </h3>
        <Card variant="glass" padding="md" className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Enable email notifications</p>
              <p className="text-[10px] text-starlight-500">Email delivery is not configured in this local build.</p>
            </div>
            <Switch
              checked={emailConfigured && emailEnabled}
              onChange={() => {
                if (emailConfigured) toggle('notif_email', emailEnabled, setEmailEnabled)
              }}
              label=""
              size="sm"
              disabled={!emailConfigured}
            />
          </div>
          {!emailConfigured && (
            <div className="flex items-start gap-2 rounded-lg border border-accent-amber/20 bg-accent-amber/5 px-3 py-2">
              <AlertTriangle size={13} className="mt-0.5 shrink-0 text-accent-amber" />
              <p className="text-[10px] text-starlight-400">
                Hidden from execution: no SMTP/provider endpoint is wired, so this page will not pretend email tests can send.
              </p>
            </div>
          )}
          {emailConfigured && emailEnabled && (
            <div className="space-y-3 pt-2 border-t border-white/5">
              <div>
                <label className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Email</label>
                <input
                  type="email"
                  defaultValue={userEmail}
                  className="w-full glass-input px-3 py-2 rounded-lg text-xs text-starlight-200 mt-1"
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-starlight-200">Daily digest</p>
                  <p className="text-[10px] text-starlight-500">Summary of overnight activity every morning.</p>
                </div>
                <Switch checked={dailyDigest} onChange={() => toggle('notif_daily_digest', dailyDigest, setDailyDigest)} label="" size="sm" />
              </div>
            </div>
          )}
        </Card>
      </section>

      {/* Test */}
      <section className="space-y-3">
        <h3 className="text-sm font-display font-semibold text-starlight-100 flex items-center gap-2">
          Test
        </h3>
        <Card variant="glass" padding="md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Send a test notification</p>
              <p className="text-[10px] text-starlight-500">Calls POST /notifications/test → creates one in-app row + bell entry. OS notification fires only if browser permission was granted above.</p>
            </div>
            <button
              onClick={() => { void handleSendTest() }}
              disabled={sendingTest}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-500/10 text-primary-400 border border-primary-500/20 hover:bg-primary-500/20 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sendingTest ? 'Sending…' : 'Send Test'}
            </button>
          </div>
        </Card>
      </section>
    </div>
  )
}

export default SettingsNotifications

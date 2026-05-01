/**
 * SettingsNotifications -- notification preferences tab.
 * All toggles persist to backend via PUT /settings/user JSONB.
 */
import { useState, useEffect } from 'react'
import { Bell, Volume2, Mail, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Card, Switch, Badge } from '@/components/common'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { persistUiPref } from '@/stores/uiStore'

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
            title="Phase 10C-D: master gate is meaningful — it controls whether the browser Notification permission request and the Send Test button fire on this device. Per-event sub-toggles below are disabled because the backend notification emitter does not exist yet (Phase 11 PR-S2)."
          >
            <div>
              <p className="text-sm text-starlight-200">Enable desktop notifications</p>
              <p className="text-[10px] text-starlight-500">Show system notifications for important events. (Master gate works client-side; sub-toggles below await Phase 11 emitter.)</p>
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
              title="Phase 10C-D: per-event toggles persist but no backend emitter consumes them. Phase 11 PR-S2 ships the NotificationService."
            >
              <p className="text-[10px] text-accent-amber flex items-center gap-1.5">
                <Badge variant="warning" size="sm">Coming soon</Badge>
                Per-event delivery is queued for Phase 11 — toggles below persist your preference but don't fire yet.
              </p>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Task completion</p>
                <Switch checked={taskComplete} onChange={() => toggle('notif_task_complete', taskComplete, setTaskComplete)} label="" size="sm" disabled />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Budget alerts</p>
                <Switch checked={budgetAlert} onChange={() => toggle('notif_budget_alert', budgetAlert, setBudgetAlert)} label="" size="sm" disabled />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Daena Heartbeat findings</p>
                <Switch checked={heartbeat} onChange={() => toggle('notif_heartbeat', heartbeat, setHeartbeat)} label="" size="sm" disabled />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Governance rejections</p>
                <Switch checked={govReject} onChange={() => toggle('notif_gov_reject', govReject, setGovReject)} label="" size="sm" disabled />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Runtime disconnection</p>
                <Switch checked={runtimeDisc} onChange={() => toggle('notif_runtime_disconnect', runtimeDisc, setRuntimeDisc)} label="" size="sm" disabled />
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
            title="Phase 10C-D: sound preference persists but the backend notification emitter does not exist. Phase 11 PR-S2."
          >
            <div>
              <p className="text-sm text-starlight-200">
                Notification sound
                <Badge variant="warning" size="sm" className="ml-2 align-middle">Coming soon</Badge>
              </p>
              <p className="text-[10px] text-starlight-500">Play a sound when notifications arrive. (Toggle persists; emitter pending.)</p>
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
              <p className="text-[10px] text-starlight-500">Verify your notification setup is working.</p>
            </div>
            <button
              onClick={() => {
                if (desktop && permStatus === 'granted') {
                  new Notification('Test from Daena', { body: 'Notifications are working correctly!', icon: '/daena-blue.png' })
                }
                import('@/stores/uiStore').then(({ useUiStore }) => {
                  useUiStore.getState().addNotification({ type: 'info', title: 'Test', message: 'Notification system is working.' })
                })
              }}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-500/10 text-primary-400 border border-primary-500/20 hover:bg-primary-500/20 cursor-pointer"
            >
              Send Test
            </button>
          </div>
        </Card>
      </section>
    </div>
  )
}

export default SettingsNotifications

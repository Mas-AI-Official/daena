/**
 * SettingsNotifications -- notification preferences tab.
 * All toggles persist to backend via PUT /settings/user JSONB.
 */
import { useState, useEffect } from 'react'
import { Bell, Volume2, Mail } from 'lucide-react'
import { Card, Switch } from '@/components/common'
import { api } from '@/lib/api'
import { persistUiPref } from '@/stores/uiStore'

export function SettingsNotifications() {
  const [desktop, setDesktop] = useState(true)
  const [taskComplete, setTaskComplete] = useState(true)
  const [budgetAlert, setBudgetAlert] = useState(true)
  const [heartbeat, setHeartbeat] = useState(true)
  const [govReject, setGovReject] = useState(true)
  const [runtimeDisc, setRuntimeDisc] = useState(true)
  const [sound, setSound] = useState(false)
  const [emailEnabled, setEmailEnabled] = useState(false)
  const [dailyDigest, setDailyDigest] = useState(false)

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
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Enable desktop notifications</p>
              <p className="text-[10px] text-starlight-500">Show system notifications for important events.</p>
            </div>
            <Switch checked={desktop} onChange={() => toggle('notif_desktop', desktop, setDesktop)} label="" size="sm" />
          </div>
          {desktop && (
            <div className="pl-4 border-l border-white/10 space-y-3 mt-1">
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Task completion</p>
                <Switch checked={taskComplete} onChange={() => toggle('notif_task_complete', taskComplete, setTaskComplete)} label="" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Budget alerts</p>
                <Switch checked={budgetAlert} onChange={() => toggle('notif_budget_alert', budgetAlert, setBudgetAlert)} label="" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Daena Heartbeat findings</p>
                <Switch checked={heartbeat} onChange={() => toggle('notif_heartbeat', heartbeat, setHeartbeat)} label="" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Governance rejections</p>
                <Switch checked={govReject} onChange={() => toggle('notif_gov_reject', govReject, setGovReject)} label="" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-starlight-300">Runtime disconnection</p>
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
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Notification sound</p>
              <p className="text-[10px] text-starlight-500">Play a sound when notifications arrive.</p>
            </div>
            <Switch checked={sound} onChange={() => toggle('notif_sound', sound, setSound)} label="" size="sm" />
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
              <p className="text-[10px] text-starlight-500">Receive important updates via email.</p>
            </div>
            <Switch checked={emailEnabled} onChange={() => toggle('notif_email', emailEnabled, setEmailEnabled)} label="" size="sm" />
          </div>
          {emailEnabled && (
            <div className="space-y-3 pt-2 border-t border-white/5">
              <div>
                <label className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Email</label>
                <input
                  type="email"
                  defaultValue="masoud.masoori@mas-ai.co"
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
    </div>
  )
}

export default SettingsNotifications

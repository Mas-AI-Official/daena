/**
 * Web Push helpers -- frontend half of the G6 founder-alert push channel.
 *
 * Backend contract (app/api/v1/notifications.py):
 *   GET  /notifications/push/status      -> { success, enabled, public_key, subscriptions }
 *                                           (any authenticated user, so Settings renders honestly)
 *   POST /notifications/push/subscribe   -> PushSubscription.toJSON() passthrough (FOUNDER only)
 *   POST /notifications/push/unsubscribe -> { endpoint }, soft-revoke (FOUNDER only)
 *
 * The VAPID public key comes ONLY from the status endpoint -- it is never
 * bundled into the frontend. The service worker (/sw.js) registers on
 * demand inside the subscribe flow, deliberately NOT in main.tsx, so
 * users who never enable push never pay for it.
 *
 * Both mutations are sent `silent: true`: the Settings component owns the
 * user-facing outcome message, so the generic interceptor toast would be
 * a duplicate. Failures still hit errorStore + console.warn per ADR-001.
 */
import { api } from '@/lib/api'

export interface PushStatus {
  enabled: boolean
  publicKey: string | null
  subscriptions: number
}

/** Browser capability check -- all three APIs are required. */
export function isPushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

/**
 * Server-side channel state. Silent: the caller renders failures inline
 * (per-component error state), a toast on a background status poll is noise.
 */
export async function fetchPushStatus(): Promise<PushStatus> {
  const res = await api.get('/notifications/push/status', { silent: true })
  return {
    enabled: !!res.data?.enabled,
    publicKey: res.data?.public_key ?? null,
    subscriptions: res.data?.subscriptions ?? 0,
  }
}

/** VAPID applicationServerKey wants raw bytes; the key arrives base64url. */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}

/** The push subscription this browser currently holds, if any. */
export async function getLocalSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null
  const reg = await navigator.serviceWorker.getRegistration('/')
  if (!reg) return null
  return reg.pushManager.getSubscription()
}

/**
 * Full subscribe flow: permission -> register /sw.js -> pushManager
 * subscription -> POST to the backend. Throws Error('permission_denied')
 * when the user blocks the browser prompt so the caller can message it
 * precisely; other failures propagate as-is.
 */
export async function subscribeThisDevice(publicKey: string): Promise<void> {
  if (!isPushSupported()) throw new Error('push_unsupported')
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('permission_denied')

  const reg = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready

  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    })
  }

  const json = sub.toJSON()
  // PushSubscriptionJSON fields are optional in the DOM types -- guard the
  // shape before it crosses the wire (backend validates the same trio).
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    throw new Error('subscription_incomplete')
  }
  await api.post(
    '/notifications/push/subscribe',
    {
      endpoint: json.endpoint,
      keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
      user_agent: navigator.userAgent.slice(0, 200),
    },
    { silent: true },
  )
}

/**
 * Server revoke first, THEN drop the browser subscription. A 404 from the
 * server (endpoint never registered or already revoked) is safe to absorb;
 * any other failure aborts before unsubscribing locally, so we never end
 * up silently deaf while the server still believes the device is live.
 * Returns false when this browser had no subscription to begin with.
 */
export async function unsubscribeThisDevice(): Promise<boolean> {
  const sub = await getLocalSubscription()
  if (!sub) return false
  try {
    await api.post(
      '/notifications/push/unsubscribe',
      { endpoint: sub.endpoint },
      { silent: true },
    )
  } catch (err) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status !== 404) throw err
  }
  await sub.unsubscribe()
  return true
}

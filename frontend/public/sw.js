/* Daena service worker -- G6 founder-alert push renderer.
 *
 * Served from /sw.js so its scope is the whole origin. It is registered
 * ON DEMAND by src/lib/push.ts (the subscribe flow in Settings), never
 * in the app boot path -- users who never enable push never load it.
 *
 * Payload contract (backend app/services/notification_service.py,
 * _mirror_to_push): { type, title, message, severity, notification_id }.
 * A non-JSON payload falls back to plain text so a malformed push still
 * renders honestly instead of being dropped.
 */

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { title: 'Daena', message: event.data ? event.data.text() : '' }
  }
  const title = payload.title || 'Daena'
  const options = {
    body: payload.message || '',
    icon: '/daena-blue.png',
    badge: '/daena-blue.png',
    // tag collapses redeliveries of the same notification row
    tag: payload.notification_id || undefined,
    data: {
      notification_id: payload.notification_id || null,
      type: payload.type || null,
    },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if ('focus' in client) return client.focus()
        }
        return self.clients.openWindow('/')
      }),
  )
})

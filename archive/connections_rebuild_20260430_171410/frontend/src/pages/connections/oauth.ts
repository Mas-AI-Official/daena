/**
 * Shared OAuth launcher used by ConnectorRow and the Browse modal.
 *
 * Session 10: extracted from ConnectorRow so the Browse modal can start
 * the same OAuth popup flow instead of opening the product homepage.
 * When OAuth broker credentials are missing, opens the inline setup
 * modal via `onRequestSetup` instead of navigating to /settings.
 *
 * NOTE: The popup-cleanup behavior here (popupCheckInterval poll +
 * 5-minute hard timeout + idempotent `cleanup()` helper) is a recent
 * audit fix. Do NOT alter without re-reading the comment block inside
 * the `try` body — it explains why the listener used to leak for the
 * full 5 minutes after the user closed the popup.
 */
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { StartOAuthOptions } from './types'

export async function startOAuthConnect(opts: StartOAuthOptions): Promise<void> {
  // Open the popup SYNCHRONOUSLY in the click gesture. If we wait until
  // after the await below to call window.open, Chrome/Safari/Edge all
  // block the popup because the call is no longer in the user-gesture
  // stack -- "the connect button does nothing" was exactly this.
  //
  // We point it at an interim loading page (served by the frontend
  // itself at /oauth-loading.html); once we have the real auth URL we
  // navigate this same popup to it. If the backend says "creds missing"
  // we close the popup and open the inline setup modal instead.
  const popup = window.open(
    '/oauth-loading.html',
    `daena_oauth_${opts.connectorId}`,
    'width=600,height=700,popup=yes',
  )
  if (!popup) {
    toast.error(
      `Popup blocked. Allow popups for localhost in your browser, then click Connect again.`,
      15_000,
    )
    return
  }

  try {
    const res = await api.get(`/connectors/${opts.connectorId}/oauth/authorize`)
    const data = res.data as {
      error_type?: string
      missing_field?: string
      authorization_url?: string
    }

    if (data?.error_type === 'oauth_not_configured') {
      popup.close()
      const missing = data.missing_field || 'OAuth credentials'
      if (opts.onRequestSetup) {
        opts.onRequestSetup(missing)
      } else {
        toast.error(
          `${opts.connectorName} OAuth not configured. Missing: ${missing}.`,
          10_000,
        )
      }
      return
    }

    const authUrl = data?.authorization_url
    if (!authUrl) {
      popup.close()
      toast.error(`Failed to get authorization URL for ${opts.connectorName}`)
      return
    }

    // Navigate the already-open popup to the real OAuth consent URL.
    popup.location.href = authUrl

    // Track popup state so we can clean up the message listener if the
    // user closes the popup without completing OAuth (previously the
    // listener stayed alive for 5 minutes burning memory + potentially
    // misfiring on a later popup with the same connector id).
    let cleanedUp = false
    const cleanup = () => {
      if (cleanedUp) return
      cleanedUp = true
      window.removeEventListener('message', handler)
      if (popupCheckInterval) clearInterval(popupCheckInterval)
      if (timeoutId) clearTimeout(timeoutId)
    }

    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'oauth_success' && event.data?.connector === opts.connectorId) {
        toast.success(`${opts.connectorName} connected successfully`)
        cleanup()
        opts.onSuccess?.()
      } else if (event.data?.type === 'oauth_error' && event.data?.connector === opts.connectorId) {
        toast.error(`${opts.connectorName} connection failed: ${event.data.error || 'Unknown error'}`)
        cleanup()
      }
    }
    window.addEventListener('message', handler)

    // Poll the popup — if user closes it without completing, abandon the
    // listener so it doesn't sit dormant for the full 5-minute timeout.
    const popupCheckInterval: ReturnType<typeof setInterval> | null = setInterval(() => {
      if (popup.closed) {
        cleanup()
      }
    }, 1000)

    // Hard timeout — if no message arrives in 5 minutes, give up cleanly.
    const timeoutId: ReturnType<typeof setTimeout> = setTimeout(() => {
      if (!cleanedUp) {
        toast.info(`${opts.connectorName} OAuth window timed out. Try again if you still want to connect.`)
        cleanup()
      }
    }, 300_000)
  } catch (err: unknown) {
    popup.close()
    const axiosErr = err as {
      response?: { data?: { error_type?: string; missing_field?: string } }
    }
    // Connector not in OAUTH_PROVIDERS on the backend (e.g. Notion,
    // Linear, PayPal right now). Surface an actionable message rather
    // than a generic "Unknown error" toast.
    const errorText = JSON.stringify(axiosErr?.response?.data || {})
    if (errorText.includes('No OAuth provider configured')) {
      toast.error(
        `${opts.connectorName} OAuth is not yet supported. Supported: Gmail, Google Drive, Google Calendar, GitHub, Figma, Slack, Canva.`,
        12_000,
      )
      return
    }
    if (axiosErr?.response?.data?.error_type === 'oauth_not_configured') {
      const missing = axiosErr.response.data.missing_field || 'OAuth credentials'
      if (opts.onRequestSetup) {
        opts.onRequestSetup(missing)
      } else {
        toast.error(
          `${opts.connectorName} OAuth not configured. Missing: ${missing}.`,
          10_000,
        )
      }
      return
    }
    const msg = err instanceof Error ? err.message : 'Unknown error'
    toast.error(`Failed to start OAuth: ${msg}`)
  }
}

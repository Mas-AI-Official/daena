/**
 * Install flow dispatcher for the Connections page.
 *
 * One function, three branches keyed by `auth.method`:
 *   - oauth_managed     -- popup-based OAuth (Google, GitHub, Slack...)
 *   - mcp_remote_oauth  -- popup-based OAuth against a remote MCP server
 *   - api_token         -- inline token form, POST to /install/complete
 *   - none              -- instant connect, no popup
 *
 * Replaces the old "click connect, hope a popup works" path with a
 * unified API that the dialog drives. The popup is always opened
 * SYNCHRONOUSLY in the click gesture so Chrome/Safari/Edge do not
 * block it; we navigate the popup to the real auth URL once the
 * backend returns it.
 */
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

export type InstallMethod =
  | 'oauth_managed'
  | 'mcp_remote_oauth'
  | 'api_token'
  | 'none'

export interface InstallStartResponse {
  method: InstallMethod
  popup: boolean
  authorization_url?: string
  state?: string
  form?: {
    fields: Array<{
      key: string
      label: string
      type: string
      required?: boolean
      help?: string
    }>
    settings_url?: string
    help?: string
  }
  fallback?: {
    method: InstallMethod
    field_label?: string
    help?: string
  }
  error_type?: string
  missing_field?: string
  help?: string
  connected?: boolean
  instance_id?: string
}

export interface InstallCallbacks {
  onSuccess?: (instanceId?: string, accountIdentity?: string) => void
  onError?: (message: string) => void
  onRequestSetup?: (missingField: string) => void
  /**
   * Surface a token form to the user. Called when the chosen auth
   * method needs an inline credential entry. The dialog component is
   * the canonical implementer.
   */
  onShowTokenForm?: (form: NonNullable<InstallStartResponse['form']>) => void
}

/**
 * Start the install flow for a connector. Returns the parsed start
 * response so the caller can choose to render a token form, an error
 * banner, or wait for the popup callback.
 */
export async function startInstall(
  slug: string,
  connectorName: string,
  callbacks: InstallCallbacks = {},
): Promise<InstallStartResponse | null> {
  // Open popup synchronously in the gesture to avoid block.
  // We may end up not needing it (api_token, none); close in those cases.
  const popup = window.open(
    '/oauth-loading.html',
    `daena_install_${slug}`,
    'width=600,height=720,popup=yes',
  )
  if (!popup) {
    toast.error(
      'Popup blocked. Allow popups for this site, then click Install again.',
      15_000,
    )
    return null
  }

  let response: InstallStartResponse
  try {
    const res = await api.post(`/connectors/${slug}/install/start`, {})
    response = res.data as InstallStartResponse
  } catch (err: unknown) {
    popup.close()
    const axiosErr = err as { response?: { data?: InstallStartResponse } }
    const data = axiosErr?.response?.data
    if (data?.error_type === 'oauth_not_configured' && callbacks.onRequestSetup) {
      callbacks.onRequestSetup(data.missing_field || 'OAuth credentials')
      return null
    }
    const msg = err instanceof Error ? err.message : 'Failed to start install'
    callbacks.onError?.(msg)
    toast.error(`${connectorName}: ${msg}`)
    return null
  }

  // Branch on method.
  if (response.method === 'none' && response.connected) {
    popup.close()
    toast.success(`${connectorName} connected`)
    callbacks.onSuccess?.(response.instance_id)
    return response
  }

  if (response.popup && response.authorization_url) {
    // OAuth: navigate the popup to the real consent URL.
    popup.location.href = response.authorization_url
    _watchPopup(popup, slug, connectorName, callbacks)
    return response
  }

  // api_token (or mcp_remote_oauth fallen back to api_token): close
  // the popup and surface the form to the dialog.
  popup.close()
  if (response.form) {
    callbacks.onShowTokenForm?.(response.form)
  } else {
    toast.error(`${connectorName}: backend returned no form spec`)
  }
  return response
}

function _watchPopup(
  popup: Window,
  slug: string,
  connectorName: string,
  callbacks: InstallCallbacks,
): void {
  let cleanedUp = false
  const cleanup = () => {
    if (cleanedUp) return
    cleanedUp = true
    window.removeEventListener('message', handler)
    if (pollInterval) clearInterval(pollInterval)
    if (timeoutId) clearTimeout(timeoutId)
  }
  const handler = (event: MessageEvent) => {
    if (event.data?.type === 'oauth_success' && event.data?.connector === slug) {
      toast.success(`${connectorName} connected`)
      cleanup()
      callbacks.onSuccess?.()
    } else if (event.data?.type === 'oauth_error' && event.data?.connector === slug) {
      const e = event.data.error || 'Unknown error'
      toast.error(`${connectorName}: ${e}`)
      callbacks.onError?.(e)
      cleanup()
    }
  }
  window.addEventListener('message', handler)
  const pollInterval = setInterval(() => {
    if (popup.closed) cleanup()
  }, 1000)
  const timeoutId = setTimeout(() => {
    if (!cleanedUp) {
      toast.info(`${connectorName} OAuth window timed out.`)
      cleanup()
    }
  }, 300_000)
}

/**
 * Submit credentials for an api_token connector. The dialog calls this
 * after the user fills the form.
 */
export async function completeApiTokenInstall(
  slug: string,
  connectorName: string,
  credentials: Record<string, string>,
  callbacks: InstallCallbacks = {},
): Promise<boolean> {
  try {
    const res = await api.post(`/connectors/${slug}/install/complete`, {
      credentials,
    })
    const data = res.data as {
      status: string
      instance_id?: string
      account_identity?: string
    }
    if (data.status === 'connected') {
      toast.success(
        data.account_identity
          ? `${connectorName} connected as ${data.account_identity}`
          : `${connectorName} connected`,
      )
      callbacks.onSuccess?.(data.instance_id, data.account_identity)
      return true
    }
    callbacks.onError?.('Provider did not confirm connection')
    return false
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Token rejected'
    callbacks.onError?.(msg)
    toast.error(`${connectorName}: ${msg}`)
    return false
  }
}

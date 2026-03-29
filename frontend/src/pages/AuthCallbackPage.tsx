import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Cpu } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

/**
 * OAuth callback landing page.
 *
 * Flow: Provider → backend callback → redirect here with ?code=X&provider=Y.
 * This page exchanges the one-time code for JWT tokens, then navigates to /chat.
 * Shows a spinner while the exchange is in-flight.
 */
export function AuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { oauthExchange } = useAuthStore()
  const [error, setError] = useState<string | null>(null)
  const exchanged = useRef(false)

  useEffect(() => {
    // Prevent double-fire in React 18 StrictMode
    if (exchanged.current) return
    exchanged.current = true

    const code = searchParams.get('code')
    const provider = searchParams.get('provider')

    if (!code) {
      setError('Missing authorization code')
      return
    }

    oauthExchange(code)
      .then(() => {
        if (useAuthStore.getState().isAuthenticated) {
          navigate('/chat', { replace: true })
        } else {
          const storeError = useAuthStore.getState().error
          setError(storeError || `${provider ?? 'OAuth'} login failed`)
        }
      })
      .catch(() => {
        setError(`${provider ?? 'OAuth'} login failed`)
      })
  }, [searchParams, navigate, oauthExchange])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-midnight-900 px-4">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary-500 to-accent-purple flex items-center justify-center shadow-[var(--shadow-glow-primary)]">
            <Cpu size={28} className="text-white" />
          </div>
          <div className="glass-card p-8 max-w-sm">
            <p className="text-status-error text-sm mb-4">{error}</p>
            <button
              onClick={() => navigate('/login', { replace: true })}
              className="text-primary-400 hover:text-primary-500 text-sm transition-colors cursor-pointer"
            >
              Back to sign in
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-midnight-900">
      <div className="text-center space-y-4">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary-500 to-accent-purple flex items-center justify-center shadow-[var(--shadow-glow-primary)]">
          <Cpu size={28} className="text-white" />
        </div>
        <div className="flex items-center gap-2 text-starlight-400">
          <div className="w-5 h-5 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Completing sign in…</span>
        </div>
      </div>
    </div>
  )
}

export default AuthCallbackPage

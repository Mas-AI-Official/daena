import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Mail } from 'lucide-react'
import { motion } from 'framer-motion'
import { Button, Input } from '@/components/common'
import api from '@/lib/api'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      const { data } = await api.post<{
        success: boolean
        data: { message: string; dev_reset_token?: string; dev_reset_url?: string }
      }>('/auth/forgot-password', { email })

      setSubmitted(true)

      // Dev mode: capture the reset URL for easy testing
      if (data.data.dev_reset_url) {
        setDevResetUrl(data.data.dev_reset_url)
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || 'Something went wrong. Please try again.'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-midnight-900 px-4">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-purple/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative w-20 h-20 mb-3">
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{
                border: '2px solid rgba(0,212,255,0.25)',
                boxShadow: '0 0 16px rgba(0,136,255,0.2)',
              }}
              animate={{ rotate: 360, scale: [1, 1.04, 1] }}
              transition={{
                rotate: { duration: 12, repeat: Infinity, ease: 'linear' },
                scale: { duration: 3, repeat: Infinity, ease: 'easeInOut' },
              }}
            />
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{
                background: 'radial-gradient(circle, rgba(0,212,255,0.1), transparent 70%)',
                filter: 'blur(12px)',
              }}
              animate={{ scale: [1, 1.25, 1], opacity: [0.3, 0.5, 0.3] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            />
            <motion.img
              src="/daena-blue.png"
              alt="Daena"
              className="absolute inset-1.5 w-17 h-17 object-contain rounded-full select-none"
              style={{ filter: 'drop-shadow(0 0 8px rgba(0,136,255,0.3))' }}
              animate={{ scale: [1, 1.03, 1] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              draggable={false}
            />
          </div>
          <h1 className="font-display text-3xl font-bold text-starlight-100">Daena</h1>
          <p className="text-starlight-400 text-sm mt-1">Governed Multi-Agent AI Platform</p>
        </div>

        {/* Card */}
        <div className="glass-card p-8">
          {submitted ? (
            /* Success state */
            <div className="text-center space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-status-success/10 border border-status-success/20 flex items-center justify-center">
                <Mail size={20} className="text-status-success" />
              </div>
              <h2 className="text-xl font-display font-semibold text-starlight-100">
                Check your email
              </h2>
              <p className="text-starlight-400 text-sm leading-relaxed">
                If an account exists for <span className="text-starlight-200">{email}</span>,
                we&apos;ve sent password reset instructions.
              </p>

              {/* Dev mode: show reset link for testing */}
              {devResetUrl && (
                <div className="p-3 rounded-lg bg-accent-purple/10 border border-accent-purple/20 text-left">
                  <p className="text-xs text-accent-purple mb-1 font-medium">Dev Mode — Reset Link:</p>
                  <Link
                    to={devResetUrl.replace(/^https?:\/\/[^/]+/, '')}
                    className="text-xs text-primary-400 hover:text-primary-500 break-all transition-colors"
                  >
                    {devResetUrl}
                  </Link>
                </div>
              )}

              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-sm text-primary-400 hover:text-primary-500 transition-colors mt-2"
              >
                <ArrowLeft size={14} />
                Back to sign in
              </Link>
            </div>
          ) : (
            /* Form state */
            <>
              <div className="mb-6">
                <h2 className="text-xl font-display font-semibold text-starlight-100 mb-2">
                  Forgot password?
                </h2>
                <p className="text-starlight-400 text-sm">
                  Enter your email and we&apos;ll send you a link to reset your password.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <Input
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  autoFocus
                />

                {error && (
                  <div className="p-3 rounded-lg bg-status-error/10 border border-status-error/20 text-sm text-status-error">
                    {error}
                  </div>
                )}

                <Button type="submit" variant="primary" className="w-full" isLoading={isLoading}>
                  Send reset link
                </Button>
              </form>

              <div className="text-center mt-6">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-sm text-starlight-400 hover:text-starlight-200 transition-colors"
                >
                  <ArrowLeft size={14} />
                  Back to sign in
                </Link>
              </div>
            </>
          )}
        </div>

        {/* Legal footer */}
        <div className="flex items-center justify-center gap-3 mt-6 text-[10px] text-starlight-600">
          <Link to="/terms" className="hover:text-starlight-400 transition-colors">Terms</Link>
          <span>&middot;</span>
          <Link to="/privacy" className="hover:text-starlight-400 transition-colors">Privacy</Link>
          <span>&middot;</span>
          <span>MAS-AI Technologies Inc.</span>
        </div>
      </div>
    </div>
  )
}

export default ForgotPasswordPage

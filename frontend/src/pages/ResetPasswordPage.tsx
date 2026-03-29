import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Eye, EyeOff, ArrowLeft, CheckCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { Button, Input } from '@/components/common'
import { PasswordStrengthMeter } from '@/components/auth/PasswordStrengthMeter'
import api from '@/lib/api'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const passwordsMatch = confirmPassword.length > 0 && password === confirmPassword
  const canSubmit = password.length >= 12 && passwordsMatch

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!token) return
    setError(null)
    setIsLoading(true)

    try {
      await api.post('/auth/reset-password', {
        token,
        password,
        confirm_password: confirmPassword,
      })
      setSuccess(true)
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || 'Failed to reset password. The link may have expired.'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  // No token in URL
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-midnight-900 px-4">
        <div className="relative w-full max-w-md">
          <div className="flex flex-col items-center mb-8">
            <div className="relative w-20 h-20 mb-3">
              <motion.img
                src="/daena-blue.png"
                alt="Daena"
                className="absolute inset-1.5 w-17 h-17 object-contain rounded-full select-none"
                style={{ filter: 'drop-shadow(0 0 8px rgba(0,136,255,0.3))' }}
                draggable={false}
              />
            </div>
          </div>
          <div className="glass-card p-8 text-center space-y-4">
            <p className="text-status-error text-sm">
              Invalid or missing reset link. Please request a new one.
            </p>
            <Link
              to="/forgot-password"
              className="inline-flex items-center gap-1.5 text-sm text-primary-400 hover:text-primary-500 transition-colors"
            >
              Request new reset link
            </Link>
          </div>
        </div>
      </div>
    )
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
          {success ? (
            /* Success state */
            <div className="text-center space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-status-success/10 border border-status-success/20 flex items-center justify-center">
                <CheckCircle size={20} className="text-status-success" />
              </div>
              <h2 className="text-xl font-display font-semibold text-starlight-100">
                Password reset!
              </h2>
              <p className="text-starlight-400 text-sm">
                Your password has been updated. You can now sign in with your new password.
              </p>
              <Button
                variant="primary"
                className="w-full"
                onClick={() => navigate('/login', { replace: true })}
              >
                Sign in
              </Button>
            </div>
          ) : (
            /* Form state */
            <>
              <div className="mb-6">
                <h2 className="text-xl font-display font-semibold text-starlight-100 mb-2">
                  Set new password
                </h2>
                <p className="text-starlight-400 text-sm">
                  Choose a strong password for your account.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* New password */}
                <div className="relative">
                  <Input
                    label="New password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 12 characters"
                    required
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                <PasswordStrengthMeter password={password} />

                {/* Confirm password */}
                <div className="relative">
                  <Input
                    label="Confirm password"
                    type={showConfirm ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your password"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
                  >
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                {/* Match indicator */}
                {confirmPassword.length > 0 && (
                  <p className={`text-xs ${passwordsMatch ? 'text-status-success' : 'text-status-error'}`}>
                    {passwordsMatch ? 'Passwords match' : 'Passwords do not match'}
                  </p>
                )}

                {error && (
                  <div className="p-3 rounded-lg bg-status-error/10 border border-status-error/20 text-sm text-status-error">
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  isLoading={isLoading}
                  disabled={!canSubmit}
                >
                  Reset password
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

export default ResetPasswordPage

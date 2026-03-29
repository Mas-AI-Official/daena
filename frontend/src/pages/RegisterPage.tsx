import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { motion } from 'framer-motion'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/authStore'
import { Button, Input } from '@/components/common'
import { PasswordStrengthMeter } from '@/components/auth/PasswordStrengthMeter'
import { OAuthButtons } from '@/components/auth/OAuthButtons'

export function RegisterPage() {
  usePageTitle('Create Account')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const { register, isLoading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()

    if (password !== confirmPassword) return

    await register(email, password, displayName, tenantName)
    if (useAuthStore.getState().isAuthenticated) {
      navigate('/chat')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-midnight-900 px-4 py-12">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-purple/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
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
          <p className="text-starlight-400 text-sm mt-1">Create your workspace</p>
        </div>

        <div className="glass-card p-8">
          <h2 className="text-xl font-display font-semibold text-starlight-100 mb-6">Register</h2>

          <OAuthButtons />

          <div className="relative flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-midnight-600" />
            <span className="text-xs text-starlight-500 uppercase tracking-wider">
              or continue with email
            </span>
            <div className="flex-1 h-px bg-midnight-600" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Display Name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your full name"
              required
              autoFocus
              autoComplete="name"
            />

            <Input
              label="Organization"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              placeholder="Your company or team name"
              autoComplete="organization"
              required
            />

            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
            />

            {/* Password with eye toggle */}
            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 12 chars, 1 upper, 1 digit, 1 special"
                required
                minLength={12}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Strength meter — compact bar below password */}
            <PasswordStrengthMeter password={password} />

            {/* Confirm password with eye toggle — extra top margin to breathe */}
            <div className="relative">
              <Input
                label="Confirm Password"
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                required
                minLength={12}
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-3 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Mismatch warning */}
            {!passwordsMatch && (
              <p className="text-xs text-status-error -mt-2">Passwords do not match</p>
            )}

            {/* Terms of Service agreement */}
            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="mt-0.5 w-4 h-4 rounded border-white/20 bg-midnight-900/50
                           text-primary-500 focus:ring-primary-500/40 focus:ring-offset-0
                           cursor-pointer accent-primary-500"
              />
              <span className="text-xs text-starlight-400 leading-relaxed">
                I agree to the{' '}
                <Link to="/terms" target="_blank" className="text-primary-400 hover:text-primary-500 underline">
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link to="/privacy" target="_blank" className="text-primary-400 hover:text-primary-500 underline">
                  Privacy Policy
                </Link>.
                I understand that Daena uses third-party AI models and that AI-generated content
                may be inaccurate. I am responsible for reviewing all outputs.
              </span>
            </label>

            {error && (
              <div className="p-3 rounded-lg bg-status-error/10 border border-status-error/20 text-sm text-status-error">
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="premium"
              className="w-full"
              isLoading={isLoading}
              disabled={!passwordsMatch || confirmPassword.length === 0 || !agreedToTerms}
            >
              Create Workspace
            </Button>
          </form>

          <p className="text-center text-sm text-starlight-400 mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-400 hover:text-primary-500 transition-colors">
              Sign in
            </Link>
          </p>

          {/* Legal footer */}
          <div className="flex items-center justify-center gap-3 mt-4 text-[10px] text-starlight-600">
            <Link to="/terms" className="hover:text-starlight-400 transition-colors">Terms</Link>
            <span>&middot;</span>
            <Link to="/privacy" className="hover:text-starlight-400 transition-colors">Privacy</Link>
            <span>&middot;</span>
            <span>MAS-AI Technologies Inc.</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RegisterPage

import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, Shield } from 'lucide-react'
import { motion } from 'framer-motion'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/authStore'
import { Button, Input } from '@/components/common'
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
    <div className="h-screen flex items-center justify-center bg-midnight-900 px-4 overflow-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-purple/5 rounded-full blur-3xl" />
      </div>

      <motion.div
        className="relative w-full max-w-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {/* Compact header -- logo + title inline */}
        <div className="flex items-center justify-center gap-3 mb-3">
          <img src="/daena-blue.png" alt="Daena" className="w-8 h-8 object-contain rounded-full" style={{ filter: 'drop-shadow(0 0 8px rgba(0,136,255,0.3))' }} />
          <div>
            <h1 className="font-display text-xl font-bold text-starlight-100 leading-tight">Daena</h1>
            <p className="text-starlight-400 text-[10px] leading-tight">Create your workspace</p>
          </div>
        </div>

        {/* Form card */}
        <div className="glass-card p-5">
          <OAuthButtons />

          <div className="relative flex items-center gap-3 my-3">
            <div className="flex-1 h-px bg-midnight-600" />
            <span className="text-[10px] text-starlight-500 uppercase tracking-wider">or with email</span>
            <div className="flex-1 h-px bg-midnight-600" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-2.5">
            {/* Row 1: Name + Organization side by side */}
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Display Name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
                required
                autoFocus
                autoComplete="name"
              />
              <Input
                label="Organization"
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                placeholder="Company or team"
                autoComplete="organization"
                required
              />
            </div>

            {/* Row 2: Email full width */}
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
            />

            {/* Row 3: Password + Confirm side by side */}
            <div className="grid grid-cols-2 gap-3">
              <div className="relative">
                <Input
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 12 chars"
                  required
                  minLength={12}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <div className="relative">
                <Input
                  label="Confirm Password"
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter"
                  required
                  minLength={12}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-2 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
                >
                  {showConfirm ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {!passwordsMatch && (
              <p className="text-[11px] text-status-error">Passwords do not match</p>
            )}

            {/* Terms -- compact */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-white/20 bg-midnight-900/50
                           text-primary-500 focus:ring-primary-500/40 focus:ring-offset-0
                           cursor-pointer accent-primary-500 shrink-0"
              />
              <span className="text-[11px] text-starlight-400">
                I agree to the{' '}
                <Link to="/terms" target="_blank" className="text-primary-400 hover:text-primary-500 underline">Terms</Link>
                {' & '}
                <Link to="/privacy" target="_blank" className="text-primary-400 hover:text-primary-500 underline">Privacy Policy</Link>.
                AI outputs may be inaccurate.
              </span>
            </label>

            {error && (
              <div className="p-2 rounded-lg bg-status-error/10 border border-status-error/20 text-xs text-status-error">
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
              <Shield size={14} className="mr-1.5" />
              Create Workspace
            </Button>
          </form>

          {/* Footer inside card */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-midnight-600/50">
            <p className="text-xs text-starlight-400">
              Already have an account?{' '}
              <Link to="/login" className="text-primary-400 hover:text-primary-500 transition-colors font-medium">
                Sign in
              </Link>
            </p>
            <div className="flex items-center gap-2 text-[10px] text-starlight-600">
              <Link to="/terms" className="hover:text-starlight-400 transition-colors">Terms</Link>
              <span>&middot;</span>
              <Link to="/privacy" className="hover:text-starlight-400 transition-colors">Privacy</Link>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

export default RegisterPage

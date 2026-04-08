import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, LogIn } from 'lucide-react'
import { motion } from 'framer-motion'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/authStore'
import { Button, Input } from '@/components/common'
import { OAuthButtons } from '@/components/auth/OAuthButtons'

export function LoginPage() {
  usePageTitle('Sign In')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(true)
  const { login, isLoading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()
    await login(email, password)
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
        {/* Compact header -- logo + title inline (matches register) */}
        <div className="flex items-center justify-center gap-3 mb-3">
          <img src="/daena-blue.png" alt="Daena" className="w-8 h-8 object-contain rounded-full" style={{ filter: 'drop-shadow(0 0 8px rgba(0,136,255,0.3))' }} />
          <div>
            <h1 className="font-display text-xl font-bold text-starlight-100 leading-tight">Daena</h1>
            <p className="text-starlight-400 text-[10px] leading-tight">Governed Multi-Agent AI Platform</p>
          </div>
        </div>

        {/* Form card */}
        <div className="glass-card p-5">
          <h2 className="text-base font-display font-semibold text-starlight-100 mb-3">Sign in</h2>

          <OAuthButtons />

          <div className="relative flex items-center gap-3 my-3">
            <div className="flex-1 h-px bg-midnight-600" />
            <span className="text-[10px] text-starlight-500 uppercase tracking-wider">or with email</span>
            <div className="flex-1 h-px bg-midnight-600" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoFocus
            />

            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-[30px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Remember me + Forgot password */}
            <div className="flex items-center justify-between -mt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-white/20 bg-midnight-900/50
                             text-primary-500 focus:ring-primary-500/40 focus:ring-offset-0
                             cursor-pointer accent-primary-500"
                />
                <span className="text-xs text-starlight-400">Remember me</span>
              </label>
              <Link
                to="/forgot-password"
                className="text-xs text-primary-400 hover:text-primary-500 transition-colors"
              >
                Forgot password?
              </Link>
            </div>

            {error && (
              <div className="p-2 rounded-lg bg-status-error/10 border border-status-error/20 text-xs text-status-error">
                {error}
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full" isLoading={isLoading}>
              <LogIn size={14} className="mr-1.5" />
              Sign in
            </Button>
          </form>

          {/* Footer inside card */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-midnight-600/50">
            <p className="text-xs text-starlight-400">
              No account?{' '}
              <Link to="/register" className="text-primary-400 hover:text-primary-500 transition-colors font-medium">
                Create one
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

export default LoginPage

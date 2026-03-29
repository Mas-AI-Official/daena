import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
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
    <div className="min-h-screen flex items-center justify-center bg-midnight-900 px-4 py-12">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-purple/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative w-24 h-24 mb-3">
            {/* Animated halo ring */}
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{
                border: '2px solid rgba(0,212,255,0.25)',
                boxShadow: '0 0 20px rgba(0,136,255,0.2), inset 0 0 12px rgba(0,212,255,0.08)',
              }}
              animate={{ rotate: 360, scale: [1, 1.04, 1] }}
              transition={{
                rotate: { duration: 12, repeat: Infinity, ease: 'linear' },
                scale: { duration: 3, repeat: Infinity, ease: 'easeInOut' },
              }}
            />
            {/* Counter-rotating dashed ring */}
            <motion.div
              className="absolute inset-1 rounded-full"
              style={{ border: '1px dashed rgba(0,136,255,0.15)' }}
              animate={{ rotate: -360 }}
              transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
            />
            {/* Ambient glow */}
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{
                background: 'radial-gradient(circle, rgba(0,212,255,0.12), transparent 70%)',
                filter: 'blur(16px)',
              }}
              animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.6, 0.3] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            />
            {/* Logo image */}
            <motion.img
              src="/daena-blue.png"
              alt="Daena"
              className="absolute inset-2 w-20 h-20 object-contain rounded-full select-none"
              style={{ filter: 'drop-shadow(0 0 10px rgba(0,136,255,0.35))' }}
              animate={{ scale: [1, 1.03, 1] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              draggable={false}
            />
            {/* 4 orbital particles */}
            {[0, 90, 180, 270].map((angle) => (
              <motion.div
                key={angle}
                className="absolute rounded-full"
                style={{
                  width: 3,
                  height: 3,
                  backgroundColor: '#66e0ff',
                  boxShadow: '0 0 6px #66e0ff',
                  left: '50%',
                  top: '50%',
                  marginLeft: -1.5,
                  marginTop: -1.5,
                }}
                animate={{
                  x: [
                    Math.cos((angle * Math.PI) / 180) * 44,
                    Math.cos(((angle + 360) * Math.PI) / 180) * 44,
                  ],
                  y: [
                    Math.sin((angle * Math.PI) / 180) * 44,
                    Math.sin(((angle + 360) * Math.PI) / 180) * 44,
                  ],
                  opacity: [0.3, 0.8, 0.3],
                }}
                transition={{ duration: 8, delay: (angle / 360) * 2, repeat: Infinity, ease: 'linear' }}
              />
            ))}
          </div>
          <h1 className="font-display text-3xl font-bold text-starlight-100">Daena</h1>
          <p className="text-starlight-400 text-sm mt-1">Governed Multi-Agent AI Platform</p>
        </div>

        {/* Form card */}
        <div className="glass-card p-8">
          <h2 className="text-xl font-display font-semibold text-starlight-100 mb-6">Sign in</h2>

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
              <div className="p-3 rounded-lg bg-status-error/10 border border-status-error/20 text-sm text-status-error">
                {error}
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full" isLoading={isLoading}>
              Sign in
            </Button>
          </form>

          <p className="text-center text-sm text-starlight-400 mt-6">
            No account?{' '}
            <Link to="/register" className="text-primary-400 hover:text-primary-500 transition-colors">
              Create one
            </Link>
          </p>
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

export default LoginPage

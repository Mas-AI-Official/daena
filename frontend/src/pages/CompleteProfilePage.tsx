/**
 * CompleteProfilePage -- Required for OAuth users who haven't accepted terms yet.
 *
 * After Google/GitHub OAuth sign-up, users land here to:
 *  1. Accept Terms of Service + Privacy Policy (required)
 *  2. Set their company/workspace name (optional)
 *
 * On submit, calls PATCH /auth/complete-profile which sets terms_accepted_at
 * and issues new JWT tokens with profile_complete=true.
 */
import { useState } from 'react'
import { useNavigate, Navigate, Link } from 'react-router-dom'
import { Cpu, Building2, Shield, Loader2, CheckCircle2 } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

export function CompleteProfilePage() {
  const navigate = useNavigate()
  const { user, completeProfile, isLoading, error, clearError, profileComplete } = useAuthStore()
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [tenantName, setTenantName] = useState('')

  // If profile is already complete, redirect to app.
  // Use the declarative <Navigate> rather than calling navigate() during render --
  // React Router v6 refuses imperative navigation in the render phase, which left a
  // profile-complete user stranded on a blank /complete-profile dead-end (Rule 17:
  // every failure must be visible; no silent no-op redirect). Mirrors ProtectedRoute.
  if (profileComplete) {
    return <Navigate to="/chat" replace />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()

    if (!agreedToTerms) return

    await completeProfile(agreedToTerms, tenantName.trim() || undefined)

    // If successful, profileComplete will be true and ProtectedRoute will let through
    if (useAuthStore.getState().profileComplete) {
      navigate('/chat', { replace: true })
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-midnight-900 px-4">
      <div className="w-full max-w-md space-y-6">
        {/* Logo */}
        <div className="text-center space-y-3">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-primary-500 to-accent-purple flex items-center justify-center shadow-[var(--shadow-glow-primary)]">
            <Cpu size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-display font-bold text-starlight-100">
            Complete Your Profile
          </h1>
          <p className="text-sm text-starlight-400">
            Welcome{user?.display_name ? `, ${user.display_name}` : ''}! Just one more step to get started with Daena.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="glass-card p-6 space-y-5">
          {/* Company / Workspace Name */}
          <div className="space-y-1.5">
            <label htmlFor="tenant-name" className="text-sm font-medium text-starlight-200 flex items-center gap-2">
              <Building2 size={14} className="text-starlight-400" />
              Company or Workspace Name
              <span className="text-starlight-500 text-xs font-normal">(optional)</span>
            </label>
            <input
              id="tenant-name"
              type="text"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              placeholder="e.g. Acme Corp, My Startup, Personal"
              // PR-A11Y-PHASE85 (SC 1.3.5 Identify Input Purpose): this field's
              // purpose is the company/organization name, so expose the standard
              // autocomplete token -- matches RegisterPage's existing convention.
              autoComplete="organization"
              className="w-full glass-input px-4 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500"
            />
            <p className="text-xs text-starlight-500">
              This names your Daena workspace. You can change it later in Settings.
            </p>
          </div>

          {/* Terms Agreement */}
          <div className="space-y-3">
            <div className="flex items-start gap-3 p-4 rounded-lg border border-white/5 bg-midnight-400/30">
              <Shield size={16} className="text-primary-400 shrink-0 mt-0.5" />
              <div className="space-y-2 text-xs text-starlight-400">
                <p>Daena is a governed AI platform. All actions are auditable, and your data stays under your control.</p>
              </div>
            </div>

            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="mt-0.5 w-4 h-4 rounded border-white/20 bg-midnight-400 text-primary-500 focus:ring-primary-500/30 cursor-pointer"
              />
              <span className="text-sm text-starlight-300 group-hover:text-starlight-200 transition-colors">
                I agree to the{' '}
                <Link to="/terms" target="_blank" className="text-primary-400 hover:text-primary-300 underline underline-offset-2">
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link to="/privacy" target="_blank" className="text-primary-400 hover:text-primary-300 underline underline-offset-2">
                  Privacy Policy
                </Link>
              </span>
            </label>
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-status-error bg-status-error/10 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!agreedToTerms || isLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-primary-500 to-accent-purple text-white hover:from-primary-600 hover:to-accent-purple/80 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-all"
          >
            {isLoading ? (
              <><Loader2 size={16} className="animate-spin" /> Completing...</>
            ) : (
              <><CheckCircle2 size={16} /> Continue to Daena</>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

export default CompleteProfilePage

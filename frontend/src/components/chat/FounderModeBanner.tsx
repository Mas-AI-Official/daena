/**
 * FounderModeBanner
 *
 * Subtle founder-only strip at the top of /chat that confirms
 * elevated mode is active. The header already shows a gold lightning
 * icon for this, so the banner is REDUNDANT -- the founder can dismiss
 * it permanently and rely on the header indicator going forward.
 *
 * Render rules (all must hold; else returns null):
 *   1. User role is FOUNDER
 *   2. securityModeStore.state.active === true
 *   3. User has not dismissed the banner (permanent, not session)
 *
 * Before: dismissal cleared on every off->on toggle, so every
 * reactivation shoved the banner back over the chat. That reads as
 * nagging. Now the dismiss flag persists across toggles -- one click
 * hides it forever. The header's gold lightning indicator still
 * surfaces elevated state, so the founder never loses the signal.
 */
import { useEffect, useState } from 'react'
import { Zap, X } from 'lucide-react'
import { useSecurityModeStore } from '@/stores/securityModeStore'
import { useAuthStore } from '@/stores/authStore'

const DISMISS_KEY = 'daena:founderModeBannerDismissed'

export function FounderModeBanner() {
  const active = useSecurityModeStore((s) => s.state.active)
  const fetchState = useSecurityModeStore((s) => s.fetchState)
  const role = useAuthStore((s) => s.user?.role)
  const [dismissed, setDismissed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === 'true'
    } catch {
      return false
    }
  })

  // Ensure the store fetched its state at least once after mount.
  // securityModeStore also polls on its own; this just shortcuts
  // the first render.
  useEffect(() => {
    fetchState()
  }, [fetchState])

  const isFounder = (role ?? '').toUpperCase() === 'FOUNDER'
  if (!isFounder || !active || dismissed) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-between gap-3 px-4 py-1.5 border-b border-accent-amber/25 bg-accent-amber/[0.06]"
    >
      <div className="flex items-center gap-2 text-[11px] text-accent-amber font-medium">
        <Zap size={12} className="text-accent-amber" />
        <span>Elevated mode active</span>
        <span className="text-starlight-500 font-normal hidden sm:inline">
          full-tier access unlocked for this session
        </span>
      </div>
      <button
        onClick={() => {
          try { localStorage.setItem(DISMISS_KEY, 'true') } catch {}
          setDismissed(true)
        }}
        className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer"
        title="Hide this notice until the next activation"
        aria-label="Dismiss elevated mode notice"
      >
        <X size={12} />
      </button>
    </div>
  )
}

export default FounderModeBanner

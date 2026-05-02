/**
 * ScopeStatusBanner - precondition status for the Security Scan launcher.
 *
 * PR-4 (Security Scan UX Consolidation, 2026-05-02). Closes the "operator
 * presses Start, gets surprise 403" UX gap. Now the operator can see
 * BEFORE they type a target whether the tenant's authorized scope is
 * empty, populated, or unreachable. Three branches:
 *
 *   1. FOUNDER + scope empty: warning banner + button to /security/scope
 *   2. FOUNDER + scope populated: confirmation pill + link to /security/scope
 *   3. Non-FOUNDER: passive informational copy explaining scope is
 *      Founder-controlled (the GET /security/authorized-scope endpoint
 *      is FOUNDER-only, so we cannot show counts to non-Founders)
 *
 * Backend contract: GET /security/authorized-scope returns
 *   { exact_domains, wildcard_domains, ipv4_cidrs, source_paths,
 *     has_any_entry: bool }
 * Founder-only. 403 for everyone else; we treat the 403 as
 * "non-founder mode" not as an error.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert, ShieldCheck, ShieldQuestion, ExternalLink } from 'lucide-react'
import { Card } from '@/components/common'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

interface ScopeSummary {
  has_any_entry: boolean
  exact_domains: string[]
  wildcard_domains: string[]
  ipv4_cidrs: string[]
  source_paths: string[]
}

type LoadState = 'loading' | 'ready' | 'forbidden' | 'unreachable'

export default function ScopeStatusBanner() {
  const role = useAuthStore((s) => s.user?.role)
  const isFounder = role === 'FOUNDER'

  const [scope, setScope] = useState<ScopeSummary | null>(null)
  const [loadState, setLoadState] = useState<LoadState>('loading')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data } = await api.get<ScopeSummary>('/security/authorized-scope', {
          timeout: 5000,
        })
        if (cancelled) return
        setScope(data)
        setLoadState('ready')
      } catch (err) {
        if (cancelled) return
        const status = (err as { response?: { status?: number } })?.response?.status
        if (status === 403) {
          setLoadState('forbidden')
        } else {
          setLoadState('unreachable')
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  // Non-founder OR backend returns 403: render passive informational copy.
  // We deliberately do NOT show entry counts here - the GET endpoint is
  // founder-only and inferring counts from a 403 would be a leak.
  if (!isFounder || loadState === 'forbidden') {
    return (
      <Card className="border border-white/10 bg-midnight-200/40 p-3 flex items-start gap-3">
        <ShieldQuestion size={16} className="text-starlight-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-starlight-300">
            Scans run only against targets the Founder has authorized for this tenant.
          </p>
          <p className="text-[11px] text-starlight-500 mt-0.5">
            If your scan returns a scope-blocked error, ask the Founder to add the
            target to Scan Scope.
          </p>
        </div>
      </Card>
    )
  }

  if (loadState === 'loading') {
    return (
      <Card className="border border-white/5 bg-midnight-200/30 p-3">
        <p className="text-xs text-starlight-500">Checking authorized scope...</p>
      </Card>
    )
  }

  if (loadState === 'unreachable' || !scope) {
    return (
      <Card className="border border-status-warning/30 bg-status-warning/5 p-3 flex items-start gap-3">
        <ShieldAlert size={16} className="text-status-warning shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-starlight-200 font-medium">
            Could not load authorized scope
          </p>
          <p className="text-[11px] text-starlight-500 mt-0.5">
            The scan launcher will still post to the backend, but the REST
            scope gate will reject any out-of-scope target with a 403.
          </p>
        </div>
      </Card>
    )
  }

  // FOUNDER + scope populated: subtle confirmation
  if (scope.has_any_entry) {
    const counts = [
      scope.exact_domains.length && `${scope.exact_domains.length} exact`,
      scope.wildcard_domains.length && `${scope.wildcard_domains.length} wildcard`,
      scope.ipv4_cidrs.length && `${scope.ipv4_cidrs.length} CIDR`,
      scope.source_paths.length && `${scope.source_paths.length} source path`,
    ].filter(Boolean).join(' / ')
    return (
      <Card className="border border-status-success/20 bg-status-success/5 p-3 flex items-start gap-3">
        <ShieldCheck size={16} className="text-status-success shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-starlight-200">
            Scope authorized:{' '}
            <span className="font-mono text-starlight-300">{counts || 'declared'}</span>
          </p>
          <p className="text-[11px] text-starlight-500 mt-0.5">
            Targets outside this list are blocked at the REST boundary.
          </p>
        </div>
        <Link
          to="/security/scope"
          className="text-[11px] text-starlight-400 hover:text-primary-400 inline-flex items-center gap-1 shrink-0"
        >
          Edit
          <ExternalLink size={11} />
        </Link>
      </Card>
    )
  }

  // FOUNDER + scope empty: WARN. Without scope, every scan is rejected
  // at the REST boundary. Operator needs the link to fix this before
  // pressing Start.
  return (
    <Card className="border border-status-warning/40 bg-status-warning/10 p-3 flex items-start gap-3">
      <ShieldAlert size={16} className="text-status-warning shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-status-warning font-semibold">
          No authorized scope yet - this scan will not run
        </p>
        <p className="text-[11px] text-starlight-300 mt-0.5">
          Every scan attempt is blocked with a 403 until at least one
          target is declared. Open Scan Scope to add a domain, CIDR, or
          repo path you own.
        </p>
      </div>
      <Link
        to="/security/scope"
        className="text-[11px] inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-status-warning/20 text-status-warning hover:bg-status-warning/30 shrink-0"
      >
        Open Scan Scope
        <ExternalLink size={11} />
      </Link>
    </Card>
  )
}

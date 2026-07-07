import { lazy } from 'react'
import { FileClock, ScrollText, ShieldCheck, TrendingUp } from 'lucide-react'
import { TabbedSurface, type SurfaceTab } from '@/components/layout/TabbedSurface'

// Governance surface (FM-1, 2026-07-02): Approvals / Policies / Audit Log /
// Trust Ladder were four separate nav entries + routes. They are the four
// lenses of the same governance-oversight loop, so they fold into ONE tabbed
// surface. Each tab keeps its real route (/governance/approvals, /policies,
// /governance/audit, /governance/trust) so every deep-link + query param
// (?status on Approvals, ?tab on Policies) still lands on the right tab with
// the child page's state intact -- no redirect drops them (Rule 17). The
// pending-approvals SSE badge lives on GovernanceApprovalsPage and is
// unchanged; the sidebar entry carries the approvals count as before.
// Security Ops / Scan Scope / Opportunities are NOT folded here -- they are the
// v3.7.0 security stack (HANDS-OFF) and stay as their own entries.
const GovernanceApprovalsPage = lazy(() => import('@/pages/GovernanceApprovalsPage'))
const PoliciesPage = lazy(() => import('@/pages/PoliciesPage'))
const GovernanceAuditPage = lazy(() => import('@/pages/GovernanceAuditPage'))
const GovernanceTrustPage = lazy(() => import('@/pages/GovernanceTrustPage'))

const GOVERNANCE_TABS: SurfaceTab[] = [
  { label: 'Approvals', path: '/governance/approvals', icon: <ShieldCheck size={15} />, Component: GovernanceApprovalsPage },
  { label: 'Policies', path: '/policies', icon: <ScrollText size={15} />, Component: PoliciesPage },
  { label: 'Audit Log', path: '/governance/audit', icon: <FileClock size={15} />, Component: GovernanceAuditPage },
  { label: 'Trust Ladder', path: '/governance/trust', icon: <TrendingUp size={15} />, Component: GovernanceTrustPage },
]

/** Lazy-loaded, so this must default-export. */
export default function GovernancePage() {
  return <TabbedSurface tabs={GOVERNANCE_TABS} ariaLabel="Governance views" />
}

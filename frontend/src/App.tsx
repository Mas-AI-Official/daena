import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
// Auth hydration happens at import time in authStore.ts
import '@/stores/authStore'
import { PageLayout } from '@/components/layout/PageLayout'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { ToastContainer, ConfirmDialog, ErrorBoundary, Shimmer, ShimmerBar } from '@/components/common'
import { VoiceProvider } from '@/providers/VoiceProvider'

// Auth pages -- small, load eagerly
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { AuthCallbackPage } from '@/pages/AuthCallbackPage'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { ResetPasswordPage } from '@/pages/ResetPasswordPage'
import { TermsPage } from '@/pages/TermsPage'
import { PrivacyPage } from '@/pages/PrivacyPage'
import { CompleteProfilePage } from '@/pages/CompleteProfilePage'

// Protected pages -- lazy loaded to keep the shell bundle smaller
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const DepartmentChatPage = lazy(() => import('@/pages/DepartmentChatPage'))
// CompanyDashboard + DepartmentInbox deleted 2026-04-17. The /departments
// route is now the single source of truth for the 10-department model --
// live status merged into the existing department cards. Inter-department
// messages surface inside each department's chat room, not in a separate
// inbox page. Backend services (DepartmentStateService,
// DepartmentMessageService) preserved for agent programmatic use.
// Governance surface (FM-1, 2026-07-02): Approvals / Policies / Audit Log /
// Trust Ladder fold into ONE path-driven tabbed container (GovernancePage). It
// owns those four routes and renders the existing tested pages unchanged inside
// its tab region -- deep-links + query params preserved. Opportunities and the
// v3.7.0 security stack are NOT folded in (HANDS-OFF), so they stay separate.
const GovernancePage = lazy(() => import('@/pages/GovernancePage'))
const OpportunityInboxPage = lazy(() => import('@/pages/OpportunityInboxPage'))
const DepartmentsPage = lazy(() => import('@/pages/DepartmentsPage'))
// Department Minds (soul personas) + Company Mode activation -- shipped
// with the TICKET-DEPT-MINDS-01 stack. Consumes /souls + /company-mode.
// The standalone /minds gallery was consolidated into DepartmentsPage
// (FM-4, 2026-07-01) -- each department IS its Mind. Only the per-Mind
// detail view survives; the list route now redirects to /departments.
const MindDetailPage = lazy(() => import('@/pages/MindDetailPage'))
const CompanyModePage = lazy(() => import('@/pages/CompanyModePage'))
// Mission Control "Brain" -- read-only force-graph over the live org
// projection (departments -> agents -> mcp servers -> skills). Wired
// 2026-06-24 per founder go-ahead (Task #6). Renders an honest error
// state when GET /graph is unavailable, so it is safe to expose now.
const MissionControlPage = lazy(() => import('@/pages/MissionControlPage'))
// Work surface (FM-3, 2026-07-02): Tasks / Workstreams / Projects / Pipeline
// fold into ONE path-driven tabbed container (WorkPage). It owns those four
// routes and renders the existing tested pages unchanged inside its tab region
// -- deep-links + query params preserved. /projects/:projectId (the detail
// view) stays a separate route below.
const WorkPage = lazy(() => import('@/pages/WorkPage'))
const SkillsPage = lazy(() => import('@/pages/SkillsPage'))
const ConnectionsPage = lazy(() => import('@/pages/ConnectionsPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const ProjectDetailPage = lazy(() => import('@/pages/ProjectDetailPage'))
// EngagementConsolePage archived 2026-06-20 -- it was self-marked DEPRECATED
// (PR-4, 2026-05-02): the /engagements route redirects to /scan (the single
// canonical scan launcher), so this lazy-import was dead -- never rendered in
// any <Route>. Page moved to .archive/. The /engagements -> /scan redirect
// below stays for old bookmarks.
// CrmPage and VoiceConsolePage were removed 2026-04-17 -- the department
// model (/departments/{id}) is the canonical UX. CRM lives inside the
// Sales department room; voice is an agent capability in Customer
// Service, not a user-facing page. Backend endpoints remain so the
// department rooms can consume them.
// AutopilotPage (P0-5 "Accept-and-Go" console) archived 2026-07-01 -- it was
// never imported and never had a <Route>; the live surface for autopilot runs
// is WorkstreamsPage (/workstreams). Moved to .archive/. The catch-all
// path="*" -> /chat redirect below already covers any stale /autopilot bookmark.

// New pages (Perplexity-level redesign)
const AccountPage = lazy(() => import('@/pages/AccountPage'))
const FilesPage = lazy(() => import('@/pages/FilesPage'))
// AnalyticsPage consolidated into the Brain cockpit 2026-07-02 (FM-5): its
// usage/cost/governance panels now render inside MissionControlPage as an
// "Analytics" overlay. /analytics redirects to /brain below. The page is lazy-
// imported there, so it is no longer routed directly here.
const SecurityDashboardPage = lazy(() => import('@/pages/SecurityDashboardPage'))
const ScanPage = lazy(() => import('@/pages/ScanPage'))
const ScanWalkthroughPage = lazy(() => import('@/pages/ScanWalkthroughPage'))
const SecurityScopePage = lazy(() => import('@/pages/SecurityScopePage'))
const OrgPage = lazy(() => import('@/pages/OrgPage'))

/** Skeleton loading fallback with shimmer animation for polished load perception */
function PageLoader() {
  return (
    <div className="flex-1 overflow-hidden">
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <ShimmerBar width="200px" height="24px" />
        <ShimmerBar width="320px" height="14px" />
        <Shimmer count={4} layout="list" className="pt-4" />
      </div>
    </div>
  )
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />

      {/* Complete Profile -- authenticated but no PageLayout */}
      <Route
        path="/complete-profile"
        element={
          <ProtectedRoute>
            <CompleteProfilePage />
          </ProtectedRoute>
        }
      />

      {/* Protected -- wrapped in PageLayout */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <PageLayout>
              <ErrorBoundary>
              <Suspense fallback={<PageLoader />}>
                <div className="page-enter contents">
                <Routes>
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/chat/:sessionId" element={<ChatPage />} />
                  {/* Dashboard consolidated into the Brain cockpit 2026-06-25
                      (founder go-ahead): /brain is now the single system-overview
                      surface. The Dashboard's unique panels live inside it as an
                      "Overview" overlay. Redirect keeps old bookmarks/links alive. */}
                  <Route path="/dashboard" element={<Navigate to="/brain" replace />} />
                  {/* Legacy URLs redirect to /departments (unified department model).
                      /crm lived as a standalone page; now Sales owns CRM from its room.
                      /voice lived as a standalone page; voice is agent infra -- Customer
                      Service owns inbound calls from its room. */}
                  <Route path="/company" element={<Navigate to="/departments" replace />} />
                  <Route path="/inbox" element={<Navigate to="/departments" replace />} />
                  <Route path="/crm" element={<Navigate to="/departments" replace />} />
                  <Route path="/voice" element={<Navigate to="/departments" replace />} />
                  {/* Governance oversight: /policies, /governance/approvals,
                      /governance/audit, /governance/trust all render the folded
                      GovernancePage container, which preselects the tab from the
                      pathname so each old route + its query params still work. */}
                  <Route path="/policies" element={<GovernancePage />} />
                  <Route path="/governance/approvals" element={<GovernancePage />} />
                  <Route path="/governance/audit" element={<GovernancePage />} />
                  <Route path="/governance/trust" element={<GovernancePage />} />
                  <Route path="/opportunities" element={<OpportunityInboxPage />} />
                  <Route path="/security" element={<SecurityDashboardPage />} />
                  <Route path="/security/scope" element={<SecurityScopePage />} />
                  <Route path="/scan" element={<ScanPage />} />
                  <Route path="/scan/walkthrough/:jobId" element={<ScanWalkthroughPage />} />
                  {/* /engagements was the old scan launcher; sidebar removed
                      2026-04-21. Route preserved for bookmarks but redirects
                      to the canonical /scan entry point. */}
                  <Route path="/engagements" element={<Navigate to="/scan" replace />} />

                  {/* Intelligence */}
                  <Route path="/departments" element={<DepartmentsPage />} />
                  <Route path="/departments/:departmentId" element={<DepartmentChatPage />} />
                  <Route path="/departments/:departmentId/chat" element={<DepartmentChatPage />} />
                  <Route path="/departments/:departmentId/chat/:sessionId" element={<DepartmentChatPage />} />
                  {/* /minds gallery consolidated into /departments (FM-4). The
                      list route redirects; the per-Mind detail view survives. */}
                  <Route path="/minds" element={<Navigate to="/departments" replace />} />
                  <Route path="/minds/:slug" element={<MindDetailPage />} />
                  <Route path="/company-mode" element={<CompanyModePage />} />
                  <Route path="/brain" element={<MissionControlPage />} />
                  <Route path="/skills" element={<SkillsPage />} />

                  {/* Execution: /tasks, /workstreams, /projects, /pipeline all
                      render the folded WorkPage container, which preselects the
                      tab from the pathname so each old route + its query params
                      still work. /projects/:projectId stays separate below. */}
                  <Route path="/tasks" element={<WorkPage />} />
                  <Route path="/workstreams" element={<WorkPage />} />
                  <Route path="/connections" element={<ConnectionsPage />} />
                  <Route path="/daenabot" element={<Navigate to="/chat" replace />} />

                  {/* New pages (Perplexity-level) */}
                  <Route path="/files" element={<FilesPage />} />
                  {/* Analytics folded into the Brain (FM-5, 2026-07-02): its
                      panels live inside /brain as an "Analytics" overlay.
                      Redirect keeps old bookmarks/links alive. */}
                  <Route path="/analytics" element={<Navigate to="/brain" replace />} />

                  {/* Account -- profile management only */}
                  <Route path="/account" element={<AccountPage />} />
                  <Route path="/account/org" element={<OrgPage />} />
                  <Route path="/account/:category" element={<AccountPage />} />

                  {/* Settings -- 13 real Daena settings tabs */}
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/settings/:category" element={<SettingsPage />} />

                  {/* Projects: list + pipeline are tabs of the Work surface;
                      the per-project detail view stays its own route. */}
                  <Route path="/projects" element={<WorkPage />} />
                  <Route path="/pipeline" element={<WorkPage />} />
                  <Route path="/projects/:projectId" element={<ProjectDetailPage />} />

                  {/* Legacy redirects */}
                  <Route path="/founder" element={<Navigate to="/settings/governance" replace />} />

                  {/* Catch-all -> chat */}
                  <Route path="*" element={<Navigate to="/chat" replace />} />
                </Routes>
                </div>
              </Suspense>
              </ErrorBoundary>
            </PageLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default function App() {
  // Auth hydration happens synchronously at module scope in authStore.ts
  // so ProtectedRoute sees the token on initial mount.

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <VoiceProvider>
          <AppRoutes />
          <ToastContainer />
          {/* Global themed confirm/alert dialog. Reads state from
              confirmStore so any non-React code can call
              confirmDialog({...}) and get a Promise<boolean>. */}
          <ConfirmDialog />
        </VoiceProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

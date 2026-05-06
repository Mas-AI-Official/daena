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
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
// CompanyDashboard + DepartmentInbox deleted 2026-04-17. The /departments
// route is now the single source of truth for the 10-department model --
// live status merged into the existing department cards. Inter-department
// messages surface inside each department's chat room, not in a separate
// inbox page. Backend services (DepartmentStateService,
// DepartmentMessageService) preserved for agent programmatic use.
const PoliciesPage = lazy(() => import('@/pages/PoliciesPage'))
const GovernanceApprovalsPage = lazy(() => import('@/pages/GovernanceApprovalsPage'))
const GovernanceAuditPage = lazy(() => import('@/pages/GovernanceAuditPage'))
const GovernanceTrustPage = lazy(() => import('@/pages/GovernanceTrustPage'))
const DepartmentsPage = lazy(() => import('@/pages/DepartmentsPage'))
// Department Minds (soul personas) + Company Mode activation -- shipped
// with the TICKET-DEPT-MINDS-01 stack. Consumes /souls + /company-mode.
const MindsPage = lazy(() => import('@/pages/MindsPage'))
const MindDetailPage = lazy(() => import('@/pages/MindDetailPage'))
const CompanyModePage = lazy(() => import('@/pages/CompanyModePage'))
const TasksPage = lazy(() => import('@/pages/TasksPage'))
const SkillsPage = lazy(() => import('@/pages/SkillsPage'))
const ConnectionsPage = lazy(() => import('@/pages/ConnectionsPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const ProjectsPage = lazy(() => import('@/pages/ProjectsPage'))
const ProjectDetailPage = lazy(() => import('@/pages/ProjectDetailPage'))
const PipelinePage = lazy(() => import('@/pages/PipelinePage'))
const WorkstreamsPage = lazy(() => import('@/pages/WorkstreamsPage'))
const EngagementConsolePage = lazy(() => import('@/pages/EngagementConsolePage'))
// CrmPage and VoiceConsolePage were removed 2026-04-17 -- the department
// model (/departments/{id}) is the canonical UX. CRM lives inside the
// Sales department room; voice is an agent capability in Customer
// Service, not a user-facing page. Backend endpoints remain so the
// department rooms can consume them.

// New pages (Perplexity-level redesign)
const AccountPage = lazy(() => import('@/pages/AccountPage'))
const FilesPage = lazy(() => import('@/pages/FilesPage'))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const SecurityDashboardPage = lazy(() => import('@/pages/SecurityDashboardPage'))
const ScanPage = lazy(() => import('@/pages/ScanPage'))
const ScanWalkthroughPage = lazy(() => import('@/pages/ScanWalkthroughPage'))
const SecurityScopePage = lazy(() => import('@/pages/SecurityScopePage'))

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
                  <Route path="/dashboard" element={<DashboardPage />} />
                  {/* Legacy URLs redirect to /departments (unified department model).
                      /crm lived as a standalone page; now Sales owns CRM from its room.
                      /voice lived as a standalone page; voice is agent infra -- Customer
                      Service owns inbound calls from its room. */}
                  <Route path="/company" element={<Navigate to="/departments" replace />} />
                  <Route path="/inbox" element={<Navigate to="/departments" replace />} />
                  <Route path="/crm" element={<Navigate to="/departments" replace />} />
                  <Route path="/voice" element={<Navigate to="/departments" replace />} />
                  <Route path="/policies" element={<PoliciesPage />} />

                  {/* Governance + Security */}
                  <Route path="/governance/approvals" element={<GovernanceApprovalsPage />} />
                  <Route path="/governance/audit" element={<GovernanceAuditPage />} />
                  <Route path="/governance/trust" element={<GovernanceTrustPage />} />
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
                  <Route path="/minds" element={<MindsPage />} />
                  <Route path="/minds/:slug" element={<MindDetailPage />} />
                  <Route path="/company-mode" element={<CompanyModePage />} />
                  <Route path="/skills" element={<SkillsPage />} />

                  {/* Execution */}
                  <Route path="/tasks" element={<TasksPage />} />
                  <Route path="/workstreams" element={<WorkstreamsPage />} />
                  <Route path="/connections" element={<ConnectionsPage />} />
                  <Route path="/daenabot" element={<Navigate to="/chat" replace />} />

                  {/* New pages (Perplexity-level) */}
                  <Route path="/files" element={<FilesPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />

                  {/* Account -- profile management only */}
                  <Route path="/account" element={<AccountPage />} />
                  <Route path="/account/:category" element={<AccountPage />} />

                  {/* Settings -- 13 real Daena settings tabs */}
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/settings/:category" element={<SettingsPage />} />

                  {/* Projects */}
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/pipeline" element={<PipelinePage />} />
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

import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
// Auth hydration happens at import time in authStore.ts
import '@/stores/authStore'
import { PageLayout } from '@/components/layout/PageLayout'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { ToastContainer, ErrorBoundary, Shimmer, ShimmerBar } from '@/components/common'
import { VoiceProvider } from '@/providers/VoiceProvider'

// Auth pages — small, load eagerly
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { AuthCallbackPage } from '@/pages/AuthCallbackPage'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { ResetPasswordPage } from '@/pages/ResetPasswordPage'
import { TermsPage } from '@/pages/TermsPage'
import { PrivacyPage } from '@/pages/PrivacyPage'
import { CompleteProfilePage } from '@/pages/CompleteProfilePage'

// Protected pages — lazy loaded to keep the shell bundle smaller
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const DepartmentChatPage = lazy(() => import('@/pages/DepartmentChatPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const GovernanceApprovalsPage = lazy(() => import('@/pages/GovernanceApprovalsPage'))
const GovernanceAuditPage = lazy(() => import('@/pages/GovernanceAuditPage'))
const DepartmentsPage = lazy(() => import('@/pages/DepartmentsPage'))
const TasksPage = lazy(() => import('@/pages/TasksPage'))
const SkillsPage = lazy(() => import('@/pages/SkillsPage'))
const DaenaBotPage = lazy(() => import('@/pages/DaenaBotPage'))
const ConnectionsPage = lazy(() => import('@/pages/ConnectionsPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const FounderPage = lazy(() => import('@/pages/FounderPage'))
const ProjectsPage = lazy(() => import('@/pages/ProjectsPage'))
const ProjectDetailPage = lazy(() => import('@/pages/ProjectDetailPage'))
const PipelinePage = lazy(() => import('@/pages/PipelinePage'))

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

      {/* Complete Profile — authenticated but no PageLayout */}
      <Route
        path="/complete-profile"
        element={
          <ProtectedRoute>
            <CompleteProfilePage />
          </ProtectedRoute>
        }
      />

      {/* Protected — wrapped in PageLayout */}
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

                  {/* Governance */}
                  <Route path="/governance/approvals" element={<GovernanceApprovalsPage />} />
                  <Route path="/governance/audit" element={<GovernanceAuditPage />} />

                  {/* Intelligence */}
                  <Route path="/departments" element={<DepartmentsPage />} />
                  <Route path="/departments/:departmentId" element={<DepartmentChatPage />} />
                  <Route path="/departments/:departmentId/chat" element={<DepartmentChatPage />} />
                  <Route path="/departments/:departmentId/chat/:sessionId" element={<DepartmentChatPage />} />
                  <Route path="/skills" element={<SkillsPage />} />

                  {/* Execution */}
                  <Route path="/tasks" element={<TasksPage />} />
                  <Route path="/daenabot" element={<Navigate to="/chat" replace />} />
                  <Route path="/connections" element={<ConnectionsPage />} />

                  {/* Settings (9 categories) */}
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/settings/:category" element={<SettingsPage />} />

                  {/* Projects */}
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/pipeline" element={<PipelinePage />} />
                  <Route path="/projects/:projectId" element={<ProjectDetailPage />} />

                  {/* Founder (removed, redirect to settings) */}
                  <Route path="/founder" element={<Navigate to="/settings/governance" replace />} />

                  {/* Catch-all → chat */}
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
        </VoiceProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

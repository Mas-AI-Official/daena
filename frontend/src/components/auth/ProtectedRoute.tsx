import { useEffect, useRef } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { hydrateUiFromBackend } from '@/stores/uiStore'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, profileComplete } = useAuthStore()
  const location = useLocation()
  const hydrated = useRef(false)

  // Hydrate UI preferences from backend once after auth confirmed
  useEffect(() => {
    if (isAuthenticated && profileComplete && !hydrated.current) {
      hydrated.current = true
      void hydrateUiFromBackend()
    }
  }, [isAuthenticated, profileComplete])

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // OAuth users who haven't accepted terms yet
  if (!profileComplete && location.pathname !== '/complete-profile') {
    return <Navigate to="/complete-profile" replace />
  }

  return <>{children}</>
}

export default ProtectedRoute

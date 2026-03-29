import { useEffect, useRef } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { hydrateUiFromBackend } from '@/stores/uiStore'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()
  const hydrated = useRef(false)

  // Hydrate UI preferences from backend once after auth confirmed
  useEffect(() => {
    if (isAuthenticated && !hydrated.current) {
      hydrated.current = true
      void hydrateUiFromBackend()
    }
  }, [isAuthenticated])

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

export default ProtectedRoute

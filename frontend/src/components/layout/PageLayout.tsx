import { useEffect, type ReactNode } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useUiStore } from '@/stores/uiStore'

interface PageLayoutProps {
  children: ReactNode
}

/**
 * Main app shell — CSS Grid layout with:
 * - Row 1: Header (64px fixed)
 * - Row 2: Sidebar (left) + Main content (right, scrollable)
 */
export function PageLayout({ children }: PageLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { mobileSidebarOpen, setMobileSidebarOpen } = useUiStore()

  // Ctrl+N / Cmd+N -> new chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        navigate('/chat')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate])

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [location.pathname, setMobileSidebarOpen])

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-midnight-900">
      {/* Skip-to-content link: visible only on Tab focus */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100]
                   focus:px-4 focus:py-2 focus:rounded-lg focus:bg-primary-500 focus:text-white
                   focus:text-sm focus:font-medium focus:shadow-lg"
      >
        Skip to main content
      </a>

      {/* Header */}
      <Header />

      {/* Body */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Desktop sidebar */}
        <Sidebar />

        {/* Mobile sidebar overlay */}
        {mobileSidebarOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/60 z-40 sm:hidden"
              onClick={() => setMobileSidebarOpen(false)}
            />
            <div className="fixed inset-y-0 left-0 w-64 z-50 sm:hidden">
              <Sidebar mobile />
            </div>
          </>
        )}

        <main id="main-content" role="main" className="flex-1 overflow-y-auto scrollbar-hide page-enter">
          {children}
        </main>
      </div>
    </div>
  )
}

export default PageLayout

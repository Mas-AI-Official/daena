import { Suspense, type ComponentType, type LazyExoticComponent, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BACKGROUNDS } from '@/styles/designTokens'

export interface SurfaceTab {
  /** Visible tab label. */
  label: string
  /**
   * The tab's REAL route (e.g. /tasks). Clicking navigates here and the tab
   * is active when location.pathname === path. Keeping the real path -- not a
   * synthetic ?tab= query -- means every existing deep-link and query param
   * (?status, ?focus, ?tab) still lands on the right tab with the child page's
   * own state intact. A redirect would drop those (Rule 17 regression).
   */
  path: string
  icon?: ReactNode
  /**
   * The existing, tested page -- rendered UNCHANGED inside the tab region
   * (reuse, not rewrite -- Rule 17 safe). Lazy so only the active tab's chunk
   * loads on demand.
   */
  Component: LazyExoticComponent<ComponentType>
}

interface TabbedSurfaceProps {
  tabs: SurfaceTab[]
  /** Accessible name for the tablist (e.g. "Work views"). */
  ariaLabel: string
}

/**
 * TabbedSurface -- a path-driven container that folds several sibling pages
 * into ONE surface with a shared tab bar, without rewriting any of them.
 *
 * Each tab owns its real route; the active tab is read from the URL, so
 * /tasks?status=RUNNING or /policies?tab=department_rules deep-link straight
 * to the right tab with the child's query params preserved. Old routes keep
 * working because App.tsx points each of them at this container.
 *
 * Layout: `flex h-full flex-col` fills the routed <main> (which is a
 * flex-1 overflow-y-auto child with a definite height). A `shrink-0` tab bar
 * sits on top; the region below is `flex-1 overflow-y-auto min-h-0` so BOTH
 * self-contained (`h-full overflow-y-auto`) pages -- their h-full resolves
 * against the region's definite flex height and they scroll internally -- and
 * natural-flow pages (which would clip under overflow-hidden) scroll correctly.
 */
export function TabbedSurface({ tabs, ariaLabel }: TabbedSurfaceProps) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const active = tabs.find((t) => t.path === pathname) ?? tabs[0]
  const ActivePage = active.Component

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: BACKGROUNDS.midnight }}>
      <div
        role="tablist"
        aria-label={ariaLabel}
        className="flex shrink-0 items-center gap-1 overflow-x-auto scrollbar-hide border-b border-white/5 px-4 py-2"
      >
        {tabs.map((t) => {
          const isActive = t.path === active.path
          return (
            <button
              key={t.path}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => {
                if (!isActive) navigate(t.path)
              }}
              className={
                isActive
                  ? 'flex shrink-0 items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-sm font-medium text-white'
                  : 'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-white/55 transition-colors hover:bg-white/5 hover:text-white'
              }
            >
              {t.icon}
              {t.label}
            </button>
          )
        })}
      </div>
      <div className="relative min-h-0 flex-1 overflow-y-auto">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-white/50">
              Loading...
            </div>
          }
        >
          <ActivePage />
        </Suspense>
      </div>
    </div>
  )
}

export default TabbedSurface

/**
 * Shimmer: animated loading placeholder that replaces basic spinners.
 * Uses the shimmer keyframe from globals.css for a Slack/Linear-style
 * loading effect. Renders rows of varying widths by default, or accepts
 * a custom layout via the `layout` prop.
 */

interface ShimmerBarProps {
  width?: string
  height?: string
  className?: string
}

/** Single shimmer bar with gradient sweep animation */
export function ShimmerBar({ width = '100%', height = '12px', className = '' }: ShimmerBarProps) {
  return (
    <div
      className={`rounded-md animate-shimmer ${className}`}
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 75%)',
        backgroundSize: '200% 100%',
      }}
    />
  )
}

type ShimmerLayout = 'list' | 'card-grid' | 'detail'

interface ShimmerProps {
  /** Number of placeholder rows/cards to show */
  count?: number
  /** Predefined layout pattern */
  layout?: ShimmerLayout
  className?: string
}

/** Composite shimmer loader with predefined layouts */
export function Shimmer({ count = 4, layout = 'list', className = '' }: ShimmerProps) {
  if (layout === 'card-grid') {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 ${className}`}>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="p-4 rounded-xl border border-white/5 bg-midnight-300/30 space-y-3">
            <ShimmerBar width="60%" height="14px" />
            <ShimmerBar width="100%" height="10px" />
            <ShimmerBar width="80%" height="10px" />
            <div className="flex gap-2 pt-1">
              <ShimmerBar width="48px" height="20px" className="rounded-full" />
              <ShimmerBar width="64px" height="20px" className="rounded-full" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (layout === 'detail') {
    return (
      <div className={`space-y-4 ${className}`}>
        <ShimmerBar width="40%" height="20px" />
        <ShimmerBar width="70%" height="12px" />
        <div className="space-y-2 pt-2">
          {Array.from({ length: count }).map((_, i) => (
            <ShimmerBar key={i} width={`${85 - i * 10}%`} height="10px" />
          ))}
        </div>
      </div>
    )
  }

  // Default: list layout
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-white/5 bg-midnight-300/20">
          <ShimmerBar width="32px" height="32px" className="rounded-lg shrink-0" />
          <div className="flex-1 space-y-2">
            <ShimmerBar width={`${65 + (i % 3) * 10}%`} height="12px" />
            <ShimmerBar width={`${45 + (i % 2) * 15}%`} height="10px" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default Shimmer

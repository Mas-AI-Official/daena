import type { ReactNode } from 'react'

// BadgeVariant accepts both semantic names (danger/success/warning/info)
// and alias forms used by various pages (error is an alias for danger,
// outline is an unstyled/bordered variant used by ScanPage).
type BadgeVariant =
  | 'default' | 'success' | 'warning' | 'danger' | 'info'
  | 'purple' | 'cyan' | 'amber'
  | 'error'   // alias for danger, used by SecurityDashboardPage
  | 'outline' // bordered-only variant used by ScanPage

interface BadgeProps {
  variant?: BadgeVariant
  children: ReactNode
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-primary-500/20 text-primary-400 border-primary-500/30',
  success: 'bg-status-success/20 text-status-success border-status-success/30',
  warning: 'bg-status-warning/20 text-status-warning border-status-warning/30',
  danger: 'bg-status-error/20 text-status-error border-status-error/30',
  info: 'bg-primary-500/20 text-primary-400 border-primary-500/30',
  purple: 'bg-accent-purple/20 text-accent-purple border-accent-purple/30',
  cyan: 'bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30',
  amber: 'bg-accent-amber/20 text-accent-amber border-accent-amber/30',
  error: 'bg-status-error/20 text-status-error border-status-error/30',
  outline: 'bg-transparent text-starlight-300 border-white/15',
}

const dotColors: Record<BadgeVariant, string> = {
  default: 'bg-primary-400',
  success: 'bg-status-success',
  warning: 'bg-status-warning',
  danger: 'bg-status-error',
  info: 'bg-primary-400',
  purple: 'bg-accent-purple',
  cyan: 'bg-accent-cyan',
  amber: 'bg-accent-amber',
  error: 'bg-status-error',
  outline: 'bg-starlight-400',
}

export function Badge({ variant = 'default', children, size = 'sm', dot, className = '' }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full border font-medium
        ${size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs'}
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]}`} />}
      {children}
    </span>
  )
}

export default Badge

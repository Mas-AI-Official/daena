/**
 * EmptyState: standardized empty-data display for all pages.
 * Shows a relevant icon, clear message, and optional action suggestion.
 * Prevents blank white space which signals a broken app to users.
 *
 * Icon prop accepts either a LucideIcon component or a React element.
 * Action prop accepts either a {label, onClick} object or a React element.
 */
import { type ReactNode, isValidElement } from 'react'
import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  /** LucideIcon component or pre-rendered React element */
  icon: LucideIcon | ReactNode
  title: string
  description?: string
  /** CTA button: {label, onClick} object or a React element */
  action?: { label: string; onClick: () => void } | ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
  // Render icon: if it's a React element use it directly, otherwise treat as component
  const renderIcon = () => {
    if (isValidElement(icon)) return icon
    const Icon = icon as LucideIcon
    return <Icon size={32} className="text-starlight-500" />
  }

  // Render action: if it's a React element use it directly, otherwise build button
  const renderAction = () => {
    if (!action) return null
    if (isValidElement(action)) return <div className="mt-4">{action}</div>
    const { label, onClick } = action as { label: string; onClick: () => void }
    return (
      <button
        onClick={onClick}
        className="mt-4 px-4 py-2 rounded-lg text-xs font-medium text-primary-400 bg-primary-500/10 border border-primary-500/20 hover:bg-primary-500/15 transition-colors cursor-pointer active:scale-[0.97]"
      >
        {label}
      </button>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex flex-col items-center justify-center py-16 px-6 text-center ${className}`}
    >
      <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/5 mb-4">
        {renderIcon()}
      </div>
      <h3 className="text-sm font-medium text-starlight-300 mb-1">{title}</h3>
      {description && (
        <p className="text-xs text-starlight-500 max-w-xs">{description}</p>
      )}
      {renderAction()}
    </motion.div>
  )
}

export default EmptyState

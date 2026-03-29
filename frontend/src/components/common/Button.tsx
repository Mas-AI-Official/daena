import { forwardRef, type ReactNode } from 'react'
import { motion } from 'framer-motion'

type Variant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'premium'
type Size = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps {
  variant?: Variant
  size?: Size
  isLoading?: boolean
  children?: ReactNode
  className?: string
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
}

const variantStyles: Record<Variant, string> = {
  primary:
    'bg-primary-500 hover:bg-primary-600 text-white shadow-[var(--shadow-glow-sm)] hover:shadow-[var(--shadow-glow-primary)]',
  secondary: 'bg-midnight-400 hover:bg-midnight-500 text-starlight-200 border border-white/10',
  outline: 'bg-transparent border border-white/10 hover:border-white/20 text-starlight-200 hover:bg-white/5',
  ghost: 'bg-transparent hover:bg-white/5 text-starlight-300 hover:text-starlight-100',
  danger:
    'bg-status-error hover:bg-status-error/80 text-white shadow-[var(--shadow-glow-error)]',
  premium:
    'bg-gradient-to-r from-primary-600 to-primary-400 text-white hover:from-primary-500 hover:to-primary-400',
}

const sizeStyles: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-md',
  md: 'h-10 px-4 text-sm gap-2 rounded-lg',
  lg: 'h-12 px-6 text-base gap-2.5 rounded-lg',
  icon: 'h-10 w-10 rounded-lg flex items-center justify-center',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading, children, className = '', disabled, type, onClick }, ref) => {
    return (
      <motion.button
        ref={ref}
        type={type}
        onClick={onClick}
        whileTap={{ scale: 0.98 }}
        className={`
          inline-flex items-center justify-center font-medium transition-all duration-200
          disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer
          ${variantStyles[variant]}
          ${sizeStyles[size]}
          ${className}
        `}
        disabled={disabled || isLoading}
      >
        {isLoading && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {children}
      </motion.button>
    )
  },
)

Button.displayName = 'Button'
export default Button

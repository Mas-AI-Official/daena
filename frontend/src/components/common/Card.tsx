import type { ReactNode, HTMLAttributes } from 'react'

type CardVariant = 'default' | 'glass' | 'elevated' | 'outline'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant
  children: ReactNode
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const variantStyles: Record<CardVariant, string> = {
  default: 'bg-midnight-300 border border-white/5',
  glass: 'glass-card',
  elevated: 'bg-midnight-400 shadow-lg border border-white/5',
  outline: 'bg-transparent border border-white/10',
}

const paddingStyles = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-6',
}

export function Card({ variant = 'default', padding = 'md', children, className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-xl ${variantStyles[variant]} ${paddingStyles[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export default Card

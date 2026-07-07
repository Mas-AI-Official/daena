import { forwardRef, type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', id, 'aria-describedby': ariaDescribedBy, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-')
    // Wire the error message to the input so AT announces it (WCAG 3.3.1): generate an
    // id for the message and point aria-describedby at it. Merge any consumer-supplied
    // aria-describedby so we associate the error without clobbering an existing one.
    const errorId = error && inputId ? `${inputId}-error` : undefined
    const describedBy = [ariaDescribedBy, errorId].filter(Boolean).join(' ') || undefined

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-starlight-300">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={`
            glass-input text-starlight-100 text-sm placeholder:text-starlight-400
            focus-ring transition-all duration-200
            ${error ? 'border-status-error/50 focus:ring-status-error/50' : ''}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p id={errorId} className="text-xs text-status-error">
            {error}
          </p>
        )}
      </div>
    )
  },
)

Input.displayName = 'Input'
export default Input

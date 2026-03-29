import { forwardRef, type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-')

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
          className={`
            glass-input text-starlight-100 text-sm placeholder:text-starlight-400
            focus-ring transition-all duration-200
            ${error ? 'border-status-error/50 focus:ring-status-error/50' : ''}
            ${className}
          `}
          {...props}
        />
        {error && <p className="text-xs text-status-error">{error}</p>}
      </div>
    )
  },
)

Input.displayName = 'Input'
export default Input

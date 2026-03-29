interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  size?: 'sm' | 'md'
  disabled?: boolean
}

export function Switch({ checked, onChange, label, size = 'md', disabled }: SwitchProps) {
  const trackSize = size === 'sm' ? 'h-5 w-9' : 'h-6 w-11'
  const thumbSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-5 w-5'
  const translate = size === 'sm' ? 'translate-x-4' : 'translate-x-5'

  return (
    <label className={`inline-flex items-center gap-2.5 ${disabled ? 'opacity-50' : 'cursor-pointer'}`}>
      <button
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`
          relative inline-flex ${trackSize} items-center rounded-full transition-all duration-200
          ${checked ? 'bg-primary-600 border border-primary-600' : 'bg-white/10 border border-white/20'}
          cursor-pointer
        `}
      >
        <span
          className={`
            inline-block ${thumbSize} rounded-full bg-white shadow-md
            transform transition-transform duration-200
            ${checked ? translate : 'translate-x-0.5'}
          `}
        />
      </button>
      {label && <span className="text-sm text-starlight-200 select-none">{label}</span>}
    </label>
  )
}

export default Switch

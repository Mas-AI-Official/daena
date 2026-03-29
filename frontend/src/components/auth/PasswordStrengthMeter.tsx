import { useMemo } from 'react'

/**
 * Password strength meter — compact real-time visual feedback.
 *
 * Checks 5 criteria matching the backend validator in auth.py:
 *   1. Length >= 12
 *   2. At least 1 uppercase
 *   3. At least 1 lowercase
 *   4. At least 1 digit
 *   5. At least 1 special character
 *
 * Renders a slim 5-segment bar + label. Compact checklist only
 * shows unmet criteria so it collapses as the password improves.
 */

interface PasswordStrengthMeterProps {
  password: string
}

interface Criterion {
  label: string
  test: (pw: string) => boolean
}

const CRITERIA: Criterion[] = [
  { label: '12+ chars', test: (pw) => pw.length >= 12 },
  { label: 'Uppercase', test: (pw) => /[A-Z]/.test(pw) },
  { label: 'Lowercase', test: (pw) => /[a-z]/.test(pw) },
  { label: 'Number', test: (pw) => /\d/.test(pw) },
  { label: 'Special', test: (pw) => /[^A-Za-z0-9]/.test(pw) },
]

const LEVELS = [
  { label: 'Very Weak', color: 'bg-status-error' },
  { label: 'Weak', color: 'bg-orange-500' },
  { label: 'Fair', color: 'bg-amber-500' },
  { label: 'Good', color: 'bg-lime-500' },
  { label: 'Strong', color: 'bg-status-success' },
] as const

export function PasswordStrengthMeter({ password }: PasswordStrengthMeterProps) {
  const { passed, level } = useMemo(() => {
    const results = CRITERIA.map((c) => c.test(password))
    const count = results.filter(Boolean).length
    return { passed: results, level: count }
  }, [password])

  // Don't render when empty
  if (password.length === 0) return null

  const info = LEVELS[level - 1] ?? LEVELS[0]
  const unmetCriteria = CRITERIA.filter((_, i) => !passed[i])

  return (
    <div className="-mt-2 space-y-1">
      {/* Bar + label row */}
      <div className="flex items-center gap-3">
        <div className="flex gap-0.5 flex-1">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors duration-200 ${
                i < level ? info.color : 'bg-midnight-700'
              }`}
            />
          ))}
        </div>
        <span className="text-[11px] font-medium text-starlight-400 whitespace-nowrap">
          {info.label}
        </span>
      </div>

      {/* Compact unmet criteria — disappears when all 5 pass */}
      {unmetCriteria.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
          {unmetCriteria.map((c) => (
            <span key={c.label} className="text-[10px] text-starlight-500">
              ○ {c.label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default PasswordStrengthMeter

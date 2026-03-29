/**
 * usePageTitle: sets document.title on mount, restores on unmount.
 * Format: "{title} | Daena" (or just "Daena" if no title given).
 */
import { useEffect } from 'react'

export function usePageTitle(title?: string) {
  useEffect(() => {
    const prev = document.title
    document.title = title ? `${title} | Daena` : 'Daena'
    return () => {
      document.title = prev
    }
  }, [title])
}

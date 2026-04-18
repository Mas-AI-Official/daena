/**
 * Toast notification store — global toast state driven by Zustand.
 *
 * Why Zustand instead of React context: toasts are triggered from stores
 * (chatStore, authStore) which live outside React — Zustand lets any code
 * call `addToast()` without needing a React component tree.
 *
 * Usage:
 *   import { useToastStore } from '@/stores/toastStore'
 *   useToastStore.getState().addToast({ type: 'error', message: 'Something broke' })
 */
import { create } from 'zustand'

/**
 * ToastType --
 * - success/error/warning/info: standard UX.
 * - governance: pipeline event that needs an action or review (pending
 *   approvals, blocked tools, VP plan routed to multiple departments).
 *   Rendered with a shield icon so Masoud can scan for governance-
 *   related activity in one glance.
 */
export type ToastType = 'success' | 'error' | 'warning' | 'info' | 'governance'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number // ms, default 5000
}

interface ToastState {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
  clearAll: () => void
}

let _counter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (toast) => {
    const id = `toast-${++_counter}-${Date.now()}`
    const duration = toast.duration ?? 5000

    set((s) => ({
      toasts: [...s.toasts, { ...toast, id }].slice(-5), // keep max 5
    }))

    // Auto-dismiss
    if (duration > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
      }, duration)
    }
  },

  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  clearAll: () => set({ toasts: [] }),
}))

// ── Convenience helpers (import-free from stores) ──

export const toast = {
  success: (message: string, duration?: number) =>
    useToastStore.getState().addToast({ type: 'success', message, duration }),
  error: (message: string, duration?: number) =>
    useToastStore.getState().addToast({ type: 'error', message, duration }),
  warning: (message: string, duration?: number) =>
    useToastStore.getState().addToast({ type: 'warning', message, duration }),
  info: (message: string, duration?: number) =>
    useToastStore.getState().addToast({ type: 'info', message, duration }),
  // Governance: pipeline events that warrant attention (pending
  // approvals, blocked tools, VP routing). Longer default duration
  // (8s) so the operator has time to see and click through.
  governance: (message: string, duration?: number) =>
    useToastStore
      .getState()
      .addToast({ type: 'governance', message, duration: duration ?? 8000 }),
}

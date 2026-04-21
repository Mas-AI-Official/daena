/**
 * Global confirm/alert store — Zustand-backed drop-in replacement for
 * ``window.confirm`` and ``window.alert`` with a Daena-themed modal.
 *
 * Why this exists: native browser dialogs break the design system
 * (ugly OS chrome, no dark mode, not styleable). ``confirm()`` /
 * ``alert()`` calls inherited this every time. This store + the
 * ``<ConfirmDialog />`` mount at App root let any code call
 * ``confirmDialog({...})`` and receive a Promise<boolean>, matching
 * the native signature while rendering the Daena palette.
 *
 * Usage:
 *     import { confirmDialog, alertDialog } from '@/stores/confirmStore'
 *
 *     const ok = await confirmDialog({
 *         title: 'Delete project?',
 *         message: 'This cannot be undone.',
 *         confirmLabel: 'Delete',
 *         variant: 'danger',
 *     })
 *     if (!ok) return
 *
 *     await alertDialog({ title: 'Heads up', message: 'Saved.' })
 */
import { create } from 'zustand'

/**
 * Dialog variants control the confirm button colour only -- the modal
 * chrome is identical for all.
 *   - ``danger``   -> red tint, used for irreversible destructive ops
 *   - ``warning``  -> amber tint, used for high-cost / noisy actions
 *   - ``primary``  -> teal tint, used for routine confirmations
 */
export type ConfirmVariant = 'danger' | 'warning' | 'primary'

export interface ConfirmRequest {
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: ConfirmVariant
  /**
   * When provided, the dialog is alert-style: only a single dismiss
   * button, Promise resolves to ``true`` on dismiss. Internal use.
   */
  _alertOnly?: boolean
  /**
   * When set, the dialog renders a text input above the buttons. The
   * confirm button then resolves with the typed string (not a bool).
   * See ``promptDialog()`` below for the public helper. Internal use.
   */
  _promptConfig?: {
    placeholder?: string
    defaultValue?: string
    multiline?: boolean
    maxLength?: number
  }
}

type ResolveFn = (value: boolean | string | null) => void

interface ConfirmState {
  open: boolean
  request: ConfirmRequest | null
  resolve: ResolveFn | null
  ask: (request: ConfirmRequest) => Promise<boolean | string | null>
  resolveAnd: (value: boolean | string | null) => void
  close: () => void
}

export const useConfirmStore = create<ConfirmState>((set, get) => ({
  open: false,
  request: null,
  resolve: null,

  ask: (request) => {
    // If a dialog is already open, resolve it as cancelled before
    // opening the next one. Prevents pending promises from leaking.
    const current = get().resolve
    if (current) {
      // Cancel-like value for the already-open dialog regardless of
      // its mode (confirm → false, prompt → null).
      current(request._promptConfig ? null : false)
    }

    return new Promise<boolean | string | null>((resolve) => {
      set({ open: true, request, resolve: resolve as ResolveFn })
    })
  },

  resolveAnd: (value) => {
    const { resolve } = get()
    if (resolve) resolve(value)
    set({ open: false, request: null, resolve: null })
  },

  close: () => {
    const { resolve, request } = get()
    if (resolve) {
      // Prompt-style cancel → null. Confirm-style cancel → false.
      resolve(request?._promptConfig ? null : false)
    }
    set({ open: false, request: null, resolve: null })
  },
}))

/**
 * Themed replacement for ``window.confirm``.
 *
 * Returns Promise<boolean>:
 *   - ``true``  -> user clicked the confirm button
 *   - ``false`` -> user cancelled / pressed ESC / clicked backdrop
 */
export function confirmDialog(
  request: Omit<ConfirmRequest, '_alertOnly' | '_promptConfig'>,
): Promise<boolean> {
  return useConfirmStore
    .getState()
    .ask(request)
    .then((value) => value === true)
}

/**
 * Themed replacement for ``window.alert``. The Promise resolves when
 * the user dismisses the dialog; callers that don't care about the
 * dismiss timing can fire and forget.
 */
export function alertDialog(
  request: Omit<ConfirmRequest, '_alertOnly' | '_promptConfig'>,
): Promise<void> {
  return useConfirmStore
    .getState()
    .ask({ ...request, _alertOnly: true })
    .then(() => undefined)
}

export interface PromptRequest
  extends Omit<ConfirmRequest, '_alertOnly' | '_promptConfig'> {
  placeholder?: string
  defaultValue?: string
  /** Render a textarea instead of a single-line input. */
  multiline?: boolean
  /** Enforced on the input element's ``maxLength``. */
  maxLength?: number
}

/**
 * Themed replacement for ``window.prompt``.
 *
 * Returns Promise<string | null>:
 *   - string -> the value the user submitted (possibly empty)
 *   - null   -> user cancelled / pressed ESC / clicked backdrop
 *
 * Matches native ``prompt()`` semantics so existing call sites that
 * check ``=== null`` for "cancelled" keep working.
 */
export function promptDialog(request: PromptRequest): Promise<string | null> {
  const { placeholder, defaultValue, multiline, maxLength, ...rest } = request
  return useConfirmStore
    .getState()
    .ask({
      ...rest,
      _promptConfig: { placeholder, defaultValue, multiline, maxLength },
    })
    .then((value) => {
      if (value === null || value === false) return null
      return typeof value === 'string' ? value : null
    })
}

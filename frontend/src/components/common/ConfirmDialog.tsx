/**
 * ConfirmDialog — Daena-themed replacement for the native
 * ``window.confirm`` / ``window.alert`` popups. Mounted once at App
 * root; reads state from ``confirmStore`` so any code can trigger it
 * via ``confirmDialog({...})`` without a React render tree.
 *
 * Variant styling:
 *   - danger   -> red primary button, used for irreversible deletes
 *   - warning  -> amber primary button, used for high-cost ops
 *   - primary  -> teal primary button, used for routine confirms
 *
 * All variants share the same dark-slate card, rounded-3xl chrome,
 * and spring motion so the transition matches the rest of the Daena
 * dialog surface.
 */
import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Modal } from './Modal'
import { useConfirmStore, type ConfirmVariant } from '@/stores/confirmStore'

const VARIANT_STYLES: Record<
  ConfirmVariant,
  { button: string; iconBg: string; iconColor: string; Icon: typeof AlertTriangle }
> = {
  danger: {
    button:
      'bg-status-error/90 hover:bg-status-error text-white border border-status-error/50 shadow-lg shadow-status-error/20',
    iconBg: 'bg-status-error/10 border-status-error/20',
    iconColor: 'text-status-error',
    Icon: AlertTriangle,
  },
  warning: {
    button:
      'bg-accent-amber/90 hover:bg-accent-amber text-midnight-950 border border-accent-amber/50 shadow-lg shadow-accent-amber/20',
    iconBg: 'bg-accent-amber/10 border-accent-amber/20',
    iconColor: 'text-accent-amber',
    Icon: AlertCircle,
  },
  primary: {
    button:
      'bg-primary-500/90 hover:bg-primary-500 text-white border border-primary-500/50 shadow-lg shadow-primary-500/20',
    iconBg: 'bg-primary-500/10 border-primary-500/20',
    iconColor: 'text-primary-400',
    Icon: CheckCircle2,
  },
}

export function ConfirmDialog() {
  const { open, request, resolveAnd, close } = useConfirmStore()
  const promptConfig = request?._promptConfig
  const isPrompt = Boolean(promptConfig)
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Reset the input every time the dialog opens. Without this, the
  // previous prompt's text would leak into the next one.
  useEffect(() => {
    if (open) {
      setInputValue(promptConfig?.defaultValue ?? '')
    }
  }, [open, promptConfig?.defaultValue])

  // Autofocus the input element when the dialog opens in prompt mode.
  // The confirm button has its own autoFocus for the no-input case.
  useEffect(() => {
    if (!open || !isPrompt) return
    const timer = setTimeout(() => {
      if (promptConfig?.multiline) textareaRef.current?.focus()
      else inputRef.current?.focus()
    }, 50)
    return () => clearTimeout(timer)
  }, [open, isPrompt, promptConfig?.multiline])

  // ESC cancels; Enter confirms. Modal already binds ESC so we only
  // need Enter here -- but suppress Enter for multiline textareas
  // (user expects Enter = newline there; Cmd/Ctrl+Enter = submit).
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Enter') return
      if (isPrompt && promptConfig?.multiline && !(e.ctrlKey || e.metaKey)) return
      e.preventDefault()
      resolveAnd(isPrompt ? inputValue : true)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, resolveAnd, isPrompt, inputValue, promptConfig?.multiline])

  if (!open || !request) return null

  const variant: ConfirmVariant = request.variant ?? 'primary'
  const styles = VARIANT_STYLES[variant]
  const Icon = styles.Icon
  const alertOnly = Boolean(request._alertOnly)
  const handleConfirm = () => resolveAnd(isPrompt ? inputValue : true)

  return (
    <Modal isOpen={open} onClose={close} size="sm">
      <div className="flex flex-col items-center text-center gap-4 py-2">
        {/* Icon */}
        <div
          className={`w-14 h-14 rounded-2xl flex items-center justify-center border ${styles.iconBg}`}
        >
          <Icon size={26} className={styles.iconColor} />
        </div>

        {/* Title + message */}
        <div className="space-y-1.5 max-w-sm">
          <h3 id="confirm-dialog-title" className="text-lg font-display font-medium text-starlight-100">
            {request.title}
          </h3>
          {request.message && (
            <p className="text-sm text-starlight-400 leading-relaxed whitespace-pre-line">
              {request.message}
            </p>
          )}
        </div>

        {/* Prompt input (only in prompt mode) */}
        {isPrompt && promptConfig && (
          <div className="w-full text-left">
            {promptConfig.multiline ? (
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                aria-labelledby="confirm-dialog-title"
                placeholder={promptConfig.placeholder}
                maxLength={promptConfig.maxLength}
                rows={3}
                className="w-full px-3 py-2.5 rounded-xl text-sm bg-midnight-950/60 border border-white/10 text-starlight-100 placeholder-starlight-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40 focus:border-primary-500/40 resize-y"
              />
            ) : (
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                aria-labelledby="confirm-dialog-title"
                placeholder={promptConfig.placeholder}
                maxLength={promptConfig.maxLength}
                className="w-full px-3 py-2.5 rounded-xl text-sm bg-midnight-950/60 border border-white/10 text-starlight-100 placeholder-starlight-500 focus:outline-none focus:ring-2 focus:ring-primary-500/40 focus:border-primary-500/40"
              />
            )}
            {promptConfig.maxLength && (
              <p className="mt-1.5 text-[11px] text-starlight-500">
                {inputValue.length} / {promptConfig.maxLength}
              </p>
            )}
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-2 pt-2 w-full">
          {!alertOnly && (
            <button
              onClick={close}
              className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-starlight-200 bg-white/5 hover:bg-white/10 border border-white/5 transition-colors cursor-pointer"
            >
              {request.cancelLabel ?? 'Cancel'}
            </button>
          )}
          <button
            onClick={handleConfirm}
            autoFocus={!isPrompt}
            className={`flex-1 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors cursor-pointer ${styles.button}`}
          >
            {request.confirmLabel ?? (alertOnly ? 'OK' : 'Confirm')}
          </button>
        </div>
      </div>
    </Modal>
  )
}

export default ConfirmDialog

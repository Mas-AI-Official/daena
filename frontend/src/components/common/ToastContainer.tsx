/**
 * ToastContainer — renders all active toasts in bottom-right corner.
 * Mount once in App.tsx or PageLayout. Auto-dismisses after duration.
 */
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useToastStore, type ToastType } from '@/stores/toastStore'

const ICON_MAP: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 size={16} className="text-status-success shrink-0" />,
  error: <XCircle size={16} className="text-status-error shrink-0" />,
  warning: <AlertTriangle size={16} className="text-status-warning shrink-0" />,
  info: <Info size={16} className="text-primary-400 shrink-0" />,
}

const BG_MAP: Record<ToastType, string> = {
  success: 'border-status-success/30 bg-status-success/10',
  error: 'border-status-error/30 bg-status-error/10',
  warning: 'border-status-warning/30 bg-status-warning/10',
  info: 'border-primary-500/30 bg-primary-500/10',
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  const removeToast = useToastStore((s) => s.removeToast)

  return (
    <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none max-w-sm w-full">
      <AnimatePresence mode="popLayout">
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 80, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className={`pointer-events-auto flex items-start gap-2.5 px-4 py-3 rounded-lg border backdrop-blur-md shadow-lg shadow-black/30 ${BG_MAP[t.type]}`}
          >
            {ICON_MAP[t.type]}
            <p className="text-xs text-starlight-200 flex-1 leading-relaxed">{t.message}</p>
            <button
              onClick={() => removeToast(t.id)}
              className="text-starlight-500 hover:text-starlight-200 transition-colors cursor-pointer shrink-0"
            >
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

export default ToastContainer

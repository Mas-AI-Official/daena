/**
 * InteractivePrompt -- renders agent-to-user prompts in chat.
 *
 * Prompt types and their render strategy:
 * - CHOICE: inline card with numbered options
 * - CREDENTIAL: modal overlay with secure input fields
 * - APPROVAL: modal with preview/approve/cancel
 * - VERIFICATION: modal with external action instructions
 * - PROGRESS: inline progress bar with continue/stop
 * - TEXT_INPUT: inline card with text area
 * - CONFIRM: toast-style yes/no
 *
 * All prompts use Daena dark theme tokens.
 * Credential fields never log actual values.
 */
import { useState, useCallback, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Check,
  X,
  Eye,
  Play,
  Pause,
  SkipForward,
  Square,
  CheckCircle2,
  RefreshCw,
  Lock,
  MessageSquare,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
import { api } from '@/lib/api'

// -- Types --

interface PromptOption {
  id: string
  label: string
  icon: string
  style: 'default' | 'primary' | 'danger' | 'success'
}

interface PromptField {
  name: string
  label: string
  type: string
  prefill?: string
}

export interface InteractivePromptData {
  id: string
  type: 'choice' | 'credential' | 'approval' | 'verification' | 'progress' | 'text_input' | 'confirm'
  title: string
  message: string
  options: PromptOption[]
  fields: PromptField[]
  default_value: string
  context: Record<string, unknown>
  created_at: string
}

// -- Icon resolver --

const ICON_MAP: Record<string, typeof Check> = {
  check: Check,
  x: X,
  eye: Eye,
  play: Play,
  pause: Pause,
  'skip-forward': SkipForward,
  square: Square,
  'check-circle': CheckCircle2,
  'refresh-cw': RefreshCw,
}

function OptionIcon({ name, size = 14 }: { name: string; size?: number }) {
  const Icon = ICON_MAP[name]
  return Icon ? <Icon size={size} /> : null
}

// -- Style resolver --

const STYLE_CLASSES: Record<string, string> = {
  default: 'bg-white/5 text-starlight-300 hover:bg-white/10 border-white/5',
  primary: 'bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 border-primary-500/20',
  success: 'bg-accent-green/15 text-accent-green hover:bg-accent-green/25 border-accent-green/20',
  danger: 'bg-accent-red/15 text-accent-red hover:bg-accent-red/25 border-accent-red/20',
}

// -- Respond helper --

async function respondToPrompt(promptId: string, data: Record<string, unknown>) {
  try {
    await api.post(`/prompts/${promptId}/respond`, data)
  } catch {
    // Silently handle -- the prompt may have already expired
  }
}

// -- CHOICE prompt (inline) --

function ChoicePrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [submitting, setSubmitting] = useState(false)
  const [customText, setCustomText] = useState('')

  const handleSelect = async (optionId: string) => {
    setSubmitting(true)
    await respondToPrompt(prompt.id, { selected: optionId })
    onDone()
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-display font-semibold text-starlight-100">
        <MessageSquare size={14} className="text-primary-400" />
        {prompt.title}
      </div>
      <p className="text-xs text-starlight-400">{prompt.message}</p>
      <div className="space-y-1.5">
        {prompt.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => handleSelect(opt.id)}
            disabled={submitting}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs border transition-all text-left disabled:opacity-50 cursor-pointer ${STYLE_CLASSES[opt.style] || STYLE_CLASSES.default}`}
          >
            <span className="w-5 h-5 rounded-md bg-white/5 flex items-center justify-center text-[10px] font-mono text-starlight-500 shrink-0">
              {opt.id}
            </span>
            {opt.label}
          </button>
        ))}
      </div>
      {/* Custom text input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={customText}
          onChange={(e) => setCustomText(e.target.value)}
          placeholder="Or type your own..."
          className="flex-1 glass-input px-3 py-2 rounded-lg text-xs text-starlight-200 placeholder:text-starlight-600 focus:outline-none focus:ring-1 focus:ring-primary-500/40"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && customText.trim()) {
              handleSelect(customText.trim())
            }
          }}
        />
        {customText.trim() && (
          <button
            onClick={() => handleSelect(customText.trim())}
            disabled={submitting}
            className="px-3 py-2 rounded-lg text-xs bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 transition-colors cursor-pointer"
          >
            Submit
          </button>
        )}
      </div>
    </div>
  )
}

// -- CREDENTIAL prompt (modal) --

function CredentialPrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const f of prompt.fields) {
      init[f.name] = f.prefill || ''
    }
    return init
  })
  const [submitting, setSubmitting] = useState(false)
  const firstInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    firstInput.current?.focus()
  }, [])

  const handleSubmit = async () => {
    setSubmitting(true)
    await respondToPrompt(prompt.id, { fields: values })
    onDone()
  }

  const handleSkip = async () => {
    await respondToPrompt(prompt.id, { selected: 'skip' })
    onDone()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg bg-accent-amber/10">
          <Lock size={16} className="text-accent-amber" />
        </div>
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">{prompt.title}</h3>
          <p className="text-xs text-starlight-400 mt-0.5">{prompt.message}</p>
        </div>
      </div>

      <div className="space-y-3">
        {prompt.fields.map((field, i) => (
          <div key={field.name}>
            <label className="block text-[10px] font-semibold text-starlight-500 uppercase tracking-wider mb-1">
              {field.label}
            </label>
            <input
              ref={i === 0 ? firstInput : undefined}
              type={field.type || 'text'}
              value={values[field.name] || ''}
              onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
              className="w-full glass-input px-3 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600 focus:outline-none focus:ring-1 focus:ring-primary-500/40"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSubmit()
              }}
            />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleSkip}
          disabled={submitting}
          className="px-4 py-2 rounded-lg text-xs bg-white/5 text-starlight-400 hover:bg-white/10 transition-colors cursor-pointer"
        >
          Skip This Site
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-4 py-2 rounded-lg text-xs bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 transition-colors flex items-center gap-1.5 cursor-pointer"
        >
          {submitting ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
          Submit
        </button>
      </div>
    </div>
  )
}

// -- APPROVAL prompt (modal) --

function ApprovalPrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [submitting, setSubmitting] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const previewContent = prompt.context?.preview_content as string | undefined

  const handleSelect = async (optionId: string) => {
    if (optionId === 'preview') {
      setShowPreview(true)
      return
    }
    setSubmitting(true)
    await respondToPrompt(prompt.id, { selected: optionId })
    onDone()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg bg-accent-amber/10">
          <AlertTriangle size={16} className="text-accent-amber" />
        </div>
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">{prompt.title}</h3>
          <p className="text-xs text-starlight-400 mt-0.5">{prompt.message}</p>
        </div>
      </div>

      {showPreview && previewContent && (
        <div className="p-3 rounded-lg bg-midnight-800/70 border border-white/5 max-h-48 overflow-y-auto">
          <pre className="text-xs text-starlight-300 whitespace-pre-wrap font-mono">{previewContent}</pre>
        </div>
      )}

      <div className="flex items-center gap-2">
        {prompt.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => handleSelect(opt.id)}
            disabled={submitting}
            className={`px-4 py-2 rounded-lg text-xs border transition-all flex items-center gap-1.5 disabled:opacity-50 cursor-pointer ${STYLE_CLASSES[opt.style] || STYLE_CLASSES.default}`}
          >
            <OptionIcon name={opt.icon} size={12} />
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// -- VERIFICATION prompt (modal) --

function VerificationPrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [submitting, setSubmitting] = useState(false)

  const handleSelect = async (optionId: string) => {
    setSubmitting(true)
    await respondToPrompt(prompt.id, { selected: optionId })
    onDone()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg bg-primary-500/10">
          <CheckCircle2 size={16} className="text-primary-400" />
        </div>
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">{prompt.title}</h3>
          <p className="text-xs text-starlight-400 mt-0.5">{prompt.message}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {prompt.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => handleSelect(opt.id)}
            disabled={submitting}
            className={`px-3 py-2 rounded-lg text-xs border transition-all flex items-center gap-1.5 disabled:opacity-50 cursor-pointer ${STYLE_CLASSES[opt.style] || STYLE_CLASSES.default}`}
          >
            <OptionIcon name={opt.icon} size={12} />
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// -- PROGRESS prompt (inline) --

function ProgressPrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [submitting, setSubmitting] = useState(false)
  const current = (prompt.context?.current as number) || 0
  const total = (prompt.context?.total as number) || 1
  const cost = (prompt.context?.cost as number) || 0
  const pct = Math.round((current / total) * 100)

  const handleSelect = async (optionId: string) => {
    setSubmitting(true)
    await respondToPrompt(prompt.id, { selected: optionId })
    onDone()
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-display font-semibold text-starlight-200">{prompt.title}</span>
        <span className="text-[10px] text-starlight-500">{current}/{total}</span>
      </div>
      {/* Progress bar */}
      <div className="h-1.5 rounded-full bg-midnight-700 overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-accent-green"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
      </div>
      <div className="flex items-center justify-between text-[10px] text-starlight-500">
        <span>{pct}% complete</span>
        <span>Cost: ${cost.toFixed(4)}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {prompt.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => handleSelect(opt.id)}
            disabled={submitting}
            className={`px-2.5 py-1.5 rounded-lg text-[10px] border transition-all flex items-center gap-1 disabled:opacity-50 cursor-pointer ${STYLE_CLASSES[opt.style] || STYLE_CLASSES.default}`}
          >
            <OptionIcon name={opt.icon} size={10} />
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// -- CONFIRM prompt (toast-style) --

function ConfirmPrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [submitting, setSubmitting] = useState(false)

  const handleSelect = async (optionId: string) => {
    setSubmitting(true)
    await respondToPrompt(prompt.id, { selected: optionId })
    onDone()
  }

  return (
    <div className="flex items-center gap-3">
      <p className="text-xs text-starlight-300 flex-1">
        <span className="font-semibold text-starlight-100">{prompt.title}:</span>{' '}
        {prompt.message}
      </p>
      <div className="flex items-center gap-1.5 shrink-0">
        {prompt.options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => handleSelect(opt.id)}
            disabled={submitting}
            className={`px-3 py-1.5 rounded-lg text-xs border transition-all disabled:opacity-50 cursor-pointer ${STYLE_CLASSES[opt.style] || STYLE_CLASSES.default}`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// -- TEXT_INPUT prompt (inline) --

function TextInputPrompt({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  const [text, setText] = useState(prompt.default_value || '')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    await respondToPrompt(prompt.id, { text })
    onDone()
  }

  return (
    <div className="space-y-3">
      <div className="text-sm font-display font-semibold text-starlight-100">{prompt.title}</div>
      <p className="text-xs text-starlight-400">{prompt.message}</p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        className="w-full glass-input px-3 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600 focus:outline-none focus:ring-1 focus:ring-primary-500/40 resize-y"
      />
      <button
        onClick={handleSubmit}
        disabled={submitting || !text.trim()}
        className="px-4 py-2 rounded-lg text-xs bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 transition-colors disabled:opacity-50 cursor-pointer"
      >
        {submitting ? 'Submitting...' : 'Submit'}
      </button>
    </div>
  )
}

// -- Modal wrapper for credential/approval/verification --

const MODAL_TYPES = new Set(['credential', 'approval', 'verification'])

function PromptModal({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Content */}
      <motion.div
        className="relative w-full sm:max-w-md mx-4 mb-0 sm:mb-0"
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 40, opacity: 0 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
      >
        <div className="glass-card rounded-t-2xl sm:rounded-2xl p-5 border border-white/10 shadow-2xl">
          <PromptRenderer prompt={prompt} onDone={onDone} />
        </div>
      </motion.div>
    </motion.div>
  )
}

// -- Inline wrapper for choice/progress/confirm/text --

function PromptInline({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="glass-card rounded-xl p-4 border border-primary-500/20 shadow-lg"
    >
      <PromptRenderer prompt={prompt} onDone={onDone} />
    </motion.div>
  )
}

// -- Type router --

function PromptRenderer({ prompt, onDone }: { prompt: InteractivePromptData; onDone: () => void }) {
  switch (prompt.type) {
    case 'choice':
      return <ChoicePrompt prompt={prompt} onDone={onDone} />
    case 'credential':
      return <CredentialPrompt prompt={prompt} onDone={onDone} />
    case 'approval':
      return <ApprovalPrompt prompt={prompt} onDone={onDone} />
    case 'verification':
      return <VerificationPrompt prompt={prompt} onDone={onDone} />
    case 'progress':
      return <ProgressPrompt prompt={prompt} onDone={onDone} />
    case 'text_input':
      return <TextInputPrompt prompt={prompt} onDone={onDone} />
    case 'confirm':
      return <ConfirmPrompt prompt={prompt} onDone={onDone} />
    default:
      return <p className="text-xs text-starlight-500">Unknown prompt type</p>
  }
}

// -- Main export: renders the active prompt --

export function InteractivePromptDisplay({
  prompt,
  onDismiss,
}: {
  prompt: InteractivePromptData | null
  onDismiss: () => void
}) {
  const handleDone = useCallback(() => {
    onDismiss()
  }, [onDismiss])

  if (!prompt) return null

  const isModal = MODAL_TYPES.has(prompt.type)

  return (
    <AnimatePresence mode="wait">
      {isModal ? (
        <PromptModal key={prompt.id} prompt={prompt} onDone={handleDone} />
      ) : (
        <PromptInline key={prompt.id} prompt={prompt} onDone={handleDone} />
      )}
    </AnimatePresence>
  )
}

export default InteractivePromptDisplay

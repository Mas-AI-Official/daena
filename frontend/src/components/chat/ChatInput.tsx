/**
 * ChatInput — message composer with mode indicators,
 * model selector, Shift+Enter for newlines, Enter to send.
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Square, Paperclip, X, ChevronDown, ChevronRight, ArrowLeft, Check, FileText } from 'lucide-react'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useUiStore } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'
import { VoiceControls } from './VoiceControls'
import { SlashCommandMenu } from './SlashCommands'
import type { ModelRegistryModelResponse } from '@/types/api'

interface ChatInputProps {
  onSend: (content: string) => void
  onCancel?: () => void
  isStreaming: boolean
  disabled?: boolean
  placeholder?: string
}

interface ModelOption {
  id: string | null
  label: string
  badge?: string
  provider?: string
  selectable: boolean
  availabilityReason?: string
}

function getModelBadge(model: ModelRegistryModelResponse): string | undefined {
  if (model.kind === 'local') return 'local'
  if (model.supports_vision) return 'vision'
  if (model.tags.length > 0) return model.tags[0]
  return undefined
}

export function ChatInput({ onSend, onCancel, isStreaming, disabled, placeholder: customPlaceholder }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [modelOpen, setModelOpen] = useState(false)
  const [activeProvider, setActiveProvider] = useState<string | null>(null)
  const [attachedFiles, setAttachedFiles] = useState<{ file_id: string; filename: string; size_bytes: number }[]>([])
  const [uploading, setUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)
  const [quotaRemaining, setQuotaRemaining] = useState<number | null>(null)
  const [isOverQuota, setIsOverQuota] = useState(false)
  const { chatMode, governanceMode, selectedModel, setSelectedModel } = useUiStore()
  const registry = useModelRegistryStore((s) => s.registry)
  const registryLoading = useModelRegistryStore((s) => s.loading)
  const registryError = useModelRegistryStore((s) => s.error)
  const fetchRegistry = useModelRegistryStore((s) => s.fetchRegistry)

  useEffect(() => {
    void fetchRegistry(true)
  }, [fetchRegistry])

  // Fetch quota on mount and every 60s
  useEffect(() => {
    const fetchQuota = () => {
      const token = localStorage.getItem('daena_token')
      if (!token) return
      fetch('/api/v1/billing/my-quota', {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.json())
        .then(data => {
          const d = data?.data ?? data
          if (d) {
            const rem = d.remaining_monthly_usd
            setQuotaRemaining(typeof rem === 'number' ? rem : null)
            setIsOverQuota(!!d.is_over_quota)
          }
        })
        .catch(() => {})
    }
    fetchQuota()
    const interval = setInterval(fetchQuota, 60000)
    return () => clearInterval(interval)
  }, [])

  const liveOptions: ModelOption[] = (registry?.models ?? []).map((model) => ({
    id: model.model_id,
    label: model.display_name,
    badge: getModelBadge(model),
    provider: model.provider_display_name,
    selectable: model.selectable,
    availabilityReason: model.availability_reason,
  }))

  const selectedLiveModel = registry?.models.find((model) => model.model_id === selectedModel)
  const selectedModelUnavailable = Boolean(
    selectedModel && (!selectedLiveModel || !selectedLiveModel.selectable),
  )

  const modelOptions: ModelOption[] = [
    { id: null, label: 'Auto', badge: 'smart', selectable: true },
    ...liveOptions,
  ]

  if (selectedModel && !selectedLiveModel) {
    modelOptions.splice(1, 0, {
      id: selectedModel,
      label: selectedModel,
      badge: 'stale',
      selectable: false,
      availabilityReason: 'Not discovered by backend registry',
    })
  }

  const currentModelLabel =
    selectedModel
      ? `${selectedLiveModel?.display_name ?? selectedModel}${selectedModelUnavailable ? ' (Unavailable)' : ''}`
      : 'Auto'

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }, [value])

  // Focus on mount
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  // Close model dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target as Node)) {
        setModelOpen(false)
        setActiveProvider(null)
      }
    }
    if (modelOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [modelOpen])

  // STT mic button always appends to the textarea for user review.
  // Conversational auto-send is handled entirely inside VoiceProvider.
  const handleVoiceTranscript = useCallback((text: string) => {
    setValue((prev) => prev ? `${prev} ${text}` : text)
  }, [])

  // Max message length: 32KB (prevents accidental huge payloads)
  const MAX_MESSAGE_LENGTH = 32_768

  // Long paste detection: when user pastes >10 lines, collapse into a file-like chip
  // (ChatGPT-style "Pasted text" attachment pattern)
  const LONG_PASTE_LINE_THRESHOLD = 25
  const [pastedChip, setPastedChip] = useState<{ text: string; lineCount: number; preview: string } | null>(null)

  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    // Image paste: check clipboard for image data BEFORE text fallback
    const items = e.clipboardData.items
    const imageFiles: File[] = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) imageFiles.push(file)
      }
    }

    if (imageFiles.length > 0) {
      e.preventDefault()
      setUploading(true)
      try {
        for (const file of imageFiles) {
          // Give pasted images a sensible filename (Chrome names them "image.png")
          const renamed = file.name === 'image.png'
            ? new File([file], `pasted-${Date.now()}.png`, { type: file.type })
            : file
          const form = new FormData()
          form.append('file', renamed)
          const token = localStorage.getItem('daena_token')
          const res = await fetch('/api/v1/files/upload', {
            method: 'POST',
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            body: form,
          })
          if (!res.ok) {
            toast.error('Image upload failed')
            continue
          }
          const json = await res.json()
          if (json.data) {
            setAttachedFiles((prev) => [...prev, json.data])
          }
        }
      } catch {
        toast.error('Image paste failed')
      } finally {
        setUploading(false)
      }
      return
    }

    // Text paste: collapse long pastes into a chip
    const pasted = e.clipboardData.getData('text')
    if (!pasted) return

    const lines = pasted.split('\n')
    if (lines.length > LONG_PASTE_LINE_THRESHOLD) {
      e.preventDefault()
      const preview = lines.slice(0, 3).join('\n') + (lines.length > 3 ? '\n...' : '')
      setPastedChip({ text: pasted, lineCount: lines.length, preview })
      requestAnimationFrame(() => textareaRef.current?.focus())
    }
  }, [])

  const removePastedChip = useCallback(() => setPastedChip(null), [])

  // Slash commands
  const showSlashMenu = value.startsWith('/') && !value.includes(' ')

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        const form = new FormData()
        form.append('file', file)
        const token = localStorage.getItem('daena_token')
        const res = await fetch('/api/v1/files/upload', {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
        })
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
          toast.error(err.detail || 'File upload failed')
          continue
        }
        const json = await res.json()
        if (json.data) {
          setAttachedFiles((prev) => [...prev, json.data])
        }
      }
    } catch {
      toast.error('File upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeAttachment = (fileId: string) => {
    setAttachedFiles((prev) => prev.filter((f) => f.file_id !== fileId))
  }

  const handleSubmit = () => {
    const trimmed = value.trim()
    const hasPastedContent = pastedChip !== null
    if ((!trimmed && attachedFiles.length === 0 && !hasPastedContent) || isStreaming || disabled) return
    // Don't send slash commands as messages -- they're handled by the menu
    if (trimmed.startsWith('/') && !trimmed.includes(' ')) return

    // Combine pasted chip content + typed message
    const fullMessage = hasPastedContent
      ? pastedChip.text + (trimmed ? `\n\n${trimmed}` : '')
      : trimmed

    if (fullMessage.length > MAX_MESSAGE_LENGTH) {
      toast.error(`Message too long (${fullMessage.length.toLocaleString()} chars). Max: ${MAX_MESSAGE_LENGTH.toLocaleString()}.`)
      return
    }
    // Prepend file references so the orchestrator can read them
    const filePrefix = attachedFiles.map((f) => `[file:${f.file_id}|${f.filename}]`).join(' ')
    const content = filePrefix ? `${filePrefix}\n${fullMessage}` : fullMessage
    onSend(content)
    setValue('')
    setAttachedFiles([])
    setPastedChip(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Let slash command menu handle Enter/Arrow keys
    if (showSlashMenu && ['ArrowUp', 'ArrowDown', 'Tab'].includes(e.key)) return
    if (e.key === 'Enter' && !e.shiftKey && !showSlashMenu) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="shrink-0 bg-transparent">
      <div className="max-w-3xl mx-auto px-4 py-3">
        {/* Mode indicator bar -- compact, inside composer area */}
        <div className="flex items-center gap-1.5 mb-2 text-[10px] font-mono px-1">
          {/* Chat mode badge */}
          <span
            className={`px-1.5 py-0.5 rounded-md ${
              chatMode === 'CMD'
                ? 'bg-accent-cyan/10 text-accent-cyan/70'
                : 'bg-accent-amber/10 text-accent-amber/70'
            }`}
          >
            {chatMode}
          </span>
          <span className="text-starlight-600/50">·</span>
          <span className={`font-mono ${
            governanceMode === 'UNLEASHED' ? 'text-status-error/80' :
            governanceMode === 'BALANCED' ? 'text-accent-cyan/80' :
            'text-starlight-500/70'
          }`}>{governanceMode}</span>
          {quotaRemaining != null && typeof quotaRemaining === 'number' && (
            <>
              <span className="text-starlight-600/50">·</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                isOverQuota
                  ? 'bg-accent-amber/10 text-accent-amber/70'
                  : quotaRemaining < 1
                    ? 'bg-accent-amber/10 text-accent-amber/70'
                    : 'text-starlight-500/70'
              }`}>
                {isOverQuota ? 'Free mode' : `$${quotaRemaining.toFixed(2)} left`}
              </span>
            </>
          )}
          <span className="text-starlight-600/50">·</span>

          {/* Model selector.
             2026-04-16: "Model:" prefix added to disambiguate this
             per-message model override from the header's Primary
             Mind (RuntimeSwapper). The header picks the RUNTIME
             (Claude Code CLI / Codex / Gemini / Ollama); this
             dropdown picks the SPECIFIC MODEL within the resolved
             runtime. Both used to show "Auto" which confused
             operators. */}
          <div className="relative" ref={modelDropdownRef}>
            <button
              onClick={() => { setModelOpen(!modelOpen); setActiveProvider(null) }}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded
                         hover:bg-white/5 transition-colors cursor-pointer"
              title="Per-message model override (the header picks the runtime)"
            >
              <span className="text-starlight-500 mr-0.5">Model:</span>
              <span className={selectedModel ? 'text-primary-300' : 'text-starlight-400'}>
                {currentModelLabel}
              </span>
              <ChevronDown
                size={10}
                className={`text-starlight-500 transition-transform ${modelOpen ? 'rotate-180' : ''}`}
              />
            </button>

            <AnimatePresence>
              {modelOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.97 }}
                  transition={{ duration: 0.12 }}
                  className="absolute bottom-full mb-1 left-0 z-30 min-w-[200px] max-w-[280px]
                             bg-midnight-400/95 backdrop-blur-md border border-white/10
                             rounded-lg shadow-xl py-1 text-xs"
                >
                  {registryLoading && modelOptions.length === 1 && (
                    <div className="px-3 py-2 text-[10px] text-starlight-500">
                      Loading live model registry...
                    </div>
                  )}
                  {!registryLoading && modelOptions.length === 1 && (
                    <div className="px-3 py-2 text-[10px] text-starlight-500">
                      No live models reported by the backend.
                    </div>
                  )}

                  {/* Two-level drill-down: providers -> models */}
                  <div className="max-h-[180px] overflow-y-auto">
                    {(() => {
                      // Build provider groups (exclude Auto, handled separately)
                      const groups: Record<string, ModelOption[]> = {}
                      for (const opt of modelOptions) {
                        if (opt.id === null) continue
                        const group = opt.provider || 'Other'
                        if (!groups[group]) groups[group] = []
                        groups[group].push(opt)
                      }
                      const providerEntries = Object.entries(groups)

                      // LEVEL 2: drilled into a specific provider
                      if (activeProvider) {
                        const providerModels = groups[activeProvider] ?? []
                        return (
                          <>
                            <button
                              onClick={() => setActiveProvider(null)}
                              className="w-full flex items-center gap-1.5 px-3 py-1.5
                                         text-starlight-400 hover:text-starlight-200
                                         hover:bg-white/5 transition-colors cursor-pointer
                                         border-b border-white/5"
                            >
                              <ArrowLeft size={10} />
                              <span className="text-[10px] font-mono uppercase tracking-wider">
                                {activeProvider}
                              </span>
                            </button>
                            {providerModels.map((opt) => (
                              <button
                                key={opt.id ?? '__auto__'}
                                onClick={() => {
                                  if (!opt.selectable) return
                                  setSelectedModel(opt.id)
                                  setModelOpen(false)
                                  setActiveProvider(null)
                                }}
                                className={`w-full flex items-center justify-between gap-2
                                            px-3 py-1.5 hover:bg-white/5 transition-colors
                                            cursor-pointer text-left ${
                                              selectedModel === opt.id
                                                ? 'text-primary-300 bg-primary-500/5'
                                                : 'text-starlight-300'
                                            } ${opt.selectable ? '' : 'opacity-50 cursor-not-allowed'}`}
                              >
                                <span className="truncate">{opt.label}</span>
                                <div className="flex items-center gap-1 shrink-0">
                                  {opt.badge && (
                                    <span className="text-[8px] px-1 py-0.5 rounded bg-white/5
                                                     text-starlight-500 capitalize">
                                      {opt.badge}
                                    </span>
                                  )}
                                  {!opt.selectable && (
                                    <span className="text-[8px] px-1 py-0.5 rounded
                                                     bg-status-error/10 text-status-error">
                                      off
                                    </span>
                                  )}
                                  {selectedModel === opt.id && (
                                    <Check size={10} className="text-primary-400" />
                                  )}
                                </div>
                              </button>
                            ))}
                          </>
                        )
                      }

                      // LEVEL 1: provider list with Auto at top
                      return (
                        <>
                          {/* Auto: always top-level, selects immediately */}
                          <button
                            onClick={() => {
                              setSelectedModel(null)
                              setModelOpen(false)
                            }}
                            className={`w-full flex items-center justify-between gap-2
                                        px-3 py-1.5 hover:bg-white/5 transition-colors
                                        cursor-pointer text-left ${
                                          selectedModel === null
                                            ? 'text-primary-300 bg-primary-500/5'
                                            : 'text-starlight-300'
                                        }`}
                          >
                            <span>Auto</span>
                            <div className="flex items-center gap-1 shrink-0">
                              <span className="text-[8px] px-1 py-0.5 rounded bg-white/5
                                               text-starlight-500">
                                smart
                              </span>
                              {selectedModel === null && (
                                <Check size={10} className="text-primary-400" />
                              )}
                            </div>
                          </button>

                          {/* Provider rows: click to drill in */}
                          {providerEntries.map(([provider, opts]) => {
                            const selectableCount = opts.filter(o => o.selectable).length
                            const hasSelectedModel = opts.some(o => o.id === selectedModel)
                            return (
                              <button
                                key={provider}
                                onClick={() => setActiveProvider(provider)}
                                className={`w-full flex items-center justify-between gap-2
                                            px-3 py-1.5 hover:bg-white/5 transition-colors
                                            cursor-pointer text-left ${
                                              hasSelectedModel
                                                ? 'text-primary-300 bg-primary-500/5'
                                                : 'text-starlight-300'
                                            }`}
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <span className="truncate">{provider}</span>
                                  <span className="text-[8px] text-starlight-600 shrink-0">
                                    {selectableCount} model{selectableCount !== 1 ? 's' : ''}
                                  </span>
                                </div>
                                <ChevronRight size={10} className="text-starlight-500 shrink-0" />
                              </button>
                            )
                          })}
                        </>
                      )
                    })()}
                  </div>

                  {registryError && (
                    <div className="px-3 py-2 text-[10px] text-status-error border-t border-white/5">
                      {registryError}
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Input row */}
        <div className="flex items-end gap-2">
          {/* Attach button */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileUpload}
            accept="text/*,application/pdf,application/json,image/*,.docx,.xlsx,.pptx,.zip"
          />
          <button
            className={`shrink-0 p-2 rounded-lg transition-colors cursor-pointer ${
              uploading ? 'text-primary-400 animate-pulse' : 'text-starlight-500 hover:text-starlight-300 hover:bg-white/5'
            }`}
            title="Attach file"
            aria-label="Attach file"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            <Paperclip size={18} />
          </button>

          {/* Voice controls (STT mic + TTS toggle) */}
          <VoiceControls
            onTranscript={handleVoiceTranscript}
            disabled={disabled}
          />

          {/* Textarea + slash command menu */}
          <div className="flex-1 min-w-0 relative">
            {/* Attached file chips */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {attachedFiles.map((f) => (
                  <span key={f.file_id} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-primary-500/10 border border-primary-500/20 text-xs text-primary-300">
                    <Paperclip size={10} />
                    <span className="max-w-[120px] truncate">{f.filename}</span>
                    <button onClick={() => removeAttachment(f.file_id)} className="hover:text-accent-red transition-colors cursor-pointer"><X size={10} /></button>
                  </span>
                ))}
              </div>
            )}
            <SlashCommandMenu
              input={value}
              visible={showSlashMenu}
              onSelect={(cmd) => { cmd.action(); setValue('') }}
              onClose={() => {}}
            />
            {/* Pasted text chip -- ChatGPT-style collapsed long paste */}
            {pastedChip && (
              <div className="mb-2 flex items-start gap-2 px-3 py-2 rounded-xl bg-white/5 border border-white/10">
                <FileText size={16} className="shrink-0 mt-0.5 text-primary-400" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-starlight-200">Pasted text</span>
                    <span className="text-[10px] text-starlight-500">{pastedChip.lineCount} lines</span>
                  </div>
                  <pre className="text-[10px] text-starlight-500 mt-0.5 line-clamp-2 whitespace-pre-wrap font-mono">{pastedChip.preview}</pre>
                </div>
                <button
                  onClick={removePastedChip}
                  className="shrink-0 p-0.5 rounded text-starlight-500 hover:text-starlight-200 hover:bg-white/10 transition-colors cursor-pointer"
                  aria-label="Remove pasted text"
                >
                  <X size={14} />
                </button>
              </div>
            )}
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={pastedChip ? 'Press Enter to send, or add a question...' : (customPlaceholder || 'Message Daena...')}
              aria-label="Message input"
              disabled={disabled}
              maxLength={MAX_MESSAGE_LENGTH}
              rows={1}
              className="w-full resize-none rounded-2xl glass-input px-4 py-3 pr-12
                         text-sm text-starlight-100 placeholder:text-starlight-500/60
                         focus:outline-none focus:ring-0 focus:border-primary-500/20
                         disabled:opacity-50 disabled:cursor-not-allowed
                         max-h-[200px] leading-relaxed transition-colors"
              style={{ outline: 'none' }}
            />
            {/* Character count + estimated cost — visible when typing */}
            {value.length > 20 && (
              <span className={`absolute bottom-1 right-2 text-[9px] font-mono transition-opacity ${
                value.length > MAX_MESSAGE_LENGTH * 0.9 ? 'text-status-error' : 'text-starlight-600'
              }`}>
                {value.length > MAX_MESSAGE_LENGTH * 0.9
                  ? `${value.length.toLocaleString()}/${MAX_MESSAGE_LENGTH.toLocaleString()}`
                  : `~${Math.ceil(value.length / 4)} tokens · ~$${(Math.ceil(value.length / 4) * 0.003 / 1000).toFixed(4)}`
                }
              </span>
            )}
          </div>

          {/* Send / Cancel */}
          {isStreaming ? (
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={onCancel}
              className="shrink-0 p-2 rounded-xl bg-status-error/20 text-status-error hover:bg-status-error/30 transition-all cursor-pointer"
              title="Stop generation"
              aria-label="Stop generation"
            >
              <Square size={14} className="fill-current" />
            </motion.button>
          ) : (
            <motion.button
              whileTap={{ scale: 0.95 }}
              onClick={handleSubmit}
              disabled={!value.trim() || disabled}
              className="shrink-0 p-2 rounded-xl bg-primary-500 text-white
                         hover:bg-primary-600 transition-all
                         disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              title="Send message"
              aria-label="Send message"
            >
              <Send size={16} />
            </motion.button>
          )}
        </div>

        <p className="text-[9px] text-starlight-600/60 mt-1.5 text-center">
          Daena can make mistakes. Verify important information.
          <span className="hidden sm:inline"> · Shift+Enter for new line</span>
        </p>
        {selectedModelUnavailable && (
          <p className="text-[10px] text-status-error mt-1 text-center">
            Selected model is unavailable. Chat will use Auto until you choose a live model.
          </p>
        )}
      </div>
    </div>
  )
}

export default ChatInput

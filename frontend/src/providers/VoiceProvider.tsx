/**
 * VoiceProvider: Global voice state via React Context.
 *
 * Two modes share ONE SpeechRecognition instance (no mic conflicts):
 *   STT mode   -- mic fills the chat input box (started by VoiceControls)
 *   Conv mode  -- mic auto-sends + auto-speaks (started by header Voice button)
 *
 * ElevenLabs TTS when API key is present, browser TTS fallback.
 * Google voices are preferred (much better quality than Microsoft/Zira).
 * Voice choice persists via localStorage key "daena_selected_voice".
 */
import React, {
  createContext,
  useContext,
  useRef,
  useState,
  useCallback,
  useEffect,
} from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AudioLines } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore } from '@/stores/chatStore'
import { useUiStore } from '@/stores/uiStore'
import { toast } from '@/stores/toastStore'

// ── Context interface ─────────────────────────────────────────────────────────

export interface VoiceState {
  /** Conversational mode: listen + speak (header Voice button) */
  isActive: boolean
  /** TTS-only mode: auto-read responses (speaker icon) */
  ttsEnabled: boolean
  /** STT-only mode: fills text input (mic icon) */
  isSttMode: boolean
  /** Microphone is currently capturing */
  isListening: boolean
  isSpeaking: boolean
  transcript: string
  availableVoices: SpeechSynthesisVoice[]
  selectedVoice: string
  /** Toggle conversational mode: listen + speak (header Voice button) */
  toggle: () => void
  /** Toggle TTS-only: just speak responses (speaker icon) */
  toggleTts: () => void
  /** Start STT-only mode; callback receives final transcript */
  startStt: (onTranscript: (text: string) => void) => void
  /** Stop STT-only mode */
  stopStt: () => void
  stopSpeaking: () => void
  setSelectedVoice: (name: string) => void
}

const VoiceContext = createContext<VoiceState | null>(null)

export function useVoice(): VoiceState {
  const ctx = useContext(VoiceContext)
  if (!ctx) throw new Error('useVoice must be used inside VoiceProvider')
  return ctx
}

// ── Web Speech API shim types ─────────────────────────────────────────────────

interface SpeechRecognitionResult {
  readonly isFinal: boolean
  readonly length: number
  readonly [index: number]: { readonly transcript: string; readonly confidence: number }
}
interface SpeechRecognitionResultList {
  readonly length: number
  readonly [index: number]: SpeechRecognitionResult
}
interface SpeechRecognitionEvent extends Event {
  readonly results: SpeechRecognitionResultList
  readonly resultIndex: number
}
interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((e: SpeechRecognitionEvent) => void) | null
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}

function getSRClass(): (new () => SpeechRecognitionInstance) | null {
  const w = window as unknown as Record<string, unknown>
  return (
    (w['SpeechRecognition'] as (new () => SpeechRecognitionInstance) | undefined) ??
    (w['webkitSpeechRecognition'] as (new () => SpeechRecognitionInstance) | undefined) ??
    null
  )
}

// ── Stop-word list ────────────────────────────────────────────────────────────

const STOP_WORDS = new Set([
  'stop', 'stop listening', 'goodbye', 'bye daena', 'stop daena', 'pause',
])

// ── Provider ──────────────────────────────────────────────────────────────────

export function VoiceProvider({ children }: { children: React.ReactNode }) {
  const [isActive, setIsActive] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(false)
  const [isSttMode, setIsSttMode] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([])
  const [selectedVoice, setSelectedVoiceState] = useState('')

  // Refs for closure-safe access inside event handlers
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)
  const isActiveRef = useRef(false)
  const ttsEnabledRef = useRef(false)
  const isSttModeRef = useRef(false)
  const isSpeakingRef = useRef(false)
  // Set to true when mic permission is denied; blocks onend restart loop
  const permissionDeniedRef = useRef(false)
  const selectedVoiceRef = useRef('')
  // Ref to latest STT callback (avoids stale closure)
  const sttCallbackRef = useRef<((text: string) => void) | null>(null)
  // Ref to latest sendVoiceMessage (avoids stale closure)
  const sendVoiceMessageRef = useRef<((text: string) => Promise<void>) | null>(null)

  // Keep refs in sync with state
  useEffect(() => { isActiveRef.current = isActive }, [isActive])
  useEffect(() => { ttsEnabledRef.current = ttsEnabled }, [ttsEnabled])
  useEffect(() => { isSttModeRef.current = isSttMode }, [isSttMode])
  useEffect(() => { isSpeakingRef.current = isSpeaking }, [isSpeaking])
  useEffect(() => { selectedVoiceRef.current = selectedVoice }, [selectedVoice])

  // Sync isListening to uiStore for backward compat
  useEffect(() => {
    useUiStore.getState().setVoiceListening(isListening)
  }, [isListening])

  // ── Voice loading ──────────────────────────────────────────────────────────

  useEffect(() => {
    const syn = window.speechSynthesis
    if (!syn) return

    const loadVoices = () => {
      const voices = syn.getVoices()
      if (voices.length === 0) return
      setAvailableVoices(voices)

      // Restore saved preference first
      const saved = localStorage.getItem('daena_selected_voice')
      if (saved && voices.some((v) => v.name === saved)) {
        setSelectedVoiceState(saved)
        selectedVoiceRef.current = saved
        return
      }

      // Auto-select best English voice:
      // 1. Google voices (cloud-based, much more natural than Microsoft)
      // 2. Neural/Natural keyword
      // 3. Known good voices by name
      // 4. Any English non-robotic
      if (!selectedVoiceRef.current) {
        const best =
          voices.find((v) => v.lang.startsWith('en') && v.name.toLowerCase().includes('google')) ??
          voices.find((v) => v.lang.startsWith('en') && /Natural|Neural/.test(v.name)) ??
          voices.find((v) => /Aria|Jenny|Samantha|Google UK English Female/i.test(v.name)) ??
          voices.find((v) => v.lang.startsWith('en') && !/david|zira|mark/i.test(v.name)) ??
          voices.find((v) => v.lang.startsWith('en')) ??
          voices[0]
        if (best) {
          setSelectedVoiceState(best.name)
          selectedVoiceRef.current = best.name
        }
      }
    }

    loadVoices()
    syn.onvoiceschanged = loadVoices
    // Fallback for browsers that don't fire onvoiceschanged on first load
    setTimeout(loadVoices, 500)
    return () => { syn.onvoiceschanged = null }
  }, [])

  // ── TTS: browser SpeechSynthesis ──────────────────────────────────────────

  const speakWithBrowser = useCallback((text: string) => {
    const syn = window.speechSynthesis
    if (!syn) return
    syn.cancel()

    // Set speaking flag synchronously before recognition.stop() below fires onend,
    // so the onend handler sees isSpeakingRef=true and skips the restart.
    isSpeakingRef.current = true
    setIsSpeaking(true)

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.95
    utterance.pitch = 1.0

    const voices = syn.getVoices()
    const voice = voices.find((v) => v.name === selectedVoiceRef.current)
    if (voice) utterance.voice = voice

    utterance.onstart = () => {
      setIsSpeaking(true)
      isSpeakingRef.current = true
    }
    utterance.onend = () => {
      setIsSpeaking(false)
      isSpeakingRef.current = false
      if (isActiveRef.current) {
        setTimeout(() => { try { recognitionRef.current?.start() } catch {} }, 300)
      }
    }
    utterance.onerror = () => {
      setIsSpeaking(false)
      isSpeakingRef.current = false
      if (isActiveRef.current) {
        try { recognitionRef.current?.start() } catch {}
      }
    }

    syn.speak(utterance)
  }, [])

  // ── TTS: ElevenLabs ───────────────────────────────────────────────────────

  const speakWithElevenLabs = useCallback(async (text: string, apiKey: string) => {
    setIsSpeaking(true)
    isSpeakingRef.current = true
    try {
      const res = await fetch(
        'https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM/stream',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'xi-api-key': apiKey,
          },
          body: JSON.stringify({
            text: text.slice(0, 5000),
            model_id: 'eleven_monolingual_v1',
            voice_settings: { stability: 0.5, similarity_boost: 0.75 },
          }),
        },
      )
      if (!res.ok) throw new Error(`ElevenLabs HTTP ${res.status}`)

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)

      await new Promise<void>((resolve, reject) => {
        audio.onended = () => { URL.revokeObjectURL(url); resolve() }
        audio.onerror = () => { URL.revokeObjectURL(url); reject(new Error('audio error')) }
        void audio.play()
      })

      setIsSpeaking(false)
      isSpeakingRef.current = false
      if (isActiveRef.current) {
        setTimeout(() => { try { recognitionRef.current?.start() } catch {} }, 300)
      }
    } catch (err) {
      console.warn('[VoiceProvider] ElevenLabs failed, falling back to browser TTS:', err)
      setIsSpeaking(false)
      isSpeakingRef.current = false
      speakWithBrowser(text)
    }
  }, [speakWithBrowser])

  // ── TTS dispatcher ────────────────────────────────────────────────────────

  const speakResponse = useCallback((text: string) => {
    if (!isActiveRef.current && !ttsEnabledRef.current) return
    try { recognitionRef.current?.stop() } catch {}

    const apiKey = localStorage.getItem('daena:elevenlabs_key')
    if (apiKey) {
      void speakWithElevenLabs(text, apiKey)
    } else {
      speakWithBrowser(text)
    }
  }, [speakWithElevenLabs, speakWithBrowser])

  // ── Voice-through-chat: send via chatStore (text shows in UI) ─────────────

  const sendViaChat = useCallback(async (text: string) => {
    try { recognitionRef.current?.stop() } catch {}
    try {
      // Send through normal chat pipeline -- message appears in chat UI
      await useChatStore.getState().sendMessage(text)
    } catch (err) {
      console.error('[VoiceProvider] sendViaChat error:', err)
    }
    // Restart mic after a delay (TTS auto-read will handle speaking)
    if (isActiveRef.current) {
      setTimeout(() => { if (isActiveRef.current && !isSpeakingRef.current) try { recognitionRef.current?.start() } catch {} }, 500)
    }
  }, [])

  useEffect(() => { sendVoiceMessageRef.current = sendViaChat }, [sendViaChat])

  // ── Auto-read: speak new assistant messages when voice is active ──────────

  useEffect(() => {
    // Subscribe to chatStore messages; when a new assistant message arrives, speak it
    let lastMsgCount = useChatStore.getState().messages.length

    const unsub = useChatStore.subscribe((state) => {
      if (!isActiveRef.current && !ttsEnabledRef.current) return
      const msgs = state.messages
      if (msgs.length <= lastMsgCount) {
        lastMsgCount = msgs.length
        return
      }
      // Check if the newest message is from assistant and is complete (not streaming)
      const newest = msgs[msgs.length - 1]
      if (
        newest &&
        newest.role === 'assistant' &&
        newest.content &&
        !state.isStreaming
      ) {
        lastMsgCount = msgs.length
        // Speak the response (strips markdown for cleaner TTS)
        const cleanText = newest.content
          .replace(/```[\s\S]*?```/g, ' code block ')
          .replace(/[#*_~`>|]/g, '')
          .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
          .trim()
        if (cleanText) speakResponse(cleanText.slice(0, 2000))
      } else {
        lastMsgCount = msgs.length
      }
    })

    return unsub
  }, [speakResponse])

  // ── SpeechRecognition singleton (created once) ────────────────────────────

  useEffect(() => {
    const SR = getSRClass()
    if (!SR) return

    const recognition = new SR()
    recognition.continuous = true    // stay open; permissionDeniedRef guards not-allowed loop
    recognition.interimResults = true
    recognition.lang = 'en-US'

    recognition.onstart = () => setIsListening(true)

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) final += result[0].transcript
        else interim += result[0].transcript
      }

      // Show interim for UI feedback
      if (interim) setTranscript(interim)

      if (final.trim()) {
        const text = final.trim()
        setTranscript(text)

        // Stop word handling
        if (STOP_WORDS.has(text.toLowerCase())) {
          if (isSttModeRef.current) {
            sttCallbackRef.current = null
            isSttModeRef.current = false
            setIsSttMode(false)
            try { recognition.stop() } catch {}
          } else {
            setIsActive(false)
          }
          return
        }

        if (isSttModeRef.current && sttCallbackRef.current) {
          // STT mode: deliver text to caller, keep listening
          sttCallbackRef.current(text)
        } else if (isActiveRef.current) {
          // Conversational mode: send to API
          sendVoiceMessageRef.current?.(text)
        }
      }
    }

    recognition.onend = () => {
      setIsListening(false)
      // If mic was denied, clear the flag and don't restart (prevents infinite loop)
      if (permissionDeniedRef.current) {
        permissionDeniedRef.current = false
        return
      }
      if (isActiveRef.current && !isSpeakingRef.current) {
        // Restart for conversational mode
        setTimeout(() => { if (isActiveRef.current && !permissionDeniedRef.current) try { recognition.start() } catch {} }, 300)
      } else if (isSttModeRef.current) {
        // Restart for STT mode
        setTimeout(() => { if (isSttModeRef.current && !permissionDeniedRef.current) try { recognition.start() } catch {} }, 100)
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const { error } = event
      if (error !== 'aborted' && error !== 'no-speech') {
        console.warn('[VoiceProvider] Recognition error:', error)
      }
      setIsListening(false)
      if (error === 'not-allowed') {
        permissionDeniedRef.current = true
        try { recognition.abort() } catch {}
        setIsActive(false)
        isActiveRef.current = false
        sttCallbackRef.current = null
        isSttModeRef.current = false
        setIsSttMode(false)
        toast.error('Microphone access denied. Enable it in your browser settings.')
        return
      }
      const delay = error === 'no-speech' ? 300 : 1000
      if (isActiveRef.current) {
        setTimeout(() => { if (isActiveRef.current) try { recognition.start() } catch {} }, delay)
      } else if (isSttModeRef.current) {
        setTimeout(() => { if (isSttModeRef.current) try { recognition.start() } catch {} }, delay)
      }
    }

    recognitionRef.current = recognition
    return () => {
      try { recognition.abort() } catch {}
      recognitionRef.current = null
    }
  }, [])

  // ── Start/stop recognition when isActive (conv mode) changes ─────────────
  // Note: when isSttModeRef is true, startStt is managing the recognition
  // directly -- skip the stop here to avoid double-stop race condition.

  useEffect(() => {
    if (isActive) {
      // Stop STT mode if switching to conversational
      if (isSttModeRef.current) {
        sttCallbackRef.current = null
        isSttModeRef.current = false
        setIsSttMode(false)
      }
      try { recognitionRef.current?.start() } catch {}
    } else if (!isSttModeRef.current) {
      // Only stop if we're NOT transitioning to STT mode
      try { recognitionRef.current?.stop() } catch {}
      window.speechSynthesis?.cancel()
      setIsListening(false)
      setIsSpeaking(false)
      isSpeakingRef.current = false
      setTranscript('')
    }
  }, [isActive])

  // ── Actions ───────────────────────────────────────────────────────────────

  const toggle = useCallback(() => setIsActive((prev) => !prev), [])

  const toggleTts = useCallback(() => {
    setTtsEnabled((prev) => {
      if (!prev) {
        // Turning TTS on -- stop conversational mode if active (they're separate)
        if (isActiveRef.current) { setIsActive(false) }
      } else {
        // Turning TTS off -- stop any speech in progress
        window.speechSynthesis?.cancel()
        setIsSpeaking(false)
        isSpeakingRef.current = false
      }
      return !prev
    })
  }, [])

  const startStt = useCallback((onTranscript: (text: string) => void) => {
    // Synchronously update ref so onend/useEffect see correct state immediately
    if (isActiveRef.current) {
      isActiveRef.current = false
      setIsActive(false)
      window.speechSynthesis?.cancel()
    }
    sttCallbackRef.current = onTranscript
    isSttModeRef.current = true
    setIsSttMode(true)
    setTranscript('')
    // Stop any running recognition cleanly. The onend handler will restart
    // it in STT mode because isSttModeRef.current is now true.
    try { recognitionRef.current?.stop() } catch {}
  }, [])

  const stopStt = useCallback(() => {
    sttCallbackRef.current = null
    isSttModeRef.current = false
    setIsSttMode(false)
    setTranscript('')
    try { recognitionRef.current?.stop() } catch {}
  }, [])

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel()
    setIsSpeaking(false)
    isSpeakingRef.current = false
  }, [])

  const setSelectedVoice = useCallback((name: string) => {
    setSelectedVoiceState(name)
    selectedVoiceRef.current = name
    localStorage.setItem('daena_selected_voice', name)
  }, [])

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <VoiceContext.Provider
      value={{
        isActive,
        ttsEnabled,
        isSttMode,
        isListening,
        isSpeaking,
        transcript,
        availableVoices,
        selectedVoice,
        toggle,
        toggleTts,
        startStt,
        stopStt,
        stopSpeaking,
        setSelectedVoice,
      }}
    >
      {children}

      {/* Floating indicator -- visible on ALL pages while voice is active (conv mode) */}
      <AnimatePresence>
        {isActive && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className="fixed bottom-20 right-6 z-50 flex items-center gap-2 px-4 py-2.5
                       bg-accent-purple/90 backdrop-blur-md text-white rounded-full
                       shadow-lg shadow-accent-purple/20 border border-accent-purple/30"
          >
            <AudioLines
              size={16}
              className={isListening || isSpeaking ? 'animate-pulse' : ''}
            />
            <span className="text-xs font-medium">
              {isSpeaking
                ? 'Daena speaking...'
                : isListening
                  ? 'Listening...'
                  : 'Voice active'}
            </span>
            {transcript && !isSpeaking && (
              <span className="ml-1 max-w-[160px] truncate text-[10px] opacity-70">
                &ldquo;{transcript}&rdquo;
              </span>
            )}
            <button
              onClick={() => setIsActive(false)}
              className="ml-1 rounded-full px-1 hover:bg-white/20 transition-colors text-xs leading-none"
              title="Stop voice"
            >
              &times;
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </VoiceContext.Provider>
  )
}

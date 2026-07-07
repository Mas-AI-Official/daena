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

// ── TTS text sanitizer ────────────────────────────────────────────────────────
//
// Windows SAPI5 voices (David, Zira, Mark, Hazel) literally vocalize
// punctuation character names: a bare "*" becomes "asterisk", "(" becomes
// "open paren", "|" becomes "vertical bar", and "``" becomes "grave accent
// grave accent". Neural voices skip these, but we can't assume the user
// has one available, so we strip everything that isn't natural speech
// before handing text to the TTS engine.
//
// What we keep:
//   * ., !, ? for end-of-sentence prosody
//   * , ; : for mid-sentence pause prosody
//   * Letters, digits, apostrophes, hyphens, dollar signs, percent signs
//   * Spaces and newlines (newlines become breath pauses)
// Everything else is dropped or substituted.

export function cleanTextForTts(raw: string): string {
  let t = raw

  // 1. Code fences ``` ... ``` -> "code block" (don't read source).
  t = t.replace(/```[\s\S]*?```/g, ' code block ')

  // 2. Inline code `foo` -> foo (drop the backticks).
  t = t.replace(/`([^`]+)`/g, '$1')

  // 3. Markdown link [label](url) -> label.
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')

  // 4. Markdown image ![alt](url) -> alt.
  t = t.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')

  // 5. Bold / italic / strike markers -- just drop them.
  t = t.replace(/\*\*([^*]+)\*\*/g, '$1')
  t = t.replace(/\*([^*]+)\*/g, '$1')
  t = t.replace(/__([^_]+)__/g, '$1')
  t = t.replace(/_([^_]+)_/g, '$1')
  t = t.replace(/~~([^~]+)~~/g, '$1')

  // 6. Headings, blockquotes, list markers at the start of lines.
  t = t.replace(/^\s*#{1,6}\s+/gm, '')
  t = t.replace(/^\s*>\s+/gm, '')
  t = t.replace(/^\s*[-*+]\s+/gm, '')
  t = t.replace(/^\s*\d+\.\s+/gm, '')

  // 7. Drop tables: any line that is just pipes and dashes.
  t = t.replace(/^\s*\|[\s\S]*?\|\s*$/gm, '')
  t = t.replace(/^\s*\|?[\s\-:|]+\|?\s*$/gm, '')

  // 8. URLs without markdown wrapping -- speak domain only or drop.
  t = t.replace(/https?:\/\/\S+/g, 'a link')

  // 9. Emoji / pictographs -- drop. Nothing good comes of the TTS
  //    engine trying to read U+1F680.
  t = t.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F02F}]/gu, '')

  // 10. HTML/XML tags.
  t = t.replace(/<[^>]+>/g, '')

  // 11. Any remaining character that isn't natural speech. Kept chars:
  //     letters, digits, space, newline, . , ! ? ; : ' - $ % & ( ) / + = @
  //     Dropped: * _ ~ ` # > | [ ] { } < > ^ and exotic punctuation.
  t = t.replace(/[*_~`#>|\[\]{}^\\]/g, '')

  // 12. Collapse whitespace runs.
  t = t.replace(/\s+/g, ' ').trim()

  return t
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function VoiceProvider({ children }: { children: React.ReactNode }) {
  const [isActive, setIsActive] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(false)
  const [isSttMode, setIsSttMode] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  // True between sending a voice utterance and the response returning
  // (the LLM round-trip). Surfaced as "Thinking..." so the floating pill
  // is never a misleading "Voice active" while a request is in flight.
  const [isProcessing, setIsProcessing] = useState(false)
  // The TTS provider that actually rendered the last spoken response, read from
  // the backend X-Daena-TTS-Provider header ("f5" | "edge"). Empty until a
  // backend synthesis succeeds, so the UI never fakes a provider / "F5 ready".
  const [activeTtsProvider, setActiveTtsProvider] = useState('')
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

      // Auto-select best English voice. 2026 Windows ships robotic
      // voices that literally *read punctuation* ("question mark",
      // "asterisk") -- unusable for conversation. Skip them hard,
      // prefer anything neural/natural/Google.
      //
      // Ranked preference:
      //   1. Google voices (cloud-based neural, best-in-class)
      //   2. Microsoft *Neural / *Natural (Aria/Jenny/Guy/Davis/etc.)
      //   3. Platform natural voices (Samantha on macOS, Siri)
      //   4. Any English voice that is NOT on the robotic blacklist
      //   5. Last resort: first English voice
      //
      // Blacklist: SAPI5 David / Zira / Mark / Hazel / Hortense are
      // the classic robotic Windows voices and some of them read
      // punctuation character names aloud.
      const ROBOTIC = /\b(david|zira|mark|hazel|hortense|eva|helen|heera|kalpana|ravi|ravi|kangkang)\b/i
      if (!selectedVoiceRef.current) {
        const english = voices.filter((v) => v.lang.toLowerCase().startsWith('en'))
        const best =
          english.find((v) => v.name.toLowerCase().includes('google')) ??
          english.find((v) => /(Natural|Neural|Online)/i.test(v.name) && !ROBOTIC.test(v.name)) ??
          english.find((v) => /(Aria|Jenny|Guy|Davis|Brian|Ana|Samantha|Siri)/i.test(v.name)) ??
          english.find((v) => !ROBOTIC.test(v.name)) ??
          english[0] ??
          voices[0]
        if (best) {
          setSelectedVoiceState(best.name)
          selectedVoiceRef.current = best.name
        }
      }
    }

    loadVoices()
    syn.onvoiceschanged = loadVoices
    // Fallback for browsers that don't fire onvoiceschanged on first load.
    // Capture the id so we can clear it on unmount; otherwise the 500ms timer
    // can fire after the component is gone and trigger a "setState on
    // unmounted component" warning in React strict mode + a minor leak.
    const voiceLoadTimer = setTimeout(loadVoices, 500)
    return () => {
      clearTimeout(voiceLoadTimer)
      syn.onvoiceschanged = null
    }
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

  // ── TTS: Edge-TTS (Microsoft neural, free, no API key) ───────────────────
  //
  // Streams audio/mpeg from the backend /api/v1/tts/speak endpoint.
  // Voices like en-US-AriaNeural / en-US-JennyNeural / en-US-GuyNeural
  // sound natural and do NOT read punctuation character names, which is
  // the #1 complaint about SAPI5 browser TTS. ~150-300ms first-byte
  // latency on a warm network.

  const speakWithEdgeTts = useCallback(async (text: string, mindVoice?: string | null): Promise<boolean> => {
    setIsSpeaking(true)
    isSpeakingRef.current = true
    let url: string | null = null
    try {
      // Per-Mind voice from the message wins; else the user's saved default.
      const voice = mindVoice || localStorage.getItem('daena_edge_voice') || 'en-US-AriaNeural'
      const token = localStorage.getItem('daena_token') || ''
      const res = await fetch('/api/v1/tts/speak', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        // provider:'auto' = backend tries F5-TTS (Daena's cloned voice) first,
        // then Edge-TTS. A non-2xx (e.g. 503 both down) throws and falls
        // through below to ElevenLabs then browser speechSynthesis.
        body: JSON.stringify({ text: text.slice(0, 5000), voice, provider: 'auto' }),
      })
      if (!res.ok) {
        throw new Error(`backend tts HTTP ${res.status}`)
      }
      // Surface which provider actually rendered (f5 | edge). Honest: only set
      // when the backend confirms via the response header.
      const renderedBy = res.headers.get('X-Daena-TTS-Provider')
      if (renderedBy) setActiveTtsProvider(renderedBy)
      const blob = await res.blob()
      if (blob.size < 100) {
        // Empty/truncated response -- treat as failure so caller falls back.
        throw new Error('edge-tts empty blob')
      }
      url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      await new Promise<void>((resolve, reject) => {
        audio.onended = () => resolve()
        audio.onerror = () => reject(new Error('audio element error'))
        void audio.play().catch(reject)
      })
      setIsSpeaking(false)
      isSpeakingRef.current = false
      if (isActiveRef.current) {
        setTimeout(() => {
          try { recognitionRef.current?.start() } catch {}
        }, 300)
      }
      return true
    } catch (err) {
      console.warn('[VoiceProvider] Edge-TTS failed:', err)
      return false
    } finally {
      if (url) URL.revokeObjectURL(url)
    }
  }, [])

  // ── TTS dispatcher ────────────────────────────────────────────────────────
  //
  // Preference order:
  //   1. Edge-TTS (free neural, no key, no "question mark" readouts)
  //   2. ElevenLabs (if the user has a key configured)
  //   3. Browser SpeechSynthesis (always-available robot-voice fallback)

  const speakResponse = useCallback(async (text: string, mindVoice?: string | null) => {
    if (!isActiveRef.current && !ttsEnabledRef.current) return
    try { recognitionRef.current?.stop() } catch {}

    // Honor an opt-out so users on locked networks who can't reach
    // Microsoft's CDN can force browser-native without editing code.
    const edgeDisabled = localStorage.getItem('daena_edge_tts_disabled') === '1'

    if (!edgeDisabled) {
      const ok = await speakWithEdgeTts(text, mindVoice)
      if (ok) return
      // ok=false resets isSpeaking internally; the finally on the function
      // already logged, fall through to next provider.
      isSpeakingRef.current = false
      setIsSpeaking(false)
    }

    const apiKey = localStorage.getItem('daena:elevenlabs_key')
    if (apiKey) {
      void speakWithElevenLabs(text, apiKey)
    } else {
      speakWithBrowser(text)
    }
  }, [speakWithEdgeTts, speakWithElevenLabs, speakWithBrowser])

  // ── Voice-through-chat: send via chatStore (text shows in UI) ─────────────
  //
  // Bug before 2026-04-22: chatStore.sendMessage silently returns when
  // ``activeSessionId`` is null. Clicking Voice on a fresh /chat page
  // (no session yet) meant the STT transcript was captured but never
  // reached the API -- no message appeared, no response, no TTS.
  //
  // Fix: use sendMessageStream with ``createSession`` init so the store
  // auto-creates a session on first message. Match the defaults used by
  // the plain-text chat input (STANDARD mode + AUTO routing) so voice
  // and keyboard inputs behave identically.

  // Voice-mode prompt prefix. Attached to the user's message before it
  // hits the LLM so responses are short, conversational, and TTS-friendly.
  // Without this, the model defaults to paragraph-length markdown which
  // the TTS has to strip and stutter through.
  const VOICE_PROMPT_PREFIX =
    "[Voice mode: the user is speaking to you out loud and the reply " +
    "will be read aloud. Reply in 1-3 natural spoken sentences. " +
    "No markdown, no bullet lists, no code blocks, no URLs -- just " +
    "plain conversation as if you were on a call.] "

  const sendViaChat = useCallback(async (text: string) => {
    try { recognitionRef.current?.stop() } catch {}
    setIsProcessing(true)
    try {
      const store = useChatStore.getState()
      // Prefix once so the LLM knows to keep it short.
      const prompted = VOICE_PROMPT_PREFIX + text
      // DO NOT pin preferredModel for voice turns.
      //
      // Previous attempt pinned 'gemma' so the local llama-server
      // auto-swap manager would hot-load Gemma-4-E4B. Problem: when
      // llama-server is down / the port is held by another service /
      // the user has no local runtime at all, the router couldn't
      // find a candidate named 'gemma' and the whole chat stream
      // returned 500. Voice messages then dropped silently.
      //
      // Letting the router decide (preferredModel=null) uses the
      // healthy-model-aware scorer + power_mode cloud bias. On hosts
      // with llama-server up, Gemma still wins via locality/tag.
      // On hosts without it, routing falls through to cloud (Claude/
      // Codex/Gemini CLI) and voice continues to work.
      if (store.activeSessionId) {
        await store.sendMessageStream(prompted, null)
      } else {
        // Enum contracts (verified against backend schemas):
        //   mode:        CMD | EXE                              (action mode)
        //   routingMode: STANDARD | COUNCIL | QUINTESSENCE      (reasoning)
        // Earlier attempt sent 'STANDARD' and 'AUTO' which failed
        // backend pattern validation with 422, voice messages dropped.
        await store.sendMessageStream(prompted, null, {
          createSession: {
            mode: 'CMD',
            routingMode: 'STANDARD',
            autopilot: false,
            thinkMode: false,
          },
        })
      }
    } catch (err) {
      console.error('[VoiceProvider] sendViaChat error:', err)
    } finally {
      setIsProcessing(false)
    }
    // Restart mic after a delay (TTS auto-read will handle speaking)
    if (isActiveRef.current) {
      setTimeout(() => {
        if (isActiveRef.current && !isSpeakingRef.current) {
          try { recognitionRef.current?.start() } catch {}
        }
      }, 500)
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
        newest.role === 'ASSISTANT' &&
        newest.content &&
        !state.stream.isStreaming
      ) {
        lastMsgCount = msgs.length
        // Speak the response. Robotic Windows voices literally say
        // "question mark" / "asterisk" / "open paren" for punctuation
        // characters, so we strip anything that isn't natural speech.
        // Terminal punctuation (. , ! ?) is kept because TTS engines
        // use it for prosody -- only the raw character names get
        // vocalized on trashy voices, and the user's neural-voice
        // preference (see auto-select) handles that.
        const cleanText = cleanTextForTts(newest.content)
        // Speak in the active department Mind's voice when the routing event
        // supplied one (chatStore attaches it to the message); else default.
        if (cleanText) speakResponse(cleanText.slice(0, 2000), newest.voice)
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

  // ── Auto-OFF voice on tab/window blur (F-0010 fix) ────────────────────────
  // Prevents the mic from continuing to capture (and auto-send) ambient audio
  // when the user switches away from Daena. Without this, the user's
  // environment microphone keeps streaming into the chat even when they're
  // working in another window. Mirrors the polling-pause-on-tab-hide pattern
  // used in TasksPage / GovernanceApprovalsPage.
  useEffect(() => {
    const stopOnBlur = () => {
      if (isActiveRef.current) {
        setIsActive(false)
        toast.info('Voice paused (tab blurred). Click the mic to resume.')
      }
    }
    const onVisibilityChange = () => {
      if (document.hidden) stopOnBlur()
    }
    window.addEventListener('blur', stopOnBlur)
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      window.removeEventListener('blur', stopOnBlur)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  // ── Actions ───────────────────────────────────────────────────────────────

  const toggle = useCallback(() => {
    // F-0010 fix: first-time activation per browser shows a one-time
    // confirmation. Without this, users can't distinguish "I activated
    // voice and Daena will read my next sentence" from "I accidentally
    // hovered the button". Voice in conversational mode AUTO-SENDS, which
    // means an ambient utterance can trigger tool execution under EXE
    // mode -- the user must explicitly opt in once.
    setIsActive((prev) => {
      if (!prev) {
        const ackd = localStorage.getItem('daena:voice_conv_acknowledged') === '1'
        if (!ackd) {
          const ok = window.confirm(
            'Voice conversation mode will AUTO-SEND what you say to Daena ' +
            '(including ambient speech captured by your mic). ' +
            'In EXE mode this could trigger tool execution. ' +
            'Click OK to enable, or Cancel to keep voice off.\n\n' +
            'You can disable mic auto-send anytime by clicking the floating "x" overlay.',
          )
          if (!ok) return prev
          localStorage.setItem('daena:voice_conv_acknowledged', '1')
        }
      }
      return !prev
    })
  }, [])

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
              className={isListening || isSpeaking || isProcessing ? 'animate-pulse' : ''}
            />
            <span className="text-xs font-medium">
              {isSpeaking
                ? (activeTtsProvider ? `Daena speaking (${activeTtsProvider})...` : 'Daena speaking...')
                : isProcessing
                  ? 'Thinking...'
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

/**
 * VoiceControls: UI buttons for voice interaction in the chat input bar.
 *
 * Delegates all recognition and TTS to VoiceProvider (App-level singleton).
 * These buttons call useVoice().toggle() to activate/deactivate voice.
 * Voice settings (voice selector, preview) live here for in-chat convenience.
 * The canonical settings location is Settings > General > Voice.
 */
import { useState, useRef, useEffect, memo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Volume2, VolumeX, Settings } from 'lucide-react'
import { useVoice } from '@/providers/VoiceProvider'

// ── Waveform animation ────────────────────────────────────────────────────────

function WaveformIndicator() {
  return (
    <div className="flex items-center gap-0.5 h-4">
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.div
          key={i}
          className="w-0.5 bg-status-error rounded-full"
          animate={{ height: ['8px', '16px', '8px'] }}
          transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.1, ease: 'easeInOut' }}
        />
      ))}
    </div>
  )
}

// ── VoiceControls ─────────────────────────────────────────────────────────────

interface VoiceControlsProps {
  /** Called when a transcript arrives (STT-only path, unused in conversational mode) */
  onTranscript?: (text: string) => void
  disabled?: boolean
  className?: string
}

export const VoiceControls = memo(function VoiceControls({
  onTranscript,
  disabled = false,
  className = '',
}: VoiceControlsProps) {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const settingsRef = useRef<HTMLDivElement>(null)

  const {
    isActive,
    ttsEnabled,
    isSttMode,
    isListening,
    isSpeaking,
    toggleTts,
    startStt,
    stopStt,
    availableVoices,
    selectedVoice,
    setSelectedVoice,
  } = useVoice()

  const handleMicClick = useCallback(() => {
    if (isSttMode) {
      stopStt()
    } else {
      startStt((text) => onTranscript?.(text))
    }
  }, [isSttMode, stopStt, startStt, onTranscript])

  const srSupported =
    typeof window !== 'undefined' &&
    !!(
      (window as unknown as Record<string, unknown>)['SpeechRecognition'] ||
      (window as unknown as Record<string, unknown>)['webkitSpeechRecognition']
    )
  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  // Close settings on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false)
      }
    }
    if (settingsOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [settingsOpen])

  if (!srSupported && !ttsSupported) return null

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      {/* Mic button: STT-only mode (fills text input) */}
      {srSupported && (
        <button
          onClick={handleMicClick}
          disabled={disabled}
          className={`relative p-2 rounded-lg transition-all ${
            isSttMode
              ? 'bg-status-error/20 text-status-error'
              : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/5'
          } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
          title={isSttMode ? 'Stop dictation' : 'Dictate text'}
        >
          {isSttMode && isListening ? (
            <>
              <MicOff size={18} />
              <span className="absolute inset-0 rounded-lg animate-ping bg-status-error/20" />
            </>
          ) : (
            <Mic size={18} />
          )}
        </button>
      )}

      {/* Waveform when listening in either mode */}
      <AnimatePresence>
        {(isActive || isSttMode) && isListening && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 'auto' }}
            exit={{ opacity: 0, width: 0 }}
            className="overflow-hidden"
          >
            <WaveformIndicator />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Speaker icon: TTS-only (auto-read responses) */}
      {ttsSupported && (
        <button
          onClick={toggleTts}
          className={`p-2 rounded-lg transition-all cursor-pointer ${
            ttsEnabled || isActive
              ? 'text-primary-400 bg-primary-500/10'
              : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/5'
          }`}
          title={ttsEnabled ? (isSpeaking ? 'Speaking...' : 'TTS ON (click to stop)') : isActive ? 'Conversation mode (TTS active)' : 'Read responses aloud'}
        >
          {ttsEnabled || isActive ? <Volume2 size={18} className={isSpeaking ? 'animate-pulse' : ''} /> : <VolumeX size={18} />}
        </button>
      )}

      {/* Voice settings popup */}
      {ttsSupported && (
        <div className="relative" ref={settingsRef}>
          <button
            onClick={() => setSettingsOpen(!settingsOpen)}
            className="p-2 rounded-lg text-starlight-400 hover:text-starlight-200 hover:bg-white/5 transition-all cursor-pointer"
            title="Voice settings"
          >
            <Settings size={14} />
          </button>

          <AnimatePresence>
            {settingsOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute bottom-full right-0 mb-2 w-64 rounded-xl bg-midnight-200 border border-white/10 shadow-2xl z-50 p-4 space-y-3"
              >
                <h4 className="text-xs font-medium text-starlight-200">Voice Settings</h4>

                {/* Voice selector */}
                <div>
                  <label className="text-[10px] text-starlight-400 mb-1 block">Voice</label>
                  {availableVoices.length > 0 ? (
                    <select
                      value={selectedVoice}
                      onChange={(e) => setSelectedVoice(e.target.value)}
                      className="w-full glass-input text-xs text-starlight-200 py-1.5 cursor-pointer"
                    >
                      {availableVoices
                        .filter((v) => v.lang.startsWith('en'))
                        .map((voice) => (
                          <option key={voice.name} value={voice.name}>
                            {voice.name} ({voice.lang})
                          </option>
                        ))}
                    </select>
                  ) : (
                    <p className="text-[10px] text-starlight-500">Loading voices...</p>
                  )}
                </div>

                {/* ElevenLabs hint */}
                <p className="text-[10px] text-starlight-500">
                  Add an ElevenLabs API key in{' '}
                  <span className="text-accent-purple">Settings &gt; General &gt; Voice</span>{' '}
                  for premium voices.
                </p>

                {/* Preview */}
                <button
                  onClick={() => {
                    const syn = window.speechSynthesis
                    if (!syn) return
                    syn.cancel()
                    const u = new SpeechSynthesisUtterance(
                      'Hello, I am Daena, your governed AI assistant.',
                    )
                    const voice = availableVoices.find((v) => v.name === selectedVoice)
                    if (voice) u.voice = voice
                    u.rate = 0.95
                    syn.speak(u)
                  }}
                  className="text-xs text-accent-purple hover:text-accent-purple/80 transition-colors cursor-pointer"
                >
                  Preview voice
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
})

// ── TTS utility (used by MessageList to read responses aloud) ─────────────────

export function speakText(
  text: string,
  voiceName?: string,
  rate: number = 1.0,
): void {
  if (!('speechSynthesis' in window)) return
  speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.rate = rate
  if (voiceName) {
    const voice = speechSynthesis.getVoices().find((v) => v.name === voiceName)
    if (voice) utterance.voice = voice
  }
  speechSynthesis.speak(utterance)
}

export function stopSpeaking(): void {
  if ('speechSynthesis' in window) speechSynthesis.cancel()
}

export default VoiceControls

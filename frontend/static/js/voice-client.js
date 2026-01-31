/**
 * Voice Client for Daena VP
 * Full implementation with:
 * - Speech-to-Text with auto-send after silence
 * - Text-to-Speech using local XTTS audio service
 * - Interruption on typing/speaking
 * - Background operation
 */

class VoiceClient {
    constructor() {
        // Service URLs
        this.audioServiceUrl = 'http://127.0.0.1:5001';
        this.backendUrl = 'http://127.0.0.1:8000';

        // State
        this.enabled = false;
        this.speaking = false;
        this.listening = false;
        this.isRecording = false;

        // Audio elements
        this.audioElement = null;
        this.audioQueue = [];

        // Speech recognition
        this.recognition = null;
        this.silenceTimer = null;
        this.silenceTimeout = 3000; // 3 seconds silence before auto-send
        this.interimTranscript = '';
        this.finalTranscript = '';

        // Initialize
        this._initAudioElement();
        this._initSpeechRecognition();
        this._setupInterruptionHandlers();

        console.log('🎤 Voice Client initialized');
    }

    _initAudioElement() {
        this.audioElement = new Audio();
        this.audioElement.onended = () => {
            this.speaking = false;
            this._updateUI();
            this._playNextInQueue();
        };
        this.audioElement.onerror = (e) => {
            console.error('Audio playback error:', e);
            this.speaking = false;
            this._updateUI();
            this._playNextInQueue();
        };
    }

    _initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('⚠️ Speech recognition not supported in this browser');
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';
        this.recognition.maxAlternatives = 1;

        this.recognition.onstart = () => {
            console.log('🎤 Listening started');
            this.listening = true;
            this.isRecording = true;
            this._updateUI();
        };

        this.recognition.onend = () => {
            console.log('🎤 Listening ended');
            this.listening = false;
            this.isRecording = false;
            this._updateUI();

            // Auto-restart if still enabled
            if (this.enabled && !this.speaking) {
                setTimeout(() => {
                    if (this.enabled) {
                        this._startListening();
                    }
                }, 500);
            }
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isRecording = false;

            if (event.error === 'no-speech') {
                // Silently restart
                if (this.enabled) {
                    setTimeout(() => this._startListening(), 1000);
                }
            } else if (event.error === 'aborted') {
                // Normal abort, restart if enabled
                if (this.enabled) {
                    setTimeout(() => this._startListening(), 500);
                }
            }
        };

        this.recognition.onresult = (event) => {
            // Stop speaking if user starts talking
            if (this.speaking) {
                this.stopSpeaking();
            }

            // Clear silence timer
            this._clearSilenceTimer();

            // Process results
            let interim = '';
            let final = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += transcript;
                } else {
                    interim += transcript;
                }
            }

            if (final) {
                this.finalTranscript += final;
            }
            this.interimTranscript = interim;

            // Update input field with current transcript
            const input = document.getElementById('message-input');
            if (input) {
                input.value = this.finalTranscript + this.interimTranscript;
                input.dispatchEvent(new Event('input', { bubbles: true }));

                // Auto-resize textarea
                input.style.height = 'auto';
                input.style.height = Math.min(input.scrollHeight, 200) + 'px';
            }

            // Start silence timer for auto-send
            if (this.finalTranscript.trim().length > 0) {
                this._startSilenceTimer();
            }

            this._updateUI();
        };
    }

    _startSilenceTimer() {
        this._clearSilenceTimer();

        this.silenceTimer = setTimeout(() => {
            // User stopped speaking for 2 seconds - auto send
            if (this.finalTranscript.trim().length > 0) {
                console.log('🔇 Silence detected - auto-sending message');
                this._autoSendMessage();
            }
        }, this.silenceTimeout);
    }

    _clearSilenceTimer() {
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }
    }

    _autoSendMessage() {
        const input = document.getElementById('message-input');
        const form = document.getElementById('chat-form');

        if (input && input.value.trim().length > 0 && form) {
            // Clear transcripts for next message
            this.finalTranscript = '';
            this.interimTranscript = '';

            // Trigger form submit
            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

            console.log('✅ Message auto-sent via voice');
        }
    }

    _setupInterruptionHandlers() {
        // Interrupt speech when user types
        document.addEventListener('keydown', (e) => {
            const target = e.target;
            if (this.speaking && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
                this.stopSpeaking();
            }
        });

        // Interrupt when clicking in input areas
        document.addEventListener('click', (e) => {
            const target = e.target;
            if (this.speaking && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
                this.stopSpeaking();
            }
        });

        // Stop silence timer when typing manually
        document.getElementById('message-input')?.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') {
                this._clearSilenceTimer();
                // Clear voice transcript if manually typing
                if (this.isRecording) {
                    this.finalTranscript = '';
                    this.interimTranscript = '';
                }
            }
        });
    }

    _startListening() {
        if (!this.recognition) {
            console.warn('Speech recognition not available');
            return;
        }

        try {
            this.recognition.start();
        } catch (e) {
            // Already started, ignore
            if (e.name !== 'InvalidStateError') {
                console.error('Failed to start recognition:', e);
            }
        }
    }

    _stopListening() {
        this._clearSilenceTimer();

        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {
                // Already stopped, ignore
            }
        }

        this.listening = false;
        this.isRecording = false;
        this.finalTranscript = '';
        this.interimTranscript = '';
    }

    async enable() {
        this.enabled = true;

        // Check audio service availability
        const available = await this.checkAudioService();
        if (!available) {
            console.warn('⚠️ Audio service not available at', this.audioServiceUrl);
            this._showToast('Voice service offline - check audio service', 'warning');
        }

        // Start listening
        this._startListening();

        this._updateUI();
        this._showToast('Voice mode enabled 🎤', 'success');

        console.log('✅ Voice mode enabled');
    }

    disable() {
        this.enabled = false;

        // Stop listening
        this._stopListening();

        // Stop any ongoing speech
        this.stopSpeaking();

        this._updateUI();
        this._showToast('Voice mode disabled', 'info');

        console.log('🔇 Voice mode disabled');
    }

    toggle() {
        if (this.enabled) {
            this.disable();
        } else {
            this.enable();
        }
    }

    async speak(text, language = 'en') {
        if (!this.enabled || !text || text.trim().length === 0) {
            return;
        }

        // Add to queue
        this.audioQueue.push({ text, language });

        // If not already speaking, start
        if (!this.speaking) {
            await this._processAudioQueue();
        }
    }

    async _processAudioQueue() {
        if (this.audioQueue.length === 0) {
            this.speaking = false;
            this._updateUI();
            return;
        }

        const { text, language } = this.audioQueue.shift();

        try {
            this.speaking = true;

            // Pause recognition while speaking to avoid feedback
            if (this.isRecording) {
                this.recognition.stop();
            }

            this._updateUI();

            // Request TTS from local audio service
            const response = await fetch(`${this.audioServiceUrl}/api/tts/speak`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    language: language,
                    speaker_wav: "" // Uses default daena_voice.wav if empty
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`TTS request failed: ${response.status} - ${errorText}`);
            }

            const data = await response.json();

            // Play the audio
            await this._playAudio(data.audio_file);

        } catch (error) {
            console.error('TTS error:', error);
            this.speaking = false;
            this._updateUI();
            // Continue with next in queue
            this._playNextInQueue();
        }
    }

    async _playAudio(audioPath) {
        return new Promise((resolve, reject) => {
            // Extract filename from path
            const filename = audioPath.split('/').pop().split('\\').pop();
            const audioUrl = `${this.audioServiceUrl}/api/tts/audio/${filename}`;

            this.audioElement.src = audioUrl;
            this.audioElement.onended = () => {
                resolve();
                this._playNextInQueue();
            };
            this.audioElement.onerror = (e) => {
                console.error('Audio playback error:', e);
                reject(e);
                this._playNextInQueue();
            };

            this.audioElement.play().catch(error => {
                console.error('Audio play failed:', error);
                reject(error);
                this._playNextInQueue();
            });
        });
    }

    _playNextInQueue() {
        if (this.audioQueue.length > 0) {
            this._processAudioQueue();
        } else {
            this.speaking = false;

            // Resume recognition after speaking
            if (this.enabled && !this.isRecording) {
                this._startListening();
            }

            this._updateUI();
        }
    }

    stopSpeaking() {
        // Clear queue
        this.audioQueue = [];

        // Stop current audio
        if (this.audioElement) {
            this.audioElement.pause();
            this.audioElement.currentTime = 0;
        }

        this.speaking = false;

        // Resume recognition after interruption
        if (this.enabled && !this.isRecording) {
            this._startListening();
        }

        this._updateUI();
    }

    _updateUI() {
        // 1. Update Chat Header UI (daena_office.html)
        const toggleBtn = document.getElementById('voice-toggle-btn');
        const icon = document.getElementById('voice-icon');

        // 2. Update Navbar UI (topbar.html / voice-widget.js)
        const navBtn = document.getElementById('voice-navbar-btn');
        const navIcon = document.getElementById('voice-navbar-icon');
        const navText = document.getElementById('voice-navbar-text');

        const updateElements = (btn, icn, txt, isNav = false) => {
            if (!btn) return;

            // Reset classes
            btn.classList.remove('text-daena-gold', 'text-green-400', 'text-white', 'text-gray-400', 'animate-pulse', 'bg-daena-gold/20', 'bg-green-500/10', 'bg-red-500/20');
            if (icn) icn.classList.remove('animate-pulse', 'fa-spin');

            if (this.enabled) {
                if (this.speaking) {
                    if (icn) icn.className = isNav ? 'fas fa-volume-up text-lg text-daena-gold' : 'fas fa-volume-up';
                    btn.classList.add(isNav ? 'bg-daena-gold/20' : 'text-daena-gold');
                    if (icn) icn.classList.add('animate-pulse');
                    if (txt) txt.textContent = 'Speaking...';
                } else if (this.isRecording) {
                    if (icn) icn.className = isNav ? 'fas fa-microphone text-lg text-red-500' : 'fas fa-microphone';
                    btn.classList.add(isNav ? 'bg-red-500/20' : 'text-green-400', 'animate-pulse');
                    if (txt) txt.textContent = 'Listening...';
                } else {
                    if (icn) icn.className = isNav ? 'fas fa-microphone text-lg text-daena-gold' : 'fas fa-microphone';
                    btn.classList.add(isNav ? 'bg-green-500/10' : 'text-white');
                    if (txt) txt.textContent = 'Say "Daena"';
                }
            } else {
                if (icn) icn.className = isNav ? 'fas fa-microphone text-lg text-gray-400' : 'fas fa-microphone-slash';
                btn.classList.add(isNav ? 'bg-white/5' : 'text-gray-400');
                if (txt) txt.textContent = 'Voice';
            }
        };

        updateElements(toggleBtn, icon, null, false);
        updateElements(navBtn, navIcon, navText, true);
    }

    async checkAudioService() {
        try {
            const response = await fetch(`${this.audioServiceUrl}/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(3000)
            });
            const data = await response.json();
            console.log('Audio service status:', data);
            return response.ok;
        } catch (error) {
            console.warn('Audio service not available:', error.message);
            return false;
        }
    }

    // Called when assistant message is received
    onMessageReceived(message) {
        if (this.enabled && message && message.content) {
            // Speak the assistant's message
            this.speak(message.content);
        }
    }

    _showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
}

// ============================================================
// GLOBAL INITIALIZATION
// ============================================================

// Create singleton instance
window.voiceClient = new VoiceClient();

// Export functions for HTML onclick handlers
window.toggleVoice = function () {
    window.voiceClient.toggle();
};

window.openVoiceSettings = function () {
    // Show voice settings modal (placeholder for now)
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50';
    modal.id = 'voice-settings-modal';
    modal.innerHTML = `
        <div class="glass-panel p-8 rounded-2xl max-w-md w-full mx-4">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold text-white">🎤 Voice Settings</h2>
                <button onclick="document.getElementById('voice-settings-modal').remove()" 
                        class="text-gray-400 hover:text-white">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="space-y-4">
                <div class="p-4 bg-white/5 rounded-lg">
                    <label class="flex items-center justify-between">
                        <span class="text-gray-300">Silence timeout (seconds)</span>
                        <input type="number" value="${window.voiceClient.silenceTimeout / 1000}" 
                               min="1" max="10" step="0.5"
                               onchange="window.voiceClient.silenceTimeout = this.value * 1000"
                               class="w-20 bg-black/30 border border-white/20 rounded px-2 py-1 text-white text-center">
                    </label>
                    <p class="text-xs text-gray-500 mt-1">Time to wait after you stop speaking before auto-send</p>
                </div>
                <div class="p-4 bg-white/5 rounded-lg">
                    <p class="text-gray-300 mb-2">Voice Sample</p>
                    <p class="text-sm text-gray-400">daena_voice.wav</p>
                    <p class="text-xs text-gray-500 mt-1">Located in project root directory</p>
                </div>
                <div class="p-4 bg-white/5 rounded-lg">
                    <p class="text-gray-300 mb-2">Audio Service</p>
                    <p class="text-sm text-green-400" id="audio-service-status">Checking...</p>
                </div>
            </div>
            <div class="mt-6 flex gap-3">
                <button onclick="document.getElementById('voice-settings-modal').remove()" 
                        class="flex-1 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-gray-300 transition-colors">
                    Close
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Check audio service status
    window.voiceClient.checkAudioService().then(available => {
        const statusEl = document.getElementById('audio-service-status');
        if (statusEl) {
            statusEl.textContent = available ? '✅ Connected (127.0.0.1:5001)' : '❌ Offline';
            statusEl.className = available ? 'text-sm text-green-400' : 'text-sm text-red-400';
        }
    });
};

// ============================================================
// AUTO-INTEGRATION WITH CHAT
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎤 Voice client DOM ready - setting up integration');

    // Check audio service on load
    window.voiceClient.checkAudioService().then(available => {
        if (available) {
            console.log('✅ Audio service connected at', window.voiceClient.audioServiceUrl);
        } else {
            console.warn('⚠️ Audio service not available - TTS will not work');
            console.warn('💡 Start audio service: venv_daena_audio_py310\\Scripts\\activate.bat && python -m uvicorn audio.audio_service.main:app --port 5001');
        }
    });

    // Hook into message display to auto-speak responses
    const originalRenderMessage = window.renderAssistantMessage;
    if (typeof originalRenderMessage === 'function') {
        window.renderAssistantMessage = function (content, ...args) {
            // Call original render
            const result = originalRenderMessage.call(this, content, ...args);

            // Speak the message
            if (window.voiceClient && window.voiceClient.enabled) {
                window.voiceClient.speak(content);
            }

            return result;
        };
    }

    // Alternative: Watch for new messages being added
    const chatContainer = document.getElementById('chat-messages');
    if (chatContainer) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if this is an assistant message
                        const messageDiv = node.querySelector('.bg-white\\/10');
                        if (messageDiv && !node.dataset.voiceSpoken) {
                            // Check if it's from Daena (has the golden avatar)
                            const avatar = node.querySelector('.bg-daena-gold');
                            if (avatar) {
                                const content = messageDiv.textContent?.trim();
                                if (content && window.voiceClient?.enabled) {
                                    node.dataset.voiceSpoken = 'true';
                                    window.voiceClient.speak(content);
                                }
                            }
                        }
                    }
                });
            });
        });

        observer.observe(chatContainer, { childList: true, subtree: true });
        console.log('✅ Voice auto-speak observer attached to chat');
    }

    // Hijack navbar button if it exists
    const navBtn = document.getElementById('voice-navbar-btn');
    if (navBtn) {
        navBtn.onclick = (e) => {
            e.preventDefault();
            window.voiceClient.toggle();
        };
        console.log('✅ Navbar voice button hijacked by VoiceClient');
    }
});

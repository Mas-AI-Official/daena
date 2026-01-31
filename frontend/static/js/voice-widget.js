/**
 * Daena Voice Widget - Wake Word & Continuous Listening Mode
 * 
 * Features:
 * - Continuous listening for wake words ("daena", "hi daena", "hey daena")
 * - Push-to-talk with Ctrl+Shift+V
 * - Automatic transcription and LLM response
 * - Background mode with navbar button
 */

class VoiceWidget {
    constructor() {
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isProcessing = false;
        this.sessionId = null;

        // Wake word detection
        this.wakeWordEnabled = true;
        this.wakeWords = ['daena', 'dina', 'deena', 'dana', 'hi daena', 'hey daena', 'ok daena'];
        this.recognition = null;
        this.isWakeListening = false;
        this.wakeWordDetected = false;

        this.init();
    }

    async init() {
        // Get or create session for voice chat
        await this.initSession();

        // Check voice service status
        this.checkStatus();

        // Setup keyboard shortcut (Ctrl+Shift+V to toggle)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'V') {
                e.preventDefault();
                this.toggleRecording();
            }
        });

        // Initialize wake word detection
        this.initWakeWordDetection();
    }

    initWakeWordDetection() {
        // Check for Web Speech API support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn('⚠️ Wake word detection not supported (Web Speech API unavailable)');
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const last = event.results.length - 1;
            const transcript = event.results[last][0].transcript.toLowerCase().trim();
            const isFinal = event.results[last].isFinal;

            console.log('🎤 Heard:', transcript, isFinal ? '(final)' : '(interim)');

            // Check for wake word
            const hasWakeWord = this.wakeWords.some(word => transcript.includes(word));

            if (hasWakeWord && !this.isRecording && !this.isProcessing) {
                console.log('✅ Wake word detected!');
                this.wakeWordDetected = true;

                // Extract command after wake word
                let command = transcript;
                for (const word of this.wakeWords) {
                    command = command.replace(word, '').trim();
                }

                // Play wake sound
                this.playWakeSound();

                // Fill message input field if it exists (daena_office uses message-input, department_office uses messageInput)
                const messageInput = document.getElementById('message-input') || document.getElementById('messageInput');
                if (messageInput) {
                    // Set the command in the input field
                    if (command.length > 0) {
                        messageInput.value = command;
                        messageInput.focus();
                    }

                    // Start continuous listening for more input
                    this.startVoiceToInput();
                } else {
                    // Fallback: start regular recording
                    this.startRecording();
                    setTimeout(() => {
                        if (this.isRecording && !this.isProcessing) {
                            this.stopRecording();
                        }
                    }, 5000);
                }
            }
        };

        this.recognition.onerror = (event) => {
            console.warn('Wake word error:', event.error);
            // Restart on error (except for "not-allowed")
            if (event.error !== 'not-allowed' && this.wakeWordEnabled) {
                setTimeout(() => this.startWakeWordListening(), 1000);
            }
        };

        this.recognition.onend = () => {
            // Auto-restart if wake word mode is enabled
            if (this.wakeWordEnabled && !this.isRecording) {
                setTimeout(() => this.startWakeWordListening(), 500);
            }
        };

        // Start wake word listening
        this.startWakeWordListening();
    }

    startWakeWordListening() {
        if (this.recognition && !this.isRecording && !this.isProcessing) {
            try {
                this.recognition.start();
                this.isWakeListening = true;
                console.log('👂 Wake word listening active...');
                this.updateNavbarUI('wake-listening');
            } catch (e) {
                // Already started
                if (e.name !== 'InvalidStateError') {
                    console.error('Failed to start wake word detection:', e);
                }
            }
        }
    }

    stopWakeWordListening() {
        if (this.recognition) {
            try {
                this.recognition.stop();
                this.isWakeListening = false;
            } catch (e) {
                // Ignore errors when stopping
            }
        }
    }

    toggleWakeWord() {
        this.wakeWordEnabled = !this.wakeWordEnabled;

        if (this.wakeWordEnabled) {
            this.startWakeWordListening();
            if (window.showToast) {
                window.showToast('Wake word enabled - say "Daena" to start', 'success');
            }
        } else {
            this.stopWakeWordListening();
            if (window.showToast) {
                window.showToast('Wake word disabled', 'info');
            }
        }

        return this.wakeWordEnabled;
    }

    playWakeSound() {
        // Play a subtle sound when wake word detected
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.2);
        } catch (e) {
            // Ignore audio errors
        }
    }

    startVoiceToInput() {
        // Use Web Speech API to transcribe directly to input field
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            if (window.showToast) window.showToast('Voice input not supported in this browser', 'error');
            return;
        }

        // Stop wake word listening
        this.stopWakeWordListening();
        this.isRecording = true;
        this.updateNavbarUI('listening');

        const voiceRecognition = new SpeechRecognition();
        voiceRecognition.continuous = true;
        voiceRecognition.interimResults = true;
        voiceRecognition.lang = 'en-US';

        let silenceTimeout = null;
        let finalTranscript = '';
        const messageInput = document.getElementById('message-input') || document.getElementById('messageInput');

        voiceRecognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                } else {
                    interim += transcript;
                }
            }

            // Update input field with current transcription
            if (messageInput) {
                messageInput.value = (finalTranscript + interim).trim();
            }

            // Reset silence timeout - auto-submit after 2.5 seconds of silence
            clearTimeout(silenceTimeout);
            silenceTimeout = setTimeout(() => {
                voiceRecognition.stop();
            }, 2500);
        };

        voiceRecognition.onerror = (e) => {
            console.warn('Voice input error:', e.error);
            this.isRecording = false;
            this.updateNavbarUI('wake-listening');
            this.startWakeWordListening();
        };

        voiceRecognition.onend = () => {
            this.isRecording = false;
            clearTimeout(silenceTimeout);

            // Auto-submit if there's content (chat-form on daena_office; department office uses sendMessage())
            const chatForm = document.getElementById('chat-form');
            if (messageInput && messageInput.value.trim().length > 0) {
                if (chatForm) {
                    chatForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                } else if (typeof window.sendMessage === 'function') {
                    window.sendMessage();
                }
                if (window.showToast) {
                    window.showToast('Message sent via voice', 'success');
                }
            }

            // Resume wake word listening
            this.updateNavbarUI('wake-listening');
            setTimeout(() => this.startWakeWordListening(), 500);
        };

        try {
            voiceRecognition.start();
            if (window.showToast) {
                window.showToast('Listening... speak now (auto-sends after pause)', 'info');
            }
        } catch (e) {
            console.error('Failed to start voice input:', e);
            this.isRecording = false;
            this.startWakeWordListening();
        }
    }

    async processVoiceCommand(command) {
        if (!command || this.isProcessing) return;

        this.isProcessing = true;
        this.updateNavbarUI('processing');

        try {
            // Send directly to Daena chat
            const response = await fetch('/api/v1/daena/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: command })
            });

            const data = await response.json();

            if (data.response) {
                // Show response
                if (window.showToast) {
                    window.showToast(`You: "${command}"`, 'info');
                    setTimeout(() => {
                        window.showToast(`Daena: "${data.response.substring(0, 100)}..."`, 'success');
                    }, 500);
                }

                // Speak response
                if (window.speak) {
                    window.speak(data.response);
                }
            }
        } catch (e) {
            console.error('Voice command failed:', e);
            if (window.showToast) {
                window.showToast('Sorry, I had trouble processing that.', 'error');
            }
        } finally {
            this.isProcessing = false;
            this.updateNavbarUI('wake-listening');
        }
    }

    async initSession() {
        // Use unified chat SessionManager (Phase 3)
        if (window.sessionManager) {
            try {
                const session = await window.sessionManager.getOrCreateSession(
                    'general',      // scope_type
                    null,           // scope_id
                    'voice',        // category
                    'Voice Conversation with Daena'  // title
                );

                this.sessionId = session.session_id;
                console.log('✅ Voice session initialized:', session.thread_key);
            } catch (e) {
                console.error('Failed to initialize voice session:', e);
                this.sessionId = `voice_${Date.now()}`;
            }
        } else {
            console.warn('SessionManager not available, using fallback');
            this.sessionId = `voice_${Date.now()}`;
        }
    }

    async checkStatus() {
        try {
            const response = await fetch('/api/v1/voice/status');
            const data = await response.json();

            const statusIndicator = document.getElementById('voice-status-indicator');
            const voiceBtn = document.getElementById('voice-navbar-btn');

            const isOnline = data.status === 'online' || data.talk_active === true;
            if (isOnline) {
                if (statusIndicator) {
                    statusIndicator.classList.remove('bg-red-500');
                    statusIndicator.classList.add('bg-green-500');
                }
                if (voiceBtn) voiceBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                if (window.RealtimeStatusManager) window.RealtimeStatusManager.updateStatus('voice', data);
            } else {
                if (statusIndicator) {
                    statusIndicator.classList.remove('bg-green-500');
                    statusIndicator.classList.add('bg-red-500');
                }
                if (voiceBtn) voiceBtn.classList.add('opacity-50', 'cursor-not-allowed');
                if (window.RealtimeStatusManager) window.RealtimeStatusManager.updateStatus('voice', { talk_active: false });
            }
        } catch (e) {
            console.error('Failed to check voice status:', e);
            if (statusIndicator) {
                statusIndicator.classList.remove('bg-green-500');
                statusIndicator.classList.add('bg-red-500');
            }
            if (voiceBtn) voiceBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    async toggleRecording() {
        if (this.isProcessing) return;

        // Stop wake word listening while recording
        this.stopWakeWordListening();

        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = () => {
                this.processAudio();
            };

            this.mediaRecorder.start();
            this.isRecording = true;

            // Update navbar button UI
            this.updateNavbarUI('listening');

        } catch (e) {
            console.error('Microphone access denied:', e);
            if (window.showToast) {
                window.showToast('Microphone access denied', 'error');
            }
            // Resume wake word listening
            this.startWakeWordListening();
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;

            // Stop all tracks
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());

            // Update navbar button UI
            this.updateNavbarUI('processing');
            this.isProcessing = true;
        }
    }

    async processAudio() {
        try {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');

            // Send to backend
            const response = await fetch('/api/v1/voice/interact', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Voice interaction failed');

            const data = await response.json();

            // Save to session silently
            if (this.sessionId && window.api) {
                await window.api.addMessageToSession(this.sessionId, 'user', data.transcription);
                await window.api.addMessageToSession(this.sessionId, 'assistant', data.response_text);
            }

            // Show toast notification
            if (window.showToast) {
                window.showToast(`You: "${data.transcription}"`, 'info');
                setTimeout(() => {
                    window.showToast(`Daena: "${data.response_text.substring(0, 100)}..."`, 'success');
                }, 1000);
            }

            // Play audio response
            if (window.speak) {
                window.speak(data.response_text);
            }

            // Handle commands
            if (data.was_command && data.command_result) {
                this.handleCommand(data.command, data.command_result);
            }

        } catch (e) {
            console.error('Voice processing error:', e);
            if (window.showToast) {
                window.showToast('Sorry, I didn\'t catch that.', 'error');
            }
        } finally {
            this.isProcessing = false;
            // Resume wake word listening
            this.updateNavbarUI('wake-listening');
            this.startWakeWordListening();
        }
    }

    handleCommand(command, result) {
        console.log('Executing command:', command, result);

        if (command === 'open_dashboard' || command === 'open_projects') {
            if (result.target) {
                window.location.href = result.target;
            }
        } else if (command === 'create_project') {
            if (window.location.pathname.includes('projects')) {
                window.location.reload();
            } else {
                if (window.showToast) {
                    window.showToast(`Project "${result.name}" created!`, 'success');
                }
            }
        }
    }

    updateNavbarUI(state) {
        const voiceBtn = document.getElementById('voice-navbar-btn');
        const voiceIcon = document.getElementById('voice-navbar-icon');
        const voiceText = document.getElementById('voice-navbar-text');

        if (!voiceBtn) return;

        // Remove all state classes
        voiceBtn.classList.remove('animate-pulse', 'bg-daena-gold/20', 'bg-white/5', 'bg-green-500/10', 'bg-red-500/20');

        switch (state) {
            case 'wake-listening':
                // Green glow for always-listening mode
                voiceBtn.classList.add('bg-green-500/10');
                if (voiceIcon) voiceIcon.className = 'fas fa-microphone text-lg text-green-400';
                if (voiceText) voiceText.textContent = 'Say "Daena"';
                break;

            case 'listening':
                voiceBtn.classList.add('animate-pulse', 'bg-red-500/20');
                if (voiceIcon) voiceIcon.className = 'fas fa-microphone-slash text-lg text-red-500';
                if (voiceText) voiceText.textContent = 'Listening...';
                break;

            case 'processing':
                voiceBtn.classList.add('bg-daena-gold/20');
                if (voiceIcon) voiceIcon.className = 'fas fa-spinner fa-spin text-lg text-daena-gold';
                if (voiceText) voiceText.textContent = 'Processing...';
                break;

            case 'idle':
            default:
                voiceBtn.classList.add('bg-white/5');
                if (voiceIcon) voiceIcon.className = 'fas fa-microphone text-lg text-daena-gold group-hover:scale-110 transition-transform';
                if (voiceText) voiceText.textContent = 'Voice';
                break;
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.voiceWidget = new VoiceWidget();
    console.log('✅ Voice Widget with Wake Word Detection initialized');
    console.log('🎤 Say "Daena" or "Hi Daena" to start talking');
    console.log('⌨️ Press Ctrl+Shift+V for push-to-talk');
});

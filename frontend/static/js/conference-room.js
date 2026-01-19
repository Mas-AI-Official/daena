/**
 * Conference Room UI
 * Manages multi-participant meetings, video conferencing, and shared workspace
 */

const ConferenceRoom = {
    roomId: null,
    participants: [],
    isRecording: false,
    isMuted: false,

    async init(roomId) {
        console.log('Initializing Conference Room:', roomId);
        this.roomId = roomId;
        await this.joinRoom();
        this.setupControls();
        this.setupChat();
        this.setupRealTimeUpdates();
    },

    async joinRoom() {
        try {
            const response = await fetch(`/api/v1/conference-rooms/${this.roomId}/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: 'current_user' })
            });

            const data = await response.json();
            this.participants = data.participants || [];
            this.renderParticipants();

            window.showToast?.(`Joined conference room: ${data.room_name}`, 'success');
        } catch (error) {
            console.error('Failed to join room:', error);
            window.showToast?.('Failed to join conference room', 'error');
        }
    },

    renderParticipants() {
        const container = document.getElementById('participants-grid');
        if (!container) return;

        container.innerHTML = this.participants.map(participant => `
            <div class="participant-tile" data-participant-id="${participant.id}">
                <div class="participant-video">
                    <div class="participant-avatar" style="background: ${participant.color || '#666'};">
                        ${participant.name.charAt(0).toUpperCase()}
                    </div>
                    ${participant.is_speaking ? '<div class="speaking-indicator"></div>' : ''}
                </div>
                <div class="participant-info">
                    <span class="participant-name">${participant.name}</span>
                    ${participant.is_muted ? '<i class="fas fa-microphone-slash"></i>' : ''}
                </div>
            </div>
        `).join('');
    },

    setupControls() {
        // Microphone toggle
        const micBtn = document.getElementById('toggle-mic-btn');
        if (micBtn) {
            micBtn.addEventListener('click', () => this.toggleMicrophone());
        }

        // Recording toggle
        const recBtn = document.getElementById('toggle-recording-btn');
        if (recBtn) {
            recBtn.addEventListener('click', () => this.toggleRecording());
        }

        // Screen share
        const screenBtn = document.getElementById('share-screen-btn');
        if (screenBtn) {
            screenBtn.addEventListener('click', () => this.shareScreen());
        }

        // Leave button
        const leaveBtn = document.getElementById('leave-room-btn');
        if (leaveBtn) {
            leaveBtn.addEventListener('click', () => this.leaveRoom());
        }
    },

    setupChat() {
        const chatInput = document.getElementById('conference-chat-input');
        const sendBtn = document.getElementById('send-chat-btn');

        if (chatInput && sendBtn) {
            sendBtn.addEventListener('click', () => {
                const message = chatInput.value.trim();
                if (message) {
                    this.sendChatMessage(message);
                    chatInput.value = '';
                }
            });

            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendBtn.click();
                }
            });
        }
    },

    setupRealTimeUpdates() {
        if (window.WebSocketClient) {
            window.WebSocketClient.on('conference_update', (data) => {
                this.handleRealTimeUpdate(data);
            });
        }
    },

    handleRealTimeUpdate(data) {
        if (data.room_id !== this.roomId) return;

        switch (data.type) {
            case 'participant_joined':
                this.participants.push(data.participant);
                this.renderParticipants();
                window.showToast?.(`${data.participant.name} joined`, 'info');
                break;

            case 'participant_left':
                this.participants = this.participants.filter(p => p.id !== data.participant_id);
                this.renderParticipants();
                break;

            case 'chat_message':
                this.addChatMessage(data.message);
                break;

            case 'speaking_update':
                this.updateSpeakingIndicator(data.participant_id, data.is_speaking);
                break;
        }
    },

    async toggleMicrophone() {
        this.isMuted = !this.isMuted;
        const micBtn = document.getElementById('toggle-mic-btn');

        if (micBtn) {
            micBtn.innerHTML = this.isMuted
                ? '<i class="fas fa-microphone-slash"></i> Unmute'
                : '<i class="fas fa-microphone"></i> Mute';
            micBtn.classList.toggle('muted', this.isMuted);
        }

        // Send mute status to server
        try {
            await fetch(`/api/v1/conference-rooms/${this.roomId}/mute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_muted: this.isMuted })
            });
        } catch (error) {
            console.error('Failed to update mute status:', error);
        }
    },

    async toggleRecording() {
        this.isRecording = !this.isRecording;
        const recBtn = document.getElementById('toggle-recording-btn');

        if (recBtn) {
            recBtn.innerHTML = this.isRecording
                ? '<i class="fas fa-stop"></i> Stop Recording'
                : '<i class="fas fa-circle"></i> Record';
            recBtn.classList.toggle('recording', this.isRecording);
        }

        try {
            const endpoint = this.isRecording ? 'start-recording' : 'stop-recording';
            const response = await fetch(`/api/v1/conference-rooms/${this.roomId}/${endpoint}`, {
                method: 'POST'
            });

            const data = await response.json();
            const message = this.isRecording
                ? 'Recording started'
                : `Recording saved: ${data.filename}`;
            window.showToast?.(message, 'success');
        } catch (error) {
            console.error('Failed to toggle recording:', error);
            window.showToast?.('Recording control failed', 'error');
        }
    },

    async shareScreen() {
        window.showToast?.('Screen sharing - Coming soon', 'info');
        console.log('Screen sharing feature not yet implemented');
    },

    async sendChatMessage(message) {
        try {
            const response = await fetch(`/api/v1/conference-rooms/${this.roomId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            if (response.ok) {
                // Message will appear via WebSocket update
                return true;
            }
        } catch (error) {
            console.error('Failed to send message:', error);
            window.showToast?.('Failed to send message', 'error');
        }
    },

    addChatMessage(messageData) {
        const chatMessages = document.getElementById('conference-chat-messages');
        if (!chatMessages) return;

        const messageEl = document.createElement('div');
        messageEl.className = 'chat-message';
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="message-author">${messageData.author}</span>
                <span class="message-time">${this.formatTime(messageData.timestamp)}</span>
            </div>
            <div class="message-content">${this.escapeHtml(messageData.content)}</div>
        `;

        chatMessages.appendChild(messageEl);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    async leaveRoom() {
        if (confirm('Leave this conference room?')) {
            try {
                await fetch(`/api/v1/conference-rooms/${this.roomId}/leave`, {
                    method: 'POST'
                });
                window.location.href = '/ui/dashboard';
            } catch (error) {
                console.error('Failed to leave room:', error);
                window.location.href = '/ui/dashboard';
            }
        }
    },

    updateSpeakingIndicator(participantId, isSpeaking) {
        const tile = document.querySelector(`[data-participant-id="${participantId}"]`);
        if (tile) {
            const indicator = tile.querySelector('.speaking-indicator');
            if (isSpeaking && !indicator) {
                const video = tile.querySelector('.participant-video');
                video.insertAdjacentHTML('beforeend', '<div class="speaking-indicator"></div>');
            } else if (!isSpeaking && indicator) {
                indicator.remove();
            }
        }
    },

    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Auto-initialize
if (typeof window !== 'undefined') {
    window.ConferenceRoom = ConferenceRoom;

    document.addEventListener('DOMContentLoaded', () => {
        const roomContainer = document.getElementById('conference-room-container');
        if (roomContainer) {
            const roomId = roomContainer.dataset.roomId;
            if (roomId) {
                ConferenceRoom.init(roomId);
            }
        }
    });
}

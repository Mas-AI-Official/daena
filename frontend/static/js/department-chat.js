/**
 * Department Chat - API-Integrated Version
 * Provides chat persistence via backend API with WebSocket real-time sync
 */

class DepartmentChat {
    constructor(deptId, deptName, deptColor, repInitials) {
        this.deptId = deptId;
        this.deptName = deptName;
        this.deptColor = deptColor;
        this.repInitials = repInitials;
        this.currentTarget = 'rep';
        this.currentSessionId = null;
        this.chatHistory = [];
        this.ws = null;
    }

    async init() {
        await this.loadChatHistory();
        this.setupWebSocket();
        this.setupInputHandler();
    }

    async loadChatHistory() {
        const container = document.getElementById('messages');
        if (!container) return;

        container.innerHTML = '<div style="color: #9CA3AF; text-align: center; padding: 20px;">Loading chat history...</div>';

        try {
            // Use unified department chat sessions endpoint (single source of truth)
            const response = await fetch(`/api/v1/departments/${this.deptId}/chat/sessions`);
            const data = await response.json();

            if (data.success && data.sessions && data.sessions.length > 0) {
                // Load the most recent session
                const latestSession = data.sessions[0];
                this.currentSessionId = latestSession.session_id;
                
                // Load messages for this session
                const messagesResponse = await fetch(`/api/v1/departments/${this.deptId}/chat/sessions/${this.currentSessionId}`);
                const messagesData = await messagesResponse.json();
                
                this.chatHistory = messagesData.messages || [];

                container.innerHTML = '';
                this.chatHistory.forEach(msg => {
                    const type = msg.role === 'user' ? 'user' : 'rep';
                    this.addMessageToDOM(type, msg.content, false);
                });

                console.log(`Loaded ${this.chatHistory.length} messages from session ${this.currentSessionId}`);
            } else {
                await this.createNewSession();
                container.innerHTML = '';
            }
        } catch (e) {
            console.error('Failed to load chat history from API:', e);
            container.innerHTML = '<div style="color: #9CA3AF; text-align: center; padding: 20px;">No chat history found. Start a new conversation!</div>';
        }
    }

    async createNewSession() {
        try {
            const title = `${this.deptId.charAt(0).toUpperCase() + this.deptId.slice(1)} Chat`;
            // Use unified chat service endpoint with scope
            const response = await fetch(`/api/v1/chat-history/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    title,
                    category: "department",
                    scope_type: "department",
                    scope_id: this.deptId
                })
            });
            const data = await response.json();
            this.currentSessionId = data.session_id;
            console.log('Created new session:', this.currentSessionId);
            return this.currentSessionId;
        } catch (e) {
            console.error('Failed to create session:', e);
            return null;
        }
    }

    setupWebSocket() {
        // Use global WebSocket client if available
        if (window.WebSocketClient) {
            // Connect to chat-specific WebSocket if we have a session
            if (this.currentSessionId) {
                window.WebSocketClient.connect(`/ws/chat/${this.currentSessionId}`, `chat_${this.currentSessionId}`);
            }
            
            // Also listen to general events
            window.WebSocketClient.on('chatMessage', (payload) => {
                if (payload.session_id === this.currentSessionId && payload.sender !== 'user') {
                    this.addMessageToDOM('rep', payload.content, true);
                }
            });
            
            window.WebSocketClient.on('sessionCreated', (payload) => {
                if (payload.session_id) {
                    this.currentSessionId = payload.session_id;
                    window.WebSocketClient.connect(`/ws/chat/${payload.session_id}`, `chat_${payload.session_id}`);
                }
            });
        } else {
            // Fallback to direct WebSocket connection
            try {
                this.ws = new WebSocket(`ws://${window.location.host}/ws/events`);

                this.ws.onopen = () => console.log('WebSocket connected for department chat');

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.event_type === 'chat.message' && data.payload?.session_id === this.currentSessionId) {
                            if (data.payload.sender !== 'user') {
                                this.addMessageToDOM('rep', data.payload.content, true);
                            }
                        }
                    } catch (e) {
                        console.log('WebSocket message parse error:', e);
                    }
                };

                this.ws.onerror = (e) => console.log('WebSocket error (non-critical):', e);
                this.ws.onclose = () => console.log('WebSocket closed');
            } catch (e) {
                console.log('WebSocket not available');
            }
        }
    }

    setupInputHandler() {
        const input = document.getElementById('messageInput');
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });
        }
    }

    selectRep(target) {
        this.currentTarget = target;
        document.querySelectorAll('.rep-card').forEach(c => c.classList.remove('active'));
        const card = document.querySelector(`[data-target="${target}"]`);
        if (card) card.classList.add('active');
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        if (!input) return;

        const message = input.value.trim();
        if (!message) return;

        // Add user message immediately
        this.addMessage('user', message);
        input.value = '';

        try {
            // Ensure we have a session
            if (!this.currentSessionId) {
                await this.createNewSession();
            }

            // Save user message to backend
            await this.saveMessageToBackend('user', message);

            // Get AI response
            const endpoint = this.currentTarget === 'daena'
                ? '/api/v1/daena/chat'
                : `/api/v1/departments/${this.deptId}/chat`;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message, 
                    context: {
                        session_id: this.currentSessionId,
                        scope_type: 'department',
                        scope_id: this.deptId
                    }
                })
            });

            const data = await response.json();
            const aiResponse = data.response || data.message || 'I heard you!';
            const senderType = this.currentTarget === 'daena' ? 'daena' : 'rep';

            this.addMessage(senderType, aiResponse);

            // Save AI response to backend
            await this.saveMessageToBackend('assistant', aiResponse);

        } catch (e) {
            console.error('Send message error:', e);
            this.addMessage('rep', 'Sorry, I had trouble processing that. Please try again.');
        }
    }

    async saveMessageToBackend(sender, content) {
        if (!this.currentSessionId) return;

        try {
            await fetch(`/api/v1/chat-history/sessions/${this.currentSessionId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sender, content })
            });
        } catch (e) {
            console.error('Failed to save message to backend:', e);
        }
    }

    addMessage(type, content) {
        this.addMessageToDOM(type, content, true);

        // Also save to localStorage as backup
        this.chatHistory.push({ type, content, time: Date.now(), sender: type });
        localStorage.setItem(`chat_${this.deptId}`, JSON.stringify(this.chatHistory.slice(-50)));
    }

    addMessageToDOM(type, content, scroll) {
        const container = document.getElementById('messages');
        if (!container) return;

        const isUser = type === 'user';
        const isDaena = type === 'daena';

        const avatarBg = isUser
            ? 'rgba(212, 175, 55, 0.3)'
            : isDaena
                ? 'linear-gradient(135deg, #FFD700, #FFA500)'
                : this.deptColor;

        const avatarContent = isUser
            ? '<i class="fas fa-user"></i>'
            : isDaena
                ? '<i class="fas fa-brain"></i>'
                : this.repInitials;

        const html = `
        <div class="message ${isUser ? 'user' : 'assistant'} ${type}">
            <div class="message-avatar" style="background: ${avatarBg}">
                ${avatarContent}
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        </div>
        `;

        container.insertAdjacentHTML('beforeend', html);
        if (scroll) container.scrollTop = container.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance (will be initialized by page)
let deptChat = null;

function initDepartmentChat(deptId, deptName, deptColor, repInitials) {
    deptChat = new DepartmentChat(deptId, deptName, deptColor, repInitials);
    deptChat.init();
}

function sendMessage() {
    if (deptChat) deptChat.sendMessage();
}

function selectRep(target) {
    if (deptChat) deptChat.selectRep(target);
}

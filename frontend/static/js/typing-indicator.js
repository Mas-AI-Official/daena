/**
 * Typing Indicator System
 * Shows when users/agents are typing via WebSocket
 */

class TypingIndicator {
    constructor() {
        this.typingUsers = new Map(); // sessionId -> Set of user IDs
        this.typingTimeouts = new Map(); // sessionId -> timeout ID
        this.typingDuration = 3000; // Show typing for 3 seconds
        this.setupWebSocket();
    }

    setupWebSocket() {
        if (window.WebSocketClient) {
            window.WebSocketClient.on('typing', (data) => {
                this.handleTypingEvent(data);
            });
        }
    }

    handleTypingEvent(data) {
        const { session_id, user_id, is_typing } = data;
        
        if (is_typing) {
            this.startTyping(session_id, user_id);
        } else {
            this.stopTyping(session_id, user_id);
        }
    }

    startTyping(sessionId, userId) {
        if (!this.typingUsers.has(sessionId)) {
            this.typingUsers.set(sessionId, new Set());
        }
        this.typingUsers.get(sessionId).add(userId);
        this.updateIndicator(sessionId);
        
        // Clear existing timeout
        if (this.typingTimeouts.has(sessionId)) {
            clearTimeout(this.typingTimeouts.get(sessionId));
        }
        
        // Auto-stop after duration
        const timeout = setTimeout(() => {
            this.stopTyping(sessionId, userId);
        }, this.typingDuration);
        this.typingTimeouts.set(sessionId, timeout);
    }

    stopTyping(sessionId, userId) {
        if (this.typingUsers.has(sessionId)) {
            this.typingUsers.get(sessionId).delete(userId);
            if (this.typingUsers.get(sessionId).size === 0) {
                this.typingUsers.delete(sessionId);
            }
        }
        this.updateIndicator(sessionId);
    }

    updateIndicator(sessionId) {
        const indicator = document.getElementById(`typing-indicator-${sessionId}`);
        if (!indicator) return;

        const users = this.typingUsers.get(sessionId);
        if (users && users.size > 0) {
            const userList = Array.from(users).join(', ');
            indicator.innerHTML = `
                <div class="typing-indicator" style="
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 12px;
                    color: rgba(255, 255, 255, 0.7);
                    font-size: 14px;
                    font-style: italic;
                ">
                    <span class="typing-dots">
                        <span style="animation: typing 1.4s infinite;">.</span>
                        <span style="animation: typing 1.4s infinite 0.2s;">.</span>
                        <span style="animation: typing 1.4s infinite 0.4s;">.</span>
                    </span>
                    <span>${userList} ${users.size === 1 ? 'is' : 'are'} typing...</span>
                </div>
            `;
            indicator.style.display = 'block';
        } else {
            indicator.style.display = 'none';
        }
    }

    sendTypingStatus(sessionId, userId, isTyping) {
        if (window.WebSocketClient) {
            window.WebSocketClient.send('events', {
                type: 'typing',
                session_id: sessionId,
                user_id: userId,
                is_typing: isTyping
            });
        }
    }
}

// Add typing animation CSS
const typingStyle = document.createElement('style');
typingStyle.textContent = `
    @keyframes typing {
        0%, 60%, 100% { opacity: 0.3; }
        30% { opacity: 1; }
    }
`;
document.head.appendChild(typingStyle);

// Global typing indicator instance
window.TypingIndicator = new TypingIndicator();

console.log('✅ Typing Indicator System initialized');




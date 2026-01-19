/**
 * Daena Real-Time WebSocket Client
 * Connects to /ws/events for live updates
 */

class DaenaWebSocket {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.handlers = {};
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/events`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('🔌 WebSocket connected');
                this.reconnectAttempts = 0;
                this.updateIndicator(true);
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleEvent(data);
                } catch (e) {
                    console.log('WS message:', event.data);
                }
            };

            this.ws.onclose = () => {
                console.log('🔌 WebSocket disconnected');
                this.updateIndicator(false);

                // Auto-reconnect with exponential backoff
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
                    this.reconnectAttempts++;
                    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
                    setTimeout(() => this.connect(), delay);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            // Heartbeat ping every 30s
            setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 30000);

        } catch (e) {
            console.error('Failed to connect WebSocket:', e);
        }
    }

    handleEvent(event) {
        const { event_type, entity_type, entity_id, payload } = event;
        console.log('📡 WS Event:', event_type, payload);

        // Call registered handlers
        if (this.handlers[event_type]) {
            this.handlers[event_type].forEach(handler => handler(event));
        }

        // Built-in event handling
        switch (event_type) {
            case 'agent.created':
            case 'agent.updated':
            case 'agent.deleted':
                if (typeof window.reloadAgents === 'function') {
                    window.reloadAgents();
                }
                if (window.showToast) {
                    window.showToast(`Agent ${event_type.split('.')[1]}: ${payload?.name || entity_id}`, 'info');
                }
                break;

            case 'task.created':
            case 'task.progress':
            case 'task.completed':
                if (typeof window.updateTask === 'function') {
                    window.updateTask(entity_id, payload);
                }
                break;

            case 'brain.status':
                if (typeof window.updateBrainStatus === 'function') {
                    window.updateBrainStatus();
                }
                break;

            case 'chat.message':
                if (typeof window.handleNewMessage === 'function') {
                    window.handleNewMessage(payload);
                }
                break;

            case 'system.reset':
                if (window.showToast) {
                    window.showToast('System reset - refreshing...', 'info');
                }
                setTimeout(() => window.location.reload(), 1500);
                break;

            case 'connected':
                console.log('WebSocket connection confirmed');
                break;
        }
    }

    on(eventType, handler) {
        if (!this.handlers[eventType]) {
            this.handlers[eventType] = [];
        }
        this.handlers[eventType].push(handler);
    }

    off(eventType, handler) {
        if (this.handlers[eventType]) {
            this.handlers[eventType] = this.handlers[eventType].filter(h => h !== handler);
        }
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
        }
    }

    updateIndicator(connected) {
        const indicator = document.getElementById('ws-status');
        if (indicator) {
            if (connected) {
                indicator.className = 'w-2 h-2 rounded-full bg-green-500';
                indicator.title = 'Real-time updates connected';
            } else {
                indicator.className = 'w-2 h-2 rounded-full bg-orange-500';
                indicator.title = 'Real-time updates reconnecting...';
            }
        }
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Create global instance
window.daenaWS = new DaenaWebSocket();

// Auto-connect when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.daenaWS.connect();
});

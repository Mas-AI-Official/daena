/**
 * Enhanced WebSocket Client with Real-Time Sync
 * Adds system_changes, agent_updates, and department_updates channels
 * Target latency: <100ms for all updates
 */

class EnhancedWebSocketClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.handlers = new Map();
        this.connectionStatus = 'disconnected';
        this.latencyMs = 0;
        this.lastPingTime = null;
    }

    connect(url = null) {
        const wsUrl = url || this.getWebSocketURL();

        console.log('🔌 Connecting to WebSocket:', wsUrl);

        try {
            this.ws = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.handleReconnect();
        }
    }

    getWebSocketURL() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/ws`;
    }

    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('✅ WebSocket connected');
            this.connectionStatus = 'connected';
            this.reconnectAttempts = 0;
            this.updateConnectionIndicator('connected');
            this.startHeartbeat();
            this.emit('connection_status', { status: 'connected' });
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
            this.connectionStatus = 'error';
            this.updateConnectionIndicator('error');
        };

        this.ws.onclose = () => {
            console.log('🔌 WebSocket disconnected');
            this.connectionStatus = 'disconnected';
            this.updateConnectionIndicator('disconnected');
            this.stopHeartbeat();
            this.handleReconnect();
        };
    }

    handleMessage(data) {
        // Calculate latency if this is a pong
        if (data.type === 'pong' && this.lastPingTime) {
            this.latencyMs = Date.now() - this.lastPingTime;
            this.emit('latency_update', { latency: this.latencyMs });
        }

        // Route message to appropriate handlers
        const messageType = data.type || data.event;

        if (messageType) {
            this.emit(messageType, data);
        }

        // Handle specific channel updates
        if (data.channel) {
            this.emit(`channel:${data.channel}`, data);
        }
    }

    // Event emitter pattern
    on(event, handler) {
        if (!this.handlers.has(event)) {
            this.handlers.set(event, []);
        }
        this.handlers.get(event).push(handler);
    }

    off(event, handler) {
        if (this.handlers.has(event)) {
            const handlers = this.handlers.get(event);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    emit(event, data) {
        if (this.handlers.has(event)) {
            this.handlers.get(event).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in ${event} handler:`, error);
                }
            });
        }
    }

    // Send message to server
    send(type, data = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ type, ...data });
            this.ws.send(message);
            return true;
        } else {
            console.warn('WebSocket not connected, cannot send message');
            return false;
        }
    }

    // Subscribe to specific channels
    subscribe(channel) {
        return this.send('subscribe', { channel });
    }

    unsubscribe(channel) {
        return this.send('unsubscribe', { channel });
    }

    // Heartbeat to measure latency
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            this.lastPingTime = Date.now();
            this.send('ping');
        }, 10000); // Every 10 seconds
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    // Reconnection logic
    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.min(this.reconnectAttempts, 5);

            console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('❌ Max reconnection attempts reached');
            this.emit('connection_failed', { attempts: this.reconnectAttempts });
        }
    }

    // Update connection status indicator in UI
    updateConnectionIndicator(status) {
        const indicator = document.getElementById('ws-connection-indicator');
        if (indicator) {
            indicator.className = `connection-indicator ${status}`;
            indicator.title = `WebSocket: ${status} (${this.latencyMs}ms)`;
        }

        // Update status text
        const statusText = document.getElementById('ws-status-text');
        if (statusText) {
            const statusLabels = {
                connected: 'Connected',
                disconnected: 'Disconnected',
                error: 'Error'
            };
            statusText.textContent = statusLabels[status] || status;
        }
    }

    // Get current connection status
    getStatus() {
        return {
            status: this.connectionStatus,
            latency: this.latencyMs,
            reconnectAttempts: this.reconnectAttempts
        };
    }

    // Close connection
    disconnect() {
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Global instance
const WebSocketClient = new EnhancedWebSocketClient();

// Auto-connect when DOM is ready
if (typeof window !== 'undefined') {
    window.WebSocketClient = WebSocketClient;

    document.addEventListener('DOMContentLoaded', () => {
        // Connect to WebSocket
        WebSocketClient.connect();

        // Subscribe to key channels
        setTimeout(() => {
            WebSocketClient.subscribe('system_changes');
            WebSocketClient.subscribe('agent_updates');
            WebSocketClient.subscribe('department_updates');
            WebSocketClient.subscribe('memory_updates');
        }, 1000);

        // Set up global handlers
        WebSocketClient.on('system_changes', (data) => {
            console.log('📝 System change:', data);
            window.dispatchEvent(new CustomEvent('system-change', { detail: data }));
        });

        WebSocketClient.on('agent_updates', (data) => {
            console.log('🤖 Agent update:', data);
            window.dispatchEvent(new CustomEvent('agent-update', { detail: data }));
        });

        WebSocketClient.on('department_updates', (data) => {
            console.log('🏢 Department update:', data);
            window.dispatchEvent(new CustomEvent('department-update', { detail: data }));
        });
    });
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnhancedWebSocketClient;
}

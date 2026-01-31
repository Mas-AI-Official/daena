/**
 * WebSocket Client for Real-Time Updates
 * Connects to backend WebSocket endpoints and handles real-time events
 */

class WebSocketClient {
    constructor() {
        this.connections = new Map();
        this.eventHandlers = new Map();
        this.reconnectAttempts = new Map();
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.connectionPool = new Map(); // Connection pooling
        this.messageQueue = []; // Message batching queue
        this.batchInterval = 100; // Batch messages every 100ms
        this.metrics = {
            totalConnections: 0,
            activeConnections: 0,
            messagesSent: 0,
            messagesReceived: 0,
            errors: 0,
            reconnects: 0
        };
        this.startBatching();
    }

    /**
     * Connect to a WebSocket endpoint
     */
    connect(endpoint, connectionId = null) {
        const id = connectionId || endpoint;

        // Don't reconnect if already connected
        if (this.connections.has(id)) {
            const ws = this.connections.get(id);
            if (ws.readyState === WebSocket.OPEN) {
                console.log(`WebSocket ${id} already connected`);
                return ws;
            }
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${endpoint}`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);

        const ws = new WebSocket(wsUrl);
        this.connections.set(id, ws);
        this.reconnectAttempts.set(id, 0);

        ws.onopen = () => {
            console.log(`✅ WebSocket connected: ${id}`);
            this.reconnectAttempts.set(id, 0);
            this.metrics.activeConnections++;
            this.metrics.totalConnections++;
            this.updateConnectionStatus(id, 'connected');
            this.emit('connected', { endpoint, id });
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.metrics.messagesReceived++;
                this.handleMessage(id, data);
            } catch (e) {
                console.error(`Error parsing WebSocket message from ${id}:`, e);
                this.metrics.errors++;
            }
        };

        ws.onerror = (error) => {
            console.error(`WebSocket error on ${id}:`, error);
            this.metrics.errors++;
            this.updateConnectionStatus(id, 'error');
            this.emit('error', { endpoint, id, error });
        };

        ws.onclose = () => {
            console.log(`WebSocket closed: ${id}`);
            this.connections.delete(id);
            this.metrics.activeConnections = Math.max(0, this.metrics.activeConnections - 1);
            this.updateConnectionStatus(id, 'disconnected');
            this.emit('disconnected', { endpoint, id });

            // Attempt to reconnect
            const attempts = this.reconnectAttempts.get(id) || 0;
            if (attempts < this.maxReconnectAttempts) {
                this.reconnectAttempts.set(id, attempts + 1);
                this.metrics.reconnects++;
                const delay = this.reconnectDelay * Math.pow(2, attempts);
                console.log(`Reconnecting to ${id} in ${delay}ms (attempt ${attempts + 1})`);
                this.updateConnectionStatus(id, 'reconnecting', { attempts: attempts + 1, delay });
                setTimeout(() => this.connect(endpoint, id), delay);
            } else {
                this.updateConnectionStatus(id, 'failed');
            }
        };

        return ws;
    }

    /**
     * Handle incoming WebSocket message
     */
    handleMessage(connectionId, data) {
        const eventType = data.event_type;

        // Emit event to registered handlers
        this.emit(eventType, data);

        // Handle specific event types
        switch (eventType) {
            case 'chat.message':
                this.emit('chatMessage', data.payload);
                break;
            case 'session.created':
                this.emit('sessionCreated', data.payload);
                break;
            case 'session.updated':
                this.emit('sessionUpdated', data.payload);
                break;
            case 'agent.activity':
                this.emit('agentActivity', data.payload);
                break;
            case 'brain.status':
                this.emit('brainStatus', data.payload);
                break;
            case 'task.update':
                this.emit('taskUpdate', data.payload);
                break;
            case 'pong':
                // Keepalive response
                break;
            default:
                console.log(`Unhandled event type: ${eventType}`, data);
        }
    }

    /**
     * Register event handler
     */
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }

    /**
     * Remove event handler
     */
    off(eventType, handler) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Emit event to registered handlers
     */
    emit(eventType, data) {
        if (this.eventHandlers.has(eventType)) {
            this.eventHandlers.get(eventType).forEach(handler => {
                try {
                    handler(data);
                } catch (e) {
                    console.error(`Error in event handler for ${eventType}:`, e);
                }
            });
        }
    }

    /**
     * Disconnect from a WebSocket endpoint
     */
    disconnect(connectionId) {
        if (this.connections.has(connectionId)) {
            const ws = this.connections.get(connectionId);
            ws.close();
            this.connections.delete(connectionId);
            this.reconnectAttempts.delete(connectionId);
        }
    }

    /**
     * Disconnect all WebSocket connections
     */
    disconnectAll() {
        this.connections.forEach((ws, id) => {
            ws.close();
        });
        this.connections.clear();
        this.reconnectAttempts.clear();
    }

    /**
     * Send message to WebSocket (with batching support)
     */
    send(connectionId, message, immediate = false) {
        if (immediate) {
            this.sendImmediate(connectionId, message);
        } else {
            // Add to batch queue
            this.messageQueue.push({ connectionId, message, timestamp: Date.now() });
        }
    }

    /**
     * Send message immediately (bypass batching)
     */
    sendImmediate(connectionId, message) {
        if (this.connections.has(connectionId)) {
            const ws = this.connections.get(connectionId);
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(message));
                this.metrics.messagesSent++;
            } else {
                console.warn(`WebSocket ${connectionId} is not open`);
            }
        } else {
            console.warn(`WebSocket ${connectionId} not found`);
        }
    }

    /**
     * Start message batching
     */
    startBatching() {
        setInterval(() => {
            if (this.messageQueue.length > 0) {
                const now = Date.now();
                const batch = this.messageQueue.filter(m => now - m.timestamp < this.batchInterval);
                this.messageQueue = this.messageQueue.filter(m => now - m.timestamp >= this.batchInterval);

                // Group by connection
                const byConnection = {};
                batch.forEach(({ connectionId, message }) => {
                    if (!byConnection[connectionId]) {
                        byConnection[connectionId] = [];
                    }
                    byConnection[connectionId].push(message);
                });

                // Send batches
                Object.entries(byConnection).forEach(([connectionId, messages]) => {
                    if (messages.length === 1) {
                        this.sendImmediate(connectionId, messages[0]);
                    } else {
                        this.sendImmediate(connectionId, {
                            type: 'batch',
                            messages: messages,
                            count: messages.length
                        });
                    }
                });
            }
        }, this.batchInterval);
    }

    /**
     * Update connection status UI
     */
    updateConnectionStatus(connectionId, status, data = {}) {
        // Emit status update event
        this.emit('connectionStatus', {
            connectionId,
            status,
            ...data
        });

        // Update status indicator if it exists
        const statusElement = document.getElementById(`ws-status-${connectionId}`);
        if (statusElement) {
            statusElement.className = `ws-status ws-status-${status}`;
            statusElement.textContent = this.getStatusText(status, data);
        }
    }

    /**
     * Get status text for display
     */
    getStatusText(status, data = {}) {
        const statusMap = {
            'connected': '🟢 Connected',
            'connecting': '🟡 Connecting...',
            'disconnected': '⚪ Disconnected',
            'reconnecting': `🟡 Reconnecting... (${data.attempts || 0}/${this.maxReconnectAttempts})`,
            'error': '🔴 Error',
            'failed': '🔴 Connection Failed'
        };
        return statusMap[status] || status;
    }

    /**
     * Get connection metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            activeConnections: this.connections.size,
            connectionIds: Array.from(this.connections.keys())
        };
    }

    /**
     * Send ping to keep connection alive
     */
    ping(connectionId) {
        this.send(connectionId, {
            type: 'ping',
            timestamp: new Date().toISOString()
        });
    }
}

// Global WebSocket client instance
window.WebSocketClient = new WebSocketClient();
window.wsClient = window.WebSocketClient; // Alias for legacy code (dashboard.js, sync-manager.js)

// Auto-connect to general events on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.WebSocketClient.connect('/ws/events', 'events');
    });
} else {
    window.WebSocketClient.connect('/ws/events', 'events');
}

console.log('✅ WebSocket Client initialized');

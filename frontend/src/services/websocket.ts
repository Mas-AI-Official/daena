import { useEventsStore } from '../store/eventsStore';
import { useAgentStore } from '../store/agentStore';
import { useUIStore } from '../store/uiStore';
import { v4 as uuidv4 } from 'uuid';

class WebSocketService {
    private socket: WebSocket | null = null;
    private url: string;
    private reconnectTimeout: number | null = null;
    private maxReconnectAttempts = 5;
    private reconnectAttempts = 0;

    constructor() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Connect to the event bus endpoint
        this.url = `${protocol}//${window.location.host}/ws/events`;
    }

    connect() {
        if (this.socket || this.reconnectAttempts >= this.maxReconnectAttempts) return;

        console.log(`[WS] Connecting to ${this.url}`);
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            console.log('[WS] Connected');
            this.reconnectAttempts = 0;
            useEventsStore.getState().setConnected(true);
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (err) {
                console.error('[WS] Failed to parse message:', err);
            }
        };

        this.socket.onclose = () => {
            console.log('[WS] Disconnected');
            useEventsStore.getState().setConnected(false);
            this.socket = null;
            this.scheduleReconnect();
        };

        this.socket.onerror = (err) => {
            console.error('[WS] Error:', err);
            this.socket?.close();
        };
    }

    private scheduleReconnect() {
        if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

        console.log(`[WS] Reconnecting in ${delay}ms (Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.reconnectTimeout = window.setTimeout(() => this.connect(), delay);
    }

    private handleEvent(event: any) {
        // Add to global events store
        useEventsStore.getState().addEvent({
            id: uuidv4(),
            type: event.event_type || 'unknown',
            payload: event.payload || event,
            timestamp: new Date().toISOString()
        });

        // Specific handlers
        switch (event.event_type) {
            case 'agent.status_updated':
            case 'agent.updated':
                useAgentStore.getState().updateAgentStatus(event.payload.id || event.payload.agent_id, event.payload.status);
                break;
            case 'agent.created':
                useAgentStore.getState().fetchAgents(); // Refresh list on new agent
                break;
            case 'chat.message':
                // Handled by local ChatInterface listeners usually, 
                // but can trigger global notifications here
                if (event.payload.role !== 'user') {
                    // useUIStore.getState().addNotification(...)
                }
                break;
            case 'system.alert':
            case 'shadow.alert':
                useUIStore.getState().addNotification({
                    title: event.event_type === 'shadow.alert' ? 'SECURITY BREACH' : 'System Alert',
                    message: event.payload.message || event.payload,
                    type: event.payload.level || 'critical'
                });
                break;
        }
    }

    disconnect() {
        if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
        this.socket?.close();
        this.socket = null;
    }
}

export const wsService = new WebSocketService();

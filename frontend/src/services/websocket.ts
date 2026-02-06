
// Replaced socket.io-client with native WebSocket to match FastAPI backend
import { useEventsStore } from '../store/eventsStore';
import { useChatStore } from '../store/chatStore';
import { useAgentStore } from '../store/agentStore';

const WS_URL = 'ws://localhost:8000/ws'; // Native WebSocket URL

const audio = {
    play: (sound: string) => console.log(`Playing sound: ${sound}`)
};

class WebSocketService {
    private socket: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 10;
    private reconnectDelay = 1000;
    private listeners: Map<string, Function[]> = new Map();
    private reconnectTimer: any = null;

    connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const token = localStorage.getItem('daena_token');
        // Native WS doesn't support auth headers easily, often use query param or first message
        // For simplicity/security, we might pass it but backend needs to handle it.
        // Or keep it simple for now. 

        console.log(`Connecting to WebSocket: ${WS_URL}`);
        this.socket = new WebSocket(WS_URL);

        this.socket.onopen = () => {
            console.log('✅ WebSocket connected');
            this.reconnectAttempts = 0;
            useEventsStore.getState().setConnected(true);

            // Send auth if needed
            if (token) {
                this.send('auth', { token });
            }
        };

        this.socket.onclose = (event) => {
            console.log('❌ WebSocket disconnected:', event.reason);
            useEventsStore.getState().setConnected(false);
            this.handleReconnect();
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            // On error, onclose usually follows
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Failed to parse WS message:', event.data);
            }
        };
    }

    private handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            console.log(`Attempting reconnect in ${delay}ms...`);
            this.reconnectTimer = setTimeout(() => this.connect(), delay);
        } else {
            console.error('Max reconnect attempts reached');
        }
    }

    // Mimic socket.io message handling
    private handleMessage(payload: any) {
        // Expected format: { type: "event_name", data: ... }
        if (payload.type) {
            this.emit(payload.type, payload.data);

            // Generic Event Logging
            useEventsStore.getState().addEvent({
                id: Math.random().toString(36).substr(2, 9),
                type: payload.type,
                payload: payload.data,
                timestamp: new Date().toISOString()
            });

            // Specific Store Updates

            // 1. Agent/Task Progress
            if (payload.type === 'task.progress' || payload.type === 'agent.status.changed') {
                // @ts-ignore
                if (useAgentStore.getState().updateAgentStatus) {
                    const agentId = payload.data.agent_id || payload.data.agent_name || 'unknown';
                    const status = payload.data.status || 'running';
                    // @ts-ignore
                    useAgentStore.getState().updateAgentStatus(agentId, status);
                }
            }

            // 2. Chat Messages
            else if (payload.type === 'chat.message' || payload.type === 'chat.message.received') {
                const msgData = payload.data;
                useChatStore.getState().addMessage({
                    id: Math.random().toString(36).substr(2, 9), // Generate ID if missing
                    sender: (msgData.role === 'user') ? 'user' : 'agent', // Normalize sender
                    content: msgData.message || msgData.content,
                    timestamp: new Date().toISOString(),
                    metadata: msgData
                });
            }

            // 3. Approvals
            else if (payload.type === 'approval.required') {
                audio.play('approval');
                // Could trigger a modal store here
            }

            // 4. Security Alerts (Shadow/Integrity)
            else if (payload.type === 'security.alert' || payload.type === 'shadow.alert') {
                console.warn("SECURITY ALERT:", payload.data);
                // Could update a security store
            }
        }

    }

    on(event: string, callback: Function) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event)!.push(callback);
    }

    // Internal emit to listeners
    private emit(event: string, data: any) {
        const callbacks = this.listeners.get(event) || [];
        callbacks.forEach(cb => cb(data));
    }

    // Send message to server
    send(type: string, data: any) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type, data }));
        }
    }

    disconnect() {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
        this.socket?.close();
        this.socket = null;
    }
}

export const wsService = new WebSocketService();

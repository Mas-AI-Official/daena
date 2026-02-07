/**
 * WebSocket Client - Real-time communication with backend
 */
import { toast } from 'sonner';

// Event callbacks for state management
type EventCallback = (data: any) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageQueue: any[] = [];
  private isConnecting = false;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private eventCallbacks: Map<string, EventCallback[]> = new Map();

  constructor(private url: string) {}

  // Subscribe to events
  on(event: string, callback: EventCallback): void {
    if (!this.eventCallbacks.has(event)) {
      this.eventCallbacks.set(event, []);
    }
    this.eventCallbacks.get(event)?.push(callback);
  }

  // Unsubscribe from events
  off(event: string, callback: EventCallback): void {
    const callbacks = this.eventCallbacks.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  // Emit event to subscribers
  private emit(event: string, data: any): void {
    const callbacks = this.eventCallbacks.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (err) {
          console.error(`[WS] Error in event callback for ${event}:`, err);
        }
      });
    }
  }

  async connect(token: string): Promise<void> {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isConnecting = true;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;

        // Authenticate
        this.send({ event: 'auth', data: { token } });

        // Start heartbeat
        this.startHeartbeat();

        // Process queued messages
        this.processQueue();

        // Emit connection event
        this.emit('connected', {});
        toast.success('Real-time connection established');
      };

      this.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      };

      this.ws.onclose = (event) => {
        console.log('[WS] Disconnected', event.code);
        this.isConnecting = false;
        this.stopHeartbeat();
        this.emit('disconnected', { code: event.code });

        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect(token);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS] Error', error);
        this.isConnecting = false;
        this.emit('error', error);
      };

    } catch (error) {
      console.error('[WS] Connection failed', error);
      this.isConnecting = false;
      this.emit('error', error);
    }
  }

  private handleMessage(message: any): void {
    const { event, data } = message;

    // Emit specific event
    this.emit(event, data);

    // Handle known events with toast notifications
    switch (event) {
      case 'connection.established':
        console.log('[WS] Session established:', data?.client_id);
        break;

      case 'pong':
        // Heartbeat response
        break;

      case 'actions.completed':
        toast.success(`Executed ${data?.results?.length || 0} action(s)`);
        break;

      case 'skill.operators_updated':
        toast.success('Skill operators updated');
        break;

      case 'model.enabled':
        toast.success('Model enabled');
        break;

      case 'model.disabled':
        toast.info('Model disabled');
        break;

      case 'project.created':
        toast.success('Project created');
        break;

      case 'project.updated':
        toast.info('Project updated');
        break;

      case 'project.comment_added':
        toast.info('New comment added');
        break;

      case 'governance.approval_required':
        toast.warning('Action requires approval');
        break;

      default:
        console.log('[WS] Event received:', event);
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      this.messageQueue.push(message);
      console.log('[WS] Message queued (connection not ready)');
    }
  }

  private processQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      this.send(message);
    }
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      this.send({
        event: 'ping',
        data: { timestamp: Date.now() }
      });
    }, 30000); // 30 seconds
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private scheduleReconnect(token: string): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    toast.info(`Reconnecting... (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect(token);
    }, delay);
  }

  disconnect(): void {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Helper methods for specific actions
  sendChatMessage(message: string): void {
    this.send({ event: 'chat.message', data: { message } });
  }

  subscribe(channel: string): void {
    this.send({ event: 'subscribe', data: { channel } });
  }

  executeAction(action: any): void {
    this.send({ event: 'action.execute', data: { action } });
  }
}

// Singleton instance
let wsClient: WebSocketClient | null = null;

export function getWebSocketClient(): WebSocketClient {
  if (!wsClient) {
    wsClient = new WebSocketClient(
      import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/v1/realtime/ws'
    );
  }
  return wsClient;
}

export function initWebSocket(token: string): void {
  getWebSocketClient().connect(token);
}

export function closeWebSocket(): void {
  getWebSocketClient().disconnect();
}

// Hook for components to use WebSocket events
export function useWebSocketEvent(event: string, callback: EventCallback): void {
  const ws = getWebSocketClient();
  ws.on(event, callback);
}

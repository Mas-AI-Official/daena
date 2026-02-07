/**
 * WebSocket Client - Real-time communication with backend
 */
import { store } from '@/store';
import { toast } from 'sonner';

class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageQueue: any[] = [];
  private isConnecting = false;
  private heartbeatInterval: NodeJS.Timeout | null = null;

  constructor(private url: string) {}

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

        store.dispatch({ type: 'websocket/connected' });
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
        store.dispatch({ type: 'websocket/disconnected' });

        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect(token);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS] Error', error);
        this.isConnecting = false;
      };

    } catch (error) {
      console.error('[WS] Connection failed', error);
      this.isConnecting = false;
    }
  }

  private handleMessage(message: any): void {
    const { event, data } = message;

    switch (event) {
      case 'connection.established':
        console.log('[WS] Session established:', data.client_id);
        break;

      case 'pong':
        // Heartbeat response
        break;

      case 'chat.chunk':
        store.dispatch({ type: 'chat/addChunk', payload: data.content });
        break;

      case 'actions.detected':
        store.dispatch({ type: 'chat/actionsDetected', payload: data.actions });
        break;

      case 'actions.completed':
        store.dispatch({ type: 'chat/actionsCompleted', payload: data.results });
        toast.success(`Executed ${data.results.length} action(s)`);
        break;

      case 'skill.operators_updated':
        store.dispatch({
          type: 'skills/updateOperators',
          payload: { skillId: data.skill_id, operators: data.operators }
        });
        break;

      case 'model.enabled':
      case 'model.disabled':
        store.dispatch({
          type: 'brain/updateModelStatus',
          payload: { modelId: data.model_id, enabled: event === 'model.enabled' }
        });
        break;

      case 'project.created':
      case 'project.updated':
        store.dispatch({ type: 'projects/invalidateCache' });
        toast.info('Project updated');
        break;

      case 'project.comment_added':
        store.dispatch({
          type: 'projects/addComment',
          payload: { projectId: data.project_id, comment: data.comment }
        });
        break;

      case 'governance.approval_required':
        store.dispatch({
          type: 'governance/addApproval',
          payload: data
        });
        toast.warning('Action requires approval');
        break;

      default:
        console.log('[WS] Unknown event:', event);
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      this.messageQueue.push(message);
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

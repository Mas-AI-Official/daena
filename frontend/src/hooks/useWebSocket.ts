import { useRef, useState, useEffect, useCallback } from 'react';

interface WebSocketMessage {
    type?: string;
    event_type?: string;
    content?: string;
    payload?: any;
    timestamp?: string;
}

interface UseWebSocketOptions {
    url: string;
    onMessage?: (data: WebSocketMessage) => void;
    onOpen?: () => void;
    onClose?: () => void;
    shouldReconnect?: boolean;
}

export function useWebSocket({
    url,
    onMessage,
    onOpen,
    onClose,
    shouldReconnect = true
}: UseWebSocketOptions) {
    const [isConnected, setIsConnected] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<number | undefined>(undefined);

    const connect = useCallback(() => {
        try {
            // Use relative URL handled by Vite proxy if starts with /
            const wsUrl = url.startsWith('/')
                ? `ws://${window.location.host}${url}` // Vite proxy handles this? No, usually browser to dev server needs explicit port if not proxied correctly for WS.
                // Actually vite proxy set in config: '/ws': { target: 'ws://localhost:8000', ws: true }
                // So ws://localhost:5173/ws/... -> ws://localhost:8000/ws/...
                : url;

            // Ensure we use the correct protocol (ws vs wss)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const finalUrl = wsUrl.startsWith('ws') ? wsUrl : `${protocol}//${window.location.host}${wsUrl}`;

            console.log(`Connecting to WebSocket: ${finalUrl}`);
            const ws = new WebSocket(finalUrl);

            ws.onopen = () => {
                console.log('WebSocket connected');
                setIsConnected(true);
                onOpen?.();
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    // Handle heartbeat pong automatically?
                    if (data.event_type === 'ping') {
                        ws.send(JSON.stringify({ type: 'pong' }));
                        return;
                    }
                    onMessage?.(data);
                } catch (err) {
                    console.error('Failed to parse WebSocket message:', err);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setIsConnected(false);
                socketRef.current = null;
                onClose?.();

                if (shouldReconnect) {
                    reconnectTimeoutRef.current = window.setTimeout(() => {
                        console.log('Attempting to reconnect...');
                        connect();
                    }, 3000);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                ws.close();
            };

            socketRef.current = ws;
        } catch (error) {
            console.error('WebSocket connection failed:', error);
        }
    }, [url, onMessage, onOpen, onClose, shouldReconnect]);

    useEffect(() => {
        connect();

        return () => {
            if (socketRef.current) {
                socketRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [connect]);

    const sendMessage = useCallback((message: any) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket is not open. Cannot send message.');
        }
    }, []);

    return { isConnected, sendMessage };
}

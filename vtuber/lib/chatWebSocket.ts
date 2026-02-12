import { useEffect, useRef, useState, useCallback } from 'react';

// Types matches backend
export interface WebSocketMessage {
    type: 'chat_message' | 'ai_response' | 'status_update' | 'stream_start' | 'stream_end' | 'text_chunk' | 'audio_chunk' | 'vision_status' | 'browser_screenshot' | 'browser_action';
    username?: string;
    message?: string;
    audio_base64?: string;
    image_base64?: string;
    emotion?: 'happy' | 'sad' | 'angry' | 'excited' | 'neutral';
    timestamp?: number;
    data?: any;
    content?: string;
    // Streaming fields
    chunk?: string;
    complete?: boolean;
    volume?: number;
}

export function useChatWebSocket(onMessage?: (msg: WebSocketMessage) => void) {
    const [isConnected, setIsConnected] = useState(false);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    // Use a ref for the callback to avoid recreating connect when callback changes
    const onMessageRef = useRef(onMessage);
    onMessageRef.current = onMessage;

    const connect = useCallback(() => {
        // Clear any existing reconnect timer
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        // Don't connect if already connected or connecting
        if (wsRef.current?.readyState === WebSocket.OPEN ||
            wsRef.current?.readyState === WebSocket.CONNECTING) {
            return;
        }

        // Connect directly to local backend
        const wsUrl = 'http://localhost:8000/ws/chat';

        console.log(`[WebSocket] Connecting to ${wsUrl}...`);
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('[WebSocket] Connected');
            setIsConnected(true);
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Use the ref to get the latest callback
                if (onMessageRef.current) {
                    onMessageRef.current(data);
                }
            } catch (e) {
                console.error('[WebSocket] Failed to parse message:', event.data);
            }
        };

        socket.onclose = () => {
            console.log('[WebSocket] Disconnected');
            setIsConnected(false);
            wsRef.current = null;

            // Auto-reconnect after 3 seconds
            reconnectTimeoutRef.current = setTimeout(() => {
                console.log('[WebSocket] Attempting reconnect...');
                connect();
            }, 3000);
        };

        socket.onerror = (event) => {
            console.warn('[WebSocket] Connection error occurred. Will attempt reconnect...');
            socket.close();
        };

        wsRef.current = socket;
    }, []); // No dependencies - connect function is stable

    useEffect(() => {
        connect();

        return () => {
            // Cleanup on unmount
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
                reconnectTimeoutRef.current = null;
            }
        };
    }, [connect]);

    // Function to send messages (if needed)
    const sendMessage = useCallback((msg: any) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(msg));
        } else {
            console.warn('[WebSocket] Cannot send - not connected');
        }
    }, []);

    return { isConnected, sendMessage };
}

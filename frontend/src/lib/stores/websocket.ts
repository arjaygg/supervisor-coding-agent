import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: number;
}

export interface WebSocketState {
  connected: boolean;
  reconnectAttempts: number;
  lastMessage: WebSocketMessage | null;
}

function createWebSocketStore() {
  const { subscribe, set, update } = writable<WebSocketState>({
    connected: false,
    reconnectAttempts: 0,
    lastMessage: null
  });

  let ws: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 2000;

  const connect = () => {
    if (!browser) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    try {
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        set({ connected: true, reconnectAttempts: 0, lastMessage: null });
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = {
            type: 'message',
            data: JSON.parse(event.data),
            timestamp: Date.now()
          };
          
          update(state => ({
            ...state,
            lastMessage: message
          }));
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        update(state => ({ ...state, connected: false }));
        
        // Attempt to reconnect
        update(state => {
          if (state.reconnectAttempts < maxReconnectAttempts) {
            reconnectTimer = window.setTimeout(() => {
              connect();
            }, reconnectDelay);
            
            return { ...state, reconnectAttempts: state.reconnectAttempts + 1 };
          }
          return state;
        });
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  };

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    
    if (ws) {
      ws.close();
      ws = null;
    }
    
    set({ connected: false, reconnectAttempts: 0, lastMessage: null });
  };

  const send = (data: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  };

  return {
    subscribe,
    connect,
    disconnect,
    send
  };
}

export const websocket = createWebSocketStore();
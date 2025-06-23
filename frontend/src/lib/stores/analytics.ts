import { writable, type Readable } from "svelte/store";

export interface AnalyticsSummary {
  total_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  average_execution_time_ms: number;
  system_health_score: number;
  cost_today_usd: string;
}

export interface AnalyticsMetrics {
  timestamp: string;
  queue_depth: number;
  active_workflows: number;
}

export interface AnalyticsUpdate {
  summary: AnalyticsSummary;
  metrics: AnalyticsMetrics;
}

interface AnalyticsState {
  connected: boolean;
  summary: AnalyticsSummary | null;
  metrics: AnalyticsMetrics | null;
  lastUpdate: string | null;
  error: string | null;
}

const initialState: AnalyticsState = {
  connected: false,
  summary: null,
  metrics: null,
  lastUpdate: null,
  error: null,
};

// Get WebSocket URL from environment or default to localhost:8000
const WS_BASE_URL = import.meta.env?.VITE_WS_URL || "ws://localhost:8000";

export function createAnalyticsStore() {
  const { subscribe, set, update } = writable<AnalyticsState>(initialState);

  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 2000; // 2 seconds

  function connect() {
    try {
      ws = new WebSocket(`${WS_BASE_URL}/ws/analytics`);

      ws.onopen = () => {
        console.log("Analytics WebSocket connected");
        reconnectAttempts = 0;
        update((state) => ({ ...state, connected: true, error: null }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleMessage(message);
        } catch (error) {
          console.error("Error parsing analytics WebSocket message:", error);
        }
      };

      ws.onclose = () => {
        console.log("Analytics WebSocket disconnected");
        update((state) => ({ ...state, connected: false }));

        // Attempt to reconnect
        if (reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          console.log(
            `Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`
          );
          setTimeout(connect, reconnectDelay);
        }
      };

      ws.onerror = (error) => {
        console.error("Analytics WebSocket error:", error);
        update((state) => ({
          ...state,
          connected: false,
          error: "WebSocket connection error",
        }));
      };
    } catch (error) {
      console.error("Error creating analytics WebSocket:", error);
      update((state) => ({
        ...state,
        connected: false,
        error: "Failed to create WebSocket connection",
      }));
    }
  }

  function handleMessage(message: any) {
    const { type, data, timestamp } = message;

    switch (type) {
      case "initial_analytics":
      case "analytics_response":
        update((state) => ({
          ...state,
          summary: data.summary,
          metrics: data.metrics || state.metrics,
          lastUpdate: timestamp,
        }));
        break;

      case "analytics_update":
        update((state) => ({
          ...state,
          summary: data.summary || state.summary,
          metrics: data.metrics || state.metrics,
          lastUpdate: timestamp,
        }));
        break;

      case "pong":
        // Handle ping/pong for keep-alive
        break;

      case "error":
        console.error("Analytics WebSocket error:", message.message);
        update((state) => ({ ...state, error: message.message }));
        break;

      default:
        console.log("Unknown analytics message type:", type);
    }
  }

  function sendMessage(message: any) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }

  function ping() {
    sendMessage({ type: "ping" });
  }

  function requestAnalytics(timeRange: string = "day") {
    sendMessage({
      type: "request_analytics",
      time_range: timeRange,
    });
  }

  function subscribeToMetrics(metricTypes: string[]) {
    sendMessage({
      type: "subscribe_metrics",
      metric_types: metricTypes,
    });
  }

  function disconnect() {
    if (ws) {
      ws.close();
      ws = null;
    }
    set(initialState);
  }

  // Auto-connect when store is created
  connect();

  return {
    subscribe,
    connect,
    disconnect,
    ping,
    requestAnalytics,
    subscribeToMetrics,
    // Computed values
    isConnected: {
      subscribe: (callback: (value: boolean) => void): (() => void) => {
        return subscribe((state) => callback(state.connected));
      },
    } as Readable<boolean>,
    summary: {
      subscribe: (
        callback: (value: AnalyticsSummary | null) => void
      ): (() => void) => {
        return subscribe((state) => callback(state.summary));
      },
    } as Readable<AnalyticsSummary | null>,
    metrics: {
      subscribe: (
        callback: (value: AnalyticsMetrics | null) => void
      ): (() => void) => {
        return subscribe((state) => callback(state.metrics));
      },
    } as Readable<AnalyticsMetrics | null>,
  };
}

// Global analytics store instance
export const analyticsStore = createAnalyticsStore();

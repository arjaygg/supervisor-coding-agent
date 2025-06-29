import { writable, derived } from "svelte/store";
import { api, ApiError } from "../utils/api";

export interface ProviderInfo {
  name: string;
  type: string;
  health_status: string;
  health_score: number;
  capabilities: string[];
  max_concurrent: number;
  metrics: Record<string, any>;
}

export interface ProviderDashboardData {
  timestamp: string;
  overview: {
    total_providers: number;
    healthy_providers: number;
    unhealthy_providers: number;
    total_tasks_today: number;
    total_cost_today: number;
    average_response_time: number;
    success_rate: number;
  };
  providers: Record<string, ProviderInfo>;
  usage_analytics: Record<string, any>;
  system_health: Record<string, any>;
  cost_breakdown: Record<string, any>;
  performance_metrics: Record<string, any>;
  quota_status: Record<string, any>;
}

export interface ProviderComparison {
  timestamp: string;
  time_range: string;
  comparison: Record<string, ProviderPerformanceData>;
  rankings: {
    fastest: [string, ProviderPerformanceData][];
    most_reliable: [string, ProviderPerformanceData][];
    most_cost_effective: [string, ProviderPerformanceData][];
    healthiest: [string, ProviderPerformanceData][];
  };
  summary: {
    total_providers: number;
    average_health_score: number;
    average_success_rate: number;
    total_requests: number;
  };
}

export interface ProviderPerformanceData {
  name: string;
  type: string;
  health_score: number;
  success_rate: number;
  average_response_time: number;
  cost_per_request: number;
  total_requests: number;
  uptime_percentage: number;
  quota_utilization: number;
}

interface ProviderAnalyticsState {
  dashboardData: ProviderDashboardData | null;
  comparison: ProviderComparison | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
}

function createProviderAnalyticsStore() {
  const { subscribe, set, update } = writable<ProviderAnalyticsState>({
    dashboardData: null,
    comparison: null,
    loading: false,
    error: null,
    lastUpdated: null,
  });

  return {
    subscribe,

    async fetchDashboardData(): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const dashboardData = await api.get<ProviderDashboardData>(
          "/api/v1/analytics/providers/dashboard"
        );

        update((state) => ({
          ...state,
          dashboardData,
          loading: false,
          lastUpdated: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch provider dashboard data";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchProviderComparison(timeRange: string = "day"): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const comparison = await api.get<ProviderComparison>(
          `/api/v1/analytics/providers/performance-comparison?time_range=${timeRange}`
        );

        update((state) => ({
          ...state,
          comparison,
          loading: false,
          lastUpdated: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch provider comparison";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchProviderMetrics(providerId: string, timeRange: string = "day") {
      try {
        return await api.get(
          `/api/v1/analytics/providers/${providerId}/metrics?time_range=${timeRange}`
        );
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch provider metrics";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchCostOptimization() {
      try {
        return await api.get("/api/v1/analytics/providers/cost-optimization");
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch cost optimization data";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    clearError(): void {
      update((state) => ({ ...state, error: null }));
    },

    reset(): void {
      set({
        dashboardData: null,
        comparison: null,
        loading: false,
        error: null,
        lastUpdated: null,
      });
    },
  };
}

export const providerAnalytics = createProviderAnalyticsStore();

// Derived stores for easy access
export const providerOverview = derived(
  providerAnalytics,
  ($analytics) => $analytics.dashboardData?.overview || null
);

export const healthyProviders = derived(
  providerAnalytics,
  ($analytics) => {
    if (!$analytics.dashboardData?.providers) return [];
    
    return Object.entries($analytics.dashboardData.providers)
      .filter(([_, provider]) => provider.health_status === "healthy")
      .map(([id, provider]) => ({ id, ...provider }));
  }
);

export const unhealthyProviders = derived(
  providerAnalytics,
  ($analytics) => {
    if (!$analytics.dashboardData?.providers) return [];
    
    return Object.entries($analytics.dashboardData.providers)
      .filter(([_, provider]) => provider.health_status !== "healthy")
      .map(([id, provider]) => ({ id, ...provider }));
  }
);

export const topPerformingProviders = derived(
  providerAnalytics,
  ($analytics) => {
    if (!$analytics.comparison?.rankings) return null;
    
    return {
      fastest: $analytics.comparison.rankings.fastest.slice(0, 3),
      mostReliable: $analytics.comparison.rankings.most_reliable.slice(0, 3),
      mostCostEffective: $analytics.comparison.rankings.most_cost_effective.slice(0, 3),
      healthiest: $analytics.comparison.rankings.healthiest.slice(0, 3),
    };
  }
);

export const systemHealth = derived(
  providerAnalytics,
  ($analytics) => {
    if (!$analytics.dashboardData?.overview) return null;
    
    const { overview } = $analytics.dashboardData;
    const healthPercentage = overview.total_providers > 0 
      ? (overview.healthy_providers / overview.total_providers) * 100 
      : 0;
    
    return {
      percentage: healthPercentage,
      status: healthPercentage >= 80 ? "healthy" : healthPercentage >= 60 ? "warning" : "critical",
      providers: {
        total: overview.total_providers,
        healthy: overview.healthy_providers,
        unhealthy: overview.unhealthy_providers,
      },
      metrics: {
        successRate: overview.success_rate,
        avgResponseTime: overview.average_response_time,
        costToday: overview.total_cost_today,
        tasksToday: overview.total_tasks_today,
      }
    };
  }
);
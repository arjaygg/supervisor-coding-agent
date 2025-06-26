import { writable, derived } from "svelte/store";
import { api, ApiError } from "../utils/api";

export interface TrendPrediction {
  metric_type: string;
  predicted_values: PredictedValue[];
  confidence_score: number;
  trend_direction: "increasing" | "decreasing" | "stable" | "unknown";
  model_used: string;
}

export interface PredictedValue {
  timestamp: string;
  value: number;
  labels: Record<string, any>;
  metadata: Record<string, any>;
}

export interface AnalyticsInsight {
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  metric_type: string;
  value: number;
  threshold: number;
  recommendation: string;
}

export interface CostOptimizationRecommendation {
  timestamp: string;
  recommendations: {
    potential_monthly_savings: number;
    opportunities: Array<{
      type: string;
      description: string;
      potential_savings: number;
      implementation_effort: "low" | "medium" | "high";
    }>;
    provider_efficiency: Record<string, number>;
    usage_patterns: Record<string, any>;
  };
}

interface PredictiveAnalyticsState {
  trends: Record<string, TrendPrediction>;
  insights: AnalyticsInsight[];
  costOptimization: CostOptimizationRecommendation | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
}

function createPredictiveAnalyticsStore() {
  const { subscribe, set, update } = writable<PredictiveAnalyticsState>({
    trends: {},
    insights: [],
    costOptimization: null,
    loading: false,
    error: null,
    lastUpdated: null,
  });

  return {
    subscribe,

    async fetchTrendPrediction(metricType: string, predictionHours: number = 24): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const prediction = await api.get<TrendPrediction>(
          `/api/v1/analytics/trends/${metricType}?prediction_hours=${predictionHours}`
        );

        update((state) => ({
          ...state,
          trends: { ...state.trends, [metricType]: prediction },
          loading: false,
          lastUpdated: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : `Failed to fetch trend prediction for ${metricType}`;
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchMultipleTrends(metricTypes: string[], predictionHours: number = 24): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const predictions = await Promise.all(
          metricTypes.map(async (metricType) => {
            const prediction = await api.get<TrendPrediction>(
              `/api/v1/analytics/trends/${metricType}?prediction_hours=${predictionHours}`
            );
            return [metricType, prediction] as [string, TrendPrediction];
          })
        );

        const trendsMap = Object.fromEntries(predictions);

        update((state) => ({
          ...state,
          trends: { ...state.trends, ...trendsMap },
          loading: false,
          lastUpdated: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch trend predictions";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchInsights(timeframe: string = "day"): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const insights = await api.get<AnalyticsInsight[]>(
          `/api/v1/analytics/insights?timeframe=${timeframe}`
        );

        update((state) => ({
          ...state,
          insights,
          loading: false,
          lastUpdated: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch analytics insights";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchCostOptimization(): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const costOptimization = await api.get<CostOptimizationRecommendation>(
          "/api/v1/analytics/providers/cost-optimization"
        );

        update((state) => ({
          ...state,
          costOptimization,
          loading: false,
          lastUpdated: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch cost optimization recommendations";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async refreshAllData(predictionHours: number = 24): Promise<void> {
      const commonMetrics = [
        "task_execution",
        "system_performance", 
        "cost_tracking",
        "error_rate"
      ];

      try {
        await Promise.all([
          this.fetchMultipleTrends(commonMetrics, predictionHours),
          this.fetchInsights("day"),
          this.fetchCostOptimization()
        ]);
      } catch (error) {
        console.error("Failed to refresh all predictive analytics data:", error);
      }
    },

    clearError(): void {
      update((state) => ({ ...state, error: null }));
    },

    reset(): void {
      set({
        trends: {},
        insights: [],
        costOptimization: null,
        loading: false,
        error: null,
        lastUpdated: null,
      });
    },
  };
}

export const predictiveAnalytics = createPredictiveAnalyticsStore();

// Derived stores for easy access
export const criticalInsights = derived(
  predictiveAnalytics,
  ($analytics) => $analytics.insights.filter(insight => insight.severity === "critical")
);

export const warningInsights = derived(
  predictiveAnalytics,
  ($analytics) => $analytics.insights.filter(insight => insight.severity === "warning")
);

export const trendingSummary = derived(
  predictiveAnalytics,
  ($analytics) => {
    const trends = Object.entries($analytics.trends);
    
    return {
      totalTrends: trends.length,
      increasingTrends: trends.filter(([_, trend]) => trend.trend_direction === "increasing").length,
      decreasingTrends: trends.filter(([_, trend]) => trend.trend_direction === "decreasing").length,
      stableTrends: trends.filter(([_, trend]) => trend.trend_direction === "stable").length,
      averageConfidence: trends.length > 0 
        ? trends.reduce((sum, [_, trend]) => sum + trend.confidence_score, 0) / trends.length 
        : 0,
    };
  }
);

export const costSavingsOpportunity = derived(
  predictiveAnalytics,
  ($analytics) => {
    if (!$analytics.costOptimization) return null;
    
    const { recommendations } = $analytics.costOptimization;
    const totalSavings = recommendations.potential_monthly_savings;
    const highImpactOpportunities = recommendations.opportunities.filter(
      op => op.potential_savings > totalSavings * 0.1 // Opportunities worth more than 10% of total savings
    );
    
    return {
      totalPotentialSavings: totalSavings,
      highImpactCount: highImpactOpportunities.length,
      quickWins: recommendations.opportunities.filter(
        op => op.implementation_effort === "low" && op.potential_savings > 0
      ).length,
      averageEfficiency: Object.values(recommendations.provider_efficiency).reduce(
        (sum, eff) => sum + eff, 0
      ) / Object.keys(recommendations.provider_efficiency).length,
    };
  }
);
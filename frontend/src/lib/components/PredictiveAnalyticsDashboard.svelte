<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { 
    predictiveAnalytics, 
    criticalInsights, 
    warningInsights,
    trendingSummary,
    costSavingsOpportunity 
  } from "../stores/predictiveAnalytics";
  import TrendChart from "./TrendChart.svelte";
  import InsightCard from "./InsightCard.svelte";
  import CostOptimizationPanel from "./CostOptimizationPanel.svelte";

  let refreshInterval: NodeJS.Timeout;
  let selectedPredictionHours = 24;
  let autoRefresh = true;

  const predictionOptions = [
    { value: 6, label: "6 Hours" },
    { value: 12, label: "12 Hours" },
    { value: 24, label: "1 Day" },
    { value: 48, label: "2 Days" },
    { value: 72, label: "3 Days" },
    { value: 168, label: "1 Week" }
  ];

  onMount(async () => {
    await refreshData();
    
    if (autoRefresh) {
      startAutoRefresh();
    }
  });

  onDestroy(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });

  function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(refreshData, 60000); // 1 minute
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  }

  async function refreshData() {
    try {
      await predictiveAnalytics.refreshAllData(selectedPredictionHours);
    } catch (error) {
      console.error("Failed to refresh predictive analytics:", error);
    }
  }

  function handlePredictionHoursChange() {
    refreshData();
  }

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    if (autoRefresh) {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  }

  function formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(value);
  }

  function formatPercentage(value: number): string {
    return `${value.toFixed(1)}%`;
  }

  function getTrendIcon(direction: string): string {
    switch (direction) {
      case "increasing": return "📈";
      case "decreasing": return "📉";
      case "stable": return "➡️";
      default: return "❓";
    }
  }

  function getTrendColor(direction: string): string {
    switch (direction) {
      case "increasing": return "text-green-600";
      case "decreasing": return "text-red-600";
      case "stable": return "text-blue-600";
      default: return "text-gray-600";
    }
  }
</script>

<div class="predictive-analytics-dashboard p-6 space-y-6">
  <!-- Header -->
  <div class="flex justify-between items-center">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Predictive Analytics Dashboard</h1>
      <p class="text-sm text-gray-600">AI-powered forecasting and optimization insights</p>
    </div>
    
    <div class="flex items-center space-x-4">
      <!-- Prediction Timeline Selector -->
      <select 
        bind:value={selectedPredictionHours} 
        on:change={handlePredictionHoursChange}
        class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
      >
        {#each predictionOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>

      <!-- Auto Refresh Toggle -->
      <button
        on:click={toggleAutoRefresh}
        class="px-3 py-2 text-sm rounded-md border {autoRefresh 
          ? 'bg-blue-100 border-blue-300 text-blue-700' 
          : 'bg-gray-100 border-gray-300 text-gray-700'}"
      >
        Auto Refresh {autoRefresh ? 'ON' : 'OFF'}
      </button>

      <!-- Manual Refresh -->
      <button
        on:click={refreshData}
        class="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 focus:ring-2 focus:ring-blue-500"
        disabled={$predictiveAnalytics.loading}
      >
        {#if $predictiveAnalytics.loading}
          <span class="animate-spin">⟳</span>
        {:else}
          🔮 Predict
        {/if}
      </button>
    </div>
  </div>

  <!-- Error Display -->
  {#if $predictiveAnalytics.error}
    <div class="bg-red-50 border border-red-200 rounded-md p-4">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">Prediction Error</h3>
          <p class="text-sm text-red-700 mt-1">{$predictiveAnalytics.error}</p>
        </div>
        <div class="ml-auto">
          <button
            on:click={() => predictiveAnalytics.clearError()}
            class="text-red-400 hover:text-red-600"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Trends Summary -->
  {#if $trendingSummary.totalTrends > 0}
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-gray-900">{$trendingSummary.totalTrends}</p>
        <p class="text-sm text-gray-600">Total Trends</p>
      </div>
      
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-green-600">{$trendingSummary.increasingTrends}</p>
        <p class="text-sm text-gray-600">📈 Increasing</p>
      </div>
      
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-red-600">{$trendingSummary.decreasingTrends}</p>
        <p class="text-sm text-gray-600">📉 Decreasing</p>
      </div>
      
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-blue-600">{$trendingSummary.stableTrends}</p>
        <p class="text-sm text-gray-600">➡️ Stable</p>
      </div>
      
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-purple-600">{formatPercentage($trendingSummary.averageConfidence * 100)}</p>
        <p class="text-sm text-gray-600">Avg Confidence</p>
      </div>
    </div>
  {/if}

  <!-- Critical Insights -->
  {#if $criticalInsights.length > 0}
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200 bg-red-50">
        <h2 class="text-lg font-semibold text-red-800">🚨 Critical Insights</h2>
        <p class="text-sm text-red-600">Immediate attention required</p>
      </div>
      <div class="p-6">
        <div class="space-y-4">
          {#each $criticalInsights as insight}
            <InsightCard {insight} />
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Warning Insights -->
  {#if $warningInsights.length > 0}
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200 bg-yellow-50">
        <h2 class="text-lg font-semibold text-yellow-800">⚠️ Warning Insights</h2>
        <p class="text-sm text-yellow-600">Monitor closely</p>
      </div>
      <div class="p-6">
        <div class="space-y-4">
          {#each $warningInsights as insight}
            <InsightCard {insight} />
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Cost Optimization -->
  {#if $costSavingsOpportunity}
    <CostOptimizationPanel 
      costOptimization={$predictiveAnalytics.costOptimization}
      summary={$costSavingsOpportunity}
    />
  {/if}

  <!-- Trend Predictions -->
  {#if Object.keys($predictiveAnalytics.trends).length > 0}
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900">📊 Trend Predictions</h2>
        <p class="text-sm text-gray-600">Next {selectedPredictionHours} hours forecast</p>
      </div>
      <div class="p-6">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {#each Object.entries($predictiveAnalytics.trends) as [metricType, trend]}
            <div class="border border-gray-200 rounded-lg p-4">
              <div class="flex justify-between items-center mb-4">
                <div>
                  <h3 class="font-medium text-gray-900 capitalize">
                    {metricType.replace(/_/g, ' ')}
                  </h3>
                  <div class="flex items-center space-x-2 text-sm">
                    <span class="{getTrendColor(trend.trend_direction)}">
                      {getTrendIcon(trend.trend_direction)} {trend.trend_direction}
                    </span>
                    <span class="text-gray-500">
                      • {formatPercentage(trend.confidence_score * 100)} confidence
                    </span>
                  </div>
                </div>
                <div class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                  {trend.model_used}
                </div>
              </div>
              
              <TrendChart 
                data={trend.predicted_values}
                metricType={metricType}
                trendDirection={trend.trend_direction}
                confidenceScore={trend.confidence_score}
              />
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Last Updated -->
  {#if $predictiveAnalytics.lastUpdated}
    <div class="text-center text-sm text-gray-500">
      Last prediction update: {$predictiveAnalytics.lastUpdated.toLocaleString()}
    </div>
  {/if}
</div>

<style>
  .predictive-analytics-dashboard {
    min-height: 100vh;
    background-color: #f8fafc;
  }
</style>
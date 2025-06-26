<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { 
    providerAnalytics, 
    providerOverview, 
    systemHealth, 
    healthyProviders, 
    topPerformingProviders 
  } from "../stores/providerAnalytics";
  import StatusIndicator from "./StatusIndicator.svelte";
  import Chart from "./Chart.svelte";

  let refreshInterval: NodeJS.Timeout;
  let selectedTimeRange = "day";
  let autoRefresh = true;

  const timeRangeOptions = [
    { value: "hour", label: "1 Hour" },
    { value: "day", label: "24 Hours" },
    { value: "week", label: "1 Week" },
    { value: "month", label: "1 Month" }
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
    refreshInterval = setInterval(refreshData, 30000); // 30 seconds
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  }

  async function refreshData() {
    try {
      await Promise.all([
        providerAnalytics.fetchDashboardData(),
        providerAnalytics.fetchProviderComparison(selectedTimeRange)
      ]);
    } catch (error) {
      console.error("Failed to refresh dashboard data:", error);
    }
  }

  function handleTimeRangeChange() {
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

  function formatNumber(value: number): string {
    return new Intl.NumberFormat('en-US').format(value);
  }

  function formatPercentage(value: number): string {
    return `${value.toFixed(1)}%`;
  }

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  }

  function getHealthStatusColor(status: string): string {
    switch (status) {
      case "healthy": return "text-green-600";
      case "warning": return "text-yellow-600";
      case "critical": return "text-red-600";
      default: return "text-gray-600";
    }
  }

  function getHealthStatusBg(status: string): string {
    switch (status) {
      case "healthy": return "bg-green-100";
      case "warning": return "bg-yellow-100";
      case "critical": return "bg-red-100";
      default: return "bg-gray-100";
    }
  }
</script>

<div class="resource-monitoring-dashboard p-6 space-y-6">
  <!-- Header -->
  <div class="flex justify-between items-center">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Resource Monitoring Dashboard</h1>
      <p class="text-sm text-gray-600">Real-time multi-provider performance analytics</p>
    </div>
    
    <div class="flex items-center space-x-4">
      <!-- Time Range Selector -->
      <select 
        bind:value={selectedTimeRange} 
        on:change={handleTimeRangeChange}
        class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
      >
        {#each timeRangeOptions as option}
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
        disabled={$providerAnalytics.loading}
      >
        {#if $providerAnalytics.loading}
          <span class="animate-spin">⟳</span>
        {:else}
          Refresh
        {/if}
      </button>
    </div>
  </div>

  <!-- Error Display -->
  {#if $providerAnalytics.error}
    <div class="bg-red-50 border border-red-200 rounded-md p-4">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">Error</h3>
          <p class="text-sm text-red-700 mt-1">{$providerAnalytics.error}</p>
        </div>
        <div class="ml-auto">
          <button
            on:click={() => providerAnalytics.clearError()}
            class="text-red-400 hover:text-red-600"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- System Health Overview -->
  {#if $systemHealth}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-1">
            <p class="text-sm font-medium text-gray-600">System Health</p>
            <div class="flex items-center mt-2">
              <div class="flex-1">
                <div class="flex items-center">
                  <div class="w-full bg-gray-200 rounded-full h-2 mr-3">
                    <div 
                      class="h-2 rounded-full {$systemHealth.status === 'healthy' ? 'bg-green-500' : $systemHealth.status === 'warning' ? 'bg-yellow-500' : 'bg-red-500'}"
                      style="width: {$systemHealth.percentage}%"
                    ></div>
                  </div>
                  <span class="text-2xl font-bold {getHealthStatusColor($systemHealth.status)}">
                    {formatPercentage($systemHealth.percentage)}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <StatusIndicator status={$systemHealth.status} />
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <p class="text-sm font-medium text-gray-600">Success Rate</p>
        <p class="text-2xl font-bold text-green-600 mt-2">
          {formatPercentage($systemHealth.metrics.successRate)}
        </p>
        <p class="text-xs text-gray-500 mt-1">
          {formatNumber($systemHealth.metrics.tasksToday)} tasks today
        </p>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <p class="text-sm font-medium text-gray-600">Avg Response Time</p>
        <p class="text-2xl font-bold text-blue-600 mt-2">
          {formatDuration($systemHealth.metrics.avgResponseTime)}
        </p>
        <p class="text-xs text-gray-500 mt-1">Real-time average</p>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <p class="text-sm font-medium text-gray-600">Cost Today</p>
        <p class="text-2xl font-bold text-purple-600 mt-2">
          {formatCurrency($systemHealth.metrics.costToday)}
        </p>
        <p class="text-xs text-gray-500 mt-1">24-hour total</p>
      </div>
    </div>
  {/if}

  <!-- Provider Status Grid -->
  {#if $providerOverview}
    <div class="bg-white rounded-lg shadow">
      <div class="px-6 py-4 border-b border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900">Provider Status</h2>
      </div>
      <div class="p-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div class="text-center">
            <p class="text-2xl font-bold text-gray-900">{$providerOverview.total_providers}</p>
            <p class="text-sm text-gray-600">Total Providers</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-bold text-green-600">{$providerOverview.healthy_providers}</p>
            <p class="text-sm text-gray-600">Healthy</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-bold text-red-600">{$providerOverview.unhealthy_providers}</p>
            <p class="text-sm text-gray-600">Unhealthy</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-bold text-blue-600">{formatNumber($providerOverview.total_tasks_today)}</p>
            <p class="text-sm text-gray-600">Tasks Today</p>
          </div>
        </div>

        <!-- Individual Provider Cards -->
        {#if $healthyProviders.length > 0}
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {#each $healthyProviders as provider}
              <div class="border border-gray-200 rounded-lg p-4 {getHealthStatusBg(provider.health_status)}">
                <div class="flex justify-between items-start mb-2">
                  <div>
                    <h3 class="font-medium text-gray-900">{provider.name}</h3>
                    <p class="text-sm text-gray-600">{provider.type}</p>
                  </div>
                  <StatusIndicator status={provider.health_status} />
                </div>
                <div class="space-y-1 text-sm">
                  <div class="flex justify-between">
                    <span class="text-gray-600">Health Score:</span>
                    <span class="font-medium {getHealthStatusColor(provider.health_status)}">
                      {formatPercentage(provider.health_score)}
                    </span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-gray-600">Max Concurrent:</span>
                    <span class="font-medium">{provider.max_concurrent}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-gray-600">Capabilities:</span>
                    <span class="font-medium">{provider.capabilities.length}</span>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Performance Rankings -->
  {#if $topPerformingProviders}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-semibold text-gray-900">Fastest Providers</h2>
        </div>
        <div class="p-6">
          <div class="space-y-3">
            {#each $topPerformingProviders.fastest as [providerId, provider], index}
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div class="flex items-center">
                  <span class="flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-800 text-sm font-medium rounded-full mr-3">
                    {index + 1}
                  </span>
                  <div>
                    <p class="font-medium text-gray-900">{provider.name}</p>
                    <p class="text-sm text-gray-600">{provider.type}</p>
                  </div>
                </div>
                <span class="text-sm font-medium text-blue-600">
                  {formatDuration(provider.average_response_time)}
                </span>
              </div>
            {/each}
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow">
        <div class="px-6 py-4 border-b border-gray-200">
          <h2 class="text-lg font-semibold text-gray-900">Most Reliable</h2>
        </div>
        <div class="p-6">
          <div class="space-y-3">
            {#each $topPerformingProviders.mostReliable as [providerId, provider], index}
              <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div class="flex items-center">
                  <span class="flex items-center justify-center w-6 h-6 bg-green-100 text-green-800 text-sm font-medium rounded-full mr-3">
                    {index + 1}
                  </span>
                  <div>
                    <p class="font-medium text-gray-900">{provider.name}</p>
                    <p class="text-sm text-gray-600">{provider.type}</p>
                  </div>
                </div>
                <span class="text-sm font-medium text-green-600">
                  {formatPercentage(provider.success_rate)}
                </span>
              </div>
            {/each}
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Last Updated -->
  {#if $providerAnalytics.lastUpdated}
    <div class="text-center text-sm text-gray-500">
      Last updated: {$providerAnalytics.lastUpdated.toLocaleString()}
    </div>
  {/if}
</div>

<style>
  .resource-monitoring-dashboard {
    min-height: 100vh;
    background-color: #f8fafc;
  }
</style>
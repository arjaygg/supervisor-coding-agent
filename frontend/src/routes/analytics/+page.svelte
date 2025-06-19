<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/utils/api';

  let analytics = {
    costSummary: null,
    usageTrends: null,
    agentPerformance: null
  };
  let loading = true;
  let error = null;
  let timeRange = 7; // days

  onMount(async () => {
    await loadAnalytics();
  });

  async function loadAnalytics() {
    loading = true;
    error = null;
    
    try {
      const [costResponse, trendsResponse, performanceResponse] = await Promise.all([
        api.get(`/analytics/cost?days=${timeRange}`),
        api.get(`/analytics/usage-trends?days=${timeRange}`),
        api.get(`/analytics/agent-performance?days=${timeRange}`)
      ]);
      
      analytics = {
        costSummary: costResponse.data,
        usageTrends: trendsResponse.data,
        agentPerformance: performanceResponse.data
      };
    } catch (err) {
      error = 'Failed to load analytics data';
      console.error('Error loading analytics:', err);
    } finally {
      loading = false;
    }
  }

  async function handleTimeRangeChange(event) {
    timeRange = parseInt(event.target.value);
    await loadAnalytics();
  }

  function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4
    }).format(amount || 0);
  }

  function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num || 0);
  }
</script>

<svelte:head>
  <title>Analytics - Supervisor Coding Agent</title>
</svelte:head>

<div class="container mx-auto px-4 py-8">
  <div class="mb-8 flex justify-between items-center">
    <div>
      <h1 class="text-3xl font-bold text-white mb-2">Analytics</h1>
      <p class="text-gray-400">Cost tracking and performance insights</p>
    </div>
    
    <div class="flex items-center gap-2">
      <label for="timeRange" class="text-gray-400 text-sm">Time Range:</label>
      <select 
        id="timeRange"
        bind:value={timeRange} 
        on:change={handleTimeRangeChange}
        class="bg-gray-800 border border-gray-600 rounded-md px-3 py-1 text-white text-sm focus:outline-none focus:border-blue-500"
      >
        <option value={1}>Last 24 hours</option>
        <option value={7}>Last 7 days</option>
        <option value={30}>Last 30 days</option>
        <option value={90}>Last 90 days</option>
      </select>
    </div>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      <span class="ml-3 text-gray-400">Loading analytics...</span>
    </div>
  {:else if error}
    <div class="bg-red-900/20 border border-red-500/50 rounded-lg p-4">
      <h3 class="text-red-400 font-semibold mb-2">Error</h3>
      <p class="text-gray-300">{error}</p>
    </div>
  {:else}
    <!-- Cost Summary Cards -->
    {#if analytics.costSummary}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="stat-card">
          <h3 class="stat-title">Total Cost</h3>
          <p class="stat-value">{formatCurrency(analytics.costSummary.total_cost)}</p>
          <p class="stat-subtitle">Last {timeRange} days</p>
        </div>
        
        <div class="stat-card">
          <h3 class="stat-title">Input Tokens</h3>
          <p class="stat-value">{formatNumber(analytics.costSummary.total_input_tokens)}</p>
          <p class="stat-subtitle">{formatCurrency(analytics.costSummary.input_token_cost)}</p>
        </div>
        
        <div class="stat-card">
          <h3 class="stat-title">Output Tokens</h3>
          <p class="stat-value">{formatNumber(analytics.costSummary.total_output_tokens)}</p>
          <p class="stat-subtitle">{formatCurrency(analytics.costSummary.output_token_cost)}</p>
        </div>
        
        <div class="stat-card">
          <h3 class="stat-title">Tasks Processed</h3>
          <p class="stat-value">{formatNumber(analytics.costSummary.task_count)}</p>
          <p class="stat-subtitle">Avg cost: {formatCurrency(analytics.costSummary.average_cost_per_task)}</p>
        </div>
      </div>
    {/if}

    <!-- Usage Trends -->
    {#if analytics.usageTrends}
      <div class="bg-gray-800 rounded-lg p-6 mb-8">
        <h2 class="text-xl font-semibold text-white mb-4">Usage Trends</h2>
        
        {#if analytics.usageTrends.daily_usage && analytics.usageTrends.daily_usage.length > 0}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Daily Tasks Chart Placeholder -->
            <div class="bg-gray-900 rounded-lg p-4">
              <h3 class="text-lg font-medium text-gray-300 mb-3">Daily Task Volume</h3>
              <div class="h-48 flex items-center justify-center text-gray-500">
                <div class="text-center">
                  <svg class="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <p>Chart visualization coming soon</p>
                </div>
              </div>
            </div>
            
            <!-- Task Type Distribution -->
            <div class="bg-gray-900 rounded-lg p-4">
              <h3 class="text-lg font-medium text-gray-300 mb-3">Task Type Distribution</h3>
              <div class="space-y-2">
                {#each Object.entries(analytics.usageTrends.task_type_distribution || {}) as [type, count]}
                  <div class="flex justify-between items-center">
                    <span class="text-gray-400">{type.replace('_', ' ')}</span>
                    <span class="text-white font-mono">{count}</span>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {:else}
          <div class="text-center py-8 text-gray-500">
            <p>No usage data available for the selected time range</p>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Agent Performance -->
    {#if analytics.agentPerformance}
      <div class="bg-gray-800 rounded-lg p-6">
        <h2 class="text-xl font-semibold text-white mb-4">Agent Performance</h2>
        
        {#if analytics.agentPerformance.agents && analytics.agentPerformance.agents.length > 0}
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b border-gray-700">
                  <th class="text-left py-3 text-gray-400 font-medium">Agent</th>
                  <th class="text-left py-3 text-gray-400 font-medium">Tasks</th>
                  <th class="text-left py-3 text-gray-400 font-medium">Success Rate</th>
                  <th class="text-left py-3 text-gray-400 font-medium">Avg Time</th>
                  <th class="text-left py-3 text-gray-400 font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {#each analytics.agentPerformance.agents as agent}
                  <tr class="border-b border-gray-700/50">
                    <td class="py-3 text-white font-mono">{agent.agent_id}</td>
                    <td class="py-3 text-gray-300">{agent.task_count}</td>
                    <td class="py-3">
                      <span class="text-{agent.success_rate >= 95 ? 'green' : agent.success_rate >= 80 ? 'yellow' : 'red'}-400">
                        {(agent.success_rate || 0).toFixed(1)}%
                      </span>
                    </td>
                    <td class="py-3 text-gray-300">{(agent.avg_execution_time || 0).toFixed(1)}s</td>
                    <td class="py-3 text-gray-300">{formatCurrency(agent.total_cost)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <div class="text-center py-8 text-gray-500">
            <p>No agent performance data available</p>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .stat-card {
    @apply bg-gray-800 rounded-lg p-6 border border-gray-700;
  }
  
  .stat-title {
    @apply text-gray-400 text-sm font-medium mb-2;
  }
  
  .stat-value {
    @apply text-2xl font-bold text-white mb-1;
  }
  
  .stat-subtitle {
    @apply text-gray-500 text-sm;
  }
</style>
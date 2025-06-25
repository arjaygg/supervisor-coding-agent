<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { api } from "$lib/utils/api";
  import Chart from "$lib/components/Chart.svelte";
  import { analyticsStore } from "$lib/stores/analytics";

  let analytics = {
    costSummary: null,
    usageTrends: null,
    agentPerformance: null,
  };
  let summary = null;
  let loading = true;
  let error = null;
  let timeRange = 7; // days

  // Multi-provider analytics
  let providerDashboard = null;
  let providerPerformance = null;
  let costOptimization = null;
  let multiProviderEnabled = false;
  let loadingProviders = false;

  // Chart data
  let dailyTasksChart = {
    labels: [],
    datasets: [
      {
        label: "Tasks",
        data: [],
        borderColor: "rgb(59, 130, 246)",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        fill: true,
      },
    ],
  };

  let taskTypeChart = {
    labels: [],
    datasets: [
      {
        data: [],
        backgroundColor: [
          "rgb(59, 130, 246)", // blue
          "rgb(16, 185, 129)", // green
          "rgb(245, 158, 11)", // yellow
          "rgb(239, 68, 68)", // red
          "rgb(139, 92, 246)", // purple
          "rgb(236, 72, 153)", // pink
        ],
      },
    ],
  };

  // Provider charts
  let providerHealthChart = {
    labels: [],
    datasets: [
      {
        label: "Health Score",
        data: [],
        backgroundColor: "rgba(16, 185, 129, 0.6)",
        borderColor: "rgb(16, 185, 129)",
        borderWidth: 2,
      },
    ],
  };

  let providerCostChart = {
    labels: [],
    datasets: [
      {
        label: "Cost Distribution",
        data: [],
        backgroundColor: [
          "rgb(59, 130, 246)",
          "rgb(16, 185, 129)",
          "rgb(245, 158, 11)",
          "rgb(239, 68, 68)",
          "rgb(139, 92, 246)",
        ],
      },
    ],
  };

  // Subscribe to real-time analytics updates
  $: if ($analyticsStore.summary) {
    updateAnalyticsFromWebSocket($analyticsStore.summary);
  }

  onMount(async () => {
    await loadAnalytics();

    // Check if multi-provider is enabled and load provider analytics
    await loadProviderAnalytics();

    // Request initial analytics data via WebSocket
    analyticsStore.requestAnalytics();

    // Subscribe to specific metrics
    analyticsStore.subscribeToMetrics(["task_execution", "system_metrics"]);
  });

  onDestroy(() => {
    // Clean up WebSocket connection
    analyticsStore.disconnect();
  });

  function updateAnalyticsFromWebSocket(summary: any) {
    // Update analytics object with real-time data
    if (analytics.costSummary) {
      analytics.costSummary.task_count = summary.total_tasks;
      analytics.costSummary.total_cost = parseFloat(
        summary.cost_today_usd || "0"
      );
    }

    // Update charts with real data from WebSocket summary
    const realTaskTypes = generateTaskTypeDataFromSummary(summary);

    taskTypeChart = {
      ...taskTypeChart,
      labels: realTaskTypes.labels,
      datasets: [
        {
          ...taskTypeChart.datasets[0],
          data: realTaskTypes.values,
        },
      ],
    };
  }

  async function loadProviderAnalytics() {
    if (!multiProviderEnabled) {
      // First check if multi-provider is available
      try {
        const response = await fetch('/api/v1/analytics/providers/dashboard');
        if (response.status === 400) {
          // Multi-provider is not enabled
          multiProviderEnabled = false;
          return;
        }
        multiProviderEnabled = true;
      } catch (error) {
        console.log('Multi-provider not available:', error);
        multiProviderEnabled = false;
        return;
      }
    }

    if (!multiProviderEnabled) return;

    loadingProviders = true;
    try {
      // Load provider dashboard data
      const dashboardResponse = await fetch('/api/v1/analytics/providers/dashboard');
      if (dashboardResponse.ok) {
        providerDashboard = await dashboardResponse.json();
        
        // Update provider charts
        updateProviderCharts();
      }

      // Load provider performance comparison
      const performanceResponse = await fetch('/api/v1/analytics/providers/performance-comparison');
      if (performanceResponse.ok) {
        providerPerformance = await performanceResponse.json();
      }

      // Load cost optimization recommendations
      const costResponse = await fetch('/api/v1/analytics/providers/cost-optimization');
      if (costResponse.ok) {
        costOptimization = await costResponse.json();
      }

    } catch (error) {
      console.error('Error loading provider analytics:', error);
      // Gracefully handle when multi-provider is not available
      multiProviderEnabled = false;
    } finally {
      loadingProviders = false;
    }
  }

  function updateProviderCharts() {
    if (!providerDashboard) return;

    const providers = Object.values(providerDashboard.providers || {});
    
    // Update provider health chart
    providerHealthChart = {
      ...providerHealthChart,
      labels: providers.map(p => p.name || p.id),
      datasets: [{
        ...providerHealthChart.datasets[0],
        data: providers.map(p => (p.health_score * 100).toFixed(1))
      }]
    };

    // Update provider cost chart
    const costData = Object.entries(providerDashboard.cost_breakdown || {});
    providerCostChart = {
      ...providerCostChart,
      labels: costData.map(([name]) => name),
      datasets: [{
        ...providerCostChart.datasets[0],
        data: costData.map(([, cost]) => cost)
      }]
    };
  }

  async function loadAnalytics() {
    loading = true;
    error = null;

    try {
      // Get analytics summary from the real API
      summary = await api.getAnalyticsSummary();

      // Get real metrics data instead of using mocks
      const metricsData = await api.getAnalyticsMetrics(undefined, 100);
      const realDailyData = generateDailyDataFromMetrics(metricsData);
      const realTaskTypes = generateTaskTypeDataFromSummary(summary);

      // Update chart data with real data
      dailyTasksChart = {
        ...dailyTasksChart,
        labels: realDailyData.labels,
        datasets: [
          {
            ...dailyTasksChart.datasets[0],
            data: realDailyData.values,
          },
        ],
      };

      taskTypeChart = {
        ...taskTypeChart,
        labels: realTaskTypes.labels,
        datasets: [
          {
            ...taskTypeChart.datasets[0],
            data: realTaskTypes.values,
          },
        ],
      };

      // Update analytics object with real data
      analytics = {
        costSummary: {
          total_cost: parseFloat(summary.cost_today_usd || "0"),
          total_input_tokens: 0, // Would need cost tracking data
          total_output_tokens: 0,
          input_token_cost: 0,
          output_token_cost: 0,
          task_count: summary.total_tasks,
          average_cost_per_task:
            summary.total_tasks > 0
              ? parseFloat(summary.cost_today_usd || "0") / summary.total_tasks
              : 0,
        },
        usageTrends: {
          daily_usage: realDailyData.labels.map((label, i) => ({
            date: label,
            task_count: realDailyData.values[i],
          })),
          task_type_distribution: realTaskTypes.labels.reduce(
            (acc, label, i) => {
              acc[label.toLowerCase().replace(" ", "_")] =
                realTaskTypes.values[i];
              return acc;
            },
            {}
          ),
        },
        agentPerformance: await generateAgentPerformanceData(summary),
      };
    } catch (err) {
      error = "Failed to load analytics data";
      console.error("Error loading analytics:", err);
    } finally {
      loading = false;
    }
  }

  function generateDailyDataFromMetrics(metricsData) {
    // Group metrics by date
    const dateGroups = {};

    // If no metrics data, create placeholder for recent days
    if (!metricsData || metricsData.length === 0) {
      const labels = [];
      const values = [];

      for (let i = timeRange - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString());
        values.push(0);
      }

      return { labels, values };
    }

    // Group metrics by date
    metricsData.forEach((metric) => {
      const date = new Date(metric.timestamp).toLocaleDateString();
      if (!dateGroups[date]) {
        dateGroups[date] = 0;
      }
      if (metric.metric_type === "task_execution") {
        dateGroups[date]++;
      }
    });

    // Generate labels and values for the time range
    const labels = [];
    const values = [];

    for (let i = timeRange - 1; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const dateStr = date.toLocaleDateString();
      labels.push(dateStr);
      values.push(dateGroups[dateStr] || 0);
    }

    return { labels, values };
  }

  function generateTaskTypeDataFromSummary(summary) {
    // Calculate task type distribution from summary data
    const taskTypes = ["Completed", "Failed", "Pending"];

    const values = [
      summary.successful_tasks || 0,
      summary.failed_tasks || 0,
      (summary.total_tasks || 0) -
        (summary.successful_tasks || 0) -
        (summary.failed_tasks || 0),
    ];

    return { labels: taskTypes, values };
  }

  async function generateAgentPerformanceData(summary) {
    try {
      // Get agent data from the API
      const agents = await api.getAgents();

      if (!agents || agents.length === 0) {
        return {
          agents: [],
        };
      }

      // Calculate performance metrics for each agent
      const agentPerformance = agents.map((agent) => ({
        agent_id: agent.id,
        task_count: Math.floor(summary.total_tasks / agents.length), // Distribute evenly
        success_rate:
          summary.total_tasks > 0
            ? (summary.successful_tasks / summary.total_tasks) * 100
            : 0,
        avg_execution_time: summary.average_execution_time_ms / 1000,
        total_cost: parseFloat(summary.cost_today_usd || "0") / agents.length,
      }));

      return { agents: agentPerformance };
    } catch (error) {
      console.error("Error generating agent performance data:", error);
      return { agents: [] };
    }
  }

  async function handleTimeRangeChange(event) {
    timeRange = parseInt(event.target.value);
    await loadAnalytics();
    if (multiProviderEnabled) {
      await loadProviderAnalytics();
    }
  }

  function formatCurrency(amount) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 4,
    }).format(amount || 0);
  }

  function formatNumber(num) {
    return new Intl.NumberFormat("en-US").format(num || 0);
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

    <div class="flex items-center gap-4">
      <!-- Real-time connection status -->
      <div class="flex items-center gap-2">
        <div
          class="w-2 h-2 rounded-full {$analyticsStore.connected
            ? 'bg-green-500'
            : 'bg-red-500'}"
        />
        <span class="text-xs text-gray-400">
          {$analyticsStore.connected ? "Live" : "Offline"}
        </span>
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
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"
      />
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
          <p class="stat-value">
            {formatCurrency(analytics.costSummary.total_cost)}
          </p>
          <p class="stat-subtitle">Last {timeRange} days</p>
        </div>

        <div class="stat-card">
          <h3 class="stat-title">Input Tokens</h3>
          <p class="stat-value">
            {formatNumber(analytics.costSummary.total_input_tokens)}
          </p>
          <p class="stat-subtitle">
            {formatCurrency(analytics.costSummary.input_token_cost)}
          </p>
        </div>

        <div class="stat-card">
          <h3 class="stat-title">Output Tokens</h3>
          <p class="stat-value">
            {formatNumber(analytics.costSummary.total_output_tokens)}
          </p>
          <p class="stat-subtitle">
            {formatCurrency(analytics.costSummary.output_token_cost)}
          </p>
        </div>

        <div class="stat-card">
          <h3 class="stat-title">Tasks Processed</h3>
          <p class="stat-value">
            {formatNumber(analytics.costSummary.task_count)}
          </p>
          <p class="stat-subtitle">
            Avg cost: {formatCurrency(
              analytics.costSummary.average_cost_per_task
            )}
          </p>
        </div>
      </div>
    {/if}

    <!-- Usage Trends -->
    {#if analytics.usageTrends}
      <div class="bg-gray-800 rounded-lg p-6 mb-8">
        <h2 class="text-xl font-semibold text-white mb-4">Usage Trends</h2>

        {#if analytics.usageTrends.daily_usage && analytics.usageTrends.daily_usage.length > 0}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Daily Tasks Chart -->
            <div class="bg-gray-900 rounded-lg p-4">
              <h3 class="text-lg font-medium text-gray-300 mb-3">
                Daily Task Volume
              </h3>
              <div class="h-48">
                <Chart
                  type="line"
                  data={dailyTasksChart}
                  width={400}
                  height={192}
                />
              </div>
            </div>

            <!-- Task Type Distribution -->
            <div class="bg-gray-900 rounded-lg p-4">
              <h3 class="text-lg font-medium text-gray-300 mb-3">
                Task Type Distribution
              </h3>
              <div class="h-48">
                <Chart
                  type="doughnut"
                  data={taskTypeChart}
                  width={400}
                  height={192}
                  options={{
                    plugins: {
                      legend: {
                        position: "bottom",
                        labels: {
                          color: "rgb(156, 163, 175)",
                          padding: 15,
                        },
                      },
                    },
                  }}
                />
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
      <div class="bg-gray-800 rounded-lg p-6 mb-8">
        <h2 class="text-xl font-semibold text-white mb-4">Agent Performance</h2>

        {#if analytics.agentPerformance.agents && analytics.agentPerformance.agents.length > 0}
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b border-gray-700">
                  <th class="text-left py-3 text-gray-400 font-medium">Agent</th
                  >
                  <th class="text-left py-3 text-gray-400 font-medium">Tasks</th
                  >
                  <th class="text-left py-3 text-gray-400 font-medium"
                    >Success Rate</th
                  >
                  <th class="text-left py-3 text-gray-400 font-medium"
                    >Avg Time</th
                  >
                  <th class="text-left py-3 text-gray-400 font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {#each analytics.agentPerformance.agents as agent}
                  <tr class="border-b border-gray-700/50">
                    <td class="py-3 text-white font-mono">{agent.agent_id}</td>
                    <td class="py-3 text-gray-300">{agent.task_count}</td>
                    <td class="py-3">
                      <span
                        class="text-{agent.success_rate >= 95
                          ? 'green'
                          : agent.success_rate >= 80
                          ? 'yellow'
                          : 'red'}-400"
                      >
                        {(agent.success_rate || 0).toFixed(1)}%
                      </span>
                    </td>
                    <td class="py-3 text-gray-300"
                      >{(agent.avg_execution_time || 0).toFixed(1)}s</td
                    >
                    <td class="py-3 text-gray-300"
                      >{formatCurrency(agent.total_cost)}</td
                    >
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

    <!-- Multi-Provider Analytics (if enabled) -->
    {#if multiProviderEnabled}
      <div class="mb-8">
        <h2 class="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span class="bg-gradient-to-r from-blue-500 to-purple-500 w-1 h-8 rounded"></span>
          Multi-Provider Analytics
          {#if loadingProviders}
            <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          {/if}
        </h2>

        <!-- Provider Overview Cards -->
        {#if providerDashboard}
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="stat-card">
              <h3 class="stat-title">Total Providers</h3>
              <p class="stat-value">{providerDashboard.overview.total_providers}</p>
              <p class="stat-subtitle">
                {providerDashboard.overview.healthy_providers} healthy, 
                {providerDashboard.overview.unhealthy_providers} issues
              </p>
            </div>

            <div class="stat-card">
              <h3 class="stat-title">Tasks Today</h3>
              <p class="stat-value">{formatNumber(providerDashboard.overview.total_tasks_today)}</p>
              <p class="stat-subtitle">
                {(providerDashboard.overview.success_rate * 100).toFixed(1)}% success rate
              </p>
            </div>

            <div class="stat-card">
              <h3 class="stat-title">Cost Today</h3>
              <p class="stat-value">{formatCurrency(providerDashboard.overview.total_cost_today)}</p>
              <p class="stat-subtitle">
                Avg: {(providerDashboard.overview.average_response_time / 1000).toFixed(2)}s response
              </p>
            </div>

            <div class="stat-card">
              <h3 class="stat-title">System Health</h3>
              <p class="stat-value">
                {(providerDashboard.system_health.overall_status === 'healthy' ? '✓' : '⚠')} 
                {providerDashboard.system_health.overall_status}
              </p>
              <p class="stat-subtitle">
                {providerDashboard.system_health.legacy_system.agents} legacy agents
              </p>
            </div>
          </div>
        {/if}

        <!-- Provider Health & Cost Charts -->
        {#if providerDashboard && Object.keys(providerDashboard.providers).length > 0}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Provider Health Chart -->
            <div class="bg-gray-800 rounded-lg p-6">
              <h3 class="text-xl font-semibold text-white mb-4">Provider Health Scores</h3>
              <div class="h-64">
                <Chart
                  type="bar"
                  data={providerHealthChart}
                  width={400}
                  height={256}
                  options={{
                    plugins: {
                      legend: { display: false },
                    },
                    scales: {
                      y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { color: 'rgb(156, 163, 175)' },
                        grid: { color: 'rgba(156, 163, 175, 0.1)' }
                      },
                      x: {
                        ticks: { color: 'rgb(156, 163, 175)' },
                        grid: { display: false }
                      }
                    }
                  }}
                />
              </div>
            </div>

            <!-- Provider Cost Distribution -->
            <div class="bg-gray-800 rounded-lg p-6">
              <h3 class="text-xl font-semibold text-white mb-4">Cost Distribution</h3>
              <div class="h-64">
                <Chart
                  type="doughnut"
                  data={providerCostChart}
                  width={400}
                  height={256}
                  options={{
                    plugins: {
                      legend: {
                        position: "bottom",
                        labels: {
                          color: "rgb(156, 163, 175)",
                          padding: 15,
                        },
                      },
                    },
                  }}
                />
              </div>
            </div>
          </div>
        {/if}

        <!-- Provider Performance Comparison -->
        {#if providerPerformance && providerPerformance.comparison}
          <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h3 class="text-xl font-semibold text-white mb-4">Provider Performance Comparison</h3>
            
            <div class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-gray-700">
                    <th class="text-left py-3 text-gray-400 font-medium">Provider</th>
                    <th class="text-left py-3 text-gray-400 font-medium">Type</th>
                    <th class="text-left py-3 text-gray-400 font-medium">Health</th>
                    <th class="text-left py-3 text-gray-400 font-medium">Success Rate</th>
                    <th class="text-left py-3 text-gray-400 font-medium">Avg Response</th>
                    <th class="text-left py-3 text-gray-400 font-medium">Cost/Request</th>
                    <th class="text-left py-3 text-gray-400 font-medium">Requests</th>
                  </tr>
                </thead>
                <tbody>
                  {#each Object.entries(providerPerformance.comparison) as [providerId, provider]}
                    <tr class="border-b border-gray-700/50">
                      <td class="py-3 text-white font-mono">{provider.name}</td>
                      <td class="py-3 text-gray-300">{provider.type}</td>
                      <td class="py-3">
                        <span class="text-{provider.health_score >= 0.9 ? 'green' : provider.health_score >= 0.7 ? 'yellow' : 'red'}-400">
                          {(provider.health_score * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td class="py-3">
                        <span class="text-{provider.success_rate >= 95 ? 'green' : provider.success_rate >= 80 ? 'yellow' : 'red'}-400">
                          {provider.success_rate.toFixed(1)}%
                        </span>
                      </td>
                      <td class="py-3 text-gray-300">{(provider.average_response_time / 1000).toFixed(2)}s</td>
                      <td class="py-3 text-gray-300">{formatCurrency(provider.cost_per_request)}</td>
                      <td class="py-3 text-gray-300">{formatNumber(provider.total_requests)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

            <!-- Performance Rankings -->
            {#if providerPerformance.rankings}
              <div class="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-gray-900 rounded-lg p-4">
                  <h4 class="text-green-400 font-medium mb-2">🏆 Most Reliable</h4>
                  <p class="text-white text-sm">{providerPerformance.rankings.most_reliable[0]?.[1]?.name || 'N/A'}</p>
                </div>
                <div class="bg-gray-900 rounded-lg p-4">
                  <h4 class="text-blue-400 font-medium mb-2">⚡ Fastest</h4>
                  <p class="text-white text-sm">{providerPerformance.rankings.fastest[0]?.[1]?.name || 'N/A'}</p>
                </div>
                <div class="bg-gray-900 rounded-lg p-4">
                  <h4 class="text-yellow-400 font-medium mb-2">💰 Most Cost-Effective</h4>
                  <p class="text-white text-sm">{providerPerformance.rankings.most_cost_effective[0]?.[1]?.name || 'N/A'}</p>
                </div>
                <div class="bg-gray-900 rounded-lg p-4">
                  <h4 class="text-purple-400 font-medium mb-2">💚 Healthiest</h4>
                  <p class="text-white text-sm">{providerPerformance.rankings.healthiest[0]?.[1]?.name || 'N/A'}</p>
                </div>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Cost Optimization Recommendations -->
        {#if costOptimization && costOptimization.recommendations}
          <div class="bg-gray-800 rounded-lg p-6">
            <h3 class="text-xl font-semibold text-white mb-4">Cost Optimization</h3>
            
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
              <div class="bg-green-900/20 border border-green-500/30 rounded-lg p-4">
                <h4 class="text-green-400 font-medium mb-2">Potential Monthly Savings</h4>
                <p class="text-2xl font-bold text-white">{formatCurrency(costOptimization.potential_savings)}</p>
              </div>
              
              <div class="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
                <h4 class="text-blue-400 font-medium mb-2">Optimization Opportunities</h4>
                <p class="text-2xl font-bold text-white">{costOptimization.optimization_opportunities?.length || 0}</p>
              </div>
              
              <div class="bg-purple-900/20 border border-purple-500/30 rounded-lg p-4">
                <h4 class="text-purple-400 font-medium mb-2">Provider Efficiency</h4>
                <p class="text-2xl font-bold text-white">
                  {Object.keys(costOptimization.provider_efficiency || {}).length} analyzed
                </p>
              </div>
            </div>

            {#if costOptimization.optimization_opportunities?.length > 0}
              <div class="space-y-3">
                <h4 class="text-gray-300 font-medium">Recommendations:</h4>
                {#each costOptimization.optimization_opportunities as opportunity}
                  <div class="bg-gray-900 rounded-lg p-4 border-l-4 border-yellow-500">
                    <div class="flex justify-between items-start">
                      <div>
                        <h5 class="text-white font-medium">{opportunity.title || 'Optimization Opportunity'}</h5>
                        <p class="text-gray-400 text-sm mt-1">{opportunity.description || 'Detailed recommendation available'}</p>
                      </div>
                      <span class="text-green-400 font-medium text-sm">
                        {formatCurrency(opportunity.potential_savings || 0)}
                      </span>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
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

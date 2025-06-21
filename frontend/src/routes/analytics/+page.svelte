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

  // Subscribe to real-time analytics updates
  $: if ($analyticsStore.summary) {
    updateAnalyticsFromWebSocket($analyticsStore.summary);
  }

  onMount(async () => {
    await loadAnalytics();
    
    // Request initial analytics data via WebSocket
    analyticsStore.requestAnalytics();
    
    // Subscribe to specific metrics
    analyticsStore.subscribeToMetrics(['task_execution', 'system_metrics']);
  });

  onDestroy(() => {
    // Clean up WebSocket connection
    analyticsStore.disconnect();
  });

  function updateAnalyticsFromWebSocket(summary: any) {
    // Update analytics object with real-time data
    if (analytics.costSummary) {
      analytics.costSummary.task_count = summary.total_tasks;
    }
    
    // Trigger reactive updates for charts
    const mockDailyData = generateMockDailyData();
    const mockTaskTypes = generateMockTaskTypeData();
    
    // Update charts with latest task count influencing the data
    dailyTasksChart = {
      ...dailyTasksChart,
      datasets: [{
        ...dailyTasksChart.datasets[0],
        data: mockDailyData.values.map(v => v + Math.floor(summary.total_tasks * 0.1))
      }]
    };
  }

  async function loadAnalytics() {
    loading = true;
    error = null;

    try {
      // Get analytics summary from the real API
      const summaryResponse = await api.get("/analytics/summary");
      summary = summaryResponse.data;

      // For now, create mock trend data since we don't have historical data yet
      const mockDailyData = generateMockDailyData();
      const mockTaskTypes = generateMockTaskTypeData();

      // Update chart data
      dailyTasksChart = {
        ...dailyTasksChart,
        labels: mockDailyData.labels,
        datasets: [
          {
            ...dailyTasksChart.datasets[0],
            data: mockDailyData.values,
          },
        ],
      };

      taskTypeChart = {
        ...taskTypeChart,
        labels: mockTaskTypes.labels,
        datasets: [
          {
            ...taskTypeChart.datasets[0],
            data: mockTaskTypes.values,
          },
        ],
      };

      // Update analytics object for compatibility
      analytics = {
        costSummary: {
          total_cost: 0,
          total_input_tokens: 0,
          total_output_tokens: 0,
          input_token_cost: 0,
          output_token_cost: 0,
          task_count: summary.total_tasks,
          average_cost_per_task: 0,
        },
        usageTrends: {
          daily_usage: mockDailyData.labels.map((label, i) => ({
            date: label,
            task_count: mockDailyData.values[i],
          })),
          task_type_distribution: mockTaskTypes.labels.reduce(
            (acc, label, i) => {
              acc[label.toLowerCase().replace(" ", "_")] =
                mockTaskTypes.values[i];
              return acc;
            },
            {}
          ),
        },
        agentPerformance: {
          agents: [
            {
              agent_id: "agent-1",
              task_count: Math.floor(summary.total_tasks * 0.4),
              success_rate: 95.2,
              avg_execution_time: summary.average_execution_time_ms / 1000,
              total_cost: 0,
            },
            {
              agent_id: "agent-2",
              task_count: Math.floor(summary.total_tasks * 0.35),
              success_rate: 98.1,
              avg_execution_time:
                (summary.average_execution_time_ms / 1000) * 0.8,
              total_cost: 0,
            },
            {
              agent_id: "agent-3",
              task_count: Math.floor(summary.total_tasks * 0.25),
              success_rate: 92.7,
              avg_execution_time:
                (summary.average_execution_time_ms / 1000) * 1.2,
              total_cost: 0,
            },
          ],
        },
      };
    } catch (err) {
      error = "Failed to load analytics data";
      console.error("Error loading analytics:", err);
    } finally {
      loading = false;
    }
  }

  function generateMockDailyData() {
    const labels = [];
    const values = [];

    for (let i = timeRange - 1; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      labels.push(date.toLocaleDateString());
      values.push(Math.floor(Math.random() * 20) + 5);
    }

    return { labels, values };
  }

  function generateMockTaskTypeData() {
    const taskTypes = [
      "Code Review",
      "Bug Fix",
      "Feature Dev",
      "Refactor",
      "Testing",
    ];
    const values = taskTypes.map(() => Math.floor(Math.random() * 30) + 10);

    return { labels: taskTypes, values };
  }

  async function handleTimeRangeChange(event) {
    timeRange = parseInt(event.target.value);
    await loadAnalytics();
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
        <div class="w-2 h-2 rounded-full {$analyticsStore.connected ? 'bg-green-500' : 'bg-red-500'}"></div>
        <span class="text-xs text-gray-400">
          {$analyticsStore.connected ? 'Live' : 'Offline'}
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
      <div class="bg-gray-800 rounded-lg p-6">
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

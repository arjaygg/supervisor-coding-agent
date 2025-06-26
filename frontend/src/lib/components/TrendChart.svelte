<script lang="ts">
  export let data: Array<{
    timestamp: string;
    value: number;
    labels: Record<string, any>;
    metadata: Record<string, any>;
  }>;
  export let metricType: string;
  export let trendDirection: string;
  export let confidenceScore: number;

  let chartContainer: HTMLDivElement;

  // Simple SVG-based chart implementation
  $: chartData = data.map((point, index) => ({
    ...point,
    x: (index / (data.length - 1)) * 100,
    y: normalizeValue(point.value, data)
  }));

  function normalizeValue(value: number, allData: typeof data): number {
    const values = allData.map(d => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;
    
    if (range === 0) return 50; // Center line if no variation
    
    // Invert Y coordinate (SVG 0,0 is top-left)
    return 90 - ((value - min) / range) * 80; // Use 90-10 range for padding
  }

  function formatValue(value: number): string {
    if (metricType.includes('cost')) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2
      }).format(value);
    } else if (metricType.includes('rate') || metricType.includes('percentage')) {
      return `${value.toFixed(1)}%`;
    } else if (value >= 1000) {
      return new Intl.NumberFormat('en-US', {
        notation: 'compact',
        maximumFractionDigits: 1
      }).format(value);
    } else {
      return value.toFixed(1);
    }
  }

  function formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  }

  function getGradientColor(): string {
    switch (trendDirection) {
      case "increasing": return "stroke-green-500";
      case "decreasing": return "stroke-red-500";
      case "stable": return "stroke-blue-500";
      default: return "stroke-gray-500";
    }
  }

  function getConfidenceOpacity(): number {
    return Math.max(0.3, confidenceScore);
  }

  $: pathData = chartData.length > 1 
    ? `M ${chartData[0].x} ${chartData[0].y} ` + 
      chartData.slice(1).map(point => `L ${point.x} ${point.y}`).join(' ')
    : '';
</script>

<div bind:this={chartContainer} class="trend-chart">
  <div class="chart-container">
    <svg viewBox="0 0 100 100" class="w-full h-32">
      <!-- Grid lines -->
      <defs>
        <pattern id="grid-{metricType}" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e5e7eb" stroke-width="0.5"/>
        </pattern>
      </defs>
      <rect width="100" height="100" fill="url(#grid-{metricType})" opacity="0.3"/>
      
      <!-- Confidence band -->
      {#if chartData.length > 1}
        <path
          d={pathData}
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-opacity={getConfidenceOpacity()}
          class={getGradientColor()}
        />
      {/if}
      
      <!-- Data points -->
      {#each chartData as point, index}
        <circle
          cx={point.x}
          cy={point.y}
          r="1.5"
          fill="currentColor"
          class={getGradientColor()}
          opacity={getConfidenceOpacity()}
        >
          <title>
            {formatTimestamp(point.timestamp)}: {formatValue(point.value)}
          </title>
        </circle>
      {/each}
    </svg>
  </div>

  <!-- Chart Info -->
  <div class="chart-info mt-2">
    <div class="flex justify-between text-xs text-gray-500">
      <span>
        {#if chartData.length > 0}
          Start: {formatValue(data[0].value)}
        {/if}
      </span>
      <span>
        {#if chartData.length > 0}
          End: {formatValue(data[data.length - 1].value)}
        {/if}
      </span>
    </div>
    
    {#if data.length > 1}
      <div class="text-xs text-gray-500 mt-1">
        {data.length} prediction points over {Math.round((new Date(data[data.length - 1].timestamp).getTime() - new Date(data[0].timestamp).getTime()) / (1000 * 60 * 60))} hours
      </div>
    {/if}
  </div>
</div>

<style>
  .trend-chart {
    @apply w-full;
  }
  
  .chart-container {
    @apply bg-gray-50 rounded border p-2;
  }
  
  .chart-info {
    @apply px-2;
  }
</style>
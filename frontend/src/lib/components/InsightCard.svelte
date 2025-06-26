<script lang="ts">
  export let insight: {
    title: string;
    description: string;
    severity: "info" | "warning" | "critical";
    metric_type: string;
    value: number;
    threshold: number;
    recommendation: string;
  };

  function getSeverityIcon(severity: string): string {
    switch (severity) {
      case "critical": return "🚨";
      case "warning": return "⚠️";
      case "info": return "ℹ️";
      default: return "📊";
    }
  }

  function getSeverityColor(severity: string): string {
    switch (severity) {
      case "critical": return "border-red-200 bg-red-50";
      case "warning": return "border-yellow-200 bg-yellow-50";
      case "info": return "border-blue-200 bg-blue-50";
      default: return "border-gray-200 bg-gray-50";
    }
  }

  function getSeverityTextColor(severity: string): string {
    switch (severity) {
      case "critical": return "text-red-800";
      case "warning": return "text-yellow-800";
      case "info": return "text-blue-800";
      default: return "text-gray-800";
    }
  }

  function getSeverityAccentColor(severity: string): string {
    switch (severity) {
      case "critical": return "text-red-600";
      case "warning": return "text-yellow-600";
      case "info": return "text-blue-600";
      default: return "text-gray-600";
    }
  }

  function formatValue(value: number, metricType: string): string {
    if (metricType.includes('cost') || metricType.includes('usd')) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2
      }).format(value);
    } else if (metricType.includes('rate') || metricType.includes('percentage') || metricType.includes('score')) {
      return `${value.toFixed(1)}%`;
    } else if (metricType.includes('time') || metricType.includes('duration')) {
      if (value < 1000) return `${value.toFixed(0)}ms`;
      if (value < 60000) return `${(value / 1000).toFixed(1)}s`;
      return `${(value / 60000).toFixed(1)}m`;
    } else {
      return new Intl.NumberFormat('en-US', {
        maximumFractionDigits: 1
      }).format(value);
    }
  }

  function getValueComparison(): { comparison: string; isExceeded: boolean } {
    const isExceeded = insight.value > insight.threshold;
    const diff = Math.abs(insight.value - insight.threshold);
    const percentage = ((diff / insight.threshold) * 100).toFixed(1);
    
    if (isExceeded) {
      return {
        comparison: `${percentage}% above threshold`,
        isExceeded: true
      };
    } else {
      return {
        comparison: `${percentage}% below threshold`,
        isExceeded: false
      };
    }
  }

  $: valueComparison = getValueComparison();
</script>

<div class="insight-card border rounded-lg p-4 {getSeverityColor(insight.severity)}">
  <div class="flex items-start space-x-3">
    <!-- Icon -->
    <div class="flex-shrink-0 text-xl">
      {getSeverityIcon(insight.severity)}
    </div>
    
    <!-- Content -->
    <div class="flex-1 min-w-0">
      <!-- Header -->
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-medium {getSeverityTextColor(insight.severity)} truncate">
          {insight.title}
        </h3>
        <span class="text-xs {getSeverityAccentColor(insight.severity)} font-mono bg-white px-2 py-1 rounded">
          {insight.metric_type.replace(/_/g, ' ')}
        </span>
      </div>
      
      <!-- Description -->
      <p class="text-sm {getSeverityTextColor(insight.severity)} mb-3">
        {insight.description}
      </p>
      
      <!-- Metrics -->
      <div class="grid grid-cols-2 gap-4 mb-3">
        <div class="bg-white rounded p-2">
          <p class="text-xs text-gray-500">Current Value</p>
          <p class="text-sm font-medium {getSeverityAccentColor(insight.severity)}">
            {formatValue(insight.value, insight.metric_type)}
          </p>
        </div>
        <div class="bg-white rounded p-2">
          <p class="text-xs text-gray-500">Threshold</p>
          <p class="text-sm font-medium text-gray-700">
            {formatValue(insight.threshold, insight.metric_type)}
          </p>
        </div>
      </div>
      
      <!-- Status -->
      <div class="mb-3">
        <div class="flex items-center justify-between text-xs">
          <span class="text-gray-500">Status:</span>
          <span class="{valueComparison.isExceeded ? 'text-red-600' : 'text-green-600'} font-medium">
            {valueComparison.comparison}
          </span>
        </div>
        
        <!-- Progress bar -->
        <div class="mt-1 w-full bg-gray-200 rounded-full h-2">
          <div 
            class="h-2 rounded-full {valueComparison.isExceeded ? 'bg-red-500' : 'bg-green-500'}"
            style="width: {Math.min(100, (insight.value / insight.threshold) * 100)}%"
          ></div>
        </div>
      </div>
      
      <!-- Recommendation -->
      <div class="bg-white rounded p-3 border">
        <p class="text-xs text-gray-500 mb-1">💡 Recommendation</p>
        <p class="text-sm text-gray-700">
          {insight.recommendation}
        </p>
      </div>
    </div>
  </div>
</div>

<style>
  .insight-card {
    @apply transition-all duration-200 hover:shadow-md;
  }
</style>
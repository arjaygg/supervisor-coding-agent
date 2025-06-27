<script lang="ts">
  export let costOptimization: {
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
  } | null;

  export let summary: {
    totalPotentialSavings: number;
    highImpactCount: number;
    quickWins: number;
    averageEfficiency: number;
  } | null;

  function formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  }

  function formatPercentage(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
  }

  function getEffortIcon(effort: string): string {
    switch (effort) {
      case "low": return "🟢";
      case "medium": return "🟡";
      case "high": return "🔴";
      default: return "⚪";
    }
  }

  function getEffortColor(effort: string): string {
    switch (effort) {
      case "low": return "text-green-600 bg-green-100";
      case "medium": return "text-yellow-600 bg-yellow-100";
      case "high": return "text-red-600 bg-red-100";
      default: return "text-gray-600 bg-gray-100";
    }
  }

  function getSavingsImpact(savings: number, total: number): "high" | "medium" | "low" {
    const percentage = (savings / total) * 100;
    if (percentage >= 20) return "high";
    if (percentage >= 10) return "medium";
    return "low";
  }

  function getImpactColor(impact: "high" | "medium" | "low"): string {
    switch (impact) {
      case "high": return "border-l-green-500 bg-green-50";
      case "medium": return "border-l-yellow-500 bg-yellow-50";
      case "low": return "border-l-blue-500 bg-blue-50";
    }
  }

  $: sortedOpportunities = costOptimization?.recommendations.opportunities
    ?.slice()
    .sort((a, b) => b.potential_savings - a.potential_savings) || [];

  $: sortedProviders = costOptimization 
    ? Object.entries(costOptimization.recommendations.provider_efficiency)
        .sort(([,a], [,b]) => b - a)
    : [];
</script>

{#if costOptimization && summary}
  <div class="cost-optimization-panel bg-white rounded-lg shadow">
    <div class="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-green-50 to-blue-50">
      <h2 class="text-lg font-semibold text-gray-900">💰 Cost Optimization Opportunities</h2>
      <p class="text-sm text-gray-600">AI-powered savings recommendations</p>
    </div>

    <div class="p-6">
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-green-700">
            {formatCurrency(summary.totalPotentialSavings)}
          </p>
          <p class="text-sm text-green-600">Monthly Savings</p>
        </div>
        
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-blue-700">{summary.highImpactCount}</p>
          <p class="text-sm text-blue-600">High Impact</p>
        </div>
        
        <div class="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-purple-700">{summary.quickWins}</p>
          <p class="text-sm text-purple-600">Quick Wins</p>
        </div>
        
        <div class="bg-orange-50 border border-orange-200 rounded-lg p-4 text-center">
          <p class="text-2xl font-bold text-orange-700">
            {formatPercentage(summary.averageEfficiency)}
          </p>
          <p class="text-sm text-orange-600">Avg Efficiency</p>
        </div>
      </div>

      <!-- Optimization Opportunities -->
      <div class="mb-6">
        <h3 class="text-md font-medium text-gray-900 mb-4">🎯 Optimization Opportunities</h3>
        <div class="space-y-3">
          {#each sortedOpportunities as opportunity}
            {@const impact = getSavingsImpact(opportunity.potential_savings, summary.totalPotentialSavings)}
            <div class="border-l-4 {getImpactColor(impact)} p-4 rounded-r-lg">
              <div class="flex justify-between items-start mb-2">
                <div class="flex-1">
                  <div class="flex items-center space-x-2 mb-1">
                    <h4 class="font-medium text-gray-900 capitalize">
                      {opportunity.type.replace(/_/g, ' ')}
                    </h4>
                    <span class="text-xs px-2 py-1 rounded-full {getEffortColor(opportunity.implementation_effort)}">
                      {getEffortIcon(opportunity.implementation_effort)} {opportunity.implementation_effort}
                    </span>
                  </div>
                  <p class="text-sm text-gray-600 mb-2">
                    {opportunity.description}
                  </p>
                </div>
                <div class="text-right ml-4">
                  <p class="text-lg font-bold text-green-600">
                    {formatCurrency(opportunity.potential_savings)}
                  </p>
                  <p class="text-xs text-gray-500">per month</p>
                </div>
              </div>
              
              <!-- Savings percentage bar -->
              <div class="w-full bg-gray-200 rounded-full h-2">
                <div 
                  class="h-2 rounded-full bg-green-500"
                  style="width: {Math.min(100, (opportunity.potential_savings / summary.totalPotentialSavings) * 100)}%"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Provider Efficiency -->
      <div>
        <h3 class="text-md font-medium text-gray-900 mb-4">⚡ Provider Efficiency Rankings</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          {#each sortedProviders as [providerId, efficiency], index}
            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div class="flex items-center space-x-3">
                <span class="flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                  {index + 1}
                </span>
                <div>
                  <p class="font-medium text-gray-900 capitalize">
                    {providerId.replace(/-/g, ' ')}
                  </p>
                  <p class="text-sm text-gray-600">Provider</p>
                </div>
              </div>
              <div class="text-right">
                <p class="text-lg font-bold {efficiency >= 0.8 ? 'text-green-600' : efficiency >= 0.6 ? 'text-yellow-600' : 'text-red-600'}">
                  {formatPercentage(efficiency)}
                </p>
                <p class="text-xs text-gray-500">Efficiency</p>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Last Updated -->
      <div class="mt-6 pt-4 border-t border-gray-200 text-center">
        <p class="text-xs text-gray-500">
          Recommendations updated: {new Date(costOptimization.timestamp).toLocaleString()}
        </p>
      </div>
    </div>
  </div>
{/if}

<style>
  .cost-optimization-panel {
    @apply transition-all duration-200;
  }
</style>
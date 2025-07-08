<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { contextService, type ContextOptimization, type ContextWarning } from "$lib/services/contextService";

  export let optimization: ContextOptimization | null = null;
  export let visible: boolean = true;
  export let compact: boolean = false;

  const dispatch = createEventDispatcher();

  let showDetails = false;
  let warnings: ContextWarning[] = [];

  $: if (optimization) {
    warnings = contextService.analyzeContextOptimization(optimization);
  }

  $: hasOptimization = optimization && (optimization.truncated_messages > 0 || optimization.summarized_chunks > 0);

  $: usageColor = optimization ? contextService.getUsageColor(optimization.context_window_used) : 'text-gray-500';

  function toggleDetails() {
    showDetails = !showDetails;
  }

  function handleNewConversation() {
    dispatch('new-conversation');
  }

  function getOptimizationSummary(): string {
    if (!optimization) return '';
    
    const parts = [];
    if (optimization.truncated_messages > 0) {
      parts.push(`${optimization.truncated_messages} messages removed`);
    }
    if (optimization.summarized_chunks > 0) {
      parts.push(`${optimization.summarized_chunks} messages summarized`);
    }
    return parts.join(', ');
  }
</script>

{#if visible && optimization}
  <div 
    class="context-indicator border rounded-lg transition-all duration-200"
    class:bg-gray-800={!compact}
    class:border-gray-600={!compact}
    class:bg-gray-700={compact}
    class:border-gray-500={compact}
    class:p-3={!compact}
    class:p-2={compact}
  >
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-2">
        <!-- Context Usage Indicator -->
        <div class="flex items-center space-x-1">
          <div class="w-2 h-2 rounded-full {usageColor}"></div>
          <span class="text-xs text-gray-400">
            Context: <span class="{usageColor}">{(optimization.context_window_used * 100).toFixed(0)}%</span>
          </span>
        </div>

        <!-- Optimization Status -->
        {#if hasOptimization}
          <div class="flex items-center space-x-1">
            <svg class="w-3 h-3 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span class="text-xs text-blue-400">Optimized</span>
          </div>
        {/if}
      </div>

      <!-- Actions -->
      <div class="flex items-center space-x-1">
        {#if !compact}
          <button
            class="text-xs text-gray-400 hover:text-white transition-colors"
            on:click={toggleDetails}
            title={showDetails ? "Hide details" : "Show details"}
          >
            {showDetails ? "Less" : "More"}
          </button>
        {/if}
        
        {#if optimization.context_window_used > 0.8}
          <button
            class="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
            on:click={handleNewConversation}
            title="Start new conversation"
          >
            New Chat
          </button>
        {/if}
      </div>
    </div>

    <!-- Warnings -->
    {#if warnings.length > 0}
      <div class="mt-2 space-y-1">
        {#each warnings as warning}
          <div 
            class="flex items-start space-x-2 text-xs p-2 rounded"
            class:bg-blue-900/20={warning.severity === 'info'}
            class:text-blue-300={warning.severity === 'info'}
            class:bg-yellow-900/20={warning.severity === 'warning'}
            class:text-yellow-300={warning.severity === 'warning'}
            class:bg-red-900/20={warning.severity === 'error'}
            class:text-red-300={warning.severity === 'error'}
          >
            <svg class="w-3 h-3 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              {#if warning.severity === 'info'}
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
              {:else if warning.severity === 'warning'}
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              {:else}
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              {/if}
            </svg>
            <span>{warning.message}</span>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Detailed Metrics (collapsible) -->
    {#if showDetails && !compact}
      <div class="mt-3 pt-3 border-t border-gray-600">
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span class="text-gray-400">Messages:</span>
            <span class="text-white">{optimization.original_message_count} → {optimization.optimized_message_count}</span>
          </div>
          
          <div>
            <span class="text-gray-400">Context Usage:</span>
            <span class="{usageColor}">{(optimization.context_window_used * 100).toFixed(1)}%</span>
          </div>
          
          {#if optimization.truncated_messages > 0}
            <div>
              <span class="text-gray-400">Removed:</span>
              <span class="text-orange-400">{optimization.truncated_messages}</span>
            </div>
          {/if}
          
          {#if optimization.summarized_chunks > 0}
            <div>
              <span class="text-gray-400">Summarized:</span>
              <span class="text-blue-400">{optimization.summarized_chunks}</span>
            </div>
          {/if}
        </div>

        <!-- Optimization Summary -->
        {#if hasOptimization}
          <div class="mt-2 p-2 bg-gray-700 rounded text-xs text-gray-300">
            <strong>Applied:</strong> {getOptimizationSummary()}
          </div>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .context-indicator {
    animation: slideIn 0.3s ease-out;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(-5px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Accessibility improvements */
  @media (prefers-reduced-motion: reduce) {
    .context-indicator {
      animation: none;
    }
  }
</style>
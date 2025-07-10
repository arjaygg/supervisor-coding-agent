<script lang="ts">
  import { onMount } from "svelte";
  import { pluginService, type Plugin, type ChatFunction } from "$lib/services/pluginService";
  import type { ChatThread } from "$lib/stores/chat";

  export let thread: ChatThread | null = null;
  export let visible = false;

  let plugins: Plugin[] = [];
  let functions: ChatFunction[] = [];
  let loading = false;
  let error: string | null = null;
  let selectedTab: "plugins" | "functions" = "plugins";
  let analysisResult: any = null;
  let analyzingThread = false;

  // Function call test state
  let testFunction: ChatFunction | null = null;
  let testArgs: Record<string, any> = {};
  let testResult: any = null;
  let testLoading = false;

  onMount(() => {
    if (visible) {
      loadData();
    }
  });

  $: if (visible) {
    loadData();
  }

  async function loadData() {
    loading = true;
    error = null;

    try {
      const [pluginsData, functionsData] = await Promise.all([
        pluginService.getPlugins(),
        pluginService.getFunctions(),
      ]);

      plugins = pluginsData;
      functions = functionsData;
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to load plugin data";
    } finally {
      loading = false;
    }
  }

  async function togglePlugin(plugin: Plugin) {
    try {
      if (plugin.enabled) {
        await pluginService.deactivatePlugin(plugin.name);
      } else {
        await pluginService.activatePlugin(plugin.name);
      }
      await loadData(); // Refresh data
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to toggle plugin";
    }
  }

  async function analyzeCurrentThread() {
    if (!thread) return;

    analyzingThread = true;
    error = null;

    try {
      analysisResult = await pluginService.analyzeThread(thread);
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to analyze thread";
    } finally {
      analyzingThread = false;
    }
  }

  function openFunctionTest(func: ChatFunction) {
    testFunction = func;
    testArgs = {};
    testResult = null;

    // Initialize test args with default values
    if (func.parameters.properties) {
      for (const [key, schema] of Object.entries(func.parameters.properties)) {
        const propSchema = schema as any;
        if (propSchema.default !== undefined) {
          testArgs[key] = propSchema.default;
        } else if (func.parameters.required?.includes(key)) {
          // Set reasonable defaults for required fields
          switch (propSchema.type) {
            case "string":
              testArgs[key] = "";
              break;
            case "number":
              testArgs[key] = 0;
              break;
            case "boolean":
              testArgs[key] = false;
              break;
            case "array":
              testArgs[key] = [];
              break;
            case "object":
              testArgs[key] = {};
              break;
          }
        }
      }
    }
  }

  async function testFunctionCall() {
    if (!testFunction) return;

    testLoading = true;
    testResult = null;

    try {
      const validation = pluginService.validateFunctionArgs(testFunction, testArgs);
      if (!validation.valid) {
        testResult = {
          success: false,
          error: `Validation failed: ${validation.errors.join(", ")}`,
        };
        return;
      }

      testResult = await pluginService.callFunction(testFunction.name, testArgs);
    } catch (err) {
      testResult = {
        success: false,
        error: err instanceof Error ? err.message : "Function call failed",
      };
    } finally {
      testLoading = false;
    }
  }

  function formatJSON(obj: any): string {
    return JSON.stringify(obj, null, 2);
  }

  function getStatusColor(status: string): string {
    switch (status) {
      case "healthy":
        return "text-green-400";
      case "unhealthy":
        return "text-red-400";
      default:
        return "text-yellow-400";
    }
  }
</script>

{#if visible}
  <!-- Plugin Manager Modal -->
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black bg-opacity-50"
      on:click={() => (visible = false)}
      on:keydown={(e) => e.key === "Enter" && (visible = false)}
      role="button"
      tabindex="0"
      aria-label="Close plugin manager"
    />

    <!-- Modal Content -->
    <div class="relative bg-gray-800 rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
      <!-- Header -->
      <div class="bg-gray-700 px-6 py-4 border-b border-gray-600">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <h2 class="text-xl font-semibold text-white">Plugin Manager</h2>
            
            <!-- Tab Navigation -->
            <div class="flex space-x-1 bg-gray-600 rounded-lg p-1">
              <button
                class="px-3 py-1 rounded text-sm font-medium transition-colors {selectedTab === 'plugins' ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white'}"
                on:click={() => (selectedTab = "plugins")}
              >
                Plugins ({plugins.length})
              </button>
              <button
                class="px-3 py-1 rounded text-sm font-medium transition-colors {selectedTab === 'functions' ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white'}"
                on:click={() => (selectedTab = "functions")}
              >
                Functions ({functions.length})
              </button>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <!-- Analyze Thread Button -->
            {#if thread}
              <button
                class="px-3 py-1 bg-purple-600 hover:bg-purple-700 rounded text-sm font-medium transition-colors disabled:opacity-50"
                disabled={analyzingThread}
                on:click={analyzeCurrentThread}
              >
                {#if analyzingThread}
                  Analyzing...
                {:else}
                  Analyze Thread
                {/if}
              </button>
            {/if}

            <!-- Refresh Button -->
            <button
              class="p-2 hover:bg-gray-600 rounded transition-colors disabled:opacity-50"
              disabled={loading}
              on:click={loadData}
              title="Refresh"
            >
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>

            <!-- Close Button -->
            <button
              class="p-2 hover:bg-gray-600 rounded transition-colors"
              on:click={() => (visible = false)}
            >
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Error Display -->
      {#if error}
        <div class="bg-red-800 border border-red-600 px-4 py-3 text-red-100">
          <div class="flex items-center">
            <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            {error}
          </div>
        </div>
      {/if}

      <!-- Content -->
      <div class="p-6 overflow-y-auto max-h-[70vh]">
        {#if loading}
          <div class="text-center py-8">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <p class="mt-2 text-gray-400">Loading plugin data...</p>
          </div>
        {:else if selectedTab === "plugins"}
          <!-- Plugins Tab -->
          <div class="space-y-4">
            {#each plugins as plugin}
              <div class="bg-gray-700 rounded-lg p-4 border border-gray-600">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center space-x-3">
                      <h3 class="text-lg font-medium text-white">{plugin.name}</h3>
                      <span class="text-sm text-gray-400">v{plugin.version}</span>
                      <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium {getStatusColor(plugin.health_status)} bg-gray-800">
                        {plugin.health_status}
                      </span>
                    </div>
                    
                    <p class="mt-1 text-gray-300">{plugin.description}</p>
                    
                    <div class="mt-2 flex flex-wrap gap-2">
                      {#each plugin.capabilities as capability}
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-800 text-blue-200">
                          {capability}
                        </span>
                      {/each}
                    </div>

                    <!-- Plugin Metrics -->
                    <div class="mt-3 grid grid-cols-3 gap-4 text-sm text-gray-400">
                      <div>
                        <span class="block text-gray-500">Calls</span>
                        <span class="text-white">{plugin.metrics.calls_count}</span>
                      </div>
                      <div>
                        <span class="block text-gray-500">Success Rate</span>
                        <span class="text-white">{(plugin.metrics.success_rate * 100).toFixed(1)}%</span>
                      </div>
                      <div>
                        <span class="block text-gray-500">Avg Time</span>
                        <span class="text-white">{plugin.metrics.avg_execution_time}ms</span>
                      </div>
                    </div>
                  </div>

                  <div class="ml-4">
                    <button
                      class="px-4 py-2 rounded font-medium transition-colors {plugin.enabled ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-green-600 hover:bg-green-700 text-white'}"
                      on:click={() => togglePlugin(plugin)}
                    >
                      {plugin.enabled ? "Disable" : "Enable"}
                    </button>
                  </div>
                </div>
              </div>
            {/each}

            {#if plugins.length === 0}
              <div class="text-center py-8 text-gray-400">
                <svg class="mx-auto h-12 w-12 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <p class="mt-2">No plugins available</p>
              </div>
            {/if}
          </div>
        {:else}
          <!-- Functions Tab -->
          <div class="space-y-4">
            {#each functions as func}
              <div class="bg-gray-700 rounded-lg p-4 border border-gray-600">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center space-x-3">
                      <h3 class="text-lg font-medium text-white">{func.name}</h3>
                      <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-800 text-purple-200">
                        {func.category}
                      </span>
                      {#if !func.enabled}
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-600 text-gray-300">
                          Disabled
                        </span>
                      {/if}
                    </div>
                    
                    <p class="mt-1 text-gray-300">{func.description}</p>
                    
                    <!-- Parameters -->
                    {#if func.parameters.properties && Object.keys(func.parameters.properties).length > 0}
                      <div class="mt-2">
                        <h4 class="text-sm font-medium text-gray-400">Parameters:</h4>
                        <div class="mt-1 space-y-1">
                          {#each Object.entries(func.parameters.properties) as [name, schema]}
                            <div class="text-sm text-gray-500">
                              <span class="text-gray-300">{name}</span>
                              <span class="text-gray-400">({schema.type})</span>
                              {#if func.parameters.required?.includes(name)}
                                <span class="text-red-400">*</span>
                              {/if}
                              {#if schema.description}
                                - {schema.description}
                              {/if}
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}
                  </div>

                  <div class="ml-4">
                    <button
                      class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded font-medium text-white transition-colors disabled:opacity-50"
                      disabled={!func.enabled}
                      on:click={() => openFunctionTest(func)}
                    >
                      Test Function
                    </button>
                  </div>
                </div>
              </div>
            {/each}

            {#if functions.length === 0}
              <div class="text-center py-8 text-gray-400">
                <svg class="mx-auto h-12 w-12 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p class="mt-2">No functions available</p>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Analysis Results -->
        {#if analysisResult}
          <div class="mt-6 bg-gray-700 rounded-lg p-4 border border-gray-600">
            <h3 class="text-lg font-medium text-white mb-3">Thread Analysis Results</h3>
            
            <div class="space-y-4">
              <!-- Summary -->
              <div>
                <h4 class="text-sm font-medium text-gray-400">Summary</h4>
                <p class="mt-1 text-gray-300">{analysisResult.analysis.summary}</p>
              </div>

              <!-- Metrics -->
              <div class="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span class="block text-gray-500">Messages</span>
                  <span class="text-white">{analysisResult.metrics.message_count}</span>
                </div>
                <div>
                  <span class="block text-gray-500">Complexity</span>
                  <span class="text-white">{analysisResult.analysis.complexity_score}/10</span>
                </div>
                <div>
                  <span class="block text-gray-500">Confidence</span>
                  <span class="text-white">{(analysisResult.metrics.confidence_score * 100).toFixed(1)}%</span>
                </div>
              </div>

              <!-- Recommendations -->
              {#if analysisResult.recommendations.length > 0}
                <div>
                  <h4 class="text-sm font-medium text-gray-400">Recommendations</h4>
                  <div class="mt-2 space-y-2">
                    {#each analysisResult.recommendations as rec}
                      <div class="flex items-start space-x-2">
                        <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium {rec.priority === 'high' ? 'bg-red-800 text-red-200' : rec.priority === 'medium' ? 'bg-yellow-800 text-yellow-200' : 'bg-blue-800 text-blue-200'}">
                          {rec.priority}
                        </span>
                        <div class="flex-1">
                          <p class="text-gray-300">{rec.description}</p>
                          <p class="text-sm text-gray-500">{rec.action}</p>
                        </div>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Function Test Modal -->
{#if testFunction}
  <div class="fixed inset-0 z-60 flex items-center justify-center">
    <div
      class="absolute inset-0 bg-black bg-opacity-50"
      on:click={() => (testFunction = null)}
      on:keydown={(e) => e.key === "Enter" && (testFunction = null)}
      role="button"
      tabindex="0"
      aria-label="Close function test"
    />

    <div class="relative bg-gray-800 rounded-lg max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
      <!-- Header -->
      <div class="bg-gray-700 px-6 py-4 border-b border-gray-600">
        <h3 class="text-lg font-semibold text-white">Test Function: {testFunction.name}</h3>
      </div>

      <div class="p-6 overflow-y-auto">
        <!-- Parameters Input -->
        {#if testFunction.parameters.properties && Object.keys(testFunction.parameters.properties).length > 0}
          <div class="space-y-4">
            <h4 class="text-sm font-medium text-gray-400">Parameters</h4>
            
            {#each Object.entries(testFunction.parameters.properties) as [name, schema]}
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">
                  {name}
                  {#if testFunction.parameters.required?.includes(name)}
                    <span class="text-red-400">*</span>
                  {/if}
                </label>
                
                {#if schema.type === "boolean"}
                  <label class="inline-flex items-center">
                    <input
                      type="checkbox"
                      bind:checked={testArgs[name]}
                      class="rounded border-gray-600 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    />
                    <span class="ml-2 text-gray-300">{schema.description || name}</span>
                  </label>
                {:else if schema.type === "number"}
                  <input
                    type="number"
                    bind:value={testArgs[name]}
                    placeholder={schema.description || "Enter a number"}
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:border-blue-500 focus:ring-blue-500"
                  />
                {:else}
                  <input
                    type="text"
                    bind:value={testArgs[name]}
                    placeholder={schema.description || "Enter value"}
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:border-blue-500 focus:ring-blue-500"
                  />
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-gray-400">This function takes no parameters.</p>
        {/if}

        <!-- Test Result -->
        {#if testResult}
          <div class="mt-6">
            <h4 class="text-sm font-medium text-gray-400 mb-2">Result</h4>
            <div class="bg-gray-900 rounded-lg p-4 border border-gray-600">
              {#if testResult.success}
                <div class="text-green-400 mb-2">✓ Success</div>
                <pre class="text-gray-300 text-sm overflow-x-auto">{formatJSON(testResult.result)}</pre>
              {:else}
                <div class="text-red-400 mb-2">✗ Error</div>
                <p class="text-red-300">{testResult.error}</p>
              {/if}
              
              {#if testResult.execution_time_ms}
                <div class="mt-2 text-xs text-gray-500">
                  Execution time: {testResult.execution_time_ms}ms
                </div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- Actions -->
        <div class="mt-6 flex justify-end space-x-3">
          <button
            class="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded font-medium text-white transition-colors"
            on:click={() => (testFunction = null)}
          >
            Close
          </button>
          <button
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded font-medium text-white transition-colors disabled:opacity-50"
            disabled={testLoading}
            on:click={testFunctionCall}
          >
            {#if testLoading}
              Testing...
            {:else}
              Run Test
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Custom scrollbar styling */
  .overflow-y-auto::-webkit-scrollbar {
    width: 6px;
  }

  .overflow-y-auto::-webkit-scrollbar-track {
    background: #374151;
  }

  .overflow-y-auto::-webkit-scrollbar-thumb {
    background: #6b7280;
    border-radius: 3px;
  }

  .overflow-y-auto::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
  }
</style>
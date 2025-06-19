<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/utils/api';
  import StatusIndicator from '$lib/components/StatusIndicator.svelte';

  let agents = [];
  let loading = true;
  let error = null;

  onMount(async () => {
    try {
      const response = await api.get('/agents');
      agents = response.data || [];
    } catch (err) {
      error = 'Failed to load agents';
      console.error('Error loading agents:', err);
    } finally {
      loading = false;
    }
  });

  function getAgentStatus(agent) {
    const quotaPercentage = (agent.quota_used / agent.quota_limit) * 100;
    if (!agent.is_active) return 'inactive';
    if (quotaPercentage >= 95) return 'error';
    if (quotaPercentage >= 80) return 'warning';
    return 'success';
  }

  function formatDate(dateString) {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  }
</script>

<svelte:head>
  <title>Agents - Supervisor Coding Agent</title>
</svelte:head>

<div class="container mx-auto px-4 py-8">
  <div class="mb-8">
    <h1 class="text-3xl font-bold text-white mb-2">Agents</h1>
    <p class="text-gray-400">Manage and monitor Claude CLI agents</p>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      <span class="ml-3 text-gray-400">Loading agents...</span>
    </div>
  {:else if error}
    <div class="bg-red-900/20 border border-red-500/50 rounded-lg p-4">
      <h3 class="text-red-400 font-semibold mb-2">Error</h3>
      <p class="text-gray-300">{error}</p>
    </div>
  {:else if agents.length === 0}
    <div class="bg-gray-800 rounded-lg p-8 text-center">
      <div class="text-gray-500 mb-4">
        <svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      <h3 class="text-xl font-semibold text-gray-300 mb-2">No Agents Found</h3>
      <p class="text-gray-500">No Claude CLI agents are currently configured.</p>
    </div>
  {:else}
    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {#each agents as agent}
        <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-white">{agent.id}</h3>
            <StatusIndicator status={getAgentStatus(agent)} />
          </div>
          
          <div class="space-y-3">
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-gray-400">Quota Usage</span>
                <span class="text-gray-300">{agent.quota_used} / {agent.quota_limit}</span>
              </div>
              <div class="w-full bg-gray-700 rounded-full h-2">
                <div 
                  class="h-2 rounded-full {getAgentStatus(agent) === 'error' ? 'bg-red-500' : getAgentStatus(agent) === 'warning' ? 'bg-yellow-500' : 'bg-green-500'}"
                  style="width: {Math.min((agent.quota_used / agent.quota_limit) * 100, 100)}%"
                ></div>
              </div>
            </div>
            
            <div class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span class="text-gray-400 block">Status</span>
                <span class="text-gray-300">{agent.is_active ? 'Active' : 'Inactive'}</span>
              </div>
              <div>
                <span class="text-gray-400 block">Last Used</span>
                <span class="text-gray-300">{formatDate(agent.last_used_at)}</span>
              </div>
            </div>
            
            <div class="text-sm">
              <span class="text-gray-400 block">Quota Reset</span>
              <span class="text-gray-300">{formatDate(agent.quota_reset_at)}</span>
            </div>
            
            <div class="flex gap-2 mt-4">
              <button 
                class="btn-secondary text-xs px-3 py-1 {agent.is_active ? 'opacity-50 cursor-not-allowed' : ''}"
                disabled={agent.is_active}
              >
                Activate
              </button>
              <button 
                class="btn-outline text-xs px-3 py-1 {!agent.is_active ? 'opacity-50 cursor-not-allowed' : ''}"
                disabled={!agent.is_active}
              >
                Deactivate
              </button>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>


<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { tasks } from '$lib/stores/tasks';
  
  const dispatch = createEventDispatcher();
  
  function handleCreateTask() {
    dispatch('createTask');
  }
  
  function handleRefresh() {
    dispatch('refresh');
    tasks.fetchTasks();
    tasks.refreshStats();
  }
</script>

<!-- Quick Actions - mobile-first with horizontal scroll -->
<div class="overflow-x-auto pb-2">
  <div class="flex space-x-3 min-w-max">
    <!-- Create Task Button -->
    <button 
      class="btn-primary flex items-center space-x-2"
      on:click={handleCreateTask}
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
      </svg>
      <span>Create Task</span>
    </button>
    
    <!-- Refresh Button -->
    <button 
      class="btn-secondary flex items-center space-x-2"
      on:click={handleRefresh}
      disabled={$tasks.loading}
    >
      <svg 
        class="w-4 h-4" 
        class:animate-spin={$tasks.loading}
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      <span>Refresh</span>
    </button>
    
    <!-- Quick Filter: Active Tasks -->
    <button 
      class="btn-secondary flex items-center space-x-2"
      on:click={() => dispatch('filterTasks', 'active')}
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      <span>Active</span>
      {#if $tasks.length > 0}
        <span class="bg-blue-600 text-white text-xs px-2 py-1 rounded-full">
          {$tasks.filter(t => ['QUEUED', 'IN_PROGRESS'].includes(t.status)).length}
        </span>
      {/if}
    </button>
    
    <!-- Quick Filter: Failed Tasks -->
    {#if $tasks.filter(t => t.status === 'FAILED').length > 0}
      <button 
        class="btn-danger flex items-center space-x-2"
        on:click={() => dispatch('filterTasks', 'failed')}
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <span>Failed</span>
        <span class="bg-red-800 text-white text-xs px-2 py-1 rounded-full">
          {$tasks.filter(t => t.status === 'FAILED').length}
        </span>
      </button>
    {/if}
    
    <!-- Settings/Options -->
    <button 
      class="btn-secondary flex items-center space-x-2"
      on:click={() => dispatch('showSettings')}
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      <span class="hidden md:inline">Settings</span>
    </button>
  </div>
</div>
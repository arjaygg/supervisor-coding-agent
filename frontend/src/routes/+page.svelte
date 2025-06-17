<script lang="ts">
  import { onMount } from 'svelte';
  import { tasks, activeTasks, pendingTasks, completedTasks, failedTasks } from '$lib/stores/tasks';
  import { websocket } from '$lib/stores/websocket';
  import TaskList from '$lib/components/TaskList.svelte';
  import TaskStats from '$lib/components/TaskStats.svelte';
  import QuickActions from '$lib/components/QuickActions.svelte';
  import StatusIndicator from '$lib/components/StatusIndicator.svelte';
  
  let showCreateTaskModal = false;
  let selectedTaskStatus = 'all';
  
  $: filteredTasks = selectedTaskStatus === 'all' ? $tasks : 
                   selectedTaskStatus === 'active' ? $activeTasks :
                   selectedTaskStatus === 'pending' ? $pendingTasks :
                   selectedTaskStatus === 'completed' ? $completedTasks :
                   $failedTasks;
  
  // Refresh data periodically
  onMount(() => {
    const interval = setInterval(async () => {
      await tasks.refreshStats();
    }, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  });
</script>

<svelte:head>
  <title>Dashboard - Supervisor Coding Agent</title>
  <meta name="description" content="AI-powered task orchestration dashboard" />
</svelte:head>

<!-- Mobile-first header -->
<header class="bg-gray-800 border-b border-gray-700 px-4 py-3 md:px-6 md:py-4">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-lg md:text-xl font-bold text-white">Supervisor Agent</h1>
      <div class="flex items-center space-x-2 mt-1">
        <StatusIndicator connected={$websocket.connected} />
        <span class="text-xs text-gray-400">
          {$websocket.connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
    </div>
    
    <!-- Quick stats for mobile -->
    <div class="flex space-x-2 md:hidden">
      <div class="text-center">
        <div class="text-sm font-bold text-white">{$tasks.length}</div>
        <div class="text-xs text-gray-400">Total</div>
      </div>
      <div class="text-center">
        <div class="text-sm font-bold text-blue-400">{$activeTasks.length}</div>
        <div class="text-xs text-gray-400">Active</div>
      </div>
    </div>
  </div>
</header>

<!-- Main content -->
<div class="container mx-auto px-4 py-4 md:px-6 md:py-6 max-w-7xl">
  <!-- Desktop stats grid -->
  <div class="hidden md:block mb-6">
    <TaskStats />
  </div>
  
  <!-- Mobile filter tabs -->
  <div class="mb-4 overflow-x-auto">
    <div class="flex space-x-2 min-w-max pb-2">
      <button 
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === 'all'}
        class:btn-secondary={selectedTaskStatus !== 'all'}
        on:click={() => selectedTaskStatus = 'all'}
      >
        All ({$tasks.length})
      </button>
      <button 
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === 'active'}
        class:btn-secondary={selectedTaskStatus !== 'active'}
        on:click={() => selectedTaskStatus = 'active'}
      >
        Active ({$activeTasks.length})
      </button>
      <button 
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === 'pending'}
        class:btn-secondary={selectedTaskStatus !== 'pending'}
        on:click={() => selectedTaskStatus = 'pending'}
      >
        Pending ({$pendingTasks.length})
      </button>
      <button 
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === 'completed'}
        class:btn-secondary={selectedTaskStatus !== 'completed'}
        on:click={() => selectedTaskStatus = 'completed'}
      >
        Done ({$completedTasks.length})
      </button>
      {#if $failedTasks.length > 0}
        <button 
          class="btn-danger text-sm"
          class:btn-primary={selectedTaskStatus === 'failed'}
          on:click={() => selectedTaskStatus = 'failed'}
        >
          Failed ({$failedTasks.length})
        </button>
      {/if}
    </div>
  </div>
  
  <!-- Quick actions -->
  <div class="mb-4">
    <QuickActions on:createTask={() => showCreateTaskModal = true} />
  </div>
  
  <!-- Task list -->
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-white">
        {selectedTaskStatus === 'all' ? 'All Tasks' :
         selectedTaskStatus === 'active' ? 'Active Tasks' :
         selectedTaskStatus === 'pending' ? 'Pending Tasks' :
         selectedTaskStatus === 'completed' ? 'Completed Tasks' :
         'Failed Tasks'}
      </h2>
      
      <!-- Refresh button -->
      <button 
        class="btn-secondary text-sm"
        on:click={() => tasks.fetchTasks()}
        disabled={$tasks.loading}
      >
        {#if $tasks.loading}
          <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        {:else}
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        {/if}
        Refresh
      </button>
    </div>
    
    <TaskList tasks={filteredTasks} />
  </div>
</div>

<!-- Create task modal (mobile-optimized) -->
{#if showCreateTaskModal}
  <div class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-end md:items-center justify-center p-4">
    <div class="bg-gray-800 rounded-t-lg md:rounded-lg w-full md:max-w-md max-h-[90vh] overflow-y-auto">
      <!-- Mobile drag handle -->
      <div class="md:hidden w-8 h-1 bg-gray-600 rounded-full mx-auto mt-2 mb-4"></div>
      
      <div class="p-4 md:p-6">
        <h3 class="text-lg font-semibold text-white mb-4">Create New Task</h3>
        
        <form on:submit|preventDefault={() => {
          // Handle task creation
          showCreateTaskModal = false;
        }}>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">Task Type</label>
              <select class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                <option value="PR_REVIEW">PR Review</option>
                <option value="CODE_ANALYSIS">Code Analysis</option>
                <option value="BUG_FIX">Bug Fix</option>
                <option value="FEATURE">Feature Development</option>
                <option value="REFACTOR">Refactoring</option>
              </select>
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">Priority</label>
              <select class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
                <option value="1">🔴 Critical</option>
                <option value="3">🟡 High</option>
                <option value="5" selected>🔵 Normal</option>
                <option value="7">🟢 Low</option>
              </select>
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">Description</label>
              <textarea 
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                rows="3"
                placeholder="Describe the task..."
              ></textarea>
            </div>
          </div>
          
          <div class="flex space-x-3 mt-6">
            <button type="submit" class="btn-primary flex-1">Create Task</button>
            <button 
              type="button" 
              class="btn-secondary"
              on:click={() => showCreateTaskModal = false}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}
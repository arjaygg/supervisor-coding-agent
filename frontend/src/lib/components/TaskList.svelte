<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { Task } from '$lib/stores/tasks';
  
  export let tasks: Task[] = [];
  
  const dispatch = createEventDispatcher();
  
  // Priority emoji mapping
  const priorityEmoji = {
    1: '🔴', // Critical
    2: '🔴', // Critical
    3: '🟡', // High
    4: '🟡', // High
    5: '🔵', // Normal
    6: '🔵', // Normal
    7: '🟢', // Low
    8: '🟢', // Low
    9: '🟢', // Low
    10: '🟢' // Low
  };
  
  // Handle keyboard shortcuts for approval/rejection
  function handleKeydown(event: KeyboardEvent, task: Task) {
    if (task.status !== 'PENDING') return;
    
    switch (event.key.toLowerCase()) {
      case 'a':
        event.preventDefault();
        handleApprove(task.id);
        break;
      case 'r':
        event.preventDefault();
        handleReject(task.id);
        break;
      case 'enter':
      case ' ':
        event.preventDefault();
        dispatch('viewTask', { taskId: task.id });
        break;
    }
  }
  
  function handleApprove(taskId: number) {
    dispatch('approveTask', { taskId });
  }
  
  function handleReject(taskId: number) {
    dispatch('rejectTask', { taskId });
  }
  
  function handleRetry(taskId: number) {
    dispatch('retryTask', { taskId });
  }
  
  function formatTaskPayload(payload: any): string {
    if (typeof payload === 'string') return payload;
    if (payload?.title) return payload.title;
    if (payload?.repository) return payload.repository;
    if (payload?.pr_number) return `PR #${payload.pr_number}`;
    if (payload?.description) return payload.description.slice(0, 50) + '...';
    return JSON.stringify(payload).slice(0, 50) + '...';
  }
  
  function formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  }
  
  // Set up global keyboard listeners for focused tasks
  onMount(() => {
    return () => {
      // Cleanup if needed
    };
  });
</script>

{#if tasks.length === 0}
  <div class="card text-center py-8">
    <svg class="w-12 h-12 text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
    <h3 class="text-lg font-medium text-gray-400 mb-2">No tasks found</h3>
    <p class="text-gray-500">Create a new task to get started</p>
  </div>
{:else}
  <div class="space-y-2">
    {#each tasks as task (task.id)}
      <div 
        class="list-item cursor-pointer focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-inset {task.status === 'PENDING' ? 'bg-yellow-900/20 border-yellow-700' : ''}"
        tabindex="0"
        role="button"
        aria-label="Task {task.id}: {task.type}"
        data-testid="task-item-{task.id}"
        on:keydown={(e) => handleKeydown(e, task)}
        on:click={() => dispatch('viewTask', { taskId: task.id })}
      >
        <div class="flex items-start justify-between space-x-3">
          <!-- Task info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center space-x-2 mb-1">
              <!-- Priority indicator -->
              <span class="text-lg" title="Priority {task.priority}">
                {priorityEmoji[task.priority] || '⚪'}
              </span>
              
              <!-- Task type -->
              <span class="text-sm font-medium text-white font-mono">
                {task.type.replace('_', ' ')}
              </span>
              
              <!-- Status badge -->
              <span class="status-{task.status.toLowerCase().replace('_', '-')}">
                {task.status}
              </span>
            </div>
            
            <!-- Task description -->
            <div class="text-sm text-gray-300 mb-2">
              {formatTaskPayload(task.payload)}
            </div>
            
            <!-- Metadata -->
            <div class="flex items-center space-x-4 text-xs text-gray-500">
              <span>ID: {task.id}</span>
              <span>{formatTimestamp(task.created_at)}</span>
              {#if task.assigned_agent_id}
                <span>Agent: {task.assigned_agent_id.slice(-4)}</span>
              {/if}
              {#if task.retry_count > 0}
                <span>Retries: {task.retry_count}</span>
              {/if}
            </div>
            
            <!-- Error message for failed tasks -->
            {#if task.error_message}
              <div class="mt-2 text-xs text-red-400 bg-red-900/20 p-2 rounded">
                {task.error_message}
              </div>
            {/if}
          </div>
          
          <!-- Action buttons -->
          <div class="flex flex-col space-y-1">
            {#if task.status === 'PENDING'}
              <!-- Approval buttons for pending tasks -->
              <div class="flex space-x-1">
                <button 
                  class="btn-primary text-xs px-2 py-1"
                  on:click|stopPropagation={() => handleApprove(task.id)}
                  title="Approve (Press 'a')"
                >
                  ✓ Approve
                </button>
                <button 
                  class="btn-danger text-xs px-2 py-1"
                  on:click|stopPropagation={() => handleReject(task.id)}
                  title="Reject (Press 'r')"
                >
                  ✗ Reject
                </button>
              </div>
            {/if}
            
            {#if task.status === 'FAILED'}
              <!-- Retry button for failed tasks -->
              <button 
                class="btn-secondary text-xs px-2 py-1"
                on:click|stopPropagation={() => handleRetry(task.id)}
                title="Retry task"
              >
                🔄 Retry
              </button>
            {/if}
            
            {#if task.status === 'IN_PROGRESS'}
              <!-- Progress indicator -->
              <div class="flex items-center space-x-1 text-blue-400">
                <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span class="text-xs">Processing...</span>
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
  
  <!-- Keyboard shortcuts help (mobile-hidden) -->
  <div class="hidden md:block mt-4 text-xs text-gray-500">
    <p>Keyboard shortcuts: <kbd class="bg-gray-700 px-1 rounded">A</kbd> Approve, <kbd class="bg-gray-700 px-1 rounded">R</kbd> Reject, <kbd class="bg-gray-700 px-1 rounded">Enter</kbd> View Details</p>
  </div>
{/if}
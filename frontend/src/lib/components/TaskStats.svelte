<script lang="ts">
  import { tasks } from '$lib/stores/tasks';
</script>

<!-- Task statistics grid - mobile-first responsive -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <!-- Total Tasks -->
  <div class="card text-center">
    <div class="text-2xl md:text-3xl font-bold text-white mb-1">
      {$tasks.stats?.total_tasks || 0}
    </div>
    <div class="text-sm text-gray-400">Total Tasks</div>
  </div>
  
  <!-- Pending Tasks -->
  <div class="card text-center">
    <div class="text-2xl md:text-3xl font-bold text-yellow-400 mb-1">
      {$tasks.stats?.by_status?.PENDING || 0}
    </div>
    <div class="text-sm text-gray-400">Pending</div>
  </div>
  
  <!-- Active Tasks (Queued + In Progress) -->
  <div class="card text-center">
    <div class="text-2xl md:text-3xl font-bold text-blue-400 mb-1">
      {($tasks.stats?.by_status?.QUEUED || 0) + ($tasks.stats?.by_status?.IN_PROGRESS || 0)}
    </div>
    <div class="text-sm text-gray-400">Active</div>
  </div>
  
  <!-- Completed Tasks -->
  <div class="card text-center">
    <div class="text-2xl md:text-3xl font-bold text-green-400 mb-1">
      {$tasks.stats?.by_status?.COMPLETED || 0}
    </div>
    <div class="text-sm text-gray-400">Completed</div>
  </div>
</div>

<!-- Task Type Distribution (Desktop only) -->
<div class="hidden md:block">
  <div class="card">
    <h3 class="text-lg font-semibold text-white mb-4">Task Types</h3>
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">
      {#each Object.entries($tasks.stats?.by_type || {}) as [type, count]}
        <div class="flex justify-between items-center p-2 bg-gray-700 rounded">
          <span class="text-sm text-gray-300">
            {type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </span>
          <span class="text-sm font-medium text-white">{count}</span>
        </div>
      {/each}
    </div>
  </div>
</div>

<!-- Failed Tasks Alert (if any) -->
{#if $tasks.stats?.by_status?.FAILED > 0}
  <div class="card border-red-700 bg-red-900/20 mb-4">
    <div class="flex items-center space-x-2">
      <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
      <span class="text-red-400 font-medium">
        {$tasks.stats.by_status.FAILED} task{$tasks.stats.by_status.FAILED !== 1 ? 's' : ''} failed
      </span>
    </div>
  </div>
{/if}
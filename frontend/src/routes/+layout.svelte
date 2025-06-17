<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { websocket } from '$lib/stores/websocket';
  import { tasks } from '$lib/stores/tasks';
  
  // Initialize WebSocket connection and fetch initial data
  onMount(async () => {
    // Connect to WebSocket for real-time updates
    websocket.connect();
    
    // Fetch initial tasks
    await tasks.fetchTasks({ limit: 50 });
    await tasks.refreshStats();
    
    return () => {
      websocket.disconnect();
    };
  });
</script>

<div class="min-h-screen bg-gray-900 text-gray-100">
  <!-- Main content area with mobile-safe spacing -->
  <main class="pb-16 md:pb-0">
    <slot />
  </main>
  
  <!-- Mobile navigation (hidden on desktop) -->
  <nav class="nav-mobile md:hidden">
    <div class="flex">
      <a href="/" class="nav-item" class:active={$page.url.pathname === '/'}>
        <div class="flex flex-col items-center">
          <svg class="w-5 h-5 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          <span class="text-xs">Tasks</span>
        </div>
      </a>
      
      <a href="/agents" class="nav-item" class:active={$page.url.pathname === '/agents'}>
        <div class="flex flex-col items-center">
          <svg class="w-5 h-5 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span class="text-xs">Agents</span>
        </div>
      </a>
      
      <a href="/analytics" class="nav-item" class:active={$page.url.pathname === '/analytics'}>
        <div class="flex flex-col items-center">
          <svg class="w-5 h-5 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <span class="text-xs">Analytics</span>
        </div>
      </a>
      
      <a href="/settings" class="nav-item" class:active={$page.url.pathname === '/settings'}>
        <div class="flex flex-col items-center">
          <svg class="w-5 h-5 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span class="text-xs">Settings</span>
        </div>
      </a>
    </div>
  </nav>
</div>
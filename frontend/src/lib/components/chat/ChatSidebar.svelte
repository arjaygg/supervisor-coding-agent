<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { ChatThread } from '$lib/stores/chat';
  
  export let threads: ChatThread[] = [];
  export let totalUnreadCount: number = 0;
  export let currentThreadId: string | null = null;
  export let isMobile: boolean = false;
  
  const dispatch = createEventDispatcher();
  
  let searchQuery = '';
  let filteredThreads: ChatThread[] = [];
  
  // Filter threads based on search query
  $: {
    if (searchQuery.trim()) {
      filteredThreads = threads.filter(thread => 
        thread.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (thread.description && thread.description.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    } else {
      filteredThreads = threads;
    }
  }
  
  function selectThread(threadId: string) {
    dispatch('selectThread', { threadId });
  }
  
  function deleteThread(threadId: string, event: Event) {
    event.stopPropagation();
    
    if (confirm('Are you sure you want to delete this chat thread?')) {
      dispatch('deleteThread', { threadId });
    }
  }
  
  function formatDate(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) {
      return 'Today';
    } else if (diffDays === 2) {
      return 'Yesterday';
    } else if (diffDays <= 7) {
      return `${diffDays - 1} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  }
  
  function truncateMessage(message: string, maxLength: number = 60): string {
    if (message.length <= maxLength) return message;
    return message.substring(0, maxLength) + '...';
  }
</script>

<div class="h-full flex flex-col bg-gray-800">
  <!-- Header -->
  <div class="p-4 border-b border-gray-700">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-white">Chats</h2>
      
      <div class="flex items-center space-x-2">
        <!-- Unread count badge -->
        {#if totalUnreadCount > 0}
          <span class="bg-blue-600 text-white text-xs font-medium px-2 py-1 rounded-full">
            {totalUnreadCount}
          </span>
        {/if}
        
        <!-- New chat button -->
        <button 
          class="p-2 rounded-lg hover:bg-gray-700 transition-colors text-gray-400 hover:text-white"
          on:click={() => dispatch('newThread')}
          title="New chat"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
        </button>
        
        <!-- Close button (mobile) -->
        {#if isMobile}
          <button 
            class="p-2 rounded-lg hover:bg-gray-700 transition-colors text-gray-400 hover:text-white"
            on:click={() => dispatch('closeSidebar')}
            title="Close sidebar"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        {/if}
      </div>
    </div>
    
    <!-- Search -->
    <div class="relative">
      <input 
        type="text" 
        placeholder="Search chats..." 
        bind:value={searchQuery}
        class="w-full bg-gray-700 border border-gray-600 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      <svg class="w-4 h-4 text-gray-400 absolute left-3 top-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>
  </div>
  
  <!-- Thread list -->
  <div class="flex-1 overflow-y-auto chat-scroll">
    {#if filteredThreads.length === 0}
      <div class="p-4 text-center">
        {#if searchQuery.trim()}
          <p class="text-gray-400 text-sm">No chats found matching "{searchQuery}"</p>
        {:else if threads.length === 0}
          <div class="text-gray-400">
            <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p class="text-sm mb-2">No chats yet</p>
            <button 
              class="text-blue-400 hover:text-blue-300 text-sm font-medium"
              on:click={() => dispatch('newThread')}
            >
              Start your first chat
            </button>
          </div>
        {:else}
          <p class="text-gray-400 text-sm">No active chats</p>
        {/if}
      </div>
    {:else}
      <div class="space-y-1 p-2">
        {#each filteredThreads as thread (thread.id)}
          <button 
            class="w-full text-left p-3 rounded-lg transition-colors relative group {currentThreadId === thread.id ? 'bg-blue-600 hover:bg-blue-700' : 'hover:bg-gray-700'}"
            on:click={() => selectThread(thread.id)}
          >
            <!-- Thread content -->
            <div class="pr-8">
              <div class="flex items-center justify-between mb-1">
                <h3 class="font-medium text-white truncate text-sm">
                  {thread.title}
                </h3>
                
                <!-- Unread badge -->
                {#if thread.unread_count && thread.unread_count > 0}
                  <span class="bg-blue-500 text-white text-xs font-medium px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                    {thread.unread_count > 99 ? '99+' : thread.unread_count}
                  </span>
                {/if}
              </div>
              
              <!-- Last message preview -->
              {#if thread.last_message}
                <p class="text-gray-400 text-xs truncate mb-1">
                  {truncateMessage(thread.last_message)}
                </p>
              {/if}
              
              <!-- Timestamp -->
              {#if thread.updated_at}
                <p class="text-gray-500 text-xs">
                  {formatDate(thread.updated_at)}
                </p>
              {/if}
            </div>
            
            <!-- Delete button -->
            <button 
              class="absolute top-3 right-3 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-400 hover:bg-gray-600"
              on:click={(e) => deleteThread(thread.id, e)}
              title="Delete chat"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </button>
        {/each}
      </div>
    {/if}
  </div>
  
  <!-- Footer -->
  <div class="p-4 border-t border-gray-700">
    <div class="flex items-center justify-between text-xs text-gray-400">
      <span>{threads.length} chat{threads.length !== 1 ? 's' : ''}</span>
      <div class="flex items-center space-x-1">
        <div class="w-2 h-2 rounded-full bg-green-400"></div>
        <span>Online</span>
      </div>
    </div>
  </div>
</div>
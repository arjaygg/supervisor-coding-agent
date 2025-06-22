<script lang="ts">
  import type { ChatMessage } from '$lib/stores/chat';
  
  export let message: ChatMessage;
  export let showTimestamp: boolean = true;
  export let time: string = '';
  
  // Get avatar and styling based on role
  $: isUser = message.role === 'USER';
  $: isAssistant = message.role === 'ASSISTANT';
  $: isSystem = message.role === 'SYSTEM';
  
  // Format content based on message type
  function formatContent(content: string, messageType: string): string {
    // TODO: Add markdown parsing, code highlighting, etc.
    return content;
  }
  
  // Get message type styling
  function getMessageTypeClass(messageType: string): string {
    switch (messageType) {
      case 'TASK_BREAKDOWN':
        return 'border-l-4 border-yellow-500 bg-yellow-900/20';
      case 'PROGRESS':
        return 'border-l-4 border-blue-500 bg-blue-900/20';
      case 'NOTIFICATION':
        return 'border-l-4 border-green-500 bg-green-900/20';
      case 'ERROR':
        return 'border-l-4 border-red-500 bg-red-900/20';
      default:
        return '';
    }
  }
  
  // Get message type icon
  function getMessageTypeIcon(messageType: string): string {
    switch (messageType) {
      case 'TASK_BREAKDOWN':
        return 'M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01';
      case 'PROGRESS':
        return 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z';
      case 'NOTIFICATION':
        return 'M15 17h5l-5 5v-5zM13 3h8v8l-8-8zM3 12l9-9v9H3z';
      case 'ERROR':
        return 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
      default:
        return '';
    }
  }
</script>

<div class="flex {isUser ? 'justify-end' : 'justify-start'} space-x-3">
  <!-- Avatar (for assistant and system messages) -->
  {#if !isUser}
    <div class="flex-shrink-0">
      <div class="w-8 h-8 rounded-full flex items-center justify-center {isAssistant ? 'bg-blue-600' : 'bg-gray-600'}">
        {#if isAssistant}
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        {:else}
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        {/if}
      </div>
    </div>
  {/if}
  
  <!-- Message content -->
  <div class="flex-1 max-w-xs sm:max-w-md md:max-w-lg lg:max-w-xl xl:max-w-2xl">
    <div class="
      {isUser ? 'bg-blue-600 text-white ml-auto' : 'bg-gray-800 text-white'}
      {getMessageTypeClass(message.message_type)}
      rounded-lg p-3 shadow-sm
      {isUser ? 'rounded-br-sm' : 'rounded-bl-sm'}
    ">
      <!-- Message type indicator -->
      {#if message.message_type !== 'TEXT' && getMessageTypeIcon(message.message_type)}
        <div class="flex items-center space-x-2 mb-2 text-sm opacity-75">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={getMessageTypeIcon(message.message_type)} />
          </svg>
          <span class="capitalize">
            {message.message_type.toLowerCase().replace('_', ' ')}
          </span>
        </div>
      {/if}
      
      <!-- Message content -->
      <div class="prose prose-sm {isUser ? 'prose-invert' : 'prose-invert'} max-w-none">
        <p class="whitespace-pre-wrap break-words m-0">
          {formatContent(message.content, message.message_type)}
        </p>
      </div>
      
      <!-- Metadata (if any) -->
      {#if message.metadata && Object.keys(message.metadata).length > 0}
        <div class="mt-2 pt-2 border-t border-opacity-20 {isUser ? 'border-white' : 'border-gray-600'}">
          {#if message.metadata.task_id}
            <div class="text-xs opacity-75">
              Related to task: <code class="bg-black bg-opacity-20 px-1 rounded">{message.metadata.task_id}</code>
            </div>
          {/if}
          
          {#if message.metadata.progress}
            <div class="text-xs opacity-75 mt-1">
              Progress: {message.metadata.progress}%
            </div>
          {/if}
        </div>
      {/if}
    </div>
    
    <!-- Timestamp and status -->
    {#if showTimestamp}
      <div class="flex items-center space-x-2 mt-1 {isUser ? 'justify-end' : 'justify-start'}">
        <span class="text-xs text-gray-400">
          {time}
        </span>
        
        {#if message.edited_at}
          <span class="text-xs text-gray-500">(edited)</span>
        {/if}
        
        <!-- Read status (for user messages) -->
        {#if isUser}
          <div class="flex space-x-1">
            <svg class="w-3 h-3 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </div>
        {/if}
      </div>
    {/if}
  </div>
  
  <!-- Avatar (for user messages) -->
  {#if isUser}
    <div class="flex-shrink-0">
      <div class="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center">
        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      </div>
    </div>
  {/if}
</div>
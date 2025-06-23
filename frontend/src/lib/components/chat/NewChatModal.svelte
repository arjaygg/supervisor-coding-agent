<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  let titleInput: HTMLInputElement;
  let title = '';
  let message = '';
  let isCreating = false;
  
  // Predefined templates
  const templates = [
    {
      title: 'General Discussion',
      description: 'Ask questions or start a general conversation',
      icon: '💬',
      titleTemplate: 'General Chat',
      messageTemplate: 'Hello! I need help with...'
    },
    {
      title: 'Task Creation',
      description: 'Create and manage development tasks',
      icon: '📋',
      titleTemplate: 'New Task',
      messageTemplate: 'I need to create a task for...'
    },
    {
      title: 'Code Review',
      description: 'Get feedback on your code',
      icon: '🔍',
      titleTemplate: 'Code Review',
      messageTemplate: 'Please review this code:\n\n```\n// Your code here\n```'
    },
    {
      title: 'Bug Report',
      description: 'Report and debug issues',
      icon: '🐛',
      titleTemplate: 'Bug Report',
      messageTemplate: 'I found a bug in...\n\nSteps to reproduce:\n1. \n2. \n3. \n\nExpected: \nActual: '
    },
    {
      title: 'Feature Request',
      description: 'Discuss new features or improvements',
      icon: '✨',
      titleTemplate: 'Feature Request',
      messageTemplate: 'I would like to implement a feature that...'
    },
    {
      title: 'Architecture Discussion',
      description: 'Plan system architecture and design',
      icon: '🏗️',
      titleTemplate: 'Architecture Planning',
      messageTemplate: 'I need to design the architecture for...'
    }
  ];
  
  onMount(() => {
    if (titleInput) {
      titleInput.focus();
    }
  });
  
  function useTemplate(template: typeof templates[0]) {
    title = template.titleTemplate;
    message = template.messageTemplate;
    
    // Focus the message input after template selection
    setTimeout(() => {
      const messageInput = document.querySelector('#chat-message-input') as HTMLTextAreaElement;
      if (messageInput) {
        messageInput.focus();
        // Position cursor at the end
        messageInput.setSelectionRange(messageInput.value.length, messageInput.value.length);
      }
    }, 100);
  }
  
  async function handleSubmit() {
    if (!title.trim()) return;
    
    isCreating = true;
    
    try {
      dispatch('create', {
        title: title.trim(),
        message: message.trim() || undefined
      });
    } catch (error) {
      console.error('Failed to create chat:', error);
      isCreating = false;
    }
  }
  
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      dispatch('close');
    } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      handleSubmit();
    }
  }
  
  function handleBackdropClick(event: Event) {
    if (event.target === event.currentTarget) {
      dispatch('close');
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- Modal backdrop -->
<div 
  class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
  on:click={handleBackdropClick}
  role="dialog"
  aria-labelledby="modal-title"
  aria-modal="true"
>
  <!-- Modal content -->
  <div class="bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
    <!-- Header -->
    <div class="px-6 py-4 border-b border-gray-700">
      <div class="flex items-center justify-between">
        <h2 id="modal-title" class="text-xl font-semibold text-white">Start New Chat</h2>
        <button 
          class="p-2 rounded-lg hover:bg-gray-700 transition-colors text-gray-400 hover:text-white"
          on:click={() => dispatch('close')}
          aria-label="Close modal"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
    
    <!-- Content -->
    <div class="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
      <!-- Templates section -->
      <div class="mb-6">
        <h3 class="text-lg font-medium text-white mb-4">Choose a template</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          {#each templates as template}
            <button
              class="text-left p-4 rounded-lg border border-gray-600 hover:border-gray-500 hover:bg-gray-700 transition-colors group"
              on:click={() => useTemplate(template)}
            >
              <div class="flex items-start space-x-3">
                <span class="text-2xl">{template.icon}</span>
                <div class="flex-1 min-w-0">
                  <h4 class="font-medium text-white group-hover:text-blue-400 transition-colors">
                    {template.title}
                  </h4>
                  <p class="text-sm text-gray-400 mt-1">
                    {template.description}
                  </p>
                </div>
              </div>
            </button>
          {/each}
        </div>
      </div>
      
      <!-- Divider -->
      <div class="relative my-6">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-gray-600"></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-2 bg-gray-800 text-gray-400">Or create custom chat</span>
        </div>
      </div>
      
      <!-- Custom chat form -->
      <form on:submit|preventDefault={handleSubmit} class="space-y-4">
        <!-- Title input -->
        <div>
          <label for="chat-title" class="block text-sm font-medium text-gray-300 mb-2">
            Chat Title *
          </label>
          <input
            id="chat-title"
            bind:this={titleInput}
            bind:value={title}
            type="text"
            required
            maxlength="100"
            placeholder="e.g., User Authentication Feature"
            class="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isCreating}
          />
        </div>
        
        <!-- Initial message input -->
        <div>
          <label for="chat-message-input" class="block text-sm font-medium text-gray-300 mb-2">
            Initial Message (optional)
          </label>
          <textarea
            id="chat-message-input"
            bind:value={message}
            rows="4"
            maxlength="2000"
            placeholder="Start the conversation with a message..."
            class="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            disabled={isCreating}
          ></textarea>
          <div class="mt-1 text-xs text-gray-500">
            {message.length}/2000 characters
          </div>
        </div>
      </form>
    </div>
    
    <!-- Footer -->
    <div class="px-6 py-4 border-t border-gray-700 bg-gray-850">
      <div class="flex items-center justify-between">
        <div class="text-xs text-gray-400">
          Press <kbd class="bg-gray-700 px-1 py-0.5 rounded">Cmd+Enter</kbd> to create
        </div>
        
        <div class="flex space-x-3">
          <button 
            type="button"
            class="px-4 py-2 text-gray-400 hover:text-white transition-colors"
            on:click={() => dispatch('close')}
            disabled={isCreating}
          >
            Cancel
          </button>
          
          <button 
            type="button"
            class="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium"
            on:click={handleSubmit}
            disabled={!title.trim() || isCreating}
          >
            {#if isCreating}
              <div class="flex items-center space-x-2">
                <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Creating...</span>
              </div>
            {:else}
              Create Chat
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  kbd {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    font-size: 0.75rem;
  }
</style>
<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    chat,
    currentThread,
    currentMessages,
    activeThreads,
    totalUnreadCount,
  } from "$lib/stores/chat";
  import { websocket } from "$lib/stores/websocket";
  import ChatSidebar from "./ChatSidebar.svelte";
  import ChatArea from "./ChatArea.svelte";
  import NewChatModal from "./NewChatModal.svelte";
  import MessageSearch from "./MessageSearch.svelte";
  import PluginManager from "./PluginManager.svelte";
  import { messageSearchService } from "$lib/services/messageSearchService";
  import type { SearchResult } from "$lib/services/messageSearchService";

  // Component state
  let showNewChatModal = false;
  let sidebarCollapsed = false;
  let isMobile = false;

  // Search state
  let showSearchModal = false;
  let searchLoading = false;
  let searchComponent: MessageSearch;

  // Plugin state
  let showPluginManager = false;

  // Check screen size
  function checkScreenSize() {
    if (typeof window !== "undefined") {
      const previousMobile = isMobile;
      isMobile = window.innerWidth < 768;

      // Auto-collapse sidebar when becoming mobile
      if (isMobile && !previousMobile) {
        sidebarCollapsed = true;
      }
      // Auto-expand sidebar when becoming desktop (optional)
      else if (!isMobile && previousMobile) {
        sidebarCollapsed = false;
      }
    }
  }

  // Initialize and fetch data
  onMount(async () => {
    // Initialize mobile state and sidebar
    if (typeof window !== "undefined") {
      isMobile = window.innerWidth < 768;
      sidebarCollapsed = isMobile; // Sidebar starts collapsed on mobile
    }

    window.addEventListener("resize", checkScreenSize);

    // Connect WebSocket
    websocket.connect();

    // Initial data load
    try {
      await chat.fetchThreads();
      await chat.fetchNotifications();
    } catch (error) {
      console.error("Failed to load initial chat data:", error);
    }
  });

  onDestroy(() => {
    if (typeof window !== "undefined") {
      window.removeEventListener("resize", checkScreenSize);
      window.removeEventListener("keydown", handleGlobalKeydown);
    }
    websocket.disconnect();
  });

  // Global keyboard shortcuts
  function handleGlobalKeydown(event: KeyboardEvent) {
    // Ctrl+K or Cmd+K to open search
    if ((event.ctrlKey || event.metaKey) && event.key === "k") {
      event.preventDefault();
      showSearchModal = true;
    }
    
    // Escape to close modals
    if (event.key === "Escape") {
      if (showSearchModal) {
        showSearchModal = false;
      } else if (showNewChatModal) {
        showNewChatModal = false;
      } else if (showPluginManager) {
        showPluginManager = false;
      }
    }
  }

  // Initialize global keyboard shortcuts
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", handleGlobalKeydown);
  }

  // Handle new thread creation
  async function handleCreateThread(event: CustomEvent) {
    const { title, message } = event.detail;

    try {
      await chat.createThread(title, message);
      showNewChatModal = false;
    } catch (error) {
      console.error("Failed to create thread:", error);
    }
  }

  // Handle thread selection
  function handleSelectThread(event: CustomEvent) {
    const threadId = event.detail.threadId;
    chat.selectThread(threadId);

    // On mobile, collapse sidebar when thread is selected
    if (isMobile) {
      sidebarCollapsed = true;
    }
  }

  // Handle thread deletion
  async function handleDeleteThread(event: CustomEvent) {
    const threadId = event.detail.threadId;

    try {
      await chat.deleteThread(threadId);
    } catch (error) {
      console.error("Failed to delete thread:", error);
    }
  }

  // Toggle sidebar
  function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
  }

  // Handle creating new conversation from context optimization
  async function handleCreateNewConversation(event: CustomEvent) {
    const { currentThreadId } = event.detail;
    
    try {
      // Create a new thread with a title indicating it's a continuation
      const currentThread = $activeThreads.find(t => t.id === currentThreadId);
      const newTitle = currentThread ? `${currentThread.title} (continued)` : "New Conversation";
      
      await chat.createThread(newTitle);
      
      // The new thread will be automatically selected
      // On mobile, collapse sidebar when new thread is created
      if (isMobile) {
        sidebarCollapsed = true;
      }
    } catch (error) {
      console.error("Failed to create new conversation:", error);
    }
  }

  // Search functionality
  async function handleSearch(event: CustomEvent) {
    const { query, filters } = event.detail;
    searchLoading = true;

    try {
      const results = await messageSearchService.searchMessages(
        query,
        filters,
        $activeThreads,
        $chat.messages
      );

      searchComponent?.setSearchResults(results);
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      searchLoading = false;
    }
  }

  function handleSearchSelectMessage(event: CustomEvent) {
    const { message, threadId } = event.detail;
    
    // Switch to the thread containing the message
    chat.selectThread(threadId);
    
    // Close search modal
    showSearchModal = false;

    // Scroll to message (implementation would depend on ChatArea component)
    // This could be enhanced to highlight the specific message
  }

  function handleSearchExport(event: CustomEvent) {
    const { format, results, query } = event.detail;
    const timestamp = new Date().toISOString().split('T')[0];
    
    if (format === "json") {
      const content = messageSearchService.exportToJSON(query, {
        threads: [],
        dateRange: "",
        messageType: "all",
        role: "all",
      }, results);
      
      messageSearchService.downloadExport(
        content,
        `message-search-${timestamp}.json`,
        "application/json"
      );
    } else if (format === "markdown") {
      const content = messageSearchService.exportToMarkdown(query, {
        threads: [],
        dateRange: "",
        messageType: "all",
        role: "all",
      }, results);
      
      messageSearchService.downloadExport(
        content,
        `message-search-${timestamp}.md`,
        "text/markdown"
      );
    }
  }
</script>

<svelte:head>
  <title>Chat - Supervisor Agent</title>
  <meta
    name="description"
    content="AI-powered chat interface for task management"
  />
</svelte:head>

<!-- Main chat interface -->
<div class="flex h-screen bg-gray-900 text-white overflow-hidden">
  <!-- Sidebar -->
  <div class="relative">
    <!-- Mobile overlay - only show when mobile AND sidebar is expanded -->
    {#if isMobile && !sidebarCollapsed && typeof window !== "undefined" && window.innerWidth < 768}
      <div
        class="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
        on:click={toggleSidebar}
        on:keydown={(e) => e.key === "Enter" && toggleSidebar()}
        role="button"
        tabindex="0"
        aria-label="Close sidebar"
      />
    {/if}

    <!-- Sidebar content -->
    <div
      class="
      {sidebarCollapsed ? '-translate-x-full' : 'translate-x-0'}
      {isMobile ? 'fixed z-40' : 'relative'}
      w-80 h-full bg-gray-800 border-r border-gray-700 transform transition-transform duration-300 ease-in-out
    "
    >
      <ChatSidebar
        threads={$activeThreads}
        {totalUnreadCount}
        currentThreadId={$currentThread?.id}
        on:selectThread={handleSelectThread}
        on:deleteThread={handleDeleteThread}
        on:newThread={() => (showNewChatModal = true)}
        on:closeSidebar={toggleSidebar}
        {isMobile}
      />
    </div>
  </div>

  <!-- Main chat area -->
  <div class="flex-1 flex flex-col min-w-0">
    <!-- Header -->
    <header
      class="bg-gray-800 border-b border-gray-700 px-4 py-3 flex items-center justify-between"
    >
      <!-- Mobile menu button -->
      <button
        class="md:hidden p-2 rounded-lg hover:bg-gray-700 transition-colors"
        on:click={toggleSidebar}
        aria-label="Toggle sidebar"
      >
        <svg
          class="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>

      <!-- Current thread title -->
      <div class="flex-1 px-4">
        {#if $currentThread}
          <h1 class="text-lg font-semibold text-white truncate">
            {$currentThread.title}
          </h1>
          <div class="flex items-center space-x-2 mt-1">
            <div
              class="w-2 h-2 rounded-full {$chat.connected
                ? 'bg-green-400'
                : 'bg-red-400'}"
            />
            <span class="text-xs text-gray-400">
              {$chat.connected ? "Connected" : "Disconnected"}
            </span>
          </div>
        {:else}
          <h1 class="text-lg font-semibold text-gray-400">
            Select a chat or create a new one
          </h1>
        {/if}
      </div>

      <!-- Action buttons -->
      <div class="flex items-center space-x-2">
        <!-- Search button -->
        <button
          class="p-2 rounded-lg hover:bg-gray-700 transition-colors text-gray-400 hover:text-white"
          title="Search messages (Ctrl+K)"
          on:click={() => (showSearchModal = true)}
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </button>

        <!-- Plugin Manager button -->
        <button
          class="p-2 rounded-lg hover:bg-gray-700 transition-colors text-gray-400 hover:text-white"
          title="Plugin Manager"
          on:click={() => (showPluginManager = true)}
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            />
          </svg>
        </button>

        {#if $currentThread}
          <button
            class="p-2 rounded-lg hover:bg-gray-700 transition-colors text-gray-400 hover:text-white"
            title="Thread settings"
          >
            <svg
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
              />
            </svg>
          </button>
        {/if}

        <button
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors text-sm font-medium"
          on:click={() => (showNewChatModal = true)}
        >
          New Chat
        </button>
      </div>
    </header>

    <!-- Chat area -->
    <div class="flex-1 overflow-hidden">
      {#if $currentThread}
        <ChatArea
          thread={$currentThread}
          messages={$currentMessages}
          loading={$chat.loading}
          error={$chat.error}
          on:new-conversation={handleCreateNewConversation}
        />
      {:else}
        <!-- Welcome screen -->
        <div class="h-full flex items-center justify-center p-8">
          <div class="text-center max-w-md">
            <div
              class="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4"
            >
              <svg
                class="w-8 h-8 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>

            <h2 class="text-xl font-semibold text-white mb-2">
              Welcome to Supervisor Agent Chat
            </h2>
            <p class="text-gray-400 mb-6">
              Start a conversation to create tasks, get help, or manage your
              projects.
            </p>

            <button
              class="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors font-medium"
              on:click={() => (showNewChatModal = true)}
            >
              Start Your First Chat
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- Error notification -->
{#if $chat.error}
  <div class="fixed top-4 right-4 z-50 max-w-md">
    <div class="bg-red-800 border border-red-600 rounded-lg p-4 shadow-lg">
      <div class="flex items-start">
        <svg
          class="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clip-rule="evenodd"
          />
        </svg>
        <div class="flex-1">
          <h4 class="text-sm font-medium text-red-100 mb-1">Error</h4>
          <p class="text-sm text-red-200">{$chat.error}</p>
        </div>
        <button
          class="ml-3 text-red-400 hover:text-red-300"
          on:click={() => chat.clearError()}
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- New chat modal -->
{#if showNewChatModal}
  <NewChatModal
    on:create={handleCreateThread}
    on:close={() => (showNewChatModal = false)}
  />
{/if}

<!-- Message search modal -->
<MessageSearch
  bind:this={searchComponent}
  bind:isOpen={showSearchModal}
  bind:loading={searchLoading}
  threads={$activeThreads}
  on:search={handleSearch}
  on:selectMessage={handleSearchSelectMessage}
  on:export={handleSearchExport}
  on:close={() => (showSearchModal = false)}
/>

<!-- Plugin Manager -->
<PluginManager
  bind:visible={showPluginManager}
  thread={$currentThread}
/>

<style>
  /* Custom scrollbar for webkit browsers */
  :global(.chat-scroll::-webkit-scrollbar) {
    width: 6px;
  }

  :global(.chat-scroll::-webkit-scrollbar-track) {
    background: #374151;
  }

  :global(.chat-scroll::-webkit-scrollbar-thumb) {
    background: #6b7280;
    border-radius: 3px;
  }

  :global(.chat-scroll::-webkit-scrollbar-thumb:hover) {
    background: #9ca3af;
  }
</style>

<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { ChatThread, ChatMessage } from "$lib/stores/chat";

  export let threads: ChatThread[] = [];
  export let isOpen: boolean = false;
  export let loading: boolean = false;

  const dispatch = createEventDispatcher();

  // Search state
  let searchQuery = "";
  let searchResults: (ChatMessage & { threadTitle: string })[] = [];
  let selectedFilters = {
    threads: [] as string[],
    dateRange: "",
    messageType: "all",
    role: "all",
  };
  let showAdvancedFilters = false;

  // Debounced search
  let searchTimeout: NodeJS.Timeout;
  
  $: if (searchQuery) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      performSearch();
    }, 300);
  }

  async function performSearch() {
    if (!searchQuery.trim()) {
      searchResults = [];
      return;
    }

    dispatch("search", {
      query: searchQuery,
      filters: selectedFilters,
    });
  }

  function clearSearch() {
    searchQuery = "";
    searchResults = [];
    selectedFilters = {
      threads: [],
      dateRange: "",
      messageType: "all", 
      role: "all",
    };
  }

  function selectMessage(message: ChatMessage) {
    dispatch("selectMessage", {
      message,
      threadId: message.thread_id,
    });
    closeModal();
  }

  function closeModal() {
    isOpen = false;
    dispatch("close");
  }

  function exportResults(format: "json" | "markdown") {
    dispatch("export", {
      format,
      results: searchResults,
      query: searchQuery,
    });
  }

  // Handle search results from parent
  export function setSearchResults(results: (ChatMessage & { threadTitle: string })[]) {
    searchResults = results;
  }

  // Keyboard shortcuts
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      closeModal();
    } else if (event.key === "Enter" && event.ctrlKey) {
      performSearch();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <div
    class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
    on:click={closeModal}
    on:keydown={(e) => e.key === "Enter" && closeModal()}
    role="button"
    tabindex="0"
    aria-label="Close search modal"
  >
    <div
      class="bg-gray-800 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden"
      on:click|stopPropagation
      on:keydown|stopPropagation
      role="dialog"
      aria-labelledby="search-title"
      aria-modal="true"
    >
      <!-- Header -->
      <div class="border-b border-gray-700 p-4">
        <div class="flex items-center justify-between mb-4">
          <h2 id="search-title" class="text-xl font-semibold text-white">
            Search Messages
          </h2>
          <button
            class="text-gray-400 hover:text-white p-2 rounded-lg hover:bg-gray-700"
            on:click={closeModal}
            aria-label="Close search"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <!-- Search input -->
        <div class="relative">
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search messages... (Ctrl+Enter to search)"
            class="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 pl-10 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            autofocus
          />
          <svg
            class="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400"
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
        </div>

        <!-- Quick actions -->
        <div class="flex items-center justify-between mt-4">
          <div class="flex space-x-2">
            <button
              class="btn-secondary text-sm"
              on:click={() => (showAdvancedFilters = !showAdvancedFilters)}
            >
              <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
                />
              </svg>
              Filters
            </button>
            <button class="btn-secondary text-sm" on:click={clearSearch}>
              Clear
            </button>
          </div>

          {#if searchResults.length > 0}
            <div class="flex space-x-2">
              <button
                class="btn-secondary text-sm"
                on:click={() => exportResults("json")}
              >
                Export JSON
              </button>
              <button
                class="btn-secondary text-sm"
                on:click={() => exportResults("markdown")}
              >
                Export MD
              </button>
            </div>
          {/if}
        </div>

        <!-- Advanced filters -->
        {#if showAdvancedFilters}
          <div class="mt-4 p-4 bg-gray-900 rounded-lg space-y-4">
            <!-- Thread filter -->
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">
                Search in threads:
              </label>
              <div class="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-32 overflow-y-auto">
                {#each threads as thread}
                  <label class="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      bind:group={selectedFilters.threads}
                      value={thread.id}
                      class="rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
                    />
                    <span class="text-sm text-gray-300 truncate">
                      {thread.title}
                    </span>
                  </label>
                {/each}
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <!-- Role filter -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  Message from:
                </label>
                <select
                  bind:value={selectedFilters.role}
                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  <option value="all">All roles</option>
                  <option value="USER">User</option>
                  <option value="ASSISTANT">Assistant</option>
                  <option value="SYSTEM">System</option>
                </select>
              </div>

              <!-- Message type filter -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  Message type:
                </label>
                <select
                  bind:value={selectedFilters.messageType}
                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  <option value="all">All types</option>
                  <option value="TEXT">Text</option>
                  <option value="TASK_BREAKDOWN">Task Breakdown</option>
                  <option value="PROGRESS">Progress</option>
                  <option value="NOTIFICATION">Notification</option>
                  <option value="ERROR">Error</option>
                </select>
              </div>

              <!-- Date range filter -->
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  Date range:
                </label>
                <select
                  bind:value={selectedFilters.dateRange}
                  class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                >
                  <option value="">All time</option>
                  <option value="today">Today</option>
                  <option value="week">This week</option>
                  <option value="month">This month</option>
                  <option value="3months">Last 3 months</option>
                </select>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Results -->
      <div class="flex-1 overflow-y-auto p-4" style="max-height: calc(90vh - 200px);">
        {#if loading}
          <!-- Loading state -->
          <div class="flex items-center justify-center py-12">
            <div class="flex items-center space-x-2 text-gray-400">
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                />
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span>Searching...</span>
            </div>
          </div>
        {:else if searchQuery && searchResults.length === 0}
          <!-- No results -->
          <div class="text-center py-12">
            <svg
              class="w-12 h-12 text-gray-500 mx-auto mb-4"
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
            <h3 class="text-lg font-medium text-gray-300 mb-2">No results found</h3>
            <p class="text-gray-500">
              Try adjusting your search query or filters
            </p>
          </div>
        {:else if searchResults.length > 0}
          <!-- Search results -->
          <div class="space-y-3">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-medium text-gray-300">
                Found {searchResults.length} message{searchResults.length === 1 ? "" : "s"}
              </h3>
            </div>

            {#each searchResults as result}
              <div
                class="bg-gray-900 rounded-lg p-4 hover:bg-gray-800 cursor-pointer transition-colors"
                on:click={() => selectMessage(result)}
                on:keydown={(e) => e.key === "Enter" && selectMessage(result)}
                role="button"
                tabindex="0"
              >
                <!-- Message header -->
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center space-x-3">
                    <div
                      class="w-2 h-2 rounded-full {result.role === 'USER'
                        ? 'bg-blue-400'
                        : result.role === 'ASSISTANT'
                        ? 'bg-green-400'
                        : 'bg-yellow-400'}"
                    />
                    <span class="text-sm font-medium text-gray-300">
                      {result.role === "USER" ? "You" : result.role === "ASSISTANT" ? "Assistant" : "System"}
                    </span>
                    <span class="text-xs text-gray-500">in {result.threadTitle}</span>
                  </div>
                  <span class="text-xs text-gray-500">
                    {new Date(result.created_at).toLocaleDateString()} {new Date(result.created_at).toLocaleTimeString()}
                  </span>
                </div>

                <!-- Message content preview -->
                <div class="text-sm text-gray-300">
                  {#if result.content.length > 200}
                    {result.content.slice(0, 200)}...
                  {:else}
                    {result.content}
                  {/if}
                </div>

                <!-- Message type badge -->
                {#if result.message_type !== "TEXT"}
                  <div class="mt-2">
                    <span
                      class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium
                      {result.message_type === 'TASK_BREAKDOWN'
                        ? 'bg-blue-900 text-blue-300'
                        : result.message_type === 'PROGRESS'
                        ? 'bg-yellow-900 text-yellow-300'
                        : result.message_type === 'NOTIFICATION'
                        ? 'bg-green-900 text-green-300'
                        : 'bg-red-900 text-red-300'}"
                    >
                      {result.message_type.replace("_", " ").toLowerCase()}
                    </span>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <!-- Empty state -->
          <div class="text-center py-12">
            <svg
              class="w-12 h-12 text-gray-500 mx-auto mb-4"
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
            <h3 class="text-lg font-medium text-gray-300 mb-2">
              Search your messages
            </h3>
            <p class="text-gray-500">
              Find messages across all your conversations
            </p>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  /* Custom scrollbar */
  :global(.overflow-y-auto::-webkit-scrollbar) {
    width: 6px;
  }

  :global(.overflow-y-auto::-webkit-scrollbar-track) {
    background: #374151;
  }

  :global(.overflow-y-auto::-webkit-scrollbar-thumb) {
    background: #6b7280;
    border-radius: 3px;
  }

  :global(.overflow-y-auto::-webkit-scrollbar-thumb:hover) {
    background: #9ca3af;
  }
</style>
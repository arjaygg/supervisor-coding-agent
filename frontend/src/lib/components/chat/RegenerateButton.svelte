<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { ChatMessage } from "$lib/stores/chat";

  export let message: ChatMessage;
  export let isRegenerating: boolean = false;
  export let showOptions: boolean = false;

  const dispatch = createEventDispatcher();

  let dropdownOpen = false;

  // Regeneration options
  const regenerationOptions = [
    {
      id: "standard",
      label: "Standard Response",
      description: "Generate a new response with the same context",
      icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
    },
    {
      id: "shorter",
      label: "Shorter Response",
      description: "Generate a more concise version",
      icon: "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
    },
    {
      id: "detailed",
      label: "More Detailed",
      description: "Generate a more comprehensive response",
      icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    },
    {
      id: "different_approach",
      label: "Different Approach",
      description: "Try a completely different perspective",
      icon: "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
    },
  ];

  function handleRegenerate(optionId: string = "standard") {
    dispatch("regenerate", {
      messageId: message.id,
      option: optionId,
      originalContent: message.content,
    });
    dropdownOpen = false;
  }

  function toggleDropdown() {
    dropdownOpen = !dropdownOpen;
  }

  // Close dropdown when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as Element;
    if (dropdownOpen && !target.closest(".regenerate-dropdown")) {
      dropdownOpen = false;
    }
  }
</script>

<svelte:window on:click={handleClickOutside} />

<div class="regenerate-container relative inline-block">
  {#if showOptions}
    <!-- Regenerate button with dropdown -->
    <div class="regenerate-dropdown">
      <button
        class="regenerate-btn flex items-center space-x-1 p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        title="Regenerate response"
        disabled={isRegenerating}
        on:click={toggleDropdown}
      >
        {#if isRegenerating}
          <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
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
        {:else}
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        {/if}
        <svg class="w-2 h-2" fill="currentColor" viewBox="0 0 24 24">
          <path d="M7.41 8.84L12 13.42l4.59-4.58L18 10.25l-6 6-6-6z"/>
        </svg>
      </button>

      <!-- Dropdown menu -->
      {#if dropdownOpen && !isRegenerating}
        <div class="absolute right-0 mt-1 w-64 bg-gray-800 border border-gray-600 rounded-lg shadow-lg z-50 animate-fadeIn">
          <div class="py-1">
            <div class="px-3 py-2 text-xs font-medium text-gray-300 border-b border-gray-600">
              Regenerate Options
            </div>
            
            {#each regenerationOptions as option}
              <button
                class="w-full px-3 py-2 text-left hover:bg-gray-700 transition-colors flex items-start space-x-2"
                on:click={() => handleRegenerate(option.id)}
              >
                <svg class="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d={option.icon}
                  />
                </svg>
                <div class="flex-1">
                  <div class="text-sm font-medium text-white">{option.label}</div>
                  <div class="text-xs text-gray-400">{option.description}</div>
                </div>
              </button>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <!-- Simple regenerate button -->
    <button
      class="regenerate-btn p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      title="Regenerate response"
      disabled={isRegenerating}
      on:click={() => handleRegenerate()}
    >
      {#if isRegenerating}
        <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
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
      {:else}
        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      {/if}
    </button>
  {/if}
</div>

<style>
  .regenerate-container {
    position: relative;
  }

  .regenerate-btn {
    /* Ensure button maintains consistent sizing */
    min-width: 24px;
    min-height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* Dropdown animation */
  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .animate-fadeIn {
    animation: fadeIn 0.15s ease-out;
  }

  /* Mobile optimizations */
  @media (max-width: 768px) {
    .regenerate-dropdown .absolute {
      right: -1rem;
      width: 16rem;
    }
  }

  /* High contrast mode */
  @media (prefers-contrast: high) {
    .regenerate-btn {
      border: 1px solid currentColor;
    }
  }

  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .animate-fadeIn {
      animation: none;
    }
    
    .regenerate-btn {
      transition: none;
    }
  }
</style>
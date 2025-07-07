<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { createEventDispatcher } from "svelte";
  import type { StreamingChunk } from "$lib/services/streamingService";

  export let streamingContent: string = "";
  export let isStreaming: boolean = false;
  export let showCursor: boolean = true;
  export let cursorChar: string = "▋";
  export let typingSpeed: number = 20; // milliseconds between characters
  export let maxDisplayLength: number = 10000; // Maximum characters to display

  const dispatch = createEventDispatcher();

  let displayedContent = "";
  let currentIndex = 0;
  let typingInterval: NodeJS.Timeout;
  let cursorInterval: NodeJS.Timeout;
  let showCursorState = true;

  // Update displayed content when streaming content changes
  $: if (streamingContent !== displayedContent) {
    updateDisplayContent();
  }

  // Cursor blinking effect
  onMount(() => {
    if (showCursor) {
      cursorInterval = setInterval(() => {
        showCursorState = !showCursorState;
      }, 500);
    }
  });

  onDestroy(() => {
    if (typingInterval) clearInterval(typingInterval);
    if (cursorInterval) clearInterval(cursorInterval);
  });

  function updateDisplayContent() {
    if (typingInterval) {
      clearInterval(typingInterval);
    }

    // If streaming is disabled, show content immediately
    if (!isStreaming) {
      displayedContent = streamingContent;
      currentIndex = streamingContent.length;
      dispatch("typeComplete");
      return;
    }

    // Start typing animation from current position
    if (currentIndex < streamingContent.length) {
      typingInterval = setInterval(() => {
        if (currentIndex < streamingContent.length && currentIndex < maxDisplayLength) {
          displayedContent = streamingContent.slice(0, currentIndex + 1);
          currentIndex++;
        } else {
          clearInterval(typingInterval);
          dispatch("typeComplete");
        }
      }, typingSpeed);
    }
  }

  // Skip to end of current content
  export function skipToEnd() {
    if (typingInterval) {
      clearInterval(typingInterval);
    }
    displayedContent = streamingContent.slice(0, maxDisplayLength);
    currentIndex = Math.min(streamingContent.length, maxDisplayLength);
    dispatch("typeComplete");
  }

  // Reset the streaming display
  export function reset() {
    if (typingInterval) clearInterval(typingInterval);
    displayedContent = "";
    currentIndex = 0;
  }

  // Add new chunk to streaming content
  export function addChunk(chunk: StreamingChunk) {
    if (chunk.delta) {
      streamingContent += chunk.delta;
    } else {
      streamingContent = chunk.content;
    }
    
    dispatch("chunkAdded", chunk);
  }

  // Handle click to skip typing animation
  function handleClick() {
    if (isStreaming && typingInterval) {
      skipToEnd();
    }
  }

  // Format content with proper line breaks and basic markdown
  function formatContent(content: string): string {
    return content
      .replace(/\n/g, "<br>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }
</script>

<div
  class="streaming-message"
  class:streaming={isStreaming}
  class:clickable={isStreaming && typingInterval}
  on:click={handleClick}
  on:keydown={(e) => e.key === "Enter" && handleClick()}
  role={isStreaming && typingInterval ? "button" : ""}
  tabindex={isStreaming && typingInterval ? "0" : "-1"}
  title={isStreaming && typingInterval ? "Click to skip animation" : ""}
>
  <!-- Content display -->
  <div class="content">
    {@html formatContent(displayedContent)}
    
    <!-- Cursor -->
    {#if showCursor && isStreaming && showCursorState}
      <span class="cursor" class:blinking={!typingInterval}>
        {cursorChar}
      </span>
    {/if}
  </div>

  <!-- Streaming indicators -->
  {#if isStreaming}
    <div class="streaming-indicators">
      <!-- Progress indicator -->
      {#if streamingContent.length > 0}
        <div class="progress-bar">
          <div 
            class="progress-fill"
            style="width: {Math.min((displayedContent.length / streamingContent.length) * 100, 100)}%"
          />
        </div>
      {/if}

      <!-- Character count -->
      <div class="char-count">
        <span class="displayed">{displayedContent.length}</span>
        {#if streamingContent.length > displayedContent.length}
          <span class="separator">/</span>
          <span class="total">{streamingContent.length}</span>
        {/if}
        <span class="chars-label">chars</span>
      </div>

      <!-- Skip button -->
      {#if typingInterval && streamingContent.length > displayedContent.length}
        <button
          class="skip-button"
          on:click|stopPropagation={skipToEnd}
          title="Skip to end"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M13 5l7 7-7 7M5 5l7 7-7 7"
            />
          </svg>
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .streaming-message {
    position: relative;
    min-height: 1.5em;
    line-height: 1.6;
    font-family: inherit;
  }

  .streaming-message.clickable {
    cursor: pointer;
  }

  .streaming-message.clickable:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
  }

  .content {
    white-space: pre-wrap;
    word-break: break-word;
    margin-bottom: 0.5rem;
  }

  .content :global(code) {
    background-color: rgba(255, 255, 255, 0.1);
    padding: 0.1em 0.3em;
    border-radius: 3px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 0.9em;
  }

  .content :global(strong) {
    font-weight: 600;
  }

  .content :global(em) {
    font-style: italic;
  }

  .cursor {
    color: #3b82f6;
    font-weight: bold;
    animation: none;
  }

  .cursor.blinking {
    animation: blink 1s infinite;
  }

  @keyframes blink {
    0%, 50% {
      opacity: 1;
    }
    51%, 100% {
      opacity: 0;
    }
  }

  .streaming-indicators {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: #9ca3af;
  }

  .progress-bar {
    flex: 1;
    height: 2px;
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 1px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background-color: #3b82f6;
    transition: width 0.1s ease-out;
  }

  .char-count {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-variant-numeric: tabular-nums;
  }

  .displayed {
    color: #60a5fa;
  }

  .separator {
    color: #6b7280;
  }

  .total {
    color: #9ca3af;
  }

  .chars-label {
    color: #6b7280;
    font-size: 0.65rem;
  }

  .skip-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    background-color: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 4px;
    color: #60a5fa;
    transition: all 0.2s ease;
  }

  .skip-button:hover {
    background-color: rgba(59, 130, 246, 0.2);
    border-color: rgba(59, 130, 246, 0.5);
    color: #3b82f6;
  }

  .skip-button:active {
    transform: scale(0.95);
  }

  /* Mobile optimizations */
  @media (max-width: 768px) {
    .streaming-indicators {
      font-size: 0.7rem;
      gap: 0.5rem;
    }

    .skip-button {
      width: 1.25rem;
      height: 1.25rem;
    }

    .char-count {
      gap: 0.2rem;
    }
  }

  /* Dark mode optimizations */
  @media (prefers-color-scheme: dark) {
    .streaming-message.clickable:hover {
      background-color: rgba(255, 255, 255, 0.08);
    }
  }

  /* Reduced motion accessibility */
  @media (prefers-reduced-motion: reduce) {
    .cursor {
      animation: none !important;
    }

    .progress-fill {
      transition: none;
    }

    .skip-button {
      transition: none;
    }
  }

  /* High contrast mode */
  @media (prefers-contrast: high) {
    .cursor {
      color: #ffffff;
    }

    .progress-fill {
      background-color: #ffffff;
    }

    .skip-button {
      border-color: #ffffff;
      color: #ffffff;
    }
  }
</style>
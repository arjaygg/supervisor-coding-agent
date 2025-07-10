<script lang="ts">
  import { onMount, afterUpdate, tick, createEventDispatcher } from "svelte";
  import { chat, currentContextOptimization } from "$lib/stores/chat";
  import type { ChatThread, ChatMessage } from "$lib/stores/chat";
  import MessageBubble from "./MessageBubble.svelte";
  import MessageInput from "./MessageInput.svelte";
  import ContextIndicator from "./ContextIndicator.svelte";
  import { streamingService } from "$lib/services/streamingService";
  import type { StreamingChunk } from "$lib/services/streamingService";

  export let thread: ChatThread;
  export let messages: ChatMessage[] = [];
  export let loading: boolean = false;
  export let error: string | null = null;

  const dispatch = createEventDispatcher();

  let messagesContainer: HTMLDivElement;
  let autoScroll = true;
  let isNearBottom = true;

  // Streaming state
  let isStreaming = false;
  let streamingMessageId: string | null = null;
  let streamingContent = "";
  let streamingAbortController: AbortController | null = null;

  // Auto-scroll to bottom when new messages arrive
  afterUpdate(async () => {
    if (autoScroll && isNearBottom && messagesContainer) {
      await tick();
      scrollToBottom();
    }
  });

  onMount(() => {
    scrollToBottom();
  });

  function scrollToBottom() {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }

  function handleScroll() {
    if (!messagesContainer) return;

    const { scrollTop, scrollHeight, clientHeight } = messagesContainer;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    // Consider "near bottom" if within 100px
    isNearBottom = distanceFromBottom < 100;

    // Enable auto-scroll only when near bottom
    autoScroll = isNearBottom;
  }

  async function handleSendMessage(event: CustomEvent) {
    const { content, files } = event.detail;

    try {
      // Prepare message data with files if provided
      const messageData = {
        content,
        files: files || [],
        metadata: files && files.length > 0 ? { hasAttachments: true, fileCount: files.length } : {}
      };

      // First, send the user message normally
      const userMessage = await chat.sendMessage(thread.id, content, messageData);

      // Ensure we scroll to bottom after sending
      autoScroll = true;
      isNearBottom = true;
      await tick();
      scrollToBottom();

      // Then start streaming the AI response
      await startStreamingResponse(thread.id);

    } catch (error) {
      console.error("Failed to send message:", error);
    }
  }

  async function startStreamingResponse(threadId: string) {
    if (isStreaming) {
      // Cancel existing stream
      streamingAbortController?.abort();
    }

    isStreaming = true;
    streamingContent = "";
    streamingMessageId = `streaming_${Date.now()}`;
    streamingAbortController = new AbortController();

    try {
      await streamingService.sendMessageWithStream(
        threadId,
        "", // Empty content for AI response
        {
          signal: streamingAbortController.signal,
          onChunk: (chunk: StreamingChunk) => {
            streamingContent += chunk.delta || chunk.content;
            
            // Auto-scroll during streaming
            if (autoScroll && isNearBottom) {
              setTimeout(scrollToBottom, 50);
            }
          },
          onComplete: (finalMessage: ChatMessage) => {
            // Replace streaming message with final message
            isStreaming = false;
            streamingMessageId = null;
            streamingContent = "";
            
            // Update the chat store with the final message
            chat.addMessage(threadId, finalMessage);
            
            // Final scroll
            setTimeout(scrollToBottom, 100);
          },
          onError: (error: Error) => {
            console.error("Streaming error:", error);
            isStreaming = false;
            streamingMessageId = null;
            streamingContent = "";
          },
        }
      );
    } catch (error) {
      console.error("Failed to start streaming:", error);
      isStreaming = false;
      streamingMessageId = null;
      streamingContent = "";
    }
  }

  function cancelStreaming() {
    if (streamingAbortController) {
      streamingAbortController.abort();
    }
    isStreaming = false;
    streamingMessageId = null;
    streamingContent = "";
  }

  function handleNewConversation() {
    // Dispatch event to parent to create new conversation
    dispatch('new-conversation', { currentThreadId: thread.id });
  }

  function formatMessageTime(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function shouldShowDateSeparator(
    currentMessage: ChatMessage,
    previousMessage: ChatMessage | undefined
  ): boolean {
    if (!previousMessage) return true;

    const currentDate = new Date(currentMessage.created_at).toDateString();
    const previousDate = new Date(previousMessage.created_at).toDateString();

    return currentDate !== previousDate;
  }

  function formatDateSeparator(timestamp: string): string {
    const date = new Date(timestamp);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return "Today";
    } else if (date.toDateString() === yesterday.toDateString()) {
      return "Yesterday";
    } else {
      return date.toLocaleDateString([], {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    }
  }
</script>

<div class="h-full flex flex-col bg-gray-900">
  <!-- Messages area -->
  <div
    bind:this={messagesContainer}
    on:scroll={handleScroll}
    class="flex-1 overflow-y-auto chat-scroll p-4 space-y-4"
  >
    {#if loading && messages.length === 0}
      <!-- Loading skeleton -->
      <div class="space-y-4">
        {#each Array(3) as _}
          <div class="flex space-x-3">
            <div class="w-8 h-8 bg-gray-700 rounded-full animate-pulse" />
            <div class="flex-1 space-y-2">
              <div class="h-4 bg-gray-700 rounded animate-pulse w-1/4" />
              <div class="h-16 bg-gray-700 rounded animate-pulse" />
            </div>
          </div>
        {/each}
      </div>
    {:else if messages.length === 0}
      <!-- Empty state -->
      <div class="h-full flex items-center justify-center">
        <div class="text-center max-w-md">
          <div
            class="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4"
          >
            <svg
              class="w-8 h-8 text-gray-400"
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

          <h3 class="text-lg font-semibold text-white mb-2">
            Start the conversation
          </h3>
          <p class="text-gray-400 text-sm">
            Send a message to begin chatting with the AI assistant.
          </p>
        </div>
      </div>
    {:else}
      <!-- Messages -->
      {#each messages as message, index (message.id)}
        <!-- Date separator -->
        {#if shouldShowDateSeparator(message, messages[index - 1])}
          <div class="flex justify-center py-2">
            <span
              class="bg-gray-800 text-gray-400 text-xs px-3 py-1 rounded-full"
            >
              {formatDateSeparator(message.created_at)}
            </span>
          </div>
        {/if}

        <!-- Message bubble -->
        <MessageBubble
          {message}
          showTimestamp={true}
          time={formatMessageTime(message.created_at)}
          isStreaming={false}
        />
      {/each}

      <!-- Streaming message (shown while AI is responding) -->
      {#if isStreaming && streamingMessageId}
        <MessageBubble
          message={{
            id: streamingMessageId,
            thread_id: thread.id,
            role: "ASSISTANT",
            content: streamingContent,
            message_type: "TEXT",
            metadata: {},
            created_at: new Date().toISOString(),
          }}
          showTimestamp={true}
          time="Now"
          isStreaming={true}
          {streamingContent}
        />
      {/if}

      <!-- Loading indicator for new messages -->
      {#if loading}
        <div class="flex space-x-3">
          <div
            class="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center"
          >
            <svg
              class="w-4 h-4 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div class="flex-1 bg-gray-800 rounded-lg p-3">
            <div class="flex space-x-1">
              <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
              <div
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 0.1s"
              />
              <div
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 0.2s"
              />
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Scroll to bottom button -->
  {#if !isNearBottom && messages.length > 0}
    <div class="absolute bottom-20 right-6 z-10">
      <button
        class="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-full shadow-lg transition-colors"
        on:click={scrollToBottom}
        title="Scroll to bottom"
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
            d="M19 14l-7 7m0 0l-7-7m7 7V3"
          />
        </svg>
      </button>
    </div>
  {/if}

  <!-- Message input -->
  <div class="border-t border-gray-700 bg-gray-800">
    <!-- Streaming indicator and cancel button -->
    {#if isStreaming}
      <div class="px-4 py-2 bg-blue-900/20 border-b border-blue-800/30">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2 text-blue-300">
            <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
            <span class="text-sm">AI is responding...</span>
            <span class="text-xs opacity-75">({streamingContent.length} chars)</span>
          </div>
          <button
            class="px-3 py-1 text-xs bg-red-900/50 hover:bg-red-900/70 text-red-300 hover:text-red-200 border border-red-800/50 rounded transition-colors"
            on:click={cancelStreaming}
            title="Cancel response"
          >
            Cancel
          </button>
        </div>
      </div>
    {/if}

    <!-- Context Optimization Indicator -->
    {#if $currentContextOptimization}
      <div class="px-4 py-2 border-b border-gray-700">
        <ContextIndicator
          optimization={$currentContextOptimization}
          compact={true}
          on:new-conversation={handleNewConversation}
        />
      </div>
    {/if}

    <MessageInput
      loading={loading || isStreaming}
      placeholder={isStreaming ? "Wait for AI response..." : "Type your message..."}
      allowFileUpload={true}
      on:send={handleSendMessage}
      on:file-download={(e) => {
        // Handle file download events if needed
        console.log('File download requested:', e.detail);
      }}
    />
  </div>
</div>

<style>
  .chat-scroll {
    scrollbar-width: thin;
    scrollbar-color: #6b7280 #374151;
  }
</style>

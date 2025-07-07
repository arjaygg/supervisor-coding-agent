<script lang="ts">
  import type { ChatMessage } from "$lib/stores/chat";
  import StreamingMessage from "./StreamingMessage.svelte";
  import MessageEditor from "./MessageEditor.svelte";
  import RegenerateButton from "./RegenerateButton.svelte";
  import FileAttachment from "./FileAttachment.svelte";

  export let message: ChatMessage;
  export let showTimestamp: boolean = true;
  export let time: string = "";
  export let isStreaming: boolean = false;
  export let streamingContent: string = "";

  // Editing state
  let isEditing = false;
  let isRegenerating = false;
  let showRegenerateOptions = true;

  // Event handlers
  function handleEditStart() {
    isEditing = true;
  }

  function handleEditSave(event: CustomEvent) {
    const { messageId, content } = event.detail;
    // Update message content locally
    message.content = content;
    isEditing = false;
    
    // TODO: Call API to update message in backend
    console.log('Message edited:', { messageId, content });
  }

  function handleEditCancel() {
    isEditing = false;
  }

  function handleRegenerate(event: CustomEvent) {
    const { messageId, option, originalContent } = event.detail;
    isRegenerating = true;
    
    // TODO: Call API to regenerate message
    console.log('Message regeneration requested:', { messageId, option, originalContent });
    
    // Simulate regeneration delay
    setTimeout(() => {
      isRegenerating = false;
    }, 2000);
  }

  // Get avatar and styling based on role
  $: isUser = message.role === "USER";
  $: isAssistant = message.role === "ASSISTANT";
  $: isSystem = message.role === "SYSTEM";

  // Format content based on message type
  function formatContent(content: string, messageType: string): string {
    // Basic markdown-like formatting
    return content
      .replace(/\n/g, "<br>")
      .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }

  // Get message type styling
  function getMessageTypeClass(messageType: string): string {
    switch (messageType) {
      case "TASK_BREAKDOWN":
        return "border-l-4 border-yellow-500 bg-yellow-900/20";
      case "PROGRESS":
        return "border-l-4 border-blue-500 bg-blue-900/20";
      case "NOTIFICATION":
        return "border-l-4 border-green-500 bg-green-900/20";
      case "ERROR":
        return "border-l-4 border-red-500 bg-red-900/20";
      default:
        return "";
    }
  }

  // Get message type icon
  function getMessageTypeIcon(messageType: string): string {
    switch (messageType) {
      case "TASK_BREAKDOWN":
        return "M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01";
      case "PROGRESS":
        return "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z";
      case "NOTIFICATION":
        return "M15 17h5l-5 5v-5zM13 3h8v8l-8-8zM3 12l9-9v9H3z";
      case "ERROR":
        return "M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z";
      default:
        return "";
    }
  }

  // Get bubble background color
  function getBubbleClass(): string {
    if (isUser) {
      return "bg-blue-600 text-white ml-auto";
    } else if (isAssistant) {
      return "bg-gray-700 text-white mr-auto";
    } else {
      return "bg-yellow-800 text-yellow-100 mx-auto";
    }
  }

  // Get avatar styling
  function getAvatarClass(): string {
    if (isUser) {
      return "bg-blue-600 text-white";
    } else if (isAssistant) {
      return "bg-gray-600 text-white";
    } else {
      return "bg-yellow-600 text-yellow-100";
    }
  }

  // Get avatar icon
  function getAvatarIcon(): string {
    if (isUser) {
      return "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z";
    } else if (isAssistant) {
      return "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z";
    } else {
      return "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z";
    }
  }
</script>

<div 
  class="flex {isUser ? 'justify-end' : 'justify-start'} space-x-3 group"
  data-role={message.role}
  data-message-id={message.id}
>
  <!-- Avatar (left side for assistant/system, right side for user) -->
  {#if !isUser}
    <div class="flex-shrink-0">
      <div class="w-8 h-8 rounded-full flex items-center justify-center {getAvatarClass()}">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
          <path d={getAvatarIcon()} />
        </svg>
      </div>
    </div>
  {/if}

  <!-- Message content -->
  <div class="flex-1 max-w-xs md:max-w-md lg:max-w-lg xl:max-w-xl">
    <!-- Message bubble -->
    <div 
      class="rounded-lg px-4 py-3 shadow-sm {getBubbleClass()} {getMessageTypeClass(message.message_type)}"
      class:whitespace-pre-wrap={true}
      class:break-words={true}
    >
      <!-- Special message type indicator -->
      {#if message.message_type !== "TEXT"}
        <div class="flex items-center space-x-2 mb-2 opacity-75">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d={getMessageTypeIcon(message.message_type)}
            />
          </svg>
          <span class="text-xs font-medium uppercase tracking-wide">
            {message.message_type.replace("_", " ")}
          </span>
        </div>
      {/if}

      <!-- Message content -->
      <div class="message-content">
        {#if isStreaming && isAssistant}
          <!-- Streaming content for assistant messages -->
          <StreamingMessage
            bind:streamingContent
            {isStreaming}
            showCursor={true}
            typingSpeed={30}
            on:typeComplete={() => console.log("Streaming complete")}
            on:chunkAdded={() => console.log("Chunk added")}
          />
        {:else}
          <!-- Static content -->
          <div class="prose prose-invert prose-sm max-w-none">
            {@html formatContent(message.content, message.message_type)}
          </div>
        {/if}
      </div>

      <!-- File attachments -->
      {#if message.metadata && message.metadata.attachments && message.metadata.attachments.length > 0}
        <div class="mt-3 space-y-2">
          {#each message.metadata.attachments as attachment}
            <FileAttachment
              file={{
                id: attachment.id,
                name: attachment.name,
                size: attachment.size,
                type: attachment.type,
                category: attachment.category,
                uploadedAt: attachment.uploadedAt,
                showContent: false
              }}
              compact={true}
              removable={false}
              on:download={(e) => {
                // Handle file download for message attachments
                console.log('Download requested for attachment:', e.detail);
              }}
            />
          {/each}
        </div>
      {/if}

      <!-- Message metadata (if any) -->
      {#if message.metadata && Object.keys(message.metadata).length > 0}
        <div class="mt-2 text-xs opacity-60">
          {#if message.metadata.task_id}
            <div class="flex items-center space-x-1">
              <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <path d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <span>Task: {message.metadata.task_id}</span>
            </div>
          {/if}
          {#if message.metadata.hasAttachments}
            <div class="flex items-center space-x-1">
              <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <path d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
              <span>{message.metadata.fileCount} file{message.metadata.fileCount === 1 ? '' : 's'} attached</span>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Timestamp -->
    {#if showTimestamp && time}
      <div class="mt-1 text-xs text-gray-500 {isUser ? 'text-right' : 'text-left'}">
        <span class="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          {time}
        </span>
      </div>
    {/if}

    <!-- Message actions (visible on hover) -->
    <div class="mt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 {isUser ? 'text-right' : 'text-left'}">
      <div class="flex {isUser ? 'justify-end' : 'justify-start'} space-x-1">
        <!-- Copy message -->
        <button
          class="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
          title="Copy message"
          on:click={() => navigator.clipboard.writeText(message.content)}
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
        </button>

        <!-- Edit message (user messages only) -->
        {#if isUser}
          <button
            class="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
            title="Edit message"
            on:click={handleEditStart}
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
          </button>
        {/if}

        <!-- Regenerate response (assistant messages only) -->
        {#if isAssistant}
          <RegenerateButton
            {message}
            isRegenerating={isRegenerating}
            showOptions={showRegenerateOptions}
            on:regenerate={handleRegenerate}
          />
        {/if}

        <!-- React to message -->
        <button
          class="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
          title="React to message"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- Message Editor (when editing) -->
    {#if isEditing}
      <div class="mt-2">
        <MessageEditor
          {message}
          {isEditing}
          on:save={handleEditSave}
          on:cancel={handleEditCancel}
        />
      </div>
    {/if}
  </div>

  <!-- Avatar (right side for user) -->
  {#if isUser}
    <div class="flex-shrink-0">
      <div class="w-8 h-8 rounded-full flex items-center justify-center {getAvatarClass()}">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
          <path d={getAvatarIcon()} />
        </svg>
      </div>
    </div>
  {/if}
</div>

<style>
  /* Message content styling */
  .message-content :global(.inline-code) {
    background-color: rgba(255, 255, 255, 0.1);
    padding: 0.1em 0.3em;
    border-radius: 3px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 0.9em;
  }

  .message-content :global(a) {
    color: #60a5fa;
    text-decoration: underline;
  }

  .message-content :global(a:hover) {
    color: #93c5fd;
  }

  /* Responsive adjustments */
  @media (max-width: 768px) {
    .message-content {
      font-size: 0.9rem;
    }
  }

  /* Animation for message appearance */
  .group {
    animation: fadeInUp 0.3s ease-out;
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Accessibility improvements */
  @media (prefers-reduced-motion: reduce) {
    .group {
      animation: none;
    }
    
    button {
      transition: none;
    }
  }
</style>
<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import FileUpload from "./FileUpload.svelte";
  import FileAttachment from "./FileAttachment.svelte";

  export let loading: boolean = false;
  export let placeholder: string = "Type your message...";
  export let maxLength: number = 4000;
  export let allowFileUpload: boolean = true;

  const dispatch = createEventDispatcher();

  let message = "";
  let textArea: HTMLTextAreaElement;
  let isComposing = false;
  let attachedFiles: any[] = [];
  let showFileUpload = false;
  let uploadError = "";

  // Auto-resize textarea
  function autoResize() {
    if (textArea) {
      textArea.style.height = "auto";
      textArea.style.height = Math.min(textArea.scrollHeight, 200) + "px";
    }
  }

  // Handle input
  function handleInput() {
    autoResize();
  }

  // Handle key press
  function handleKeydown(event: KeyboardEvent) {
    // Don't send if composing (for IME input)
    if (isComposing) return;

    // Send on Enter (but not Shift+Enter)
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  // Handle composition events for IME input
  function handleCompositionStart() {
    isComposing = true;
  }

  function handleCompositionEnd() {
    isComposing = false;
  }

  // Send message
  function sendMessage() {
    const trimmedMessage = message.trim();

    if ((!trimmedMessage && attachedFiles.length === 0) || loading) return;

    dispatch("send", { 
      content: trimmedMessage,
      files: attachedFiles.length > 0 ? attachedFiles : undefined
    });

    // Clear input and files
    message = "";
    attachedFiles = [];
    showFileUpload = false;

    // Reset textarea height
    if (textArea) {
      textArea.style.height = "auto";
    }

    // Focus back to textarea
    setTimeout(() => {
      if (textArea) {
        textArea.focus();
      }
    }, 0);
  }

  // File upload handlers
  function handleFileUpload(event: CustomEvent) {
    const { files } = event.detail;
    attachedFiles = [...attachedFiles, ...files];
    showFileUpload = false;
    uploadError = "";
  }

  function handleFileUploadError(event: CustomEvent) {
    uploadError = event.detail.message;
    setTimeout(() => {
      uploadError = "";
    }, 5000);
  }

  function handleFileRemove(event: CustomEvent) {
    const { fileId } = event.detail;
    attachedFiles = attachedFiles.filter(file => file.id !== fileId);
  }

  function handleFileToggleContent(event: CustomEvent) {
    const { fileId, visible } = event.detail;
    attachedFiles = attachedFiles.map(file => 
      file.id === fileId ? { ...file, showContent: visible } : file
    );
  }

  function toggleFileUpload() {
    showFileUpload = !showFileUpload;
  }

  // Character count styling
  $: characterCountClass =
    message.length > maxLength * 0.9
      ? "text-red-400"
      : message.length > maxLength * 0.7
      ? "text-yellow-400"
      : "text-gray-500";
</script>

<div class="p-4">
  <div class="flex items-end space-x-3">
    <!-- Text input area -->
    <div class="flex-1 relative">
      <!-- Textarea -->
      <textarea
        bind:this={textArea}
        bind:value={message}
        {placeholder}
        disabled={loading}
        maxlength={maxLength}
        rows="1"
        class="
          w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 pr-12
          text-white placeholder-gray-400 resize-none overflow-hidden
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          disabled:opacity-50 disabled:cursor-not-allowed
        "
        style="max-height: 200px; min-height: 44px;"
        on:input={handleInput}
        on:keydown={handleKeydown}
        on:compositionstart={handleCompositionStart}
        on:compositionend={handleCompositionEnd}
      />

      <!-- Character count -->
      {#if message.length > maxLength * 0.5}
        <div class="absolute bottom-1 right-12 text-xs {characterCountClass}">
          {message.length}/{maxLength}
        </div>
      {/if}

      <!-- Send button (inside textarea) -->
      <button
        type="button"
        disabled={(!(message.trim() || attachedFiles.length > 0)) || loading || message.length > maxLength}
        class="
          absolute bottom-2 right-2 p-2 rounded-lg transition-colors
          {(message.trim() || attachedFiles.length > 0) && !loading && message.length <= maxLength
          ? 'bg-blue-600 hover:bg-blue-700 text-white'
          : 'bg-gray-600 text-gray-400 cursor-not-allowed'}
        "
        on:click={sendMessage}
        title="Send message (Enter)"
      >
        {#if loading}
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
        {:else}
          <svg
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
        {/if}
      </button>
    </div>

    <!-- Additional action buttons -->
    <div class="flex space-x-2">
      <!-- File upload button -->
      <button
        type="button"
        class="p-3 rounded-lg transition-colors"
        class:bg-blue-600={showFileUpload}
        class:text-white={showFileUpload}
        class:bg-gray-700={!showFileUpload}
        class:hover:bg-gray-600={!showFileUpload && allowFileUpload}
        class:text-gray-400={!showFileUpload}
        class:hover:text-white={!showFileUpload && allowFileUpload}
        class:cursor-not-allowed={!allowFileUpload}
        title={allowFileUpload ? "Attach files" : "File upload disabled"}
        disabled={!allowFileUpload || loading}
        on:click={toggleFileUpload}
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
            d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
          />
        </svg>
      </button>

      <!-- Voice message button -->
      <button
        type="button"
        class="p-3 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white transition-colors"
        title="Voice message (coming soon)"
        disabled
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
            d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
          />
        </svg>
      </button>
    </div>
  </div>

  <!-- File attachments display -->
  {#if attachedFiles.length > 0}
    <div class="mt-3 space-y-2">
      {#each attachedFiles as file (file.id)}
        <FileAttachment
          {file}
          compact={true}
          on:remove={handleFileRemove}
          on:download={(e) => dispatch('file-download', e.detail)}
          on:toggle-content={handleFileToggleContent}
        />
      {/each}
    </div>
  {/if}

  <!-- Upload error display -->
  {#if uploadError}
    <div class="mt-2 p-2 bg-red-900/20 border border-red-600 rounded-lg text-red-400 text-sm">
      {uploadError}
    </div>
  {/if}

  <!-- Helper text -->
  {#if !loading}
    <div class="mt-2 flex items-center justify-between text-xs text-gray-500">
      <span>
        Press Enter to send, Shift+Enter for new line
        {#if attachedFiles.length > 0}
          • {attachedFiles.length} file{attachedFiles.length === 1 ? '' : 's'} attached
        {/if}
      </span>

      <!-- Quick actions -->
      <div class="flex space-x-2">
        <button
          type="button"
          class="hover:text-gray-400 transition-colors"
          on:click={() => (message = "Create a task for ")}
          title="Quick: Create task"
        >
          📋 Task
        </button>
        <button
          type="button"
          class="hover:text-gray-400 transition-colors"
          on:click={() => (message = "Help me with ")}
          title="Quick: Ask for help"
        >
          ❓ Help
        </button>
        <button
          type="button"
          class="hover:text-gray-400 transition-colors"
          on:click={() => (message = "Analyze this code: ")}
          title="Quick: Code analysis"
        >
          🔍 Analyze
        </button>
      </div>
    </div>
  {/if}
</div>

<!-- File Upload Modal -->
{#if showFileUpload}
  <div class="mt-4 border border-gray-600 rounded-lg overflow-hidden">
    <FileUpload
      maxFileSize={10 * 1024 * 1024}
      maxFiles={5}
      disabled={loading}
      on:upload={handleFileUpload}
      on:error={handleFileUploadError}
    />
  </div>
{/if}

<!-- Future: Template functionality will be added in Epic 1.4 -->

<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { ChatMessage } from "$lib/stores/chat";

  export let message: ChatMessage;
  export let isEditing: boolean = false;
  export let maxLength: number = 4000;

  const dispatch = createEventDispatcher();

  let editedContent = message.content;
  let textArea: HTMLTextAreaElement;
  let isSubmitting = false;
  let hasChanges = false;

  // Track changes
  $: hasChanges = editedContent.trim() !== message.content.trim();

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

  // Handle keyboard shortcuts
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      cancelEdit();
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      saveEdit();
    }
  }

  // Save edited message
  async function saveEdit() {
    if (!hasChanges || isSubmitting) return;

    const trimmedContent = editedContent.trim();
    if (!trimmedContent) {
      alert("Message cannot be empty");
      return;
    }

    isSubmitting = true;

    try {
      dispatch("save", {
        messageId: message.id,
        content: trimmedContent,
        originalContent: message.content,
      });
    } catch (error) {
      console.error("Failed to save edit:", error);
    } finally {
      isSubmitting = false;
    }
  }

  // Cancel editing
  function cancelEdit() {
    editedContent = message.content;
    hasChanges = false;
    dispatch("cancel");
  }

  // Focus textarea when editing starts
  $: if (isEditing && textArea) {
    setTimeout(() => {
      textArea.focus();
      textArea.setSelectionRange(textArea.value.length, textArea.value.length);
      autoResize();
    }, 0);
  }

  // Character count styling
  $: characterCountClass =
    editedContent.length > maxLength * 0.9
      ? "text-red-400"
      : editedContent.length > maxLength * 0.7
      ? "text-yellow-400"
      : "text-gray-500";
</script>

{#if isEditing}
  <div class="message-editor border-2 border-blue-500/50 rounded-lg p-3 bg-gray-800/80 backdrop-blur-sm">
    <!-- Editor header -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
        <span class="text-sm font-medium text-blue-300">Editing Message</span>
      </div>
      
      <!-- Character count -->
      <div class="text-xs {characterCountClass}">
        {editedContent.length}/{maxLength}
      </div>
    </div>

    <!-- Editor textarea -->
    <div class="relative">
      <textarea
        bind:this={textArea}
        bind:value={editedContent}
        placeholder="Edit your message..."
        disabled={isSubmitting}
        maxlength={maxLength}
        rows="3"
        class="
          w-full bg-gray-700/50 border border-gray-600/50 rounded px-3 py-2
          text-white placeholder-gray-400 resize-none
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
          disabled:opacity-50 disabled:cursor-not-allowed
        "
        style="min-height: 60px;"
        on:input={handleInput}
        on:keydown={handleKeydown}
      />

      <!-- Resize handle indicator -->
      <div class="absolute bottom-1 right-1 w-3 h-3 opacity-30">
        <svg class="w-full h-full text-gray-400" fill="currentColor" viewBox="0 0 24 24">
          <path d="M22 22l-4-4m4 4l-4-4m4 4H2V2" />
        </svg>
      </div>
    </div>

    <!-- Editor actions -->
    <div class="flex items-center justify-between mt-3">
      <div class="flex items-center space-x-4">
        <!-- Help text -->
        <div class="text-xs text-gray-400">
          <span>Ctrl+Enter to save • Esc to cancel</span>
        </div>

        <!-- Change indicator -->
        {#if hasChanges}
          <div class="flex items-center space-x-1 text-xs text-yellow-400">
            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <span>Unsaved changes</span>
          </div>
        {/if}
      </div>

      <!-- Action buttons -->
      <div class="flex space-x-2">
        <button
          type="button"
          class="px-3 py-1 text-xs bg-gray-600 hover:bg-gray-500 text-gray-300 hover:text-white border border-gray-500 rounded transition-colors"
          on:click={cancelEdit}
          disabled={isSubmitting}
        >
          Cancel
        </button>
        
        <button
          type="button"
          class="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 text-white border border-blue-500 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          on:click={saveEdit}
          disabled={!hasChanges || isSubmitting || editedContent.length > maxLength}
        >
          {#if isSubmitting}
            <svg class="w-3 h-3 animate-spin mr-1 inline" fill="none" viewBox="0 0 24 24">
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
            Saving...
          {:else}
            Save
          {/if}
        </button>
      </div>
    </div>

    <!-- Validation warnings -->
    {#if editedContent.length > maxLength}
      <div class="mt-2 text-xs text-red-400 flex items-center space-x-1">
        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
        <span>Message exceeds maximum length ({maxLength} characters)</span>
      </div>
    {/if}
  </div>
{/if}

<style>
  .message-editor {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.3), 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    animation: slideIn 0.2s ease-out;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Textarea focus enhancement */
  textarea:focus {
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  /* Mobile optimizations */
  @media (max-width: 768px) {
    .message-editor {
      margin: -0.5rem;
      border-radius: 0.5rem;
    }
  }

  /* Accessibility improvements */
  @media (prefers-reduced-motion: reduce) {
    .message-editor {
      animation: none;
    }
  }
</style>
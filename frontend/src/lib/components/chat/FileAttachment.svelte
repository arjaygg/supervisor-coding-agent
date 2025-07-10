<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let file: {
    id: string;
    name: string;
    size: number;
    type: string;
    category: string;
    content?: string;
    dataUrl?: string;
    uploadedAt: string;
  };
  export let showContent: boolean = false;
  export let compact: boolean = false;
  export let removable: boolean = true;

  const dispatch = createEventDispatcher();

  let contentVisible = showContent;
  let contentTruncated = true;
  const maxContentPreview = 500; // characters

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  function getFileIcon(category: string): string {
    switch (category) {
      case 'code':
        return "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4";
      case 'document':
        return "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z";
      case 'data':
        return "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4";
      case 'config':
        return "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z";
      default:
        return "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z";
    }
  }

  function getCategoryColor(category: string): string {
    switch (category) {
      case 'code':
        return 'text-green-500';
      case 'document':
        return 'text-blue-500';
      case 'data':
        return 'text-purple-500';
      case 'config':
        return 'text-yellow-500';
      default:
        return 'text-gray-500';
    }
  }

  function getCategoryBadgeColor(category: string): string {
    switch (category) {
      case 'code':
        return 'bg-green-900/20 text-green-400 border-green-600';
      case 'document':
        return 'bg-blue-900/20 text-blue-400 border-blue-600';
      case 'data':
        return 'bg-purple-900/20 text-purple-400 border-purple-600';
      case 'config':
        return 'bg-yellow-900/20 text-yellow-400 border-yellow-600';
      default:
        return 'bg-gray-900/20 text-gray-400 border-gray-600';
    }
  }

  function toggleContent() {
    contentVisible = !contentVisible;
    dispatch('toggle-content', { fileId: file.id, visible: contentVisible });
  }

  function removeFile() {
    dispatch('remove', { fileId: file.id });
  }

  function downloadFile() {
    if (file.content) {
      // Create blob for text content
      const blob = new Blob([file.content], { type: file.type || 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else if (file.dataUrl) {
      // Use data URL for binary files
      const a = document.createElement('a');
      a.href = file.dataUrl;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
    
    dispatch('download', { fileId: file.id });
  }

  function getFileExtension(): string {
    return file.name.split('.').pop()?.toUpperCase() || 'FILE';
  }

  function getContentPreview(): string {
    if (!file.content) return '';
    
    if (contentTruncated && file.content.length > maxContentPreview) {
      return file.content.substring(0, maxContentPreview) + '...';
    }
    
    return file.content;
  }

  function isContentTruncatable(): boolean {
    return Boolean(file.content && file.content.length > maxContentPreview);
  }
</script>

<div
  class="file-attachment border rounded-lg transition-all duration-200"
  class:bg-gray-800={!compact}
  class:border-gray-600={!compact}
  class:bg-gray-700={compact}
  class:border-gray-500={compact}
  class:p-4={!compact}
  class:p-2={compact}
>
  <!-- File header -->
  <div class="flex items-start justify-between">
    <div class="flex items-start space-x-3 flex-1 min-w-0">
      <!-- File icon -->
      <div class="flex-shrink-0">
        <svg 
          class="w-8 h-8 {getCategoryColor(file.category)}" 
          class:w-6={compact}
          class:h-6={compact}
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d={getFileIcon(file.category)}
          />
        </svg>
      </div>

      <!-- File info -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center space-x-2 mb-1">
          <h4 
            class="font-medium text-white truncate" 
            class:text-sm={compact}
            title={file.name}
          >
            {file.name}
          </h4>
          
          <!-- Category badge -->
          <span 
            class="px-2 py-0.5 text-xs border rounded-full {getCategoryBadgeColor(file.category)}"
            class:px-1={compact}
            class:text-xs={compact}
          >
            {file.category}
          </span>
        </div>

        <div class="flex items-center space-x-4 text-sm text-gray-400">
          <span class:text-xs={compact}>{formatFileSize(file.size)}</span>
          <span class:text-xs={compact}>{getFileExtension()}</span>
          {#if !compact}
            <span class="text-xs">
              {new Date(file.uploadedAt).toLocaleString()}
            </span>
          {/if}
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center space-x-1 flex-shrink-0 ml-2">
      {#if file.content}
        <button
          class="p-1 text-gray-400 hover:text-blue-400 transition-colors rounded"
          on:click={toggleContent}
          title={contentVisible ? "Hide content" : "Show content"}
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {#if contentVisible}
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L8.464 8.464M9.878 9.878a3 3 0 00-.007 4.243m4.249-4.249l1.414-1.414M14.121 14.121a3 3 0 01-.007-4.242m0 4.242l1.414 1.414M14.121 14.121l4.243 4.242" />
            {:else}
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            {/if}
          </svg>
        </button>
      {/if}

      <button
        class="p-1 text-gray-400 hover:text-green-400 transition-colors rounded"
        on:click={downloadFile}
        title="Download file"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </button>

      {#if removable}
        <button
          class="p-1 text-gray-400 hover:text-red-400 transition-colors rounded"
          on:click={removeFile}
          title="Remove file"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      {/if}
    </div>
  </div>

  <!-- File content preview -->
  {#if contentVisible && file.content}
    <div class="mt-4 border-t border-gray-600 pt-4">
      <div class="bg-gray-900 rounded-lg p-3 overflow-hidden">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-medium text-gray-400">Content Preview</span>
          {#if isContentTruncatable()}
            <button
              class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              on:click={() => contentTruncated = !contentTruncated}
            >
              {contentTruncated ? 'Show more' : 'Show less'}
            </button>
          {/if}
        </div>
        
        <pre class="text-sm text-gray-300 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">{getContentPreview()}</pre>
        
        {#if contentTruncated && file.content.length > maxContentPreview}
          <div class="mt-2 text-xs text-gray-500">
            Showing {maxContentPreview} of {file.content.length} characters
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .file-attachment {
    animation: slideIn 0.3s ease-out;
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

  /* Custom scrollbar for content preview */
  pre::-webkit-scrollbar {
    width: 4px;
  }

  pre::-webkit-scrollbar-track {
    background: #374151;
  }

  pre::-webkit-scrollbar-thumb {
    background: #6b7280;
    border-radius: 2px;
  }

  pre::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
  }

  /* Mobile optimizations */
  @media (max-width: 768px) {
    .file-attachment {
      margin: -0.5rem;
      border-radius: 0.5rem;
    }
  }

  /* Accessibility improvements */
  @media (prefers-reduced-motion: reduce) {
    .file-attachment {
      animation: none;
    }
    
    button {
      transition: none;
    }
  }
</style>
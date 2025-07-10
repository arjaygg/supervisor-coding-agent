<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let accept: string = "*/*";
  export let multiple: boolean = true;
  export let maxFileSize: number = 10 * 1024 * 1024; // 10MB default
  export let maxFiles: number = 5;
  export let disabled: boolean = false;

  const dispatch = createEventDispatcher();

  let fileInput: HTMLInputElement;
  let dragOver = false;
  let uploading = false;
  let uploadProgress: Record<string, number> = {};

  // Supported file types for analysis
  const supportedTypes = {
    code: [
      ".js", ".jsx", ".ts", ".tsx", ".py", ".java", ".c", ".cpp", ".cs", ".php", 
      ".rb", ".go", ".rs", ".swift", ".kt", ".scala", ".sh", ".bash", ".zsh"
    ],
    documents: [
      ".txt", ".md", ".pdf", ".doc", ".docx", ".rtf"
    ],
    data: [
      ".json", ".xml", ".yaml", ".yml", ".csv", ".sql"
    ],
    configs: [
      ".ini", ".conf", ".config", ".env", ".toml", ".properties"
    ]
  };

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files) {
      processFiles(Array.from(target.files));
    }
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
    dragOver = true;
  }

  function handleDragLeave(event: DragEvent) {
    event.preventDefault();
    dragOver = false;
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragOver = false;
    
    if (disabled) return;

    const files = Array.from(event.dataTransfer?.files || []);
    processFiles(files);
  }

  async function processFiles(files: File[]) {
    if (files.length === 0) return;

    // Validate file count
    if (files.length > maxFiles) {
      dispatch("error", {
        message: `Maximum ${maxFiles} files allowed. Selected ${files.length} files.`,
        type: "validation"
      });
      return;
    }

    const validFiles: File[] = [];
    const errors: string[] = [];

    // Validate each file
    for (const file of files) {
      // Check file size
      if (file.size > maxFileSize) {
        errors.push(`${file.name} exceeds maximum size of ${formatFileSize(maxFileSize)}`);
        continue;
      }

      // Check file type if accept is specified
      if (accept !== "*/*" && !isFileTypeAllowed(file, accept)) {
        errors.push(`${file.name} is not an allowed file type`);
        continue;
      }

      validFiles.push(file);
    }

    // Report validation errors
    if (errors.length > 0) {
      dispatch("error", {
        message: errors.join(". "),
        type: "validation"
      });
    }

    if (validFiles.length === 0) return;

    // Process valid files
    uploading = true;
    const uploadResults: any[] = [];

    try {
      for (const file of validFiles) {
        const result = await uploadFile(file);
        uploadResults.push(result);
      }

      dispatch("upload", {
        files: uploadResults,
        count: uploadResults.length
      });

    } catch (error) {
      dispatch("error", {
        message: error instanceof Error ? error.message : "Upload failed",
        type: "upload"
      });
    } finally {
      uploading = false;
      uploadProgress = {};
      
      // Reset file input
      if (fileInput) {
        fileInput.value = "";
      }
    }
  }

  async function uploadFile(file: File): Promise<any> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = async (event) => {
        try {
          const content = event.target?.result as string;
          const fileData = {
            id: generateFileId(),
            name: file.name,
            size: file.size,
            type: file.type,
            lastModified: file.lastModified,
            content: file.type.startsWith('text/') || isTextFile(file) ? content : null,
            dataUrl: !file.type.startsWith('text/') && !isTextFile(file) ? content : null,
            category: categorizeFile(file),
            uploadedAt: new Date().toISOString()
          };

          // Simulate upload progress
          let progress = 0;
          const progressInterval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress >= 100) {
              progress = 100;
              clearInterval(progressInterval);
              delete uploadProgress[file.name];
              resolve(fileData);
            } else {
              uploadProgress[file.name] = progress;
              uploadProgress = { ...uploadProgress }; // Trigger reactivity
            }
          }, 100);

        } catch (error) {
          reject(error);
        }
      };

      reader.onerror = () => {
        reject(new Error(`Failed to read file: ${file.name}`));
      };

      // Read file as appropriate type
      if (file.type.startsWith('text/') || isTextFile(file)) {
        reader.readAsText(file);
      } else {
        reader.readAsDataURL(file);
      }
    });
  }

  function isFileTypeAllowed(file: File, acceptPattern: string): boolean {
    const patterns = acceptPattern.split(',').map(p => p.trim());
    
    for (const pattern of patterns) {
      if (pattern === '*/*') return true;
      if (pattern.startsWith('.') && file.name.toLowerCase().endsWith(pattern.toLowerCase())) return true;
      if (pattern.includes('/') && file.type.match(new RegExp(pattern.replace('*', '.*')))) return true;
    }
    
    return false;
  }

  function isTextFile(file: File): boolean {
    const textExtensions = [
      ...supportedTypes.code,
      ...supportedTypes.documents.filter(ext => ext === '.txt' || ext === '.md'),
      ...supportedTypes.data,
      ...supportedTypes.configs
    ];
    
    return textExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
  }

  function categorizeFile(file: File): string {
    const extension = '.' + file.name.split('.').pop()?.toLowerCase();
    
    if (supportedTypes.code.includes(extension)) return 'code';
    if (supportedTypes.documents.includes(extension)) return 'document';
    if (supportedTypes.data.includes(extension)) return 'data';
    if (supportedTypes.configs.includes(extension)) return 'config';
    
    return 'other';
  }

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  function generateFileId(): string {
    return 'file_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }

  function openFileDialog() {
    if (!disabled && fileInput) {
      fileInput.click();
    }
  }

  function getFileTypeIcon(category: string): string {
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
</script>

<!-- Hidden file input -->
<input
  bind:this={fileInput}
  type="file"
  {accept}
  {multiple}
  {disabled}
  class="hidden"
  on:change={handleFileSelect}
/>

<!-- Upload area -->
<div
  class="file-upload-area relative border-2 border-dashed rounded-lg p-6 transition-all duration-200"
  class:border-gray-600={!dragOver && !disabled}
  class:bg-gray-800={!dragOver && !disabled}
  class:border-blue-500={dragOver && !disabled}
  class:bg-blue-900={dragOver && !disabled}
  class:border-gray-700={disabled}
  class:bg-gray-900={disabled}
  class:cursor-not-allowed={disabled}
  class:cursor-pointer={!disabled}
  on:dragover={handleDragOver}
  on:dragleave={handleDragLeave}
  on:drop={handleDrop}
  on:click={openFileDialog}
  role="button"
  tabindex={disabled ? -1 : 0}
  on:keydown={(e) => e.key === 'Enter' && openFileDialog()}
>
  {#if uploading}
    <!-- Upload progress -->
    <div class="text-center">
      <div class="mb-4">
        <svg class="w-12 h-12 mx-auto text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
      <h3 class="text-lg font-medium text-white mb-2">Uploading files...</h3>
      
      {#if Object.keys(uploadProgress).length > 0}
        <div class="space-y-2">
          {#each Object.entries(uploadProgress) as [fileName, progress]}
            <div class="text-left">
              <div class="flex justify-between text-sm text-gray-300 mb-1">
                <span class="truncate">{fileName}</span>
                <span>{Math.round(progress)}%</span>
              </div>
              <div class="w-full bg-gray-700 rounded-full h-2">
                <div
                  class="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style="width: {progress}%"
                ></div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <!-- Upload prompt -->
    <div class="text-center">
      <div class="mb-4">
        {#if dragOver}
          <svg class="w-12 h-12 mx-auto text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
          </svg>
        {:else}
          <svg class="w-12 h-12 mx-auto text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        {/if}
      </div>

      <h3 class="text-lg font-medium text-white mb-2">
        {dragOver ? "Drop files here" : "Upload files for analysis"}
      </h3>
      
      <p class="text-sm text-gray-400 mb-4">
        {#if disabled}
          File upload is currently disabled
        {:else}
          Drag and drop files here, or click to browse
        {/if}
      </p>

      {#if !disabled}
        <!-- Supported file types -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-gray-500">
          <div class="flex flex-col items-center space-y-1">
            <svg class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={getFileTypeIcon('code')} />
            </svg>
            <span>Code Files</span>
            <span class="text-xs">.js, .py, .java...</span>
          </div>
          
          <div class="flex flex-col items-center space-y-1">
            <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={getFileTypeIcon('document')} />
            </svg>
            <span>Documents</span>
            <span class="text-xs">.txt, .md, .pdf...</span>
          </div>
          
          <div class="flex flex-col items-center space-y-1">
            <svg class="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={getFileTypeIcon('data')} />
            </svg>
            <span>Data Files</span>
            <span class="text-xs">.json, .csv, .xml...</span>
          </div>
          
          <div class="flex flex-col items-center space-y-1">
            <svg class="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={getFileTypeIcon('config')} />
            </svg>
            <span>Config Files</span>
            <span class="text-xs">.env, .ini, .yml...</span>
          </div>
        </div>

        <!-- Limits info -->
        <div class="mt-4 text-xs text-gray-500">
          <p>Maximum {maxFiles} files, {formatFileSize(maxFileSize)} per file</p>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .file-upload-area {
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* Accessibility improvements */
  .file-upload-area:focus {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
  }

  .file-upload-area:focus:not(:focus-visible) {
    outline: none;
  }

  /* Animation for drag states */
  .file-upload-area {
    transition: all 0.2s ease-in-out;
  }

  /* Mobile optimizations */
  @media (max-width: 768px) {
    .file-upload-area {
      min-height: 150px;
      padding: 1rem;
    }
    
    .grid-cols-4 {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
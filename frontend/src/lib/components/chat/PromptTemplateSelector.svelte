<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { PromptTemplate } from "$lib/stores/promptTemplates";

  export let templates: PromptTemplate[] = [];
  export let selectedTemplate: PromptTemplate | null = null;
  export let isOpen: boolean = false;
  export let position: "top" | "bottom" = "top";

  const dispatch = createEventDispatcher();

  let searchQuery = "";
  let filteredTemplates: PromptTemplate[] = [];

  // Filter templates based on search query
  $: filteredTemplates = templates.filter(template =>
    template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Group templates by category
  $: groupedTemplates = filteredTemplates.reduce((groups, template) => {
    const category = template.category || "General";
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(template);
    return groups;
  }, {} as Record<string, PromptTemplate[]>);

  function selectTemplate(template: PromptTemplate) {
    selectedTemplate = template;
    dispatch("select", template);
    isOpen = false;
    searchQuery = "";
  }

  function toggleDropdown() {
    isOpen = !isOpen;
    if (isOpen) {
      // Focus search input when opening
      setTimeout(() => {
        const searchInput = document.querySelector(".template-search") as HTMLInputElement;
        searchInput?.focus();
      }, 10);
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      isOpen = false;
      searchQuery = "";
    }
  }

  function handleClickOutside(event: MouseEvent) {
    const target = event.target as Element;
    if (isOpen && !target.closest(".template-selector")) {
      isOpen = false;
      searchQuery = "";
    }
  }

  function createNewTemplate() {
    dispatch("create-new");
    isOpen = false;
  }

  function editTemplate(template: PromptTemplate, event: Event) {
    event.stopPropagation();
    dispatch("edit", template);
  }

  function deleteTemplate(template: PromptTemplate, event: Event) {
    event.stopPropagation();
    dispatch("delete", template);
  }

  // Get category icon
  function getCategoryIcon(category: string): string {
    switch (category.toLowerCase()) {
      case "development":
        return "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4";
      case "analysis":
        return "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z";
      case "planning":
        return "M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01";
      case "documentation":
        return "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z";
      case "communication":
        return "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z";
      default:
        return "M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2h4a1 1 0 110 2h-1v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6H3a1 1 0 110-2h4z";
    }
  }

  // Get template type color
  function getTypeColor(type: string): string {
    switch (type) {
      case "system":
        return "text-blue-400 bg-blue-900/20";
      case "user":
        return "text-green-400 bg-green-900/20";
      case "community":
        return "text-purple-400 bg-purple-900/20";
      default:
        return "text-gray-400 bg-gray-900/20";
    }
  }
</script>

<svelte:window on:click={handleClickOutside} on:keydown={handleKeydown} />

<div class="template-selector relative">
  <!-- Template selector button -->
  <button
    class="template-trigger flex items-center space-x-2 px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white border border-gray-600 rounded-md transition-colors"
    on:click={toggleDropdown}
    title="Select prompt template"
  >
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M4 6h16M4 12h16M4 18h16"
      />
    </svg>
    <span>
      {selectedTemplate ? selectedTemplate.name : "Templates"}
    </span>
    <svg 
      class="w-3 h-3 transition-transform duration-200" 
      class:rotate-180={isOpen}
      fill="currentColor" 
      viewBox="0 0 24 24"
    >
      <path d="M7.41 8.84L12 13.42l4.59-4.58L18 10.25l-6 6-6-6z"/>
    </svg>
  </button>

  <!-- Dropdown panel -->
  {#if isOpen}
    <div 
      class="template-dropdown absolute z-50 w-96 bg-gray-800 border border-gray-600 rounded-lg shadow-xl"
      class:bottom-full={position === "top"}
      class:top-full={position === "bottom"}
      class:mb-2={position === "top"}
      class:mt-2={position === "bottom"}
      style="right: 0;"
    >
      <!-- Header with search -->
      <div class="p-4 border-b border-gray-600">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-medium text-white">Prompt Templates</h3>
          <button
            class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            on:click={createNewTemplate}
          >
            + New Template
          </button>
        </div>
        
        <div class="relative">
          <svg class="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            class="template-search w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Search templates..."
            bind:value={searchQuery}
          />
        </div>
      </div>

      <!-- Templates list -->
      <div class="max-h-80 overflow-y-auto">
        {#if filteredTemplates.length === 0}
          <div class="p-4 text-center text-gray-400 text-sm">
            {searchQuery ? "No templates found" : "No templates available"}
          </div>
        {:else}
          {#each Object.entries(groupedTemplates) as [category, categoryTemplates]}
            <div class="p-2">
              <!-- Category header -->
              <div class="flex items-center space-x-2 px-2 py-1 text-xs font-medium text-gray-400 uppercase tracking-wide">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d={getCategoryIcon(category)}
                  />
                </svg>
                <span>{category}</span>
              </div>

              <!-- Category templates -->
              {#each categoryTemplates as template}
                <div
                  class="template-item relative group flex items-start space-x-3 p-3 rounded-md hover:bg-gray-700 cursor-pointer transition-colors"
                  class:bg-gray-700={selectedTemplate?.id === template.id}
                  on:click={() => selectTemplate(template)}
                  role="button"
                  tabindex="0"
                  on:keydown={(e) => e.key === 'Enter' && selectTemplate(template)}
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-1">
                      <div class="flex items-center space-x-2">
                        <h4 class="text-sm font-medium text-white truncate">
                          {template.name}
                        </h4>
                        <span class="px-1.5 py-0.5 text-xs rounded {getTypeColor(template.type)}">
                          {template.type}
                        </span>
                      </div>
                      
                      <!-- Action buttons -->
                      <div class="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {#if template.type === "user"}
                          <button
                            class="p-1 text-gray-400 hover:text-blue-400 transition-colors"
                            on:click={(e) => editTemplate(template, e)}
                            title="Edit template"
                          >
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            class="p-1 text-gray-400 hover:text-red-400 transition-colors"
                            on:click={(e) => deleteTemplate(template, e)}
                            title="Delete template"
                          >
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        {/if}
                      </div>
                    </div>
                    
                    <p class="text-xs text-gray-400 mb-2 line-clamp-2">
                      {template.description}
                    </p>
                    
                    <!-- Tags -->
                    {#if template.tags.length > 0}
                      <div class="flex flex-wrap gap-1">
                        {#each template.tags.slice(0, 3) as tag}
                          <span class="px-1.5 py-0.5 text-xs bg-gray-600 text-gray-300 rounded">
                            {tag}
                          </span>
                        {/each}
                        {#if template.tags.length > 3}
                          <span class="px-1.5 py-0.5 text-xs bg-gray-600 text-gray-300 rounded">
                            +{template.tags.length - 3} more
                          </span>
                        {/if}
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/each}
        {/if}
      </div>

      <!-- Footer -->
      <div class="p-3 border-t border-gray-600 text-xs text-gray-400">
        {filteredTemplates.length} template{filteredTemplates.length !== 1 ? 's' : ''} available
      </div>
    </div>
  {/if}
</div>

<style>
  .template-dropdown {
    animation: slideIn 0.15s ease-out;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .rotate-180 {
    transform: rotate(180deg);
  }

  /* Mobile optimizations */
  @media (max-width: 768px) {
    .template-dropdown {
      width: 95vw;
      right: -50% !important;
      transform: translateX(50%);
    }
  }

  /* Accessibility improvements */
  @media (prefers-reduced-motion: reduce) {
    .template-dropdown {
      animation: none;
    }
    
    .template-trigger svg,
    .template-item {
      transition: none;
    }
  }
</style>
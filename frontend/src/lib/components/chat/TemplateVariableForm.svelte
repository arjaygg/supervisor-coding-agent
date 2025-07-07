<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { PromptTemplate, TemplateVariable } from "$lib/stores/promptTemplates";

  export let template: PromptTemplate;
  export let isOpen: boolean = false;
  export let initialValues: Record<string, any> = {};

  const dispatch = createEventDispatcher();

  let formData: Record<string, any> = {};
  let errors: Record<string, string> = {};
  let isSubmitting = false;

  // Initialize form data when template or initialValues change
  $: if (template && isOpen) {
    formData = { ...initialValues };
    
    // Set default values for variables that don't have values
    template.variables.forEach(variable => {
      if (formData[variable.name] === undefined) {
        formData[variable.name] = variable.default_value || "";
      }
    });
    
    errors = {};
  }

  function validateForm(): boolean {
    errors = {};

    template.variables.forEach(variable => {
      const value = formData[variable.name];
      
      if (variable.required && (!value || (typeof value === "string" && !value.trim()))) {
        errors[variable.name] = `${variable.description} is required`;
      }
      
      if (variable.type === "number" && value && isNaN(Number(value))) {
        errors[variable.name] = "Must be a valid number";
      }
    });

    return Object.keys(errors).length === 0;
  }

  function handleSubmit() {
    if (!validateForm()) return;

    isSubmitting = true;

    // Clean up form data
    const cleanedData: Record<string, any> = {};
    template.variables.forEach(variable => {
      let value = formData[variable.name];
      
      if (variable.type === "number" && value) {
        value = Number(value);
      } else if (typeof value === "string") {
        value = value.trim();
      }
      
      cleanedData[variable.name] = value;
    });

    dispatch("submit", cleanedData);
    isSubmitting = false;
  }

  function handleCancel() {
    formData = {};
    errors = {};
    dispatch("cancel");
  }

  function handleReset() {
    formData = {};
    template.variables.forEach(variable => {
      formData[variable.name] = variable.default_value || "";
    });
    errors = {};
  }

  function previewResult() {
    let preview = template.template;
    
    Object.entries(formData).forEach(([key, value]) => {
      const regex = new RegExp(`{{${key}}}`, 'g');
      preview = preview.replace(regex, String(value || `[${key}]`));
    });

    // Clean up any remaining unfilled variables
    preview = preview.replace(/{{[^}]+}}/g, (match) => {
      const varName = match.replace(/[{}]/g, "");
      return `[${varName}]`;
    });

    dispatch("preview", { variables: formData, preview });
  }

  // Get appropriate input component for variable type
  function getInputType(variable: TemplateVariable): string {
    switch (variable.type) {
      case "number":
        return "number";
      case "text":
      default:
        return "text";
    }
  }
</script>

{#if isOpen}
  <!-- Modal backdrop -->
  <div class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
    <!-- Modal content -->
    <div class="bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between p-6 border-b border-gray-600">
        <div>
          <h2 class="text-xl font-semibold text-white">{template.name}</h2>
          <p class="text-sm text-gray-400 mt-1">{template.description}</p>
        </div>
        <button
          class="text-gray-400 hover:text-white transition-colors"
          on:click={handleCancel}
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div class="overflow-y-auto max-h-[calc(90vh-180px)]">
        <form on:submit|preventDefault={handleSubmit} class="p-6 space-y-6">
          {#if template.variables.length === 0}
            <div class="text-center py-8">
              <p class="text-gray-400">This template has no variables to fill.</p>
              <p class="text-sm text-gray-500 mt-2">The template will be used as-is.</p>
            </div>
          {:else}
            <div class="space-y-4">
              {#each template.variables as variable}
                <div class="variable-field">
                  <label class="block text-sm font-medium text-gray-300 mb-2">
                    {variable.description}
                    {#if variable.required}
                      <span class="text-red-400">*</span>
                    {/if}
                  </label>

                  {#if variable.type === "select"}
                    <!-- Select dropdown -->
                    <select
                      bind:value={formData[variable.name]}
                      class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      class:border-red-500={errors[variable.name]}
                      required={variable.required}
                    >
                      <option value="">
                        {variable.placeholder || `Select ${variable.description.toLowerCase()}...`}
                      </option>
                      {#each variable.options || [] as option}
                        <option value={option}>{option}</option>
                      {/each}
                    </select>
                  {:else if variable.type === "multiline"}
                    <!-- Textarea -->
                    <textarea
                      bind:value={formData[variable.name]}
                      rows="4"
                      class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-vertical"
                      class:border-red-500={errors[variable.name]}
                      placeholder={variable.placeholder || `Enter ${variable.description.toLowerCase()}...`}
                      required={variable.required}
                    ></textarea>
                  {:else}
                    <!-- Text/Number input -->
                    <input
                      type={getInputType(variable)}
                      bind:value={formData[variable.name]}
                      class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      class:border-red-500={errors[variable.name]}
                      placeholder={variable.placeholder || `Enter ${variable.description.toLowerCase()}...`}
                      required={variable.required}
                    />
                  {/if}

                  {#if errors[variable.name]}
                    <p class="mt-1 text-sm text-red-400">{errors[variable.name]}</p>
                  {/if}

                  {#if variable.default_value && !variable.required}
                    <p class="mt-1 text-xs text-gray-500">
                      Default: {variable.default_value}
                    </p>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </form>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between p-6 border-t border-gray-600">
        <div class="flex space-x-2">
          <button
            type="button"
            class="px-3 py-2 text-sm text-gray-400 hover:text-white transition-colors"
            on:click={handleReset}
          >
            Reset
          </button>
          <button
            type="button"
            class="px-3 py-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
            on:click={previewResult}
          >
            Preview
          </button>
        </div>
        
        <div class="flex items-center space-x-3">
          <button
            type="button"
            class="px-4 py-2 text-gray-300 hover:text-white transition-colors"
            on:click={handleCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isSubmitting}
            on:click={handleSubmit}
          >
            {#if isSubmitting}
              <svg class="w-4 h-4 animate-spin mr-2 inline" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Processing...
            {:else}
              Use Template
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Custom scrollbar */
  .overflow-y-auto::-webkit-scrollbar {
    width: 6px;
  }

  .overflow-y-auto::-webkit-scrollbar-track {
    background: #374151;
  }

  .overflow-y-auto::-webkit-scrollbar-thumb {
    background: #6b7280;
    border-radius: 3px;
  }

  .overflow-y-auto::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
  }

  /* Variable field animations */
  .variable-field {
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

  /* Accessibility improvements */
  @media (prefers-reduced-motion: reduce) {
    .variable-field {
      animation: none;
    }
  }
</style>
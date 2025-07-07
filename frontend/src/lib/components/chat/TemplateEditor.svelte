<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { PromptTemplate, TemplateVariable } from "$lib/stores/promptTemplates";

  export let template: PromptTemplate | null = null;
  export let isOpen: boolean = false;
  export let mode: "create" | "edit" = "create";

  const dispatch = createEventDispatcher();

  // Form data
  let formData = {
    name: "",
    description: "",
    template: "",
    category: "General",
    tags: "",
    variables: [] as TemplateVariable[],
  };

  let isSubmitting = false;
  let errors: Record<string, string> = {};

  // Predefined categories
  const categories = [
    "General",
    "Development", 
    "Analysis",
    "Planning",
    "Documentation",
    "Communication",
    "Testing",
    "Deployment"
  ];

  // Variable types
  const variableTypes = [
    { value: "text", label: "Text Input" },
    { value: "multiline", label: "Multi-line Text" },
    { value: "number", label: "Number" },
    { value: "select", label: "Dropdown Select" },
  ];

  // Initialize form when template changes
  $: if (template && isOpen) {
    formData = {
      name: template.name,
      description: template.description,
      template: template.template,
      category: template.category,
      tags: template.tags.join(", "),
      variables: [...template.variables],
    };
  } else if (!template && isOpen) {
    resetForm();
  }

  function resetForm() {
    formData = {
      name: "",
      description: "",
      template: "",
      category: "General",
      tags: "",
      variables: [],
    };
    errors = {};
  }

  function addVariable() {
    formData.variables = [
      ...formData.variables,
      {
        name: "",
        description: "",
        type: "text",
        required: false,
        default_value: "",
        placeholder: "",
      },
    ];
  }

  function removeVariable(index: number) {
    formData.variables = formData.variables.filter((_, i) => i !== index);
  }

  function addVariableOption(variableIndex: number) {
    const variable = formData.variables[variableIndex];
    if (!variable.options) {
      variable.options = [];
    }
    variable.options = [...variable.options, ""];
    formData.variables = [...formData.variables];
  }

  function removeVariableOption(variableIndex: number, optionIndex: number) {
    const variable = formData.variables[variableIndex];
    if (variable.options) {
      variable.options = variable.options.filter((_, i) => i !== optionIndex);
      formData.variables = [...formData.variables];
    }
  }

  function updateVariableOption(variableIndex: number, optionIndex: number, value: string) {
    const variable = formData.variables[variableIndex];
    if (variable.options) {
      variable.options[optionIndex] = value;
      formData.variables = [...formData.variables];
    }
  }

  function validateForm(): boolean {
    errors = {};

    if (!formData.name.trim()) {
      errors.name = "Template name is required";
    }

    if (!formData.description.trim()) {
      errors.description = "Description is required";
    }

    if (!formData.template.trim()) {
      errors.template = "Template content is required";
    }

    // Validate variables
    formData.variables.forEach((variable, index) => {
      if (!variable.name.trim()) {
        errors[`variable_${index}_name`] = "Variable name is required";
      }
      
      if (!variable.description.trim()) {
        errors[`variable_${index}_description`] = "Variable description is required";
      }

      // Check for duplicate variable names
      const duplicateIndex = formData.variables.findIndex(
        (v, i) => i !== index && v.name.trim() === variable.name.trim()
      );
      if (duplicateIndex !== -1) {
        errors[`variable_${index}_name`] = "Variable name must be unique";
      }

      // Validate select options
      if (variable.type === "select") {
        if (!variable.options || variable.options.length === 0) {
          errors[`variable_${index}_options`] = "Select variables must have options";
        } else if (variable.options.some(opt => !opt.trim())) {
          errors[`variable_${index}_options`] = "All options must have values";
        }
      }
    });

    return Object.keys(errors).length === 0;
  }

  async function handleSubmit() {
    if (!validateForm()) return;

    isSubmitting = true;

    try {
      const templateData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        template: formData.template.trim(),
        category: formData.category,
        tags: formData.tags.split(",").map(tag => tag.trim()).filter(tag => tag),
        variables: formData.variables.map(variable => ({
          ...variable,
          name: variable.name.trim(),
          description: variable.description.trim(),
          options: variable.type === "select" ? variable.options?.filter(opt => opt.trim()) : undefined,
        })),
        type: "user" as const,
        is_active: true,
      };

      if (mode === "create") {
        dispatch("create", templateData);
      } else {
        dispatch("update", { id: template!.id, ...templateData });
      }

      handleClose();
    } catch (error) {
      console.error("Failed to save template:", error);
    } finally {
      isSubmitting = false;
    }
  }

  function handleClose() {
    isOpen = false;
    resetForm();
    dispatch("close");
  }

  function previewTemplate() {
    // Create sample variables for preview
    const sampleVariables: Record<string, any> = {};
    formData.variables.forEach(variable => {
      switch (variable.type) {
        case "text":
          sampleVariables[variable.name] = `[${variable.name}]`;
          break;
        case "multiline":
          sampleVariables[variable.name] = `[${variable.name}]\n(multi-line content)`;
          break;
        case "number":
          sampleVariables[variable.name] = "123";
          break;
        case "select":
          sampleVariables[variable.name] = variable.options?.[0] || `[${variable.name}]`;
          break;
        default:
          sampleVariables[variable.name] = `[${variable.name}]`;
      }
    });

    let preview = formData.template;
    Object.entries(sampleVariables).forEach(([key, value]) => {
      const regex = new RegExp(`{{${key}}}`, 'g');
      preview = preview.replace(regex, String(value));
    });

    dispatch("preview", { template: formData.template, preview });
  }

  // Extract variables from template content
  function extractVariables() {
    const matches = formData.template.match(/{{([^}]+)}}/g);
    if (!matches) return;

    const existingNames = formData.variables.map(v => v.name);
    const newVariables: TemplateVariable[] = [];

    matches.forEach(match => {
      const name = match.replace(/[{}]/g, "");
      if (!existingNames.includes(name) && !newVariables.some(v => v.name === name)) {
        newVariables.push({
          name,
          description: `Description for ${name}`,
          type: "text",
          required: true,
          placeholder: `Enter ${name}...`,
        });
      }
    });

    if (newVariables.length > 0) {
      formData.variables = [...formData.variables, ...newVariables];
    }
  }
</script>

{#if isOpen}
  <!-- Modal backdrop -->
  <div class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
    <!-- Modal content -->
    <div class="bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between p-6 border-b border-gray-600">
        <h2 class="text-xl font-semibold text-white">
          {mode === "create" ? "Create New Template" : "Edit Template"}
        </h2>
        <button
          class="text-gray-400 hover:text-white transition-colors"
          on:click={handleClose}
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div class="overflow-y-auto max-h-[calc(90vh-180px)]">
        <form on:submit|preventDefault={handleSubmit} class="p-6 space-y-6">
          <!-- Basic Information -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Template Name -->
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">
                Template Name *
              </label>
              <input
                type="text"
                bind:value={formData.name}
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                class:border-red-500={errors.name}
                placeholder="e.g., Code Review Template"
                required
              />
              {#if errors.name}
                <p class="mt-1 text-sm text-red-400">{errors.name}</p>
              {/if}
            </div>

            <!-- Category -->
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">
                Category
              </label>
              <select
                bind:value={formData.category}
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {#each categories as category}
                  <option value={category}>{category}</option>
                {/each}
              </select>
            </div>
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">
              Description *
            </label>
            <textarea
              bind:value={formData.description}
              rows="2"
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              class:border-red-500={errors.description}
              placeholder="Brief description of what this template does..."
              required
            ></textarea>
            {#if errors.description}
              <p class="mt-1 text-sm text-red-400">{errors.description}</p>
            {/if}
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">
              Tags
            </label>
            <input
              type="text"
              bind:value={formData.tags}
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="tag1, tag2, tag3"
            />
            <p class="mt-1 text-xs text-gray-400">Comma-separated tags for easier searching</p>
          </div>

          <!-- Template Content -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium text-gray-300">
                Template Content *
              </label>
              <div class="flex space-x-2">
                <button
                  type="button"
                  class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                  on:click={extractVariables}
                >
                  Extract Variables
                </button>
                <button
                  type="button"
                  class="text-xs text-green-400 hover:text-green-300 transition-colors"
                  on:click={previewTemplate}
                >
                  Preview
                </button>
              </div>
            </div>
            <textarea
              bind:value={formData.template}
              rows="8"
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              class:border-red-500={errors.template}
              placeholder="Enter your template content here. Use {{variable_name}} for variables..."
              required
            ></textarea>
            {#if errors.template}
              <p class="mt-1 text-sm text-red-400">{errors.template}</p>
            {/if}
            <p class="mt-1 text-xs text-gray-400">
              Use <code class="bg-gray-600 px-1 rounded">{{variable_name}}</code> syntax for variables
            </p>
          </div>

          <!-- Variables -->
          <div>
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-medium text-white">Variables</h3>
              <button
                type="button"
                class="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
                on:click={addVariable}
              >
                + Add Variable
              </button>
            </div>

            {#if formData.variables.length === 0}
              <p class="text-gray-400 text-center py-4">
                No variables defined. Click "Add Variable" or "Extract Variables" to get started.
              </p>
            {:else}
              <div class="space-y-4">
                {#each formData.variables as variable, index}
                  <div class="bg-gray-700 rounded-lg p-4 border border-gray-600">
                    <div class="flex items-center justify-between mb-3">
                      <h4 class="text-sm font-medium text-white">Variable {index + 1}</h4>
                      <button
                        type="button"
                        class="text-red-400 hover:text-red-300 transition-colors"
                        on:click={() => removeVariable(index)}
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <!-- Variable Name -->
                      <div>
                        <label class="block text-xs font-medium text-gray-300 mb-1">
                          Variable Name *
                        </label>
                        <input
                          type="text"
                          bind:value={variable.name}
                          class="w-full px-2 py-1 text-sm bg-gray-600 border border-gray-500 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          class:border-red-500={errors[`variable_${index}_name`]}
                          placeholder="variable_name"
                        />
                        {#if errors[`variable_${index}_name`]}
                          <p class="mt-1 text-xs text-red-400">{errors[`variable_${index}_name`]}</p>
                        {/if}
                      </div>

                      <!-- Variable Type -->
                      <div>
                        <label class="block text-xs font-medium text-gray-300 mb-1">
                          Type
                        </label>
                        <select
                          bind:value={variable.type}
                          class="w-full px-2 py-1 text-sm bg-gray-600 border border-gray-500 rounded text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                          {#each variableTypes as type}
                            <option value={type.value}>{type.label}</option>
                          {/each}
                        </select>
                      </div>

                      <!-- Variable Description -->
                      <div class="md:col-span-2">
                        <label class="block text-xs font-medium text-gray-300 mb-1">
                          Description *
                        </label>
                        <input
                          type="text"
                          bind:value={variable.description}
                          class="w-full px-2 py-1 text-sm bg-gray-600 border border-gray-500 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          class:border-red-500={errors[`variable_${index}_description`]}
                          placeholder="Description of this variable"
                        />
                        {#if errors[`variable_${index}_description`]}
                          <p class="mt-1 text-xs text-red-400">{errors[`variable_${index}_description`]}</p>
                        {/if}
                      </div>

                      <!-- Placeholder -->
                      <div>
                        <label class="block text-xs font-medium text-gray-300 mb-1">
                          Placeholder
                        </label>
                        <input
                          type="text"
                          bind:value={variable.placeholder}
                          class="w-full px-2 py-1 text-sm bg-gray-600 border border-gray-500 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="Placeholder text"
                        />
                      </div>

                      <!-- Default Value -->
                      <div>
                        <label class="block text-xs font-medium text-gray-300 mb-1">
                          Default Value
                        </label>
                        <input
                          type="text"
                          bind:value={variable.default_value}
                          class="w-full px-2 py-1 text-sm bg-gray-600 border border-gray-500 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="Default value"
                        />
                      </div>

                      <!-- Required -->
                      <div class="md:col-span-2">
                        <label class="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            bind:checked={variable.required}
                            class="rounded bg-gray-600 border-gray-500 text-blue-600 focus:ring-blue-500"
                          />
                          <span class="text-xs text-gray-300">Required field</span>
                        </label>
                      </div>

                      <!-- Select Options -->
                      {#if variable.type === "select"}
                        <div class="md:col-span-2">
                          <div class="flex items-center justify-between mb-2">
                            <label class="block text-xs font-medium text-gray-300">
                              Options *
                            </label>
                            <button
                              type="button"
                              class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                              on:click={() => addVariableOption(index)}
                            >
                              + Add Option
                            </button>
                          </div>
                          
                          {#if variable.options && variable.options.length > 0}
                            <div class="space-y-2">
                              {#each variable.options as option, optionIndex}
                                <div class="flex items-center space-x-2">
                                  <input
                                    type="text"
                                    value={option}
                                    on:input={(e) => updateVariableOption(index, optionIndex, e.target.value)}
                                    class="flex-1 px-2 py-1 text-sm bg-gray-600 border border-gray-500 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                    placeholder="Option value"
                                  />
                                  <button
                                    type="button"
                                    class="text-red-400 hover:text-red-300 transition-colors"
                                    on:click={() => removeVariableOption(index, optionIndex)}
                                  >
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                  </button>
                                </div>
                              {/each}
                            </div>
                          {:else}
                            <p class="text-xs text-gray-400">No options defined. Click "Add Option" to add select options.</p>
                          {/if}
                          
                          {#if errors[`variable_${index}_options`]}
                            <p class="mt-1 text-xs text-red-400">{errors[`variable_${index}_options`]}</p>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </form>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-end space-x-3 p-6 border-t border-gray-600">
        <button
          type="button"
          class="px-4 py-2 text-gray-300 hover:text-white transition-colors"
          on:click={handleClose}
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
            Saving...
          {:else}
            {mode === "create" ? "Create Template" : "Update Template"}
          {/if}
        </button>
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
</style>
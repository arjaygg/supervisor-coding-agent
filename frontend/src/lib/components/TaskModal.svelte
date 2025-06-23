<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import { api } from "$lib/utils/api";

  export let task = null;
  export let isOpen = false;

  const dispatch = createEventDispatcher();

  let loading = false;
  let error = null;
  let taskSessions = [];
  let editMode = false;
  let editForm = {
    priority: 5,
    payload: {},
  };

  $: if (task && isOpen) {
    loadTaskDetails();
    editForm = {
      priority: task.priority || 5,
      payload: task.payload || {},
    };
  }

  async function loadTaskDetails() {
    if (!task?.id) return;

    loading = true;
    error = null;

    try {
      const response = await api.get(`/tasks/${task.id}/sessions`);
      taskSessions = response.data || [];
    } catch (err) {
      error = "Failed to load task details";
      console.error("Error loading task details:", err);
    } finally {
      loading = false;
    }
  }

  function closeModal() {
    isOpen = false;
    editMode = false;
    error = null;
    dispatch("close");
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      closeModal();
    }
  }

  async function saveTask() {
    if (!task?.id) return;

    loading = true;
    error = null;

    try {
      const updateData = {
        priority: editForm.priority,
        payload: editForm.payload,
      };

      await api.patch(`/tasks/${task.id}`, updateData);

      // Update the task object
      task.priority = editForm.priority;
      task.payload = editForm.payload;

      editMode = false;
      dispatch("taskUpdated", task);
    } catch (err) {
      error = "Failed to save task";
      console.error("Error saving task:", err);
    } finally {
      loading = false;
    }
  }

  async function retryTask() {
    if (!task?.id) return;

    loading = true;
    error = null;

    try {
      await api.post(`/tasks/${task.id}/retry`);
      task.status = "PENDING";
      task.retry_count = (task.retry_count || 0) + 1;
      dispatch("taskUpdated", task);
    } catch (err) {
      error = "Failed to retry task";
      console.error("Error retrying task:", err);
    } finally {
      loading = false;
    }
  }

  async function deleteTask() {
    if (!task?.id || !confirm("Are you sure you want to delete this task?"))
      return;

    loading = true;
    error = null;

    try {
      await api.delete(`/tasks/${task.id}`);
      dispatch("taskDeleted", task);
      closeModal();
    } catch (err) {
      error = "Failed to delete task";
      console.error("Error deleting task:", err);
    } finally {
      loading = false;
    }
  }

  function formatDate(dateString) {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString();
  }

  function getStatusColor(status) {
    switch (status) {
      case "COMPLETED":
        return "text-green-400";
      case "FAILED":
        return "text-red-400";
      case "IN_PROGRESS":
        return "text-blue-400";
      case "QUEUED":
        return "text-yellow-400";
      case "RETRY":
        return "text-orange-400";
      default:
        return "text-gray-400";
    }
  }

  function handleKeydown(event) {
    if (event.key === "Escape") {
      closeModal();
    }
  }

  onMount(() => {
    function handleEscape(event) {
      if (event.key === "Escape" && isOpen) {
        closeModal();
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  });
</script>

{#if isOpen && task}
  <!-- Modal backdrop -->
  <div
    class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
    on:click={handleBackdropClick}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
  >
    <!-- Modal content -->
    <div
      class="bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between p-6 border-b border-gray-700"
      >
        <div>
          <h2 id="modal-title" class="text-xl font-semibold text-white">
            Task #{task.id}
          </h2>
          <p class="text-gray-400 text-sm mt-1">
            {task.type} •
            <span class={getStatusColor(task.status)}>{task.status}</span>
          </p>
        </div>

        <div class="flex items-center gap-2">
          {#if !editMode}
            <button
              on:click={() => (editMode = true)}
              class="btn-secondary text-sm px-3 py-1"
              title="Edit task"
            >
              Edit
            </button>
          {/if}

          {#if task.status === "FAILED"}
            <button
              on:click={retryTask}
              class="btn-primary text-sm px-3 py-1"
              disabled={loading}
              title="Retry task"
            >
              Retry
            </button>
          {/if}

          <button
            on:click={deleteTask}
            class="btn-danger text-sm px-3 py-1"
            disabled={loading}
            title="Delete task"
          >
            Delete
          </button>

          <button
            on:click={closeModal}
            class="text-gray-400 hover:text-white p-1"
            title="Close modal"
          >
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6">
        {#if error}
          <div
            class="bg-red-900/20 border border-red-500/50 rounded-lg p-4 mb-6"
          >
            <p class="text-red-400">{error}</p>
          </div>
        {/if}

        {#if loading}
          <div class="flex items-center justify-center py-8">
            <div
              class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"
            />
            <span class="ml-3 text-gray-400">Loading...</span>
          </div>
        {:else}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Task Details -->
            <div class="space-y-6">
              <div class="bg-gray-900 rounded-lg p-4">
                <h3 class="text-lg font-medium text-white mb-4">
                  Task Information
                </h3>

                <div class="space-y-3 text-sm">
                  <div class="flex justify-between">
                    <span class="text-gray-400">Created</span>
                    <span class="text-gray-300"
                      >{formatDate(task.created_at)}</span
                    >
                  </div>

                  <div class="flex justify-between">
                    <span class="text-gray-400">Updated</span>
                    <span class="text-gray-300"
                      >{formatDate(task.updated_at)}</span
                    >
                  </div>

                  <div class="flex justify-between">
                    <span class="text-gray-400">Priority</span>
                    <span class="text-gray-300">
                      {#if editMode}
                        <input
                          type="number"
                          min="1"
                          max="10"
                          bind:value={editForm.priority}
                          class="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white w-16"
                        />
                      {:else}
                        {task.priority}/10
                      {/if}
                    </span>
                  </div>

                  <div class="flex justify-between">
                    <span class="text-gray-400">Retry Count</span>
                    <span class="text-gray-300">{task.retry_count || 0}</span>
                  </div>

                  {#if task.assigned_agent_id}
                    <div class="flex justify-between">
                      <span class="text-gray-400">Agent</span>
                      <span class="text-gray-300 font-mono"
                        >{task.assigned_agent_id}</span
                      >
                    </div>
                  {/if}

                  {#if task.error_message}
                    <div class="mt-4">
                      <span class="text-gray-400 block mb-2">Error Message</span
                      >
                      <div
                        class="bg-red-900/20 border border-red-500/50 rounded p-3"
                      >
                        <code class="text-red-400 text-xs break-all"
                          >{task.error_message}</code
                        >
                      </div>
                    </div>
                  {/if}
                </div>
              </div>

              <!-- Task Payload -->
              <div class="bg-gray-900 rounded-lg p-4">
                <h3 class="text-lg font-medium text-white mb-4">
                  Task Payload
                </h3>

                {#if editMode}
                  <textarea
                    bind:value={editForm.payload}
                    class="w-full h-40 bg-gray-700 border border-gray-600 rounded p-3 text-white font-mono text-sm resize-none focus:outline-none focus:border-blue-500"
                    placeholder="Task payload (JSON)"
                  />
                {:else}
                  <pre
                    class="bg-gray-800 rounded p-3 text-green-400 text-xs overflow-x-auto"><code
                      >{JSON.stringify(task.payload, null, 2)}</code
                    ></pre>
                {/if}
              </div>

              {#if editMode}
                <div class="flex gap-3">
                  <button
                    on:click={saveTask}
                    disabled={loading}
                    class="btn-primary px-4 py-2"
                  >
                    Save Changes
                  </button>
                  <button
                    on:click={() => (editMode = false)}
                    class="btn-secondary px-4 py-2"
                  >
                    Cancel
                  </button>
                </div>
              {/if}
            </div>

            <!-- Task Sessions -->
            <div class="space-y-6">
              <div class="bg-gray-900 rounded-lg p-4">
                <h3 class="text-lg font-medium text-white mb-4">
                  Execution History
                </h3>

                {#if taskSessions.length === 0}
                  <p class="text-gray-500 text-center py-4">
                    No execution history available
                  </p>
                {:else}
                  <div class="space-y-4">
                    {#each taskSessions as session}
                      <div class="border border-gray-700 rounded-lg p-4">
                        <div class="flex justify-between items-center mb-2">
                          <span class="text-gray-400 text-sm"
                            >Session #{session.id}</span
                          >
                          <span class="text-gray-400 text-sm"
                            >{formatDate(session.created_at)}</span
                          >
                        </div>

                        {#if session.execution_time_seconds}
                          <div class="text-sm text-gray-400 mb-2">
                            Execution time: {session.execution_time_seconds}s
                          </div>
                        {/if}

                        {#if session.prompt}
                          <details class="mb-2">
                            <summary
                              class="text-blue-400 cursor-pointer text-sm"
                              >View Prompt</summary
                            >
                            <pre
                              class="mt-2 bg-gray-800 rounded p-2 text-xs text-gray-300 overflow-x-auto"><code
                                >{session.prompt}</code
                              ></pre>
                          </details>
                        {/if}

                        {#if session.response}
                          <details>
                            <summary
                              class="text-green-400 cursor-pointer text-sm"
                              >View Response</summary
                            >
                            <pre
                              class="mt-2 bg-gray-800 rounded p-2 text-xs text-gray-300 overflow-x-auto"><code
                                >{session.response}</code
                              ></pre>
                          </details>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

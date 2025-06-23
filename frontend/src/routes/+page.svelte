<script lang="ts">
  import { onMount } from "svelte";
  import {
    tasks,
    activeTasks,
    pendingTasks,
    completedTasks,
    failedTasks,
  } from "$lib/stores/tasks";
  import { websocket } from "$lib/stores/websocket";
  import TaskList from "$lib/components/TaskList.svelte";
  import TaskStats from "$lib/components/TaskStats.svelte";
  import QuickActions from "$lib/components/QuickActions.svelte";
  import StatusIndicator from "$lib/components/StatusIndicator.svelte";
  import TaskModal from "$lib/components/TaskModal.svelte";

  let showCreateTaskModal = false;
  let selectedTaskStatus = "all";
  let selectedTask = null;
  let isTaskModalOpen = false;

  // Task creation form state
  let taskForm = {
    type: "CODE_ANALYSIS",
    priority: 5,
    description: "",
  };
  let isCreatingTask = false;

  $: filteredTasks =
    selectedTaskStatus === "all"
      ? $tasks
      : selectedTaskStatus === "active"
      ? $activeTasks
      : selectedTaskStatus === "pending"
      ? $pendingTasks
      : selectedTaskStatus === "completed"
      ? $completedTasks
      : $failedTasks;

  // Task view handler
  function handleViewTask(event) {
    const task = $tasks.find((t) => t.id === event.detail.taskId);
    if (task) {
      selectedTask = task;
      isTaskModalOpen = true;
    }
  }

  // Task modal handlers
  function handleTaskUpdated(event) {
    const updatedTask = event.detail;
    tasks.updateTask(updatedTask);
  }

  function handleTaskDeleted(event) {
    const deletedTask = event.detail;
    tasks.removeTask(deletedTask.id);
  }

  function closeTaskModal() {
    isTaskModalOpen = false;
    selectedTask = null;
  }

  // Task creation handler
  async function handleCreateTask() {
    if (!taskForm.description.trim()) {
      alert("Please provide a task description");
      return;
    }

    isCreatingTask = true;

    try {
      const payload = {
        description: taskForm.description,
        // Add basic payload structure based on task type
        ...(taskForm.type === "CODE_ANALYSIS" && {
          code: taskForm.description,
          language: "auto-detect",
        }),
        ...(taskForm.type === "BUG_FIX" && {
          bug_description: taskForm.description,
          error_message: "",
          steps_to_reproduce: "",
        }),
        ...(taskForm.type === "FEATURE" && {
          requirements: taskForm.description,
          existing_code_context: "",
        }),
        ...(taskForm.type === "REFACTOR" && {
          target: taskForm.description,
          current_code: "",
          requirements: "",
        }),
        ...(taskForm.type === "PR_REVIEW" && {
          repository: "unknown",
          title: taskForm.description,
          description: taskForm.description,
          diff: "",
        }),
      };

      await tasks.createTask({
        type: taskForm.type,
        payload: payload,
        priority: taskForm.priority,
      });

      // Reset form and close modal
      taskForm = {
        type: "CODE_ANALYSIS",
        priority: 5,
        description: "",
      };
      showCreateTaskModal = false;

      // Refresh task list
      await tasks.fetchTasks();
    } catch (error) {
      console.error("Failed to create task:", error);
      alert("Failed to create task. Please try again.");
    } finally {
      isCreatingTask = false;
    }
  }

  // Initialize data and setup periodic refresh
  onMount(async () => {
    // Connect WebSocket
    websocket.connect();

    // Initial data load
    await tasks.fetchTasks();
    await tasks.refreshStats();

    // Setup periodic refresh
    const interval = setInterval(async () => {
      await tasks.refreshStats();
      await tasks.fetchTasks(); // Also refresh tasks list
    }, 30000); // Every 30 seconds

    return () => {
      clearInterval(interval);
      websocket.disconnect();
    };
  });
</script>

<svelte:head>
  <title>Dashboard - Supervisor Coding Agent</title>
  <meta name="description" content="AI-powered task orchestration dashboard" />
</svelte:head>

<!-- Mobile-first header -->
<header class="bg-gray-800 border-b border-gray-700 px-4 py-3 md:px-6 md:py-4">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-lg md:text-xl font-bold text-white">Supervisor Agent</h1>
      <div class="flex items-center space-x-2 mt-1">
        <StatusIndicator connected={$websocket.connected} />
        <span class="text-xs text-gray-400">
          {$websocket.connected ? "Connected" : "Disconnected"}
        </span>
      </div>
    </div>

    <!-- Quick stats for mobile -->
    <div class="flex space-x-2 md:hidden">
      <div class="text-center">
        <div class="text-sm font-bold text-white">{$tasks.length}</div>
        <div class="text-xs text-gray-400">Total</div>
      </div>
      <div class="text-center">
        <div class="text-sm font-bold text-blue-400">{$activeTasks.length}</div>
        <div class="text-xs text-gray-400">Active</div>
      </div>
    </div>
  </div>
</header>

<!-- Error notification -->
{#if $tasks.error}
  <div class="fixed top-4 right-4 z-50 max-w-md">
    <div class="bg-red-800 border border-red-600 rounded-lg p-4 shadow-lg">
      <div class="flex items-start">
        <svg
          class="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clip-rule="evenodd"
          />
        </svg>
        <div class="flex-1">
          <h4 class="text-sm font-medium text-red-100 mb-1">Error</h4>
          <p class="text-sm text-red-200">{$tasks.error}</p>
        </div>
        <button
          class="ml-3 text-red-400 hover:text-red-300"
          on:click={() => tasks.error.set(null)}
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Main content -->
<div class="container mx-auto px-4 py-4 md:px-6 md:py-6 max-w-7xl">
  <!-- Desktop stats grid -->
  <div class="hidden md:block mb-6">
    <TaskStats />
  </div>

  <!-- Mobile filter tabs -->
  <div class="mb-4 overflow-x-auto">
    <div class="flex space-x-2 min-w-max pb-2">
      <button
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === "all"}
        class:btn-secondary={selectedTaskStatus !== "all"}
        on:click={() => (selectedTaskStatus = "all")}
      >
        All ({$tasks.length})
      </button>
      <button
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === "active"}
        class:btn-secondary={selectedTaskStatus !== "active"}
        on:click={() => (selectedTaskStatus = "active")}
      >
        Active ({$activeTasks.length})
      </button>
      <button
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === "pending"}
        class:btn-secondary={selectedTaskStatus !== "pending"}
        on:click={() => (selectedTaskStatus = "pending")}
      >
        Pending ({$pendingTasks.length})
      </button>
      <button
        class="btn-secondary text-sm"
        class:btn-primary={selectedTaskStatus === "completed"}
        class:btn-secondary={selectedTaskStatus !== "completed"}
        on:click={() => (selectedTaskStatus = "completed")}
      >
        Done ({$completedTasks.length})
      </button>
      {#if $failedTasks.length > 0}
        <button
          class="btn-danger text-sm"
          class:btn-primary={selectedTaskStatus === "failed"}
          on:click={() => (selectedTaskStatus = "failed")}
        >
          Failed ({$failedTasks.length})
        </button>
      {/if}
    </div>
  </div>

  <!-- Quick actions -->
  <div class="mb-4">
    <QuickActions on:createTask={() => (showCreateTaskModal = true)} />
  </div>

  <!-- Task list -->
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-white">
        {selectedTaskStatus === "all"
          ? "All Tasks"
          : selectedTaskStatus === "active"
          ? "Active Tasks"
          : selectedTaskStatus === "pending"
          ? "Pending Tasks"
          : selectedTaskStatus === "completed"
          ? "Completed Tasks"
          : "Failed Tasks"}
      </h2>

      <!-- Refresh button -->
      <button
        class="btn-secondary text-sm"
        on:click={() => tasks.fetchTasks()}
        disabled={$tasks.loading}
      >
        {#if $tasks.loading}
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
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        {/if}
        Refresh
      </button>
    </div>

    <TaskList
      tasks={filteredTasks}
      on:viewTask={handleViewTask}
      on:approveTask={(e) => console.log("Approve task:", e.detail.taskId)}
      on:rejectTask={(e) => console.log("Reject task:", e.detail.taskId)}
      on:retryTask={(e) => console.log("Retry task:", e.detail.taskId)}
    />
  </div>
</div>

<!-- Create task modal (mobile-optimized) -->
{#if showCreateTaskModal}
  <div
    class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-end md:items-center justify-center p-4"
  >
    <div
      class="bg-gray-800 rounded-t-lg md:rounded-lg w-full md:max-w-md max-h-[90vh] overflow-y-auto"
    >
      <!-- Mobile drag handle -->
      <div
        class="md:hidden w-8 h-1 bg-gray-600 rounded-full mx-auto mt-2 mb-4"
      />

      <div class="p-4 md:p-6">
        <h3 class="text-lg font-semibold text-white mb-4">Create New Task</h3>

        <form on:submit|preventDefault={handleCreateTask}>
          <div class="space-y-4">
            <div>
              <label
                for="task-type"
                class="block text-sm font-medium text-gray-300 mb-2"
                >Task Type</label
              >
              <select
                id="task-type"
                bind:value={taskForm.type}
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                disabled={isCreatingTask}
              >
                <option value="PR_REVIEW">PR Review</option>
                <option value="CODE_ANALYSIS">Code Analysis</option>
                <option value="BUG_FIX">Bug Fix</option>
                <option value="FEATURE">Feature Development</option>
                <option value="REFACTOR">Refactoring</option>
              </select>
            </div>

            <div>
              <label
                for="task-priority"
                class="block text-sm font-medium text-gray-300 mb-2"
                >Priority</label
              >
              <select
                id="task-priority"
                bind:value={taskForm.priority}
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                disabled={isCreatingTask}
              >
                <option value={1}>🔴 Critical</option>
                <option value={3}>🟡 High</option>
                <option value={5}>🔵 Normal</option>
                <option value={7}>🟢 Low</option>
              </select>
            </div>

            <div>
              <label
                for="task-description"
                class="block text-sm font-medium text-gray-300 mb-2"
                >Description</label
              >
              <textarea
                id="task-description"
                bind:value={taskForm.description}
                class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
                rows="3"
                placeholder="Describe the task..."
                disabled={isCreatingTask}
                required
              />
            </div>
          </div>

          <div class="flex space-x-3 mt-6">
            <button
              type="submit"
              class="btn-primary flex-1"
              disabled={isCreatingTask || !taskForm.description.trim()}
            >
              {#if isCreatingTask}
                <svg
                  class="w-4 h-4 animate-spin mr-2"
                  fill="none"
                  viewBox="0 0 24 24"
                >
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
                Creating...
              {:else}
                Create Task
              {/if}
            </button>
            <button
              type="button"
              class="btn-secondary"
              on:click={() => (showCreateTaskModal = false)}
              disabled={isCreatingTask}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<!-- Task detail modal -->
<TaskModal
  bind:isOpen={isTaskModalOpen}
  bind:task={selectedTask}
  on:close={closeTaskModal}
  on:taskUpdated={handleTaskUpdated}
  on:taskDeleted={handleTaskDeleted}
/>

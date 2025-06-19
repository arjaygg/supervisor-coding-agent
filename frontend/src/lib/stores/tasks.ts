import { writable, derived } from 'svelte/store';
import { websocket } from './websocket';
import { api, ApiError } from '../utils/api';

export interface Task {
  id: number;
  type: string;
  status: string;
  payload: any;
  priority: number;
  created_at: string;
  updated_at: string;
  assigned_agent_id: string | null;
  retry_count: number;
  error_message: string | null;
}

export interface TaskStats {
  total_tasks: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  by_priority: Record<string, number>;
}

function createTaskStore() {
  const { subscribe, set, update } = writable<Task[]>([]);
  const stats = writable<TaskStats>({
    total_tasks: 0,
    by_status: {},
    by_type: {},
    by_priority: {}
  });

  const loading = writable(false);
  const error = writable<string | null>(null);

  // Subscribe to WebSocket updates
  websocket.subscribe((wsState) => {
    if (wsState.lastMessage && wsState.lastMessage.data.type === 'task_update') {
      const updatedTask = wsState.lastMessage.data.task;
      
      update(tasks => {
        const index = tasks.findIndex(t => t.id === updatedTask.id);
        if (index >= 0) {
          tasks[index] = updatedTask;
        } else {
          tasks.unshift(updatedTask);
        }
        return [...tasks];
      });
      
      // Refresh stats when tasks update
      refreshStats();
    }
  });

  const fetchTasks = async (params: {
    skip?: number;
    limit?: number;
    status?: string;
  } = {}) => {
    loading.set(true);
    error.set(null);
    
    try {
      const tasks = await api.getTasks(params);
      set(tasks);
    } catch (err) {
      if (err instanceof ApiError) {
        error.set(err.message);
      } else {
        error.set(err instanceof Error ? err.message : 'Failed to fetch tasks');
      }
      console.error('Error fetching tasks:', err);
    } finally {
      loading.set(false);
    }
  };

  const refreshStats = async () => {
    try {
      const taskStats = await api.getTaskStats();
      stats.set(taskStats);
    } catch (err) {
      console.error('Error fetching task stats:', err);
    }
  };

  const createTask = async (taskData: {
    type: string;
    payload: any;
    priority?: number;
  }) => {
    try {
      const newTask = await api.createTask(taskData);
      
      // Add to store
      update(tasks => [newTask, ...tasks]);
      
      return newTask;
    } catch (err) {
      if (err instanceof ApiError) {
        error.set(err.message);
      } else {
        error.set(err instanceof Error ? err.message : 'Failed to create task');
      }
      throw err;
    }
  };

  const retryTask = async (taskId: number) => {
    try {
      await api.retryTask(taskId);
      
      // Refresh tasks to get updated status
      await fetchTasks();
    } catch (err) {
      if (err instanceof ApiError) {
        error.set(err.message);
      } else {
        error.set(err instanceof Error ? err.message : 'Failed to retry task');
      }
      throw err;
    }
  };

  const updateTask = (updatedTask: Task) => {
    update(tasks => {
      const index = tasks.findIndex(t => t.id === updatedTask.id);
      if (index >= 0) {
        tasks[index] = updatedTask;
      }
      return [...tasks];
    });
  };

  const removeTask = (taskId: number) => {
    update(tasks => tasks.filter(t => t.id !== taskId));
  };

  return {
    subscribe,
    stats: { subscribe: stats.subscribe },
    loading: { subscribe: loading.subscribe },
    error: { subscribe: error.subscribe },
    fetchTasks,
    refreshStats,
    createTask,
    retryTask,
    updateTask,
    removeTask
  };
}

export const tasks = createTaskStore();

// Derived stores for filtered tasks
export const pendingTasks = derived(tasks, ($tasks) => 
  $tasks.filter(task => task.status === 'PENDING')
);

export const activeTasks = derived(tasks, ($tasks) => 
  $tasks.filter(task => ['QUEUED', 'IN_PROGRESS'].includes(task.status))
);

export const completedTasks = derived(tasks, ($tasks) => 
  $tasks.filter(task => task.status === 'COMPLETED')
);

export const failedTasks = derived(tasks, ($tasks) => 
  $tasks.filter(task => task.status === 'FAILED')
);
export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: any) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  const defaultOptions: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, { ...defaultOptions, ...options });

    if (!response.ok) {
      let errorMessage = `HTTP error! status: ${response.status}`;
      let errorData = null;

      try {
        errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        // If we can't parse the error response, use the default message
        if (response.status === 404) {
          errorMessage = "Resource not found";
        } else if (response.status === 500) {
          errorMessage = "Internal server error";
        } else if (response.status === 503) {
          errorMessage = "Service unavailable";
        }
      }

      throw new ApiError(response.status, errorMessage, errorData);
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return response.json();
    } else {
      return response.text() as unknown as T;
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    // Handle network errors
    if (error instanceof TypeError && error.message.includes("fetch")) {
      throw new ApiError(0, "Network error - please check your connection");
    }

    throw new ApiError(0, `Request failed: ${error.message}`);
  }
}

export const api = {
  // Generic HTTP methods
  get: <T>(endpoint: string) => apiRequest<T>(endpoint),

  post: <T>(endpoint: string, data?: any) =>
    apiRequest<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data?: any) =>
    apiRequest<T>(endpoint, {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
    }),

  delete: <T>(endpoint: string) =>
    apiRequest<T>(endpoint, { method: "DELETE" }),

  // Tasks
  getTasks: (params?: { skip?: number; limit?: number; status?: string }) =>
    apiRequest<any[]>(
      `/api/v1/tasks${
        params
          ? `?${new URLSearchParams(
              Object.entries(params).filter(([_, v]) => v !== undefined) as [
                string,
                string
              ][]
            ).toString()}`
          : ""
      }`
    ),

  getTask: (id: number) => apiRequest<any>(`/api/v1/tasks/${id}`),

  createTask: (data: { type: string; payload: any; priority?: number }) =>
    apiRequest<any>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateTask: (id: number, data: { priority?: number; payload?: any }) =>
    apiRequest<any>(`/api/v1/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteTask: (id: number) =>
    apiRequest<{ message: string }>(`/api/v1/tasks/${id}`, {
      method: "DELETE",
    }),

  retryTask: (id: number) =>
    apiRequest<{ message: string; task_id: number }>(
      `/api/v1/tasks/${id}/retry`,
      {
        method: "POST",
      }
    ),

  getTaskSessions: (id: number) =>
    apiRequest<any[]>(`/api/v1/tasks/${id}/sessions`),

  getTaskStats: () => apiRequest<any>("/api/v1/tasks/stats/summary"),

  // Agents
  getAgents: () => apiRequest<any[]>("/api/v1/agents"),

  getQuotaStatus: () => apiRequest<any>("/api/v1/agents/quota/status"),

  // Health
  getHealth: () => apiRequest<any>("/api/v1/healthz"),

  getDetailedHealth: () => apiRequest<any>("/api/v1/health/detailed"),

  // Analytics
  getAnalyticsSummary: () => apiRequest<any>("/api/v1/analytics/summary"),

  queryAnalytics: (query: any) =>
    apiRequest<any>("/api/v1/analytics/query", {
      method: "POST",
      body: JSON.stringify(query),
    }),

  getAnalyticsInsights: (timeframe?: string) =>
    apiRequest<any[]>(
      `/api/v1/analytics/insights${timeframe ? `?timeframe=${timeframe}` : ""}`
    ),

  getAnalyticsTrends: (metricType: string, predictionHours?: number) =>
    apiRequest<any>(
      `/api/v1/analytics/trends/${metricType}${
        predictionHours ? `?prediction_hours=${predictionHours}` : ""
      }`
    ),

  getAnalyticsMetrics: (metricType?: string, limit?: number) =>
    apiRequest<any[]>(
      `/api/v1/analytics/metrics?${new URLSearchParams({
        ...(metricType && { metric_type: metricType }),
        ...(limit && { limit: limit.toString() }),
      }).toString()}`
    ),

  collectTaskMetrics: (taskId: number) =>
    apiRequest<{ message: string }>(
      `/api/v1/analytics/collect/task/${taskId}`,
      {
        method: "POST",
      }
    ),

  collectSystemMetrics: () =>
    apiRequest<{ message: string }>("/api/v1/analytics/collect/system", {
      method: "POST",
    }),

  getAnalyticsHealth: () => apiRequest<any>("/api/v1/analytics/health"),

  // Chat API methods
  getChatThreads: () => apiRequest<{
    threads: any[];
    total_count: number;
  }>("/api/v1/chat/threads"),

  createChatThread: (data: { title: string; initial_message?: string }) =>
    apiRequest<any>("/api/v1/chat/threads", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getChatThread: (threadId: string) =>
    apiRequest<any>(`/api/v1/chat/threads/${threadId}`),

  updateChatThread: (threadId: string, data: any) =>
    apiRequest<any>(`/api/v1/chat/threads/${threadId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteChatThread: (threadId: string) =>
    apiRequest<{ message: string }>(`/api/v1/chat/threads/${threadId}`, {
      method: "DELETE",
    }),

  getChatMessages: (threadId: string, before?: string) => {
    const url = `/api/v1/chat/threads/${threadId}/messages`;
    const params = before ? `?before=${encodeURIComponent(before)}` : "";
    return apiRequest<{
      messages: any[];
      has_more: boolean;
      total_count: number;
    }>(`${url}${params}`);
  },

  sendChatMessage: (threadId: string, data: { content: string; message_type?: string; metadata?: any }) =>
    apiRequest<any>(`/api/v1/chat/threads/${threadId}/messages`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateChatMessage: (messageId: string, data: { content?: string; metadata?: any }) =>
    apiRequest<any>(`/api/v1/chat/messages/${messageId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Streaming chat endpoint
  streamChatResponse: (threadId: string, messageContent: string) => {
    return fetch(`/api/v1/chat/threads/${threadId}/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content: messageContent }),
    });
  },

  getChatNotifications: (unreadOnly?: boolean) => {
    const params = unreadOnly ? "?unread_only=true" : "";
    return apiRequest<any[]>(`/api/v1/chat/notifications${params}`);
  },

  markChatNotificationsRead: (threadId: string) =>
    apiRequest<{ message: string }>(
      `/api/v1/chat/threads/${threadId}/notifications/read`,
      {
        method: "POST",
      }
    ),

  // Message search
  searchMessages: (params: {
    q: string;
    role?: string;
    message_type?: string;
    date_range?: string;
    thread_ids?: string;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        searchParams.append(key, String(value));
      }
    });
    return apiRequest<{
      results: any[];
      total: number;
      took_ms: number;
    }>(`/api/v1/chat/search?${searchParams}`);
  },

  // Prompt Templates
  getPromptTemplates: () =>
    apiRequest<{
      user_templates: any[];
      community_templates: any[];
    }>("/api/v1/prompt-templates"),

  createPromptTemplate: (data: any) =>
    apiRequest<any>("/api/v1/prompt-templates", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updatePromptTemplate: (templateId: string, data: any) =>
    apiRequest<any>(`/api/v1/prompt-templates/${templateId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deletePromptTemplate: (templateId: string) =>
    apiRequest<{ message: string }>(`/api/v1/prompt-templates/${templateId}`, {
      method: "DELETE",
    }),

  logPromptTemplateUsage: (data: {
    template_id: string;
    variables: Record<string, any>;
    rendered_prompt: string;
  }) =>
    apiRequest<{ message: string }>("/api/v1/prompt-templates/usage", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Plugin Management
  getChatPlugins: () =>
    apiRequest<{
      plugins: any[];
      count: number;
      metrics: any;
    }>("/api/v1/chat/plugins"),

  getChatFunctions: () =>
    apiRequest<{
      functions: any[];
      count: number;
      categories: string[];
    }>("/api/v1/chat/functions"),

  callChatFunction: (functionName: string, args: Record<string, any>) =>
    apiRequest<any>(`/api/v1/chat/functions/${functionName}/call`, {
      method: "POST",
      body: JSON.stringify({ args }),
    }),

  activatePlugin: (pluginName: string) =>
    apiRequest<{ message: string }>(`/api/v1/chat/plugins/${pluginName}/activate`, {
      method: "POST",
    }),

  deactivatePlugin: (pluginName: string) =>
    apiRequest<{ message: string }>(`/api/v1/chat/plugins/${pluginName}/deactivate`, {
      method: "POST",
    }),

  analyzeThread: (threadId: string) =>
    apiRequest<{
      analysis: any;
      recommendations: any[];
      metrics: any;
    }>(`/api/v1/chat/threads/${threadId}/analyze`, {
      method: "POST",
    }),
};

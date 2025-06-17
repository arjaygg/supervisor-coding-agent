export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  const response = await fetch(url, { ...defaultOptions, ...options });

  if (!response.ok) {
    let errorMessage = `HTTP error! status: ${response.status}`;
    
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      // If we can't parse the error response, use the default message
    }
    
    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
}

export const api = {
  // Tasks
  getTasks: (params?: { skip?: number; limit?: number; status?: string }) =>
    apiRequest<any[]>(`/api/v1/tasks${params ? `?${new URLSearchParams(Object.entries(params).filter(([_, v]) => v !== undefined) as [string, string][]).toString()}` : ''}`),
  
  getTask: (id: number) =>
    apiRequest<any>(`/api/v1/tasks/${id}`),
  
  createTask: (data: { type: string; payload: any; priority?: number }) =>
    apiRequest<any>('/api/v1/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  retryTask: (id: number) =>
    apiRequest<{ message: string; task_id: number }>(`/api/v1/tasks/${id}/retry`, {
      method: 'POST',
    }),
  
  getTaskStats: () =>
    apiRequest<any>('/api/v1/tasks/stats/summary'),
  
  // Agents
  getAgents: () =>
    apiRequest<any[]>('/api/v1/agents'),
  
  getQuotaStatus: () =>
    apiRequest<any>('/api/v1/agents/quota/status'),
  
  // Health
  getHealth: () =>
    apiRequest<any>('/api/v1/healthz'),
  
  getDetailedHealth: () =>
    apiRequest<any>('/api/v1/health/detailed'),
};
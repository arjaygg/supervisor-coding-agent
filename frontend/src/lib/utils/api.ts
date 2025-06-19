export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: any) {
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
          errorMessage = 'Resource not found';
        } else if (response.status === 500) {
          errorMessage = 'Internal server error';
        } else if (response.status === 503) {
          errorMessage = 'Service unavailable';
        }
      }
      
      throw new ApiError(response.status, errorMessage, errorData);
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return response.json();
    } else {
      return response.text() as unknown as T;
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(0, 'Network error - please check your connection');
    }
    
    throw new ApiError(0, `Request failed: ${error.message}`);
  }
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
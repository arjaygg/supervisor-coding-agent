import { api, ApiError } from "../utils/api";
import type { ChatThread } from "../stores/chat";

export interface Plugin {
  id: string;
  name: string;
  version: string;
  description: string;
  enabled: boolean;
  health_status: "healthy" | "unhealthy" | "unknown";
  capabilities: string[];
  configuration: Record<string, any>;
  metrics: {
    calls_count: number;
    success_rate: number;
    avg_execution_time: number;
    last_used: string | null;
  };
}

export interface ChatFunction {
  name: string;
  description: string;
  category: string;
  parameters: {
    type: "object";
    properties: Record<string, any>;
    required: string[];
  };
  plugin_id: string;
  enabled: boolean;
}

export interface FunctionCallResult {
  success: boolean;
  result?: any;
  error?: string;
  execution_time_ms: number;
  metadata?: Record<string, any>;
}

export interface AnalysisResult {
  analysis: {
    summary: string;
    complexity_score: number;
    suggestions: string[];
    identified_patterns: string[];
  };
  recommendations: Array<{
    type: string;
    priority: "high" | "medium" | "low";
    description: string;
    action: string;
  }>;
  metrics: {
    message_count: number;
    analysis_time_ms: number;
    confidence_score: number;
  };
}

class PluginService {
  private pluginCache = new Map<string, Plugin>();
  private functionCache = new Map<string, ChatFunction>();
  private lastCacheUpdate = 0;
  private readonly CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  /**
   * Get all available plugins
   */
  async getPlugins(forceRefresh = false): Promise<Plugin[]> {
    if (!forceRefresh && this.isCacheValid() && this.pluginCache.size > 0) {
      return Array.from(this.pluginCache.values());
    }

    try {
      const response = await api.getChatPlugins();
      const plugins = response.plugins.map((p: any) => ({
        id: p.id,
        name: p.name,
        version: p.version,
        description: p.description,
        enabled: p.enabled,
        health_status: p.health_status,
        capabilities: p.capabilities || [],
        configuration: p.configuration || {},
        metrics: p.metrics || {
          calls_count: 0,
          success_rate: 0,
          avg_execution_time: 0,
          last_used: null,
        },
      }));

      // Update cache
      this.pluginCache.clear();
      plugins.forEach(plugin => this.pluginCache.set(plugin.id, plugin));
      this.lastCacheUpdate = Date.now();

      return plugins;
    } catch (error) {
      console.error("Failed to fetch plugins:", error);
      throw error;
    }
  }

  /**
   * Get all available functions
   */
  async getFunctions(forceRefresh = false): Promise<ChatFunction[]> {
    if (!forceRefresh && this.isCacheValid() && this.functionCache.size > 0) {
      return Array.from(this.functionCache.values());
    }

    try {
      const response = await api.getChatFunctions();
      const functions = response.functions.map((f: any) => ({
        name: f.name,
        description: f.description,
        category: f.category,
        parameters: f.parameters,
        plugin_id: f.plugin_id,
        enabled: f.enabled,
      }));

      // Update cache
      this.functionCache.clear();
      functions.forEach(func => this.functionCache.set(func.name, func));
      this.lastCacheUpdate = Date.now();

      return functions;
    } catch (error) {
      console.error("Failed to fetch functions:", error);
      throw error;
    }
  }

  /**
   * Get functions by category
   */
  async getFunctionsByCategory(category: string): Promise<ChatFunction[]> {
    const functions = await this.getFunctions();
    return functions.filter(func => func.category === category);
  }

  /**
   * Get functions by plugin
   */
  async getFunctionsByPlugin(pluginId: string): Promise<ChatFunction[]> {
    const functions = await this.getFunctions();
    return functions.filter(func => func.plugin_id === pluginId);
  }

  /**
   * Call a function
   */
  async callFunction(
    functionName: string,
    args: Record<string, any>
  ): Promise<FunctionCallResult> {
    try {
      const result = await api.callChatFunction(functionName, args);
      return {
        success: true,
        result: result.result,
        execution_time_ms: result.execution_time_ms || 0,
        metadata: result.metadata,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof ApiError ? error.message : String(error),
        execution_time_ms: 0,
      };
    }
  }

  /**
   * Activate a plugin
   */
  async activatePlugin(pluginName: string): Promise<void> {
    try {
      await api.activatePlugin(pluginName);
      // Invalidate cache to force refresh
      this.invalidateCache();
    } catch (error) {
      console.error(`Failed to activate plugin ${pluginName}:`, error);
      throw error;
    }
  }

  /**
   * Deactivate a plugin
   */
  async deactivatePlugin(pluginName: string): Promise<void> {
    try {
      await api.deactivatePlugin(pluginName);
      // Invalidate cache to force refresh
      this.invalidateCache();
    } catch (error) {
      console.error(`Failed to deactivate plugin ${pluginName}:`, error);
      throw error;
    }
  }

  /**
   * Analyze a chat thread
   */
  async analyzeThread(thread: ChatThread): Promise<AnalysisResult> {
    try {
      const response = await api.analyzeThread(thread.id);
      return {
        analysis: {
          summary: response.analysis.summary || "",
          complexity_score: response.analysis.complexity_score || 0,
          suggestions: response.analysis.suggestions || [],
          identified_patterns: response.analysis.identified_patterns || [],
        },
        recommendations: response.recommendations || [],
        metrics: {
          message_count: response.metrics.message_count || 0,
          analysis_time_ms: response.metrics.analysis_time_ms || 0,
          confidence_score: response.metrics.confidence_score || 0,
        },
      };
    } catch (error) {
      console.error(`Failed to analyze thread ${thread.id}:`, error);
      throw error;
    }
  }

  /**
   * Get plugin by ID
   */
  async getPlugin(pluginId: string): Promise<Plugin | null> {
    const plugins = await this.getPlugins();
    return plugins.find(p => p.id === pluginId) || null;
  }

  /**
   * Get function by name
   */
  async getFunction(functionName: string): Promise<ChatFunction | null> {
    const functions = await this.getFunctions();
    return functions.find(f => f.name === functionName) || null;
  }

  /**
   * Check if cache is still valid
   */
  private isCacheValid(): boolean {
    return Date.now() - this.lastCacheUpdate < this.CACHE_DURATION;
  }

  /**
   * Invalidate cache
   */
  private invalidateCache(): void {
    this.pluginCache.clear();
    this.functionCache.clear();
    this.lastCacheUpdate = 0;
  }

  /**
   * Validate function arguments against schema
   */
  validateFunctionArgs(func: ChatFunction, args: Record<string, any>): {
    valid: boolean;
    errors: string[];
  } {
    const errors: string[] = [];
    const { parameters } = func;

    // Check required parameters
    if (parameters.required) {
      for (const required of parameters.required) {
        if (!(required in args)) {
          errors.push(`Missing required parameter: ${required}`);
        }
      }
    }

    // Basic type checking for properties
    if (parameters.properties) {
      for (const [key, schema] of Object.entries(parameters.properties)) {
        if (key in args) {
          const value = args[key];
          const propSchema = schema as any;

          if (propSchema.type) {
            const expectedType = propSchema.type;
            const actualType = typeof value;

            if (expectedType === "number" && actualType !== "number") {
              errors.push(`Parameter ${key} should be a number, got ${actualType}`);
            } else if (expectedType === "string" && actualType !== "string") {
              errors.push(`Parameter ${key} should be a string, got ${actualType}`);
            } else if (expectedType === "boolean" && actualType !== "boolean") {
              errors.push(`Parameter ${key} should be a boolean, got ${actualType}`);
            } else if (expectedType === "array" && !Array.isArray(value)) {
              errors.push(`Parameter ${key} should be an array`);
            } else if (expectedType === "object" && (actualType !== "object" || Array.isArray(value))) {
              errors.push(`Parameter ${key} should be an object`);
            }
          }
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}

export const pluginService = new PluginService();
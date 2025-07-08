/**
 * Context Service - Handles context window management and optimization feedback
 */

export interface ContextMetrics {
  total_tokens: number;
  context_window_used: number;
  truncated_messages: number;
  summarized_chunks: number;
}

export interface ContextOptimization {
  original_message_count: number;
  optimized_message_count: number;
  context_window_used: number;
  truncated_messages: number;
  summarized_chunks: number;
}

export type ContextStrategy = 'conservative' | 'default' | 'aggressive';

export interface ContextWarning {
  type: 'approaching_limit' | 'optimization_applied' | 'heavy_truncation';
  message: string;
  severity: 'info' | 'warning' | 'error';
  metrics?: ContextMetrics;
}

class ContextService {
  private warningThresholds = {
    approaching_limit: 0.8, // 80% of context window
    heavy_truncation: 0.5,  // More than 50% of messages truncated
  };

  /**
   * Analyze context optimization results and generate user warnings/feedback
   */
  analyzeContextOptimization(optimization: ContextOptimization): ContextWarning[] {
    const warnings: ContextWarning[] = [];

    // Check if context window usage is high
    if (optimization.context_window_used > this.warningThresholds.approaching_limit) {
      warnings.push({
        type: 'approaching_limit',
        severity: optimization.context_window_used > 0.95 ? 'error' : 'warning',
        message: `Context window is ${(optimization.context_window_used * 100).toFixed(1)}% full. Consider starting a new conversation for better performance.`,
      });
    }

    // Check if significant optimization was applied
    if (optimization.truncated_messages > 0 || optimization.summarized_chunks > 0) {
      const truncated = optimization.truncated_messages;
      const summarized = optimization.summarized_chunks;
      
      let message = 'Context optimized: ';
      const parts = [];
      
      if (truncated > 0) {
        parts.push(`${truncated} message${truncated === 1 ? '' : 's'} removed`);
      }
      
      if (summarized > 0) {
        parts.push(`${summarized} message${summarized === 1 ? '' : 's'} summarized`);
      }
      
      message += parts.join(', ') + ' to fit model limits.';

      warnings.push({
        type: 'optimization_applied',
        severity: 'info',
        message,
      });
    }

    // Check for heavy truncation
    const truncationRatio = optimization.truncated_messages / optimization.original_message_count;
    if (truncationRatio > this.warningThresholds.heavy_truncation) {
      warnings.push({
        type: 'heavy_truncation',
        severity: 'warning',
        message: `${(truncationRatio * 100).toFixed(0)}% of conversation history was removed. Important context may be lost.`,
      });
    }

    return warnings;
  }

  /**
   * Get user-friendly description of context strategy
   */
  getStrategyDescription(strategy: ContextStrategy): string {
    const descriptions = {
      conservative: 'Keeps more conversation history, may hit context limits sooner',
      default: 'Balanced approach with smart context management',
      aggressive: 'Optimizes aggressively for token efficiency, may lose more context',
    };

    return descriptions[strategy];
  }

  /**
   * Recommend context strategy based on conversation characteristics
   */
  recommendStrategy(messageCount: number, averageMessageLength: number): ContextStrategy {
    // For short conversations, use conservative
    if (messageCount < 10) {
      return 'conservative';
    }

    // For very long messages (code, documents), use aggressive
    if (averageMessageLength > 1000) {
      return 'aggressive';
    }

    // For long conversations with normal messages, use default
    return 'default';
  }

  /**
   * Format context metrics for display
   */
  formatMetrics(metrics: ContextMetrics): Record<string, string> {
    return {
      'Total Tokens': metrics.total_tokens.toLocaleString(),
      'Context Usage': `${(metrics.context_window_used * 100).toFixed(1)}%`,
      'Messages Removed': metrics.truncated_messages.toString(),
      'Messages Summarized': metrics.summarized_chunks.toString(),
    };
  }

  /**
   * Calculate estimated cost impact of context optimization
   */
  estimateCostSavings(
    originalTokens: number,
    optimizedTokens: number,
    costPerToken: number = 0.000001 // Default rough estimate
  ): number {
    const tokensSaved = originalTokens - optimizedTokens;
    return tokensSaved * costPerToken;
  }

  /**
   * Get color coding for context usage levels
   */
  getUsageColor(percentage: number): string {
    if (percentage < 0.5) return 'text-green-500';
    if (percentage < 0.8) return 'text-yellow-500';
    if (percentage < 0.95) return 'text-orange-500';
    return 'text-red-500';
  }

  /**
   * Generate tips for optimizing conversation context
   */
  getOptimizationTips(metrics: ContextMetrics): string[] {
    const tips: string[] = [];

    if (metrics.context_window_used > 0.8) {
      tips.push('Consider starting a new conversation to reset context');
    }

    if (metrics.truncated_messages > 5) {
      tips.push('Use more concise messages to preserve more conversation history');
    }

    if (metrics.summarized_chunks > 0) {
      tips.push('Important details may be lost in summarized messages');
    }

    if (metrics.total_tokens > 50000) {
      tips.push('Break complex topics into separate conversations');
    }

    return tips;
  }
}

export const contextService = new ContextService();
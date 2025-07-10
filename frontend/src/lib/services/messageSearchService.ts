import type { ChatMessage, ChatThread } from "$lib/stores/chat";
import { api } from "$lib/utils/api";

export interface SearchFilters {
  threads: string[];
  dateRange: string;
  messageType: string;
  role: string;
}

export interface SearchResult extends ChatMessage {
  threadTitle: string;
  relevanceScore?: number;
}

export interface ExportData {
  query: string;
  filters: SearchFilters;
  results: SearchResult[];
  exportedAt: string;
  totalResults: number;
}

class MessageSearchService {
  private searchCache = new Map<string, SearchResult[]>();
  private cacheTimeout = 5 * 60 * 1000; // 5 minutes

  /**
   * Search messages across threads with filters
   */
  async searchMessages(
    query: string,
    filters: SearchFilters,
    threads: ChatThread[],
    allMessages: Record<string, ChatMessage[]>
  ): Promise<SearchResult[]> {
    if (!query.trim()) {
      return [];
    }

    const cacheKey = this.getCacheKey(query, filters);
    const cached = this.searchCache.get(cacheKey);
    
    if (cached) {
      return cached;
    }

    try {
      // If we have an API endpoint for search, use it
      const results = await this.performAPISearch(query, filters);
      this.searchCache.set(cacheKey, results);
      
      // Auto-clear cache after timeout
      setTimeout(() => {
        this.searchCache.delete(cacheKey);
      }, this.cacheTimeout);
      
      return results;
    } catch (error) {
      console.warn("API search failed, falling back to client-side search", error);
      
      // Fallback to client-side search
      const results = this.performClientSearch(query, filters, threads, allMessages);
      this.searchCache.set(cacheKey, results);
      
      setTimeout(() => {
        this.searchCache.delete(cacheKey);
      }, this.cacheTimeout);
      
      return results;
    }
  }

  /**
   * Perform server-side search via API
   */
  private async performAPISearch(query: string, filters: SearchFilters): Promise<SearchResult[]> {
    const response = await api.searchMessages({
      q: query,
      ...(filters.role !== "all" && { role: filters.role }),
      ...(filters.messageType !== "all" && { message_type: filters.messageType }),
      ...(filters.dateRange && { date_range: filters.dateRange }),
      ...(filters.threads.length > 0 && { thread_ids: filters.threads.join(",") }),
      limit: 50,
    });

    return response.results || [];
  }

  /**
   * Perform client-side search as fallback
   */
  private performClientSearch(
    query: string,
    filters: SearchFilters,
    threads: ChatThread[],
    allMessages: Record<string, ChatMessage[]>
  ): Promise<SearchResult[]> {
    return new Promise((resolve) => {
      const results: SearchResult[] = [];
      const searchTerm = query.toLowerCase().trim();
      const threadsMap = new Map(threads.map(t => [t.id, t.title]));

      // Get threads to search
      const threadsToSearch = filters.threads.length > 0 
        ? filters.threads 
        : Object.keys(allMessages);

      for (const threadId of threadsToSearch) {
        const messages = allMessages[threadId] || [];
        const threadTitle = threadsMap.get(threadId) || "Unknown Thread";

        for (const message of messages) {
          if (this.matchesFilters(message, filters) && 
              this.matchesSearchTerm(message, searchTerm)) {
            
            const relevanceScore = this.calculateRelevanceScore(message, searchTerm);
            
            results.push({
              ...message,
              threadTitle,
              relevanceScore,
            });
          }
        }
      }

      // Sort by relevance and date
      results.sort((a, b) => {
        if (a.relevanceScore !== b.relevanceScore) {
          return (b.relevanceScore || 0) - (a.relevanceScore || 0);
        }
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });

      resolve(results);
    });
  }

  /**
   * Check if message matches search filters
   */
  private matchesFilters(message: ChatMessage, filters: SearchFilters): boolean {
    // Role filter
    if (filters.role !== "all" && message.role !== filters.role) {
      return false;
    }

    // Message type filter
    if (filters.messageType !== "all" && message.message_type !== filters.messageType) {
      return false;
    }

    // Date range filter
    if (filters.dateRange) {
      const messageDate = new Date(message.created_at);
      const now = new Date();
      
      switch (filters.dateRange) {
        case "today":
          if (messageDate.toDateString() !== now.toDateString()) {
            return false;
          }
          break;
        case "week":
          const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          if (messageDate < weekAgo) {
            return false;
          }
          break;
        case "month":
          const monthAgo = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
          if (messageDate < monthAgo) {
            return false;
          }
          break;
        case "3months":
          const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
          if (messageDate < threeMonthsAgo) {
            return false;
          }
          break;
      }
    }

    return true;
  }

  /**
   * Check if message content matches search term
   */
  private matchesSearchTerm(message: ChatMessage, searchTerm: string): boolean {
    const content = message.content.toLowerCase();
    
    // Support for quoted phrases
    if (searchTerm.includes('"')) {
      const phrases = searchTerm.match(/"([^"]*)"/g);
      if (phrases) {
        return phrases.some(phrase => {
          const cleanPhrase = phrase.replace(/"/g, "");
          return content.includes(cleanPhrase);
        });
      }
    }

    // Support for multiple terms (AND logic)
    const terms = searchTerm.split(/\s+/).filter(term => term.length > 0);
    return terms.every(term => content.includes(term));
  }

  /**
   * Calculate relevance score for search result
   */
  private calculateRelevanceScore(message: ChatMessage, searchTerm: string): number {
    const content = message.content.toLowerCase();
    const terms = searchTerm.split(/\s+/).filter(term => term.length > 0);
    
    let score = 0;
    
    for (const term of terms) {
      // Exact matches get higher score
      const exactMatches = (content.match(new RegExp(term, "g")) || []).length;
      score += exactMatches * 2;
      
      // Partial matches get lower score
      if (content.includes(term)) {
        score += 1;
      }
    }

    // Boost score for shorter messages (likely more relevant)
    if (content.length < 100) {
      score *= 1.2;
    }

    // Boost score for user messages (often contain important queries)
    if (message.role === "USER") {
      score *= 1.1;
    }

    return score;
  }

  /**
   * Export search results to JSON
   */
  exportToJSON(
    query: string,
    filters: SearchFilters,
    results: SearchResult[]
  ): string {
    const exportData: ExportData = {
      query,
      filters,
      results,
      exportedAt: new Date().toISOString(),
      totalResults: results.length,
    };

    return JSON.stringify(exportData, null, 2);
  }

  /**
   * Export search results to Markdown
   */
  exportToMarkdown(
    query: string,
    filters: SearchFilters,
    results: SearchResult[]
  ): string {
    const lines: string[] = [];
    
    // Header
    lines.push(`# Message Search Results`);
    lines.push(`**Query:** ${query}`);
    lines.push(`**Total Results:** ${results.length}`);
    lines.push(`**Exported:** ${new Date().toLocaleString()}`);
    lines.push(``);

    // Filters
    if (filters.role !== "all" || filters.messageType !== "all" || filters.dateRange || filters.threads.length > 0) {
      lines.push(`## Applied Filters`);
      
      if (filters.role !== "all") {
        lines.push(`- **Role:** ${filters.role}`);
      }
      if (filters.messageType !== "all") {
        lines.push(`- **Message Type:** ${filters.messageType}`);
      }
      if (filters.dateRange) {
        lines.push(`- **Date Range:** ${filters.dateRange}`);
      }
      if (filters.threads.length > 0) {
        lines.push(`- **Threads:** ${filters.threads.length} selected`);
      }
      lines.push(``);
    }

    // Results
    lines.push(`## Results`);
    lines.push(``);

    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      const date = new Date(result.created_at);
      
      lines.push(`### ${i + 1}. ${result.role} Message`);
      lines.push(`**Thread:** ${result.threadTitle}`);
      lines.push(`**Date:** ${date.toLocaleString()}`);
      lines.push(`**Type:** ${result.message_type}`);
      lines.push(``);
      lines.push(result.content);
      lines.push(``);
      lines.push(`---`);
      lines.push(``);
    }

    return lines.join("\n");
  }

  /**
   * Download exported data as file
   */
  downloadExport(content: string, filename: string, contentType: string) {
    const blob = new Blob([content], { type: contentType });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.style.display = "none";
    
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  /**
   * Generate cache key for search results
   */
  private getCacheKey(query: string, filters: SearchFilters): string {
    return `${query}|${JSON.stringify(filters)}`;
  }

  /**
   * Clear search cache
   */
  clearCache() {
    this.searchCache.clear();
  }

  /**
   * Get cache statistics
   */
  getCacheStats() {
    return {
      size: this.searchCache.size,
      keys: Array.from(this.searchCache.keys()),
    };
  }
}

export const messageSearchService = new MessageSearchService();
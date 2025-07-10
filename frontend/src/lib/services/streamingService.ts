import type { ChatMessage } from "$lib/stores/chat";

export interface StreamingChunk {
  id: string;
  content: string;
  delta?: string;
  finished: boolean;
  metadata?: Record<string, any>;
}

export interface StreamingOptions {
  onChunk?: (chunk: StreamingChunk) => void;
  onComplete?: (finalMessage: ChatMessage) => void;
  onError?: (error: Error) => void;
  signal?: AbortSignal;
}

class StreamingService {
  private activeStreams = new Map<string, AbortController>();

  /**
   * Send a message with streaming response
   */
  async sendMessageWithStream(
    threadId: string,
    content: string,
    options: StreamingOptions = {}
  ): Promise<ChatMessage> {
    const streamId = this.generateStreamId();
    const controller = new AbortController();
    this.activeStreams.set(streamId, controller);

    // Combine signals if provided
    const combinedSignal = options.signal 
      ? this.combineAbortSignals(controller.signal, options.signal)
      : controller.signal;

    try {
      const response = await fetch(`/api/v1/chat/threads/${threadId}/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({ content }),
        signal: combinedSignal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Response body is null");
      }

      return await this.processStreamResponse(response.body, options);

    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("Request was cancelled");
      }
      throw error;
    } finally {
      this.activeStreams.delete(streamId);
    }
  }

  /**
   * Process streaming response using ReadableStream
   */
  private async processStreamResponse(
    body: ReadableStream<Uint8Array>,
    options: StreamingOptions
  ): Promise<ChatMessage> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalMessage: ChatMessage | null = null;

    try {
      while (true) {
        const { value, done } = await reader.read();
        
        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });
        
        // Process complete lines from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.trim() === "") continue;

          try {
            const chunk = this.parseSSELine(line);
            if (chunk) {
              // Handle different chunk types
              if (chunk.type === "chunk") {
                options.onChunk?.(chunk.data);
              } else if (chunk.type === "complete") {
                finalMessage = chunk.data;
                options.onComplete?.(finalMessage);
              } else if (chunk.type === "error") {
                throw new Error(chunk.data.message || "Streaming error");
              }
            }
          } catch (parseError) {
            console.warn("Failed to parse SSE line:", line, parseError);
          }
        }
      }

      if (!finalMessage) {
        throw new Error("Stream ended without final message");
      }

      return finalMessage;

    } catch (error) {
      options.onError?.(error as Error);
      throw error;
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Parse Server-Sent Events line
   */
  private parseSSELine(line: string): { type: string; data: any } | null {
    if (line.startsWith("data: ")) {
      const data = line.slice(6);
      
      // Handle special SSE events
      if (data === "[DONE]") {
        return { type: "done", data: null };
      }

      try {
        const parsed = JSON.parse(data);
        return {
          type: parsed.type || "chunk",
          data: parsed,
        };
      } catch {
        // Handle plain text chunks (fallback)
        return {
          type: "chunk",
          data: {
            id: this.generateStreamId(),
            delta: data,
            content: data,
            finished: false,
          },
        };
      }
    }

    // Handle other SSE fields
    if (line.startsWith("event: ")) {
      return { type: "event", data: line.slice(7) };
    }

    return null;
  }

  /**
   * Cancel a specific stream
   */
  cancelStream(streamId: string): void {
    const controller = this.activeStreams.get(streamId);
    if (controller) {
      controller.abort();
      this.activeStreams.delete(streamId);
    }
  }

  /**
   * Cancel all active streams
   */
  cancelAllStreams(): void {
    for (const [streamId, controller] of this.activeStreams) {
      controller.abort();
    }
    this.activeStreams.clear();
  }

  /**
   * Get active stream count
   */
  getActiveStreamCount(): number {
    return this.activeStreams.size;
  }

  /**
   * Check if there are active streams
   */
  hasActiveStreams(): boolean {
    return this.activeStreams.size > 0;
  }

  /**
   * Generate unique stream ID
   */
  private generateStreamId(): string {
    return `stream_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
  }

  /**
   * Combine multiple AbortSignals
   */
  private combineAbortSignals(...signals: AbortSignal[]): AbortSignal {
    const controller = new AbortController();

    for (const signal of signals) {
      if (signal.aborted) {
        controller.abort();
        break;
      }

      signal.addEventListener("abort", () => {
        controller.abort();
      }, { once: true });
    }

    return controller.signal;
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    this.cancelAllStreams();
  }
}

export const streamingService = new StreamingService();

// Cleanup on page unload
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    streamingService.destroy();
  });
}
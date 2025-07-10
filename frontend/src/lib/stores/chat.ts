import { writable, derived, get } from "svelte/store";
import { api, ApiError } from "../utils/api";
import { chatWebSocketHandler, type ChatUpdateHandlers } from "../services/chatWebSocketHandler";
import { notificationService } from "../services/notificationService";
import type { ContextOptimization } from "../services/contextService";
import type { UUID } from "crypto";

// Types (Updated to match backend schemas)
export interface ChatThread {
  id: string;
  title: string;
  description?: string;
  status: "ACTIVE" | "ARCHIVED" | "COMPLETED";
  created_at: string;
  updated_at?: string;
  user_id?: string;
  thread_metadata: Record<string, any>;
  unread_count?: number;
  last_message?: string;
  last_message_at?: string;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  role: "USER" | "ASSISTANT" | "SYSTEM";
  content: string;
  message_type:
    | "TEXT"
    | "TASK_BREAKDOWN"
    | "PROGRESS"
    | "NOTIFICATION"
    | "ERROR";
  message_metadata: Record<string, any>;
  created_at: string;
  edited_at?: string;
  parent_message_id?: string;
}

export interface ChatNotification {
  id: string;
  thread_id: string;
  type: "TASK_COMPLETE" | "TASK_FAILED" | "AGENT_UPDATE" | "SYSTEM_ALERT";
  title: string;
  message?: string;
  is_read: boolean;
  created_at: string;
  notification_metadata: Record<string, any>;
}

interface ChatState {
  threads: ChatThread[];
  currentThreadId: string | null;
  messages: Record<string, ChatMessage[]>;
  notifications: ChatNotification[];
  loading: boolean;
  error: string | null;
  connected: boolean;
  contextOptimization: Record<string, ContextOptimization>; // threadId -> optimization data
}


// Create the main chat store
function createChatStore() {
  const { subscribe, set, update } = writable<ChatState>({
    threads: [],
    currentThreadId: null,
    messages: {},
    notifications: [],
    loading: false,
    error: null,
    connected: false,
    contextOptimization: {},
  });

  return {
    subscribe,

    // Thread management
    async createThread(
      title: string,
      initialMessage?: string
    ): Promise<ChatThread> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const newThread = await api.createChatThread({ 
          title, 
          initial_message: initialMessage 
        });

        update((state) => ({
          ...state,
          threads: [newThread, ...state.threads],
          currentThreadId: newThread.id,
          loading: false,
        }));

        return newThread;
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to create thread";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async fetchThreads(): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const data = await api.getChatThreads();

        update((state) => ({
          ...state,
          threads: data.threads || [],
          loading: false,
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch threads";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
      }
    },

    async selectThread(threadId: string): Promise<void> {
      update((state) => ({ ...state, currentThreadId: threadId }));

      // Mark notifications as read for this thread
      try {
        await notificationService.markThreadNotificationsRead(threadId);

        // Update unread count locally
        update((state) => ({
          ...state,
          threads: state.threads.map((thread) =>
            thread.id === threadId ? { ...thread, unread_count: 0 } : thread
          ),
        }));
      } catch (error) {
        console.warn("Failed to mark notifications as read:", error);
      }

      // Fetch messages if not already loaded
      const currentState = get({ subscribe });
      if (!currentState.messages[threadId]) {
        await this.fetchMessages(threadId);
      }
    },

    async updateThread(
      threadId: string,
      updates: Partial<ChatThread>
    ): Promise<void> {
      try {
        const updatedThread = await api.updateChatThread(threadId, updates);

        update((state) => ({
          ...state,
          threads: state.threads.map((thread) =>
            thread.id === threadId ? updatedThread : thread
          ),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to update thread";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async deleteThread(threadId: string): Promise<void> {
      try {
        await api.deleteChatThread(threadId);

        update((state) => ({
          ...state,
          threads: state.threads.filter((thread) => thread.id !== threadId),
          currentThreadId:
            state.currentThreadId === threadId ? null : state.currentThreadId,
          messages: { ...state.messages, [threadId]: undefined },
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to delete thread";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    // Message management
    async fetchMessages(threadId: string, before?: string): Promise<void> {
      try {
        const data = await api.getChatMessages(threadId, before);

        update((state) => ({
          ...state,
          messages: {
            ...state.messages,
            [threadId]: before
              ? [...(state.messages[threadId] || []), ...data.messages]
              : data.messages.reverse(), // Reverse to show oldest first
          },
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch messages";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
      }
    },

    async sendMessage(threadId: string, content: string, messageData?: any): Promise<ChatMessage> {
      try {
        // Prepare message payload with optional file attachments
        const payload = {
          content,
          message_type: "TEXT",
          metadata: {
            ...((messageData && messageData.metadata) || {}),
            ...(messageData && messageData.files && messageData.files.length > 0 ? {
              attachments: messageData.files.map((file: any) => ({
                id: file.id,
                name: file.name,
                size: file.size,
                type: file.type,
                category: file.category,
                uploadedAt: file.uploadedAt
              }))
            } : {})
          }
        };

        const newMessage = await api.sendChatMessage(threadId, payload);

        update((state) => ({
          ...state,
          messages: {
            ...state.messages,
            [threadId]: [...(state.messages[threadId] || []), newMessage],
          },
        }));

        return newMessage;
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to send message";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    // Notification management (delegated to notification service)
    async fetchNotifications(): Promise<void> {
      await notificationService.fetchNotifications(true);
    },

    // Add message to store (for streaming completion)
    addMessage(threadId: string, message: ChatMessage): void {
      update((state) => ({
        ...state,
        messages: {
          ...state.messages,
          [threadId]: [...(state.messages[threadId] || []), message],
        },
      }));
      
      // Check for context optimization metadata
      if (message.message_metadata && message.message_metadata.context_optimization) {
        this.updateContextOptimization(threadId, message.message_metadata.context_optimization);
      }
    },

    // Update context optimization data
    updateContextOptimization(threadId: string, optimization: ContextOptimization): void {
      update((state) => ({
        ...state,
        contextOptimization: {
          ...state.contextOptimization,
          [threadId]: optimization,
        },
      }));
    },

    // Get context optimization for a thread
    getContextOptimization(threadId: string): ContextOptimization | null {
      const state = get({ subscribe });
      return state.contextOptimization[threadId] || null;
    },

    // Utility methods
    clearError(): void {
      update((state) => ({ ...state, error: null }));
    },

    setConnected(connected: boolean): void {
      update((state) => ({ ...state, connected }));
    },

    // Initialize WebSocket handlers
    initializeWebSocketHandlers(): void {
      const handlers: ChatUpdateHandlers = {
        onThreadCreated: (threadData) => {
          update((state) => ({
            ...state,
            threads: state.threads.some((t) => t.id === threadData.id)
              ? state.threads
              : [threadData as ChatThread, ...state.threads],
          }));
        },
        onMessageSent: (messageData) => {
          const threadId = messageData.thread_id!;
          update((state) => {
            const messages = state.messages[threadId] || [];
            const messageExists = messages.some((m) => m.id === messageData.id);

            if (!messageExists) {
              return {
                ...state,
                messages: {
                  ...state.messages,
                  [threadId]: [...messages, messageData as ChatMessage],
                },
              };
            }
            return state;
          });
        },
        onThreadUpdated: (threadId, updates) => {
          update((state) => ({
            ...state,
            threads: state.threads.map((thread) =>
              thread.id === threadId ? { ...thread, ...updates } : thread
            ),
          }));
        },
        onThreadDeleted: (threadId) => {
          update((state) => ({
            ...state,
            threads: state.threads.filter((thread) => thread.id !== threadId),
            currentThreadId:
              state.currentThreadId === threadId ? null : state.currentThreadId,
          }));
        },
        onNotificationsRead: (threadId) => {
          update((state) => ({
            ...state,
            threads: state.threads.map((thread) =>
              thread.id === threadId ? { ...thread, unread_count: 0 } : thread
            ),
          }));
        },
      };

      chatWebSocketHandler.setHandlers(handlers);
    },
  };
}

export const chat = createChatStore();

// Derived stores for convenient access
export const currentThread = derived(
  chat,
  ($chat) => $chat.threads.find((t) => t.id === $chat.currentThreadId) || null
);

export const currentMessages = derived(chat, ($chat) =>
  $chat.currentThreadId ? $chat.messages[$chat.currentThreadId] || [] : []
);

export const currentContextOptimization = derived(chat, ($chat) =>
  $chat.currentThreadId ? $chat.contextOptimization[$chat.currentThreadId] || null : null
);

export const activeThreads = derived(chat, ($chat) =>
  $chat.threads.filter((t) => t.status === "ACTIVE")
);

export const totalUnreadCount = derived(chat, ($chat) =>
  $chat.threads.reduce((sum, thread) => sum + (thread.unread_count || 0), 0)
);

// Initialize WebSocket handlers
chat.initializeWebSocketHandlers();

// Initialize connection status
if (typeof window !== "undefined") {
  import("./websocket").then(({ websocket }) => {
    websocket.subscribe(($websocket) => {
      chat.setConnected($websocket.connected);
    });
  });
}

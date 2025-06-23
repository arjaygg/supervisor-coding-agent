import { writable, derived, get } from "svelte/store";
import { websocket } from "./websocket";
import type { UUID } from "crypto";

// Types
export interface ChatThread {
  id: string;
  title: string;
  description?: string;
  status: "ACTIVE" | "ARCHIVED" | "COMPLETED";
  created_at: string;
  updated_at?: string;
  user_id?: string;
  metadata: Record<string, any>;
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
  metadata: Record<string, any>;
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
  metadata: Record<string, any>;
}

interface ChatState {
  threads: ChatThread[];
  currentThreadId: string | null;
  messages: Record<string, ChatMessage[]>;
  notifications: ChatNotification[];
  loading: boolean;
  error: string | null;
  connected: boolean;
}

// Base URL for API calls
const API_BASE = "/api/v1/chat";

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
        const response = await fetch(`${API_BASE}/threads`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, initial_message: initialMessage }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create thread: ${response.statusText}`);
        }

        const newThread: ChatThread = await response.json();

        update((state) => ({
          ...state,
          threads: [newThread, ...state.threads],
          currentThreadId: newThread.id,
          loading: false,
        }));

        return newThread;
      } catch (error) {
        update((state) => ({
          ...state,
          loading: false,
          error:
            error instanceof Error ? error.message : "Failed to create thread",
        }));
        throw error;
      }
    },

    async fetchThreads(): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const response = await fetch(`${API_BASE}/threads`);

        if (!response.ok) {
          throw new Error(`Failed to fetch threads: ${response.statusText}`);
        }

        const data = await response.json();

        update((state) => ({
          ...state,
          threads: data.threads || [],
          loading: false,
        }));
      } catch (error) {
        update((state) => ({
          ...state,
          loading: false,
          error:
            error instanceof Error ? error.message : "Failed to fetch threads",
        }));
      }
    },

    async selectThread(threadId: string): Promise<void> {
      update((state) => ({ ...state, currentThreadId: threadId }));

      // Mark notifications as read for this thread
      try {
        await fetch(`${API_BASE}/threads/${threadId}/notifications/read`, {
          method: "POST",
        });

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
        const response = await fetch(`${API_BASE}/threads/${threadId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });

        if (!response.ok) {
          throw new Error(`Failed to update thread: ${response.statusText}`);
        }

        const updatedThread: ChatThread = await response.json();

        update((state) => ({
          ...state,
          threads: state.threads.map((thread) =>
            thread.id === threadId ? updatedThread : thread
          ),
        }));
      } catch (error) {
        update((state) => ({
          ...state,
          error:
            error instanceof Error ? error.message : "Failed to update thread",
        }));
        throw error;
      }
    },

    async deleteThread(threadId: string): Promise<void> {
      try {
        const response = await fetch(`${API_BASE}/threads/${threadId}`, {
          method: "DELETE",
        });

        if (!response.ok) {
          throw new Error(`Failed to delete thread: ${response.statusText}`);
        }

        update((state) => ({
          ...state,
          threads: state.threads.filter((thread) => thread.id !== threadId),
          currentThreadId:
            state.currentThreadId === threadId ? null : state.currentThreadId,
          messages: { ...state.messages, [threadId]: undefined },
        }));
      } catch (error) {
        update((state) => ({
          ...state,
          error:
            error instanceof Error ? error.message : "Failed to delete thread",
        }));
        throw error;
      }
    },

    // Message management
    async fetchMessages(threadId: string, before?: string): Promise<void> {
      try {
        const url = new URL(
          `${window.location.origin}${API_BASE}/threads/${threadId}/messages`
        );
        if (before) {
          url.searchParams.set("before", before);
        }

        const response = await fetch(url.toString());

        if (!response.ok) {
          throw new Error(`Failed to fetch messages: ${response.statusText}`);
        }

        const data = await response.json();

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
        update((state) => ({
          ...state,
          error:
            error instanceof Error ? error.message : "Failed to fetch messages",
        }));
      }
    },

    async sendMessage(threadId: string, content: string): Promise<ChatMessage> {
      try {
        const response = await fetch(
          `${API_BASE}/threads/${threadId}/messages`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to send message: ${response.statusText}`);
        }

        const newMessage: ChatMessage = await response.json();

        update((state) => ({
          ...state,
          messages: {
            ...state.messages,
            [threadId]: [...(state.messages[threadId] || []), newMessage],
          },
        }));

        return newMessage;
      } catch (error) {
        update((state) => ({
          ...state,
          error:
            error instanceof Error ? error.message : "Failed to send message",
        }));
        throw error;
      }
    },

    // Notification management
    async fetchNotifications(): Promise<void> {
      try {
        const response = await fetch(
          `${API_BASE}/notifications?unread_only=true`
        );

        if (!response.ok) {
          throw new Error(
            `Failed to fetch notifications: ${response.statusText}`
          );
        }

        const notifications: ChatNotification[] = await response.json();

        update((state) => ({ ...state, notifications }));
      } catch (error) {
        console.warn("Failed to fetch notifications:", error);
      }
    },

    // WebSocket event handlers
    handleWebSocketMessage(event: any): void {
      if (event.type === "chat_update") {
        const { data } = event;

        switch (data.type) {
          case "thread_created":
            update((state) => ({
              ...state,
              threads: state.threads.some((t) => t.id === data.thread_id)
                ? state.threads
                : [
                    {
                      id: data.thread_id,
                      title: data.title,
                      status: "ACTIVE" as const,
                      created_at: data.created_at,
                      metadata: {},
                    },
                    ...state.threads,
                  ],
            }));
            break;

          case "message_sent":
            const threadId = data.thread_id;
            update((state) => {
              const messages = state.messages[threadId] || [];
              const messageExists = messages.some(
                (m) => m.id === data.message_id
              );

              if (!messageExists) {
                return {
                  ...state,
                  messages: {
                    ...state.messages,
                    [threadId]: [
                      ...messages,
                      {
                        id: data.message_id,
                        thread_id: threadId,
                        role: data.role.toUpperCase() as
                          | "USER"
                          | "ASSISTANT"
                          | "SYSTEM",
                        content: data.content,
                        message_type: "TEXT" as const,
                        metadata: {},
                        created_at: data.created_at,
                      },
                    ],
                  },
                };
              }
              return state;
            });
            break;

          case "thread_updated":
            update((state) => ({
              ...state,
              threads: state.threads.map((thread) =>
                thread.id === data.thread_id
                  ? { ...thread, title: data.title, status: data.status }
                  : thread
              ),
            }));
            break;

          case "thread_deleted":
            update((state) => ({
              ...state,
              threads: state.threads.filter(
                (thread) => thread.id !== data.thread_id
              ),
              currentThreadId:
                state.currentThreadId === data.thread_id
                  ? null
                  : state.currentThreadId,
            }));
            break;

          case "notifications_read":
            update((state) => ({
              ...state,
              threads: state.threads.map((thread) =>
                thread.id === data.thread_id
                  ? { ...thread, unread_count: 0 }
                  : thread
              ),
            }));
            break;
        }
      }
    },

    // Utility methods
    clearError(): void {
      update((state) => ({ ...state, error: null }));
    },

    setConnected(connected: boolean): void {
      update((state) => ({ ...state, connected }));
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

export const activeThreads = derived(chat, ($chat) =>
  $chat.threads.filter((t) => t.status === "ACTIVE")
);

export const totalUnreadCount = derived(chat, ($chat) =>
  $chat.threads.reduce((sum, thread) => sum + (thread.unread_count || 0), 0)
);

// Initialize WebSocket handlers
websocket.subscribe(($websocket) => {
  if ($websocket.connected) {
    chat.setConnected(true);
  } else {
    chat.setConnected(false);
  }
});

// Handle WebSocket messages
if (typeof window !== "undefined") {
  websocket.addMessageHandler((event) => {
    chat.handleWebSocketMessage(event);
  });
}

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { get } from "svelte/store";
import { chat, currentThread, currentMessages, activeThreads, totalUnreadCount } from "./chat";
import { api } from "../utils/api";
import { notificationService } from "../services/notificationService";

// Mock dependencies
vi.mock("../utils/api", () => ({
  api: {
    createChatThread: vi.fn(),
    getChatThreads: vi.fn(),
    updateChatThread: vi.fn(),
    deleteChatThread: vi.fn(),
    getChatMessages: vi.fn(),
    sendChatMessage: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string, public data?: any) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

vi.mock("../services/notificationService", () => ({
  notificationService: {
    fetchNotifications: vi.fn(),
    markThreadNotificationsRead: vi.fn(),
  },
}));

vi.mock("../services/chatWebSocketHandler", () => ({
  chatWebSocketHandler: {
    setHandlers: vi.fn(),
  },
}));

describe("Chat Store", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store state
    chat.subscribe((state) => {
      // Reset to initial state
      return {
        threads: [],
        currentThreadId: null,
        messages: {},
        notifications: [],
        loading: false,
        error: null,
        connected: false,
      };
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Thread Management", () => {
    describe("createThread", () => {
      it("should create a new thread successfully", async () => {
        const mockThread = {
          id: "thread-1",
          title: "Test Thread",
          status: "ACTIVE",
          created_at: "2023-01-01T00:00:00Z",
          thread_metadata: {},
        };

        vi.mocked(api.createChatThread).mockResolvedValue(mockThread);

        const result = await chat.createThread("Test Thread", "Initial message");

        expect(api.createChatThread).toHaveBeenCalledWith({
          title: "Test Thread",
          initial_message: "Initial message",
        });

        expect(result).toEqual(mockThread);

        const state = get(chat);
        expect(state.threads).toContain(mockThread);
        expect(state.currentThreadId).toBe("thread-1");
        expect(state.loading).toBe(false);
        expect(state.error).toBe(null);
      });

      it("should handle thread creation errors", async () => {
        const error = new Error("Failed to create thread");
        vi.mocked(api.createChatThread).mockRejectedValue(error);

        await expect(chat.createThread("Test Thread")).rejects.toThrow("Failed to create thread");

        const state = get(chat);
        expect(state.loading).toBe(false);
        expect(state.error).toBe("Failed to create thread");
      });

      it("should set loading state during thread creation", async () => {
        const mockThread = {
          id: "thread-1",
          title: "Test Thread",
          status: "ACTIVE",
          created_at: "2023-01-01T00:00:00Z",
          thread_metadata: {},
        };

        let loadingDuringCall = false;
        vi.mocked(api.createChatThread).mockImplementation(async () => {
          const state = get(chat);
          loadingDuringCall = state.loading;
          return mockThread;
        });

        await chat.createThread("Test Thread");

        expect(loadingDuringCall).toBe(true);
      });
    });

    describe("fetchThreads", () => {
      it("should fetch threads successfully", async () => {
        const mockThreads = [
          {
            id: "thread-1",
            title: "Thread 1",
            status: "ACTIVE",
            created_at: "2023-01-01T00:00:00Z",
            thread_metadata: {},
          },
          {
            id: "thread-2",
            title: "Thread 2", 
            status: "ACTIVE",
            created_at: "2023-01-02T00:00:00Z",
            thread_metadata: {},
          },
        ];

        vi.mocked(api.getChatThreads).mockResolvedValue({ threads: mockThreads });

        await chat.fetchThreads();

        expect(api.getChatThreads).toHaveBeenCalledTimes(1);

        const state = get(chat);
        expect(state.threads).toEqual(mockThreads);
        expect(state.loading).toBe(false);
        expect(state.error).toBe(null);
      });

      it("should handle fetch threads errors", async () => {
        const error = new Error("Failed to fetch threads");
        vi.mocked(api.getChatThreads).mockRejectedValue(error);

        await chat.fetchThreads();

        const state = get(chat);
        expect(state.loading).toBe(false);
        expect(state.error).toBe("Failed to fetch threads");
      });
    });

    describe("selectThread", () => {
      it("should select a thread and mark notifications as read", async () => {
        vi.mocked(notificationService.markThreadNotificationsRead).mockResolvedValue(undefined);

        await chat.selectThread("thread-1");

        const state = get(chat);
        expect(state.currentThreadId).toBe("thread-1");
        expect(notificationService.markThreadNotificationsRead).toHaveBeenCalledWith("thread-1");
      });

      it("should handle notification marking errors gracefully", async () => {
        vi.mocked(notificationService.markThreadNotificationsRead).mockRejectedValue(
          new Error("Failed to mark notifications")
        );

        // Should not throw error
        await expect(chat.selectThread("thread-1")).resolves.not.toThrow();

        const state = get(chat);
        expect(state.currentThreadId).toBe("thread-1");
      });
    });

    describe("updateThread", () => {
      it("should update a thread successfully", async () => {
        const updatedThread = {
          id: "thread-1",
          title: "Updated Title",
          status: "ACTIVE",
          created_at: "2023-01-01T00:00:00Z",
          thread_metadata: {},
        };

        vi.mocked(api.updateChatThread).mockResolvedValue(updatedThread);

        // Set initial state with existing thread
        const initialThreads = [
          {
            id: "thread-1",
            title: "Original Title",
            status: "ACTIVE",
            created_at: "2023-01-01T00:00:00Z",
            thread_metadata: {},
          },
        ];

        // Manually set state for testing
        chat.subscribe((state) => ({ ...state, threads: initialThreads }));

        await chat.updateThread("thread-1", { title: "Updated Title" });

        expect(api.updateChatThread).toHaveBeenCalledWith("thread-1", { title: "Updated Title" });
      });

      it("should handle thread update errors", async () => {
        const error = new Error("Failed to update thread");
        vi.mocked(api.updateChatThread).mockRejectedValue(error);

        await expect(chat.updateThread("thread-1", { title: "New Title" })).rejects.toThrow(
          "Failed to update thread"
        );

        const state = get(chat);
        expect(state.error).toBe("Failed to update thread");
      });
    });

    describe("deleteThread", () => {
      it("should delete a thread successfully", async () => {
        vi.mocked(api.deleteChatThread).mockResolvedValue({ message: "Thread deleted" });

        // Set initial state
        const initialState = {
          threads: [
            { id: "thread-1", title: "Thread 1", status: "ACTIVE", created_at: "2023-01-01T00:00:00Z", thread_metadata: {} },
            { id: "thread-2", title: "Thread 2", status: "ACTIVE", created_at: "2023-01-02T00:00:00Z", thread_metadata: {} },
          ],
          currentThreadId: "thread-1",
          messages: { "thread-1": [], "thread-2": [] },
          notifications: [],
          loading: false,
          error: null,
          connected: false,
        };

        await chat.deleteThread("thread-1");

        expect(api.deleteChatThread).toHaveBeenCalledWith("thread-1");
      });

      it("should handle thread deletion errors", async () => {
        const error = new Error("Failed to delete thread");
        vi.mocked(api.deleteChatThread).mockRejectedValue(error);

        await expect(chat.deleteThread("thread-1")).rejects.toThrow("Failed to delete thread");

        const state = get(chat);
        expect(state.error).toBe("Failed to delete thread");
      });
    });
  });

  describe("Message Management", () => {
    describe("fetchMessages", () => {
      it("should fetch messages for a thread", async () => {
        const mockMessages = [
          {
            id: "msg-1",
            thread_id: "thread-1",
            role: "USER",
            content: "Hello",
            message_type: "TEXT",
            thread_metadata: {},
            created_at: "2023-01-01T00:00:00Z",
          },
          {
            id: "msg-2",
            thread_id: "thread-1",
            role: "ASSISTANT",
            content: "Hi there!",
            message_type: "TEXT",
            thread_metadata: {},
            created_at: "2023-01-01T00:01:00Z",
          },
        ];

        vi.mocked(api.getChatMessages).mockResolvedValue({ messages: mockMessages });

        await chat.fetchMessages("thread-1");

        expect(api.getChatMessages).toHaveBeenCalledWith("thread-1", undefined);

        const state = get(chat);
        expect(state.messages["thread-1"]).toEqual(mockMessages.reverse()); // Should be reversed
      });

      it("should handle fetch messages errors", async () => {
        const error = new Error("Failed to fetch messages");
        vi.mocked(api.getChatMessages).mockRejectedValue(error);

        await chat.fetchMessages("thread-1");

        const state = get(chat);
        expect(state.error).toBe("Failed to fetch messages");
      });

      it("should append messages when fetching with 'before' parameter", async () => {
        const newMessages = [
          {
            id: "msg-3",
            thread_id: "thread-1",
            role: "USER",
            content: "More messages",
            message_type: "TEXT",
            thread_metadata: {},
            created_at: "2023-01-01T00:02:00Z",
          },
        ];

        vi.mocked(api.getChatMessages).mockResolvedValue({ messages: newMessages });

        // Set initial messages
        const initialMessages = [
          {
            id: "msg-1",
            thread_id: "thread-1",
            role: "USER",
            content: "Hello",
            message_type: "TEXT",
            thread_metadata: {},
            created_at: "2023-01-01T00:00:00Z",
          },
        ];

        await chat.fetchMessages("thread-1", "msg-1");

        expect(api.getChatMessages).toHaveBeenCalledWith("thread-1", "msg-1");
      });
    });

    describe("sendMessage", () => {
      it("should send a message successfully", async () => {
        const mockMessage = {
          id: "msg-1",
          thread_id: "thread-1",
          role: "USER",
          content: "Hello",
          message_type: "TEXT",
          message_thread_metadata: {},
          created_at: "2023-01-01T00:00:00Z",
        };

        vi.mocked(api.sendChatMessage).mockResolvedValue(mockMessage);

        const result = await chat.sendMessage("thread-1", "Hello");

        expect(api.sendChatMessage).toHaveBeenCalledWith("thread-1", { 
          content: "Hello", 
          message_type: "TEXT", 
          thread_metadata: {} 
        });
        expect(result).toEqual(mockMessage);
      });

      it("should handle send message errors", async () => {
        const error = new Error("Failed to send message");
        vi.mocked(api.sendChatMessage).mockRejectedValue(error);

        await expect(chat.sendMessage("thread-1", "Hello")).rejects.toThrow("Failed to send message");

        const state = get(chat);
        expect(state.error).toBe("Failed to send message");
      });
    });
  });

  describe("Utility Methods", () => {
    describe("clearError", () => {
      it("should clear the error state", () => {
        // Set initial error state
        chat.subscribe((state) => ({ ...state, error: "Test error" }));

        chat.clearError();

        const state = get(chat);
        expect(state.error).toBe(null);
      });
    });

    describe("setConnected", () => {
      it("should update connection status", () => {
        chat.setConnected(true);

        const state = get(chat);
        expect(state.connected).toBe(true);
      });
    });
  });

  describe("Derived Stores", () => {
    describe("currentThread", () => {
      it("should return the currently selected thread", () => {
        const threads = [
          { id: "thread-1", title: "Thread 1", status: "ACTIVE", created_at: "2023-01-01T00:00:00Z", thread_metadata: {} },
          { id: "thread-2", title: "Thread 2", status: "ACTIVE", created_at: "2023-01-02T00:00:00Z", thread_metadata: {} },
        ];

        // Manually set state for testing
        chat.subscribe((state) => ({
          ...state,
          threads,
          currentThreadId: "thread-1",
        }));

        const current = get(currentThread);
        expect(current?.id).toBe("thread-1");
        expect(current?.title).toBe("Thread 1");
      });

      it("should return null when no thread is selected", () => {
        const threads = [
          { id: "thread-1", title: "Thread 1", status: "ACTIVE", created_at: "2023-01-01T00:00:00Z", thread_metadata: {} },
        ];

        chat.subscribe((state) => ({
          ...state,
          threads,
          currentThreadId: null,
        }));

        const current = get(currentThread);
        expect(current).toBe(null);
      });
    });

    describe("currentMessages", () => {
      it("should return messages for the current thread", () => {
        const messages = [
          {
            id: "msg-1",
            thread_id: "thread-1",
            role: "USER",
            content: "Hello",
            message_type: "TEXT",
            thread_metadata: {},
            created_at: "2023-01-01T00:00:00Z",
          },
        ];

        chat.subscribe((state) => ({
          ...state,
          currentThreadId: "thread-1",
          messages: { "thread-1": messages },
        }));

        const current = get(currentMessages);
        expect(current).toEqual(messages);
      });

      it("should return empty array when no thread is selected", () => {
        chat.subscribe((state) => ({
          ...state,
          currentThreadId: null,
          messages: {},
        }));

        const current = get(currentMessages);
        expect(current).toEqual([]);
      });
    });

    describe("activeThreads", () => {
      it("should return only active threads", () => {
        const threads = [
          { id: "thread-1", title: "Thread 1", status: "ACTIVE", created_at: "2023-01-01T00:00:00Z", thread_metadata: {} },
          { id: "thread-2", title: "Thread 2", status: "ARCHIVED", created_at: "2023-01-02T00:00:00Z", thread_metadata: {} },
          { id: "thread-3", title: "Thread 3", status: "ACTIVE", created_at: "2023-01-03T00:00:00Z", thread_metadata: {} },
        ];

        chat.subscribe((state) => ({ ...state, threads }));

        const active = get(activeThreads);
        expect(active).toHaveLength(2);
        expect(active.every(thread => thread.status === "ACTIVE")).toBe(true);
      });
    });

    describe("totalUnreadCount", () => {
      it("should calculate total unread count", () => {
        const threads = [
          { id: "thread-1", title: "Thread 1", status: "ACTIVE", created_at: "2023-01-01T00:00:00Z", thread_metadata: {}, unread_count: 3 },
          { id: "thread-2", title: "Thread 2", status: "ACTIVE", created_at: "2023-01-02T00:00:00Z", thread_metadata: {}, unread_count: 2 },
          { id: "thread-3", title: "Thread 3", status: "ACTIVE", created_at: "2023-01-03T00:00:00Z", thread_metadata: {} }, // no unread_count
        ];

        chat.subscribe((state) => ({ ...state, threads }));

        const total = get(totalUnreadCount);
        expect(total).toBe(5); // 3 + 2 + 0
      });

      it("should return 0 when no threads have unread messages", () => {
        const threads = [
          { id: "thread-1", title: "Thread 1", status: "ACTIVE", created_at: "2023-01-01T00:00:00Z", thread_metadata: {} },
          { id: "thread-2", title: "Thread 2", status: "ACTIVE", created_at: "2023-01-02T00:00:00Z", thread_metadata: {}, unread_count: 0 },
        ];

        chat.subscribe((state) => ({ ...state, threads }));

        const total = get(totalUnreadCount);
        expect(total).toBe(0);
      });
    });
  });
});
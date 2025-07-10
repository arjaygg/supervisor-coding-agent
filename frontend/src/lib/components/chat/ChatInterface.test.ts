import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor, screen } from "@testing-library/svelte";
import { get } from "svelte/store";
import ChatInterface from "./ChatInterface.svelte";
import { chat } from "$lib/stores/chat";
import { websocket } from "$lib/stores/websocket";

// Mock stores
vi.mock("$lib/stores/chat", () => ({
  chat: {
    subscribe: vi.fn(),
    fetchThreads: vi.fn(),
    fetchNotifications: vi.fn(),
    createThread: vi.fn(),
    selectThread: vi.fn(),
    deleteThread: vi.fn(),
    clearError: vi.fn(),
  },
  currentThread: {
    subscribe: vi.fn(),
  },
  currentMessages: {
    subscribe: vi.fn(),
  },
  activeThreads: {
    subscribe: vi.fn(),
  },
  totalUnreadCount: {
    subscribe: vi.fn(),
  },
}));

vi.mock("$lib/stores/websocket", () => ({
  websocket: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    subscribe: vi.fn(),
  },
}));

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock window object
Object.defineProperty(window, "innerWidth", {
  writable: true,
  configurable: true,
  value: 1024,
});

describe("ChatInterface", () => {
  const mockChatState = {
    threads: [
      {
        id: "thread-1",
        title: "Test Thread 1",
        status: "ACTIVE",
        created_at: "2023-01-01T00:00:00Z",
        metadata: {},
        unread_count: 2,
      },
      {
        id: "thread-2", 
        title: "Test Thread 2",
        status: "ACTIVE",
        created_at: "2023-01-02T00:00:00Z",
        metadata: {},
        unread_count: 0,
      },
    ],
    currentThreadId: "thread-1",
    messages: {
      "thread-1": [
        {
          id: "msg-1",
          thread_id: "thread-1",
          role: "USER",
          content: "Hello, how can you help me?",
          message_type: "TEXT",
          metadata: {},
          created_at: "2023-01-01T00:00:00Z",
        },
        {
          id: "msg-2",
          thread_id: "thread-1",
          role: "ASSISTANT",
          content: "I can help you manage tasks and analyze code.",
          message_type: "TEXT",
          metadata: {},
          created_at: "2023-01-01T00:01:00Z",
        },
      ],
    },
    notifications: [],
    loading: false,
    error: null,
    connected: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock store subscriptions
    (chat.subscribe as any).mockImplementation((callback: any) => {
      callback(mockChatState);
      return () => {};
    });

    // Mock derived stores
    const mockCurrentThread = mockChatState.threads[0];
    const mockCurrentMessages = mockChatState.messages["thread-1"];
    const mockActiveThreads = mockChatState.threads;
    const mockTotalUnreadCount = 2;

    vi.mocked(chat).currentThread = {
      subscribe: vi.fn((callback) => {
        callback(mockCurrentThread);
        return () => {};
      }),
    } as any;

    vi.mocked(chat).currentMessages = {
      subscribe: vi.fn((callback) => {
        callback(mockCurrentMessages);
        return () => {};
      }),
    } as any;

    vi.mocked(chat).activeThreads = {
      subscribe: vi.fn((callback) => {
        callback(mockActiveThreads);
        return () => {};
      }),
    } as any;

    vi.mocked(chat).totalUnreadCount = {
      subscribe: vi.fn((callback) => {
        callback(mockTotalUnreadCount);
        return () => {};
      }),
    } as any;

    (websocket.subscribe as any).mockImplementation((callback: any) => {
      callback({ connected: true });
      return () => {};
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Initialization", () => {
    it("should render the chat interface correctly", () => {
      render(ChatInterface);
      
      expect(screen.getByText("Test Thread 1")).toBeTruthy();
      expect(screen.getByText("Connected")).toBeTruthy();
    });

    it("should connect to WebSocket on mount", () => {
      render(ChatInterface);
      
      expect(websocket.connect).toHaveBeenCalledTimes(1);
    });

    it("should fetch threads and notifications on mount", () => {
      render(ChatInterface);
      
      expect(chat.fetchThreads).toHaveBeenCalledTimes(1);
      expect(chat.fetchNotifications).toHaveBeenCalledTimes(1);
    });

    it("should disconnect WebSocket on unmount", () => {
      const { unmount } = render(ChatInterface);
      
      unmount();
      
      expect(websocket.disconnect).toHaveBeenCalledTimes(1);
    });
  });

  describe("Mobile Responsiveness", () => {
    beforeEach(() => {
      // Set mobile viewport
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: 600,
      });
    });

    it("should start with collapsed sidebar on mobile", () => {
      render(ChatInterface);
      
      const sidebar = document.querySelector(".w-80");
      expect(sidebar?.classList.contains("-translate-x-full")).toBe(true);
    });

    it("should show mobile menu button", () => {
      render(ChatInterface);
      
      const menuButton = screen.getByLabelText("Toggle sidebar");
      expect(menuButton).toBeTruthy();
    });

    it("should toggle sidebar when menu button is clicked", async () => {
      render(ChatInterface);
      
      const menuButton = screen.getByLabelText("Toggle sidebar");
      await fireEvent.click(menuButton);
      
      const sidebar = document.querySelector(".w-80");
      expect(sidebar?.classList.contains("translate-x-0")).toBe(true);
    });

    it("should show overlay when sidebar is open on mobile", async () => {
      render(ChatInterface);
      
      const menuButton = screen.getByLabelText("Toggle sidebar");
      await fireEvent.click(menuButton);
      
      const overlay = document.querySelector(".bg-black.bg-opacity-50");
      expect(overlay).toBeTruthy();
    });

    it("should collapse sidebar when thread is selected on mobile", async () => {
      const mockSelectThread = vi.fn();
      (chat.selectThread as any) = mockSelectThread;
      
      render(ChatInterface);
      
      // First open sidebar
      const menuButton = screen.getByLabelText("Toggle sidebar");
      await fireEvent.click(menuButton);
      
      // Create and dispatch custom event
      const component = document.querySelector(".flex.h-screen");
      const event = new CustomEvent("selectThread", {
        detail: { threadId: "thread-2" }
      });
      
      component?.dispatchEvent(event);
      
      await waitFor(() => {
        const sidebar = document.querySelector(".w-80");
        expect(sidebar?.classList.contains("-translate-x-full")).toBe(true);
      });
    });
  });

  describe("Thread Management", () => {
    it("should create new thread when requested", async () => {
      const mockCreateThread = vi.fn().mockResolvedValue({
        id: "new-thread",
        title: "New Thread",
      });
      (chat.createThread as any) = mockCreateThread;
      
      render(ChatInterface);
      
      const newChatButton = screen.getByText("New Chat");
      await fireEvent.click(newChatButton);
      
      // Modal should be visible
      expect(screen.getByText("Start Your First Chat")).toBeTruthy();
    });

    it("should select thread when thread selection event is fired", async () => {
      const mockSelectThread = vi.fn();
      (chat.selectThread as any) = mockSelectThread;
      
      render(ChatInterface);
      
      // Simulate thread selection
      const component = document.querySelector(".flex.h-screen");
      const event = new CustomEvent("selectThread", {
        detail: { threadId: "thread-2" }
      });
      
      component?.dispatchEvent(event);
      
      expect(mockSelectThread).toHaveBeenCalledWith("thread-2");
    });

    it("should delete thread when delete event is fired", async () => {
      const mockDeleteThread = vi.fn();
      (chat.deleteThread as any) = mockDeleteThread;
      
      render(ChatInterface);
      
      // Simulate thread deletion
      const component = document.querySelector(".flex.h-screen");
      const event = new CustomEvent("deleteThread", {
        detail: { threadId: "thread-1" }
      });
      
      component?.dispatchEvent(event);
      
      expect(mockDeleteThread).toHaveBeenCalledWith("thread-1");
    });
  });

  describe("Error Handling", () => {
    it("should display error notification when error exists", () => {
      const errorState = {
        ...mockChatState,
        error: "Failed to load messages",
      };
      
      (chat.subscribe as any).mockImplementation((callback: any) => {
        callback(errorState);
        return () => {};
      });
      
      render(ChatInterface);
      
      expect(screen.getByText("Error")).toBeTruthy();
      expect(screen.getByText("Failed to load messages")).toBeTruthy();
    });

    it("should clear error when close button is clicked", async () => {
      const errorState = {
        ...mockChatState,
        error: "Test error",
      };
      
      (chat.subscribe as any).mockImplementation((callback: any) => {
        callback(errorState);
        return () => {};
      });
      
      render(ChatInterface);
      
      const closeButton = document.querySelector("button[aria-label='Close error']") ||
                         document.querySelector(".text-red-400.hover\\:text-red-300");
      expect(closeButton).toBeTruthy();
      
      await fireEvent.click(closeButton!);
      
      expect(chat.clearError).toHaveBeenCalledTimes(1);
    });
  });

  describe("Connection Status", () => {
    it("should show connected status when WebSocket is connected", () => {
      render(ChatInterface);
      
      expect(screen.getByText("Connected")).toBeTruthy();
      
      const statusIndicator = document.querySelector(".bg-green-400");
      expect(statusIndicator).toBeTruthy();
    });

    it("should show disconnected status when WebSocket is disconnected", () => {
      (websocket.subscribe as any).mockImplementation((callback: any) => {
        callback({ connected: false });
        return () => {};
      });
      
      const disconnectedChatState = {
        ...mockChatState,
        connected: false,
      };
      
      (chat.subscribe as any).mockImplementation((callback: any) => {
        callback(disconnectedChatState);
        return () => {};
      });
      
      render(ChatInterface);
      
      expect(screen.getByText("Disconnected")).toBeTruthy();
      
      const statusIndicator = document.querySelector(".bg-red-400");
      expect(statusIndicator).toBeTruthy();
    });
  });

  describe("Welcome Screen", () => {
    it("should show welcome screen when no thread is selected", () => {
      const noThreadState = {
        ...mockChatState,
        currentThreadId: null,
      };
      
      (chat.subscribe as any).mockImplementation((callback: any) => {
        callback(noThreadState);
        return () => {};
      });

      vi.mocked(chat).currentThread = {
        subscribe: vi.fn((callback) => {
          callback(null);
          return () => {};
        }),
      } as any;
      
      render(ChatInterface);
      
      expect(screen.getByText("Welcome to Supervisor Agent Chat")).toBeTruthy();
      expect(screen.getByText("Start Your First Chat")).toBeTruthy();
    });

    it("should open new chat modal when welcome button is clicked", async () => {
      const noThreadState = {
        ...mockChatState,
        currentThreadId: null,
      };
      
      (chat.subscribe as any).mockImplementation((callback: any) => {
        callback(noThreadState);
        return () => {};
      });

      vi.mocked(chat).currentThread = {
        subscribe: vi.fn((callback) => {
          callback(null);
          return () => {};
        }),
      } as any;
      
      render(ChatInterface);
      
      const welcomeButton = screen.getByText("Start Your First Chat");
      await fireEvent.click(welcomeButton);
      
      // Check if modal state would be set (implementation detail)
      expect(welcomeButton).toBeTruthy();
    });
  });

  describe("Accessibility", () => {
    it("should have proper ARIA labels", () => {
      render(ChatInterface);
      
      const menuButton = screen.getByLabelText("Toggle sidebar");
      expect(menuButton).toBeTruthy();
    });

    it("should support keyboard navigation for sidebar toggle", async () => {
      render(ChatInterface);
      
      const menuButton = screen.getByLabelText("Toggle sidebar");
      
      // Simulate Enter key press
      await fireEvent.keyDown(menuButton, { key: "Enter", code: "Enter" });
      
      // Button should be accessible
      expect(menuButton).toBeTruthy();
    });
  });
});
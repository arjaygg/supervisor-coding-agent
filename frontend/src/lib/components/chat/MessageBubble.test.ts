import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import MessageBubble from "./MessageBubble.svelte";
import type { ChatMessage } from "$lib/stores/chat";

// Mock the child components
vi.mock("./MessageEditor.svelte", () => ({
  default: vi.fn(() => ({
    $$: {
      on_mount: [],
      on_destroy: [],
      before_update: [],
      after_update: [],
      callbacks: {}
    }
  }))
}));

vi.mock("./RegenerateButton.svelte", () => ({
  default: vi.fn(() => ({
    $$: {
      on_mount: [],
      on_destroy: [],
      before_update: [],
      after_update: [],
      callbacks: {}
    }
  }))
}));

vi.mock("./StreamingMessage.svelte", () => ({
  default: vi.fn(() => ({
    $$: {
      on_mount: [],
      on_destroy: [],
      before_update: [],
      after_update: [],
      callbacks: {}
    }
  }))
}));

describe("MessageBubble", () => {
  const baseMockMessage: ChatMessage = {
    id: "msg-1",
    thread_id: "thread-1",
    role: "USER",
    content: "Hello, this is a test message",
    message_type: "TEXT",
    metadata: {},
    created_at: "2023-01-01T12:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("User Messages", () => {
    it("should render user message with correct styling", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const messageContainer = document.querySelector(".justify-end");
      expect(messageContainer).toBeTruthy();

      const messageBubble = document.querySelector(".bg-blue-600");
      expect(messageBubble).toBeTruthy();

      expect(screen.getByText("Hello, this is a test message")).toBeTruthy();
    });

    it("should show user avatar for user messages", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Check for user avatar (should be on the right side)
      const avatar = document.querySelector(".bg-blue-600.rounded-full");
      expect(avatar).toBeTruthy();
    });

    it("should display timestamp when showTimestamp is true", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.getByText("12:00 PM")).toBeTruthy();
    });

    it("should hide timestamp when showTimestamp is false", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: false,
        time: "12:00 PM",
      });

      expect(screen.queryByText("12:00 PM")).toBeFalsy();
    });
  });

  describe("Assistant Messages", () => {
    const assistantMessage: ChatMessage = {
      ...baseMockMessage,
      id: "msg-2",
      role: "ASSISTANT",
      content: "I can help you with that task.",
    };

    it("should render assistant message with correct styling", () => {
      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:01 PM",
      });

      const messageContainer = document.querySelector(".justify-start");
      expect(messageContainer).toBeTruthy();

      const messageBubble = document.querySelector(".bg-gray-700");
      expect(messageBubble).toBeTruthy();

      expect(screen.getByText("I can help you with that task.")).toBeTruthy();
    });

    it("should show AI avatar for assistant messages", () => {
      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:01 PM",
      });

      // Check for AI avatar (should be on the left side with specific icon)
      const aiIcon = document.querySelector('svg[viewBox="0 0 24 24"]');
      expect(aiIcon).toBeTruthy();
    });

    it("should display assistant role indicator", () => {
      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:01 PM",
      });

      // Check for assistant identifier in DOM
      const assistantIndicator = document.querySelector(".text-gray-400");
      expect(assistantIndicator).toBeTruthy();
    });
  });

  describe("System Messages", () => {
    const systemMessage: ChatMessage = {
      ...baseMockMessage,
      id: "msg-3",
      role: "SYSTEM",
      content: "Task has been created successfully.",
      message_type: "NOTIFICATION",
    };

    it("should render system message with distinct styling", () => {
      render(MessageBubble, {
        message: systemMessage,
        showTimestamp: true,
        time: "12:02 PM",
      });

      expect(screen.getByText("Task has been created successfully.")).toBeTruthy();
      
      // System messages should have different styling
      const systemBubble = document.querySelector(".bg-yellow-800") ||
                          document.querySelector(".bg-green-800") ||
                          document.querySelector(".bg-orange-800");
      expect(systemBubble).toBeTruthy();
    });

    it("should show system icon for system messages", () => {
      render(MessageBubble, {
        message: systemMessage,
        showTimestamp: true,
        time: "12:02 PM",
      });

      // Check for system/notification icon
      const systemIcon = document.querySelector('svg');
      expect(systemIcon).toBeTruthy();
    });
  });

  describe("Message Types", () => {
    it("should handle TEXT messages", () => {
      render(MessageBubble, {
        message: { ...baseMockMessage, message_type: "TEXT" },
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.getByText("Hello, this is a test message")).toBeTruthy();
    });

    it("should handle TASK_BREAKDOWN messages", () => {
      const taskMessage: ChatMessage = {
        ...baseMockMessage,
        message_type: "TASK_BREAKDOWN",
        content: "Breaking down the task into steps...",
      };

      render(MessageBubble, {
        message: taskMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.getByText("Breaking down the task into steps...")).toBeTruthy();
    });

    it("should handle PROGRESS messages", () => {
      const progressMessage: ChatMessage = {
        ...baseMockMessage,
        message_type: "PROGRESS",
        content: "Task is 50% complete",
      };

      render(MessageBubble, {
        message: progressMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.getByText("Task is 50% complete")).toBeTruthy();
    });

    it("should handle ERROR messages", () => {
      const errorMessage: ChatMessage = {
        ...baseMockMessage,
        message_type: "ERROR",
        content: "An error occurred while processing the task",
        role: "SYSTEM",
      };

      render(MessageBubble, {
        message: errorMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.getByText("An error occurred while processing the task")).toBeTruthy();
      
      // Error messages should have red styling
      const errorBubble = document.querySelector(".bg-red-800") ||
                         document.querySelector(".text-red-400");
      expect(errorBubble).toBeTruthy();
    });
  });

  describe("Content Formatting", () => {
    it("should preserve line breaks in message content", () => {
      const multilineMessage: ChatMessage = {
        ...baseMockMessage,
        content: "Line 1\nLine 2\nLine 3",
      };

      render(MessageBubble, {
        message: multilineMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const messageContent = screen.getByText("Line 1\nLine 2\nLine 3");
      expect(messageContent).toBeTruthy();
      
      // Should have whitespace-pre-wrap or similar styling
      const contentElement = messageContent.closest('div, p, span');
      expect(contentElement?.classList.contains('whitespace-pre-wrap') ||
             contentElement?.style.whiteSpace === 'pre-wrap').toBe(true);
    });

    it("should handle empty message content", () => {
      const emptyMessage: ChatMessage = {
        ...baseMockMessage,
        content: "",
      };

      render(MessageBubble, {
        message: emptyMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Should still render the bubble structure
      const messageBubble = document.querySelector(".bg-blue-600, .bg-gray-700");
      expect(messageBubble).toBeTruthy();
    });

    it("should handle very long message content", () => {
      const longMessage: ChatMessage = {
        ...baseMockMessage,
        content: "This is a very long message that should wrap properly and not break the layout. ".repeat(10),
      };

      render(MessageBubble, {
        message: longMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const messageContent = screen.getByText(longMessage.content);
      expect(messageContent).toBeTruthy();
      
      // Should have proper word wrapping
      const contentElement = messageContent.closest('div, p, span');
      expect(contentElement?.classList.contains('break-words') ||
             contentElement?.style.wordBreak === 'break-word').toBe(true);
    });

    it("should handle special characters in message content", () => {
      const specialMessage: ChatMessage = {
        ...baseMockMessage,
        content: "Special chars: <script>alert('test')</script> & 'quotes' \"double\" @mentions #tags",
      };

      render(MessageBubble, {
        message: specialMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Content should be properly escaped/sanitized
      expect(screen.getByText(specialMessage.content)).toBeTruthy();
    });
  });

  describe("Metadata Handling", () => {
    it("should handle message with metadata", () => {
      const messageWithMetadata: ChatMessage = {
        ...baseMockMessage,
        metadata: {
          task_id: "task-123",
          priority: "high",
          source: "api",
        },
      };

      render(MessageBubble, {
        message: messageWithMetadata,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Message should render normally regardless of metadata
      expect(screen.getByText("Hello, this is a test message")).toBeTruthy();
    });

    it("should handle message with empty metadata", () => {
      const messageWithEmptyMetadata: ChatMessage = {
        ...baseMockMessage,
        metadata: {},
      };

      render(MessageBubble, {
        message: messageWithEmptyMetadata,
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.getByText("Hello, this is a test message")).toBeTruthy();
    });
  });

  describe("Timestamp Formatting", () => {
    it("should display custom time format", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "2:30 PM",
      });

      expect(screen.getByText("2:30 PM")).toBeTruthy();
    });

    it("should handle 24-hour time format", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "14:30",
      });

      expect(screen.getByText("14:30")).toBeTruthy();
    });

    it("should position timestamp correctly for user messages", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const timestamp = screen.getByText("12:00 PM");
      const timestampContainer = timestamp.closest('div');
      
      // Should be positioned on the right for user messages
      expect(timestampContainer?.classList.contains('text-right') ||
             timestampContainer?.classList.contains('justify-end')).toBe(true);
    });

    it("should position timestamp correctly for assistant messages", () => {
      const assistantMessage: ChatMessage = {
        ...baseMockMessage,
        role: "ASSISTANT",
      };

      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const timestamp = screen.getByText("12:00 PM");
      const timestampContainer = timestamp.closest('div');
      
      // Should be positioned on the left for assistant messages
      expect(timestampContainer?.classList.contains('text-left') ||
             timestampContainer?.classList.contains('justify-start')).toBe(true);
    });
  });

  describe("Message Actions", () => {
    it("should show edit button for user messages", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const editButton = screen.getByTitle("Edit message");
      expect(editButton).toBeTruthy();
    });

    it("should not show edit button for assistant messages", () => {
      const assistantMessage: ChatMessage = {
        ...baseMockMessage,
        role: "ASSISTANT",
      };

      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      expect(screen.queryByTitle("Edit message")).toBeFalsy();
    });

    it("should show copy button for all messages", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const copyButton = screen.getByTitle("Copy message");
      expect(copyButton).toBeTruthy();
    });
  });

  describe("Message Editing", () => {
    it("should start editing mode when edit button is clicked", async () => {
      const { component } = render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const editButton = screen.getByTitle("Edit message");
      await fireEvent.click(editButton);

      // Check that editing state is active
      await waitFor(() => {
        expect(component.isEditing).toBe(true);
      });
    });

    it("should handle edit save event", async () => {
      const { component } = render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const editButton = screen.getByTitle("Edit message");
      await fireEvent.click(editButton);

      // Simulate save event from MessageEditor
      const saveEvent = new CustomEvent("save", {
        detail: {
          messageId: "msg-1",
          content: "Updated message content",
        },
      });

      await fireEvent(component, saveEvent);

      // Should exit editing mode
      await waitFor(() => {
        expect(component.isEditing).toBe(false);
      });
    });

    it("should handle edit cancel event", async () => {
      const { component } = render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      const editButton = screen.getByTitle("Edit message");
      await fireEvent.click(editButton);

      // Simulate cancel event from MessageEditor
      const cancelEvent = new CustomEvent("cancel");
      await fireEvent(component, cancelEvent);

      // Should exit editing mode
      await waitFor(() => {
        expect(component.isEditing).toBe(false);
      });
    });
  });

  describe("Message Regeneration", () => {
    const assistantMessage: ChatMessage = {
      ...baseMockMessage,
      id: "msg-2",
      role: "ASSISTANT",
      content: "I can help you with that task.",
    };

    it("should handle regeneration request", async () => {
      const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});
      
      const { component } = render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Simulate regenerate event from RegenerateButton
      const regenerateEvent = new CustomEvent("regenerate", {
        detail: {
          messageId: "msg-2",
          option: "shorter",
          originalContent: "I can help you with that task.",
        },
      });

      await fireEvent(component, regenerateEvent);

      // Should log the regeneration request
      expect(consoleSpy).toHaveBeenCalledWith("Message regeneration requested:", {
        messageId: "msg-2",
        option: "shorter",
        originalContent: "I can help you with that task.",
      });

      consoleSpy.mockRestore();
    });

    it("should show regenerating state during regeneration", async () => {
      const { component } = render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Simulate regenerate event
      const regenerateEvent = new CustomEvent("regenerate", {
        detail: {
          messageId: "msg-2",
          option: "standard",
          originalContent: "I can help you with that task.",
        },
      });

      await fireEvent(component, regenerateEvent);

      // Should show regenerating state
      expect(component.isRegenerating).toBe(true);

      // Wait for regeneration to complete
      await waitFor(() => {
        expect(component.isRegenerating).toBe(false);
      }, { timeout: 3000 });
    });
  });

  describe("Streaming Messages", () => {
    const assistantMessage: ChatMessage = {
      ...baseMockMessage,
      id: "msg-2",
      role: "ASSISTANT",
      content: "I can help you with that task.",
    };

    it("should show streaming content when streaming", () => {
      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:00 PM",
        isStreaming: true,
        streamingContent: "I'm thinking...",
      });

      // Should use StreamingMessage component for streaming
      // We can't easily test the mock component, but we can verify the props are passed
      expect(screen.getByText("I can help you with that task.")).toBeTruthy();
    });

    it("should show static content when not streaming", () => {
      render(MessageBubble, {
        message: assistantMessage,
        showTimestamp: true,
        time: "12:00 PM",
        isStreaming: false,
      });

      expect(screen.getByText("I can help you with that task.")).toBeTruthy();
    });
  });

  describe("Accessibility", () => {
    it("should have proper semantic structure", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Should have proper role or semantic elements
      const messageElement = screen.getByText("Hello, this is a test message").closest('div');
      expect(messageElement).toBeTruthy();
    });

    it("should include role information for screen readers", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Could check for aria-label or data attributes that indicate role
      const messageContainer = document.querySelector('[data-role="USER"], [aria-label*="user"], [data-message-role="USER"]');
      expect(messageContainer).toBeTruthy();
    });

    it("should be keyboard accessible", () => {
      render(MessageBubble, {
        message: baseMockMessage,
        showTimestamp: true,
        time: "12:00 PM",
      });

      // Message bubbles should be focusable or within focusable containers
      const messageElement = screen.getByText("Hello, this is a test message");
      expect(messageElement).toBeTruthy();
      
      // Could check for tabindex or other focus management
    });
  });
});
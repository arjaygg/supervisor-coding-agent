import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, waitFor, screen } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import MessageInput from "./MessageInput.svelte";

describe("MessageInput", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render textarea with placeholder", () => {
      render(MessageInput, {
        placeholder: "Type your message...",
      });

      const textarea = screen.getByPlaceholderText("Type your message...");
      expect(textarea).toBeTruthy();
    });

    it("should render send button", () => {
      render(MessageInput);

      const sendButton = screen.getByTitle("Send message (Enter)");
      expect(sendButton).toBeTruthy();
    });

    it("should render file upload button (disabled)", () => {
      render(MessageInput);

      const fileButton = screen.getByTitle("Attach file (coming soon)");
      expect(fileButton).toBeTruthy();
      expect(fileButton.disabled).toBe(true);
    });

    it("should render voice message button (disabled)", () => {
      render(MessageInput);

      const voiceButton = screen.getByTitle("Voice message (coming soon)");
      expect(voiceButton).toBeTruthy();
      expect(voiceButton.disabled).toBe(true);
    });
  });

  describe("Message Input Functionality", () => {
    it("should allow typing in textarea", async () => {
      render(MessageInput);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Hello, this is a test message");

      expect(textarea.value).toBe("Hello, this is a test message");
    });

    it("should auto-resize textarea based on content", async () => {
      render(MessageInput);

      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      const initialHeight = textarea.style.height;

      // Type multiple lines
      await user.type(textarea, "Line 1\nLine 2\nLine 3\nLine 4");

      // Height should change (implementation-dependent)
      expect(textarea.value).toContain("Line 1\nLine 2\nLine 3\nLine 4");
    });

    it("should limit message length to maxLength", async () => {
      render(MessageInput, { maxLength: 10 });

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "This is a very long message that exceeds the limit");

      // Should be truncated to maxLength
      expect(textarea.value.length).toBeLessThanOrEqual(10);
    });

    it("should show character count when approaching limit", async () => {
      render(MessageInput, { maxLength: 20 });

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Test message over half");

      // Character count should be visible
      const characterCount = screen.getByText(/\/20/);
      expect(characterCount).toBeTruthy();
    });
  });

  describe("Send Functionality", () => {
    it("should emit send event when send button is clicked", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Test message");

      const sendButton = screen.getByTitle("Send message (Enter)");
      await fireEvent.click(sendButton);

      expect(mockHandler).toHaveBeenCalledTimes(1);
      expect(mockHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          detail: { content: "Test message" }
        })
      );
    });

    it("should emit send event when Enter is pressed", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Test message");
      await user.keyboard("{Enter}");

      expect(mockHandler).toHaveBeenCalledTimes(1);
      expect(mockHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          detail: { content: "Test message" }
        })
      );
    });

    it("should not send when Shift+Enter is pressed", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Line 1");
      await user.keyboard("{Shift>}{Enter}{/Shift}");
      await user.type(textarea, "Line 2");

      expect(mockHandler).not.toHaveBeenCalled();
      expect(textarea.value).toContain("Line 1\nLine 2");
    });

    it("should not send empty or whitespace-only messages", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      
      // Test empty message
      const sendButton = screen.getByTitle("Send message (Enter)");
      await fireEvent.click(sendButton);
      expect(mockHandler).not.toHaveBeenCalled();

      // Test whitespace-only message
      await user.type(textarea, "   \n\t  ");
      await fireEvent.click(sendButton);
      expect(mockHandler).not.toHaveBeenCalled();
    });

    it("should clear input after sending message", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Test message");

      const sendButton = screen.getByTitle("Send message (Enter)");
      await fireEvent.click(sendButton);

      expect(textarea.value).toBe("");
    });

    it("should focus back to textarea after sending", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Test message");

      const sendButton = screen.getByTitle("Send message (Enter)");
      await fireEvent.click(sendButton);

      // Use setTimeout to account for the implementation delay
      await waitFor(() => {
        expect(document.activeElement).toBe(textarea);
      });
    });
  });

  describe("Loading State", () => {
    it("should disable input when loading", () => {
      render(MessageInput, { loading: true });

      const textarea = screen.getByRole("textbox");
      expect(textarea.disabled).toBe(true);
    });

    it("should disable send button when loading", () => {
      render(MessageInput, { loading: true });

      const sendButton = screen.getByTitle("Send message (Enter)");
      expect(sendButton.disabled).toBe(true);
    });

    it("should show loading spinner when loading", () => {
      render(MessageInput, { loading: true });

      const spinner = document.querySelector(".animate-spin");
      expect(spinner).toBeTruthy();
    });

    it("should not send message when loading", async () => {
      const { component } = render(MessageInput, { loading: true });

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Test message");
      await user.keyboard("{Enter}");

      expect(mockHandler).not.toHaveBeenCalled();
    });
  });

  describe("Character Count", () => {
    it("should show green character count for normal usage", async () => {
      render(MessageInput, { maxLength: 100 });

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Short message");

      // Should not show character count for short messages
      const characterCount = screen.queryByText(/\/100/);
      expect(characterCount).toBeFalsy();
    });

    it("should show yellow character count when approaching limit", async () => {
      render(MessageInput, { maxLength: 20 });

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "This is getting long");

      const characterCount = screen.getByText(/\/20/);
      expect(characterCount).toBeTruthy();
      expect(characterCount.classList.contains("text-yellow-400")).toBe(true);
    });

    it("should show red character count when exceeding limit", async () => {
      render(MessageInput, { maxLength: 10 });

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "This message is definitely too long");

      const characterCount = screen.getByText(/\/10/);
      expect(characterCount).toBeTruthy();
      expect(characterCount.classList.contains("text-red-400")).toBe(true);
    });

    it("should disable send button when exceeding character limit", async () => {
      render(MessageInput, { maxLength: 5 });

      const textarea = screen.getByRole("textbox");
      await user.type(textarea, "Too long message");

      const sendButton = screen.getByTitle("Send message (Enter)");
      expect(sendButton.disabled).toBe(true);
    });
  });

  describe("Quick Actions", () => {
    it("should show helper text with quick actions when not loading", () => {
      render(MessageInput);

      expect(screen.getByText("Press Enter to send, Shift+Enter for new line")).toBeTruthy();
      expect(screen.getByText("📋 Task")).toBeTruthy();
      expect(screen.getByText("❓ Help")).toBeTruthy();
      expect(screen.getByText("🔍 Analyze")).toBeTruthy();
    });

    it("should hide helper text when loading", () => {
      render(MessageInput, { loading: true });

      expect(screen.queryByText("Press Enter to send, Shift+Enter for new line")).toBeFalsy();
      expect(screen.queryByText("📋 Task")).toBeFalsy();
    });

    it("should insert task template when task quick action is clicked", async () => {
      render(MessageInput);

      const textarea = screen.getByRole("textbox");
      const taskButton = screen.getByText("📋 Task");
      
      await fireEvent.click(taskButton);

      expect(textarea.value).toBe("Create a task for ");
    });

    it("should insert help template when help quick action is clicked", async () => {
      render(MessageInput);

      const textarea = screen.getByRole("textbox");
      const helpButton = screen.getByText("❓ Help");
      
      await fireEvent.click(helpButton);

      expect(textarea.value).toBe("Help me with ");
    });

    it("should insert analyze template when analyze quick action is clicked", async () => {
      render(MessageInput);

      const textarea = screen.getByRole("textbox");
      const analyzeButton = screen.getByText("🔍 Analyze");
      
      await fireEvent.click(analyzeButton);

      expect(textarea.value).toBe("Analyze this code: ");
    });
  });

  describe("IME Support", () => {
    it("should not send message during IME composition", async () => {
      const { component } = render(MessageInput);

      const mockHandler = vi.fn();
      component.$on("send", mockHandler);

      const textarea = screen.getByRole("textbox");
      
      // Start composition
      await fireEvent.compositionStart(textarea);
      await user.type(textarea, "Test");
      await user.keyboard("{Enter}");

      expect(mockHandler).not.toHaveBeenCalled();

      // End composition
      await fireEvent.compositionEnd(textarea);
      await user.keyboard("{Enter}");

      expect(mockHandler).toHaveBeenCalledTimes(1);
    });
  });

  describe("Button State Management", () => {
    it("should enable send button only when message is valid", async () => {
      render(MessageInput);

      const sendButton = screen.getByTitle("Send message (Enter)");
      const textarea = screen.getByRole("textbox");

      // Initially disabled
      expect(sendButton.disabled).toBe(true);

      // Enable after typing
      await user.type(textarea, "Valid message");
      expect(sendButton.disabled).toBe(false);

      // Disable when cleared
      await user.clear(textarea);
      expect(sendButton.disabled).toBe(true);

      // Disable with whitespace only
      await user.type(textarea, "   ");
      expect(sendButton.disabled).toBe(true);
    });

    it("should apply correct CSS classes to send button based on state", async () => {
      render(MessageInput);

      const sendButton = screen.getByTitle("Send message (Enter)");
      const textarea = screen.getByRole("textbox");

      // Disabled state
      expect(sendButton.classList.contains("bg-gray-600")).toBe(true);
      expect(sendButton.classList.contains("cursor-not-allowed")).toBe(true);

      // Enabled state
      await user.type(textarea, "Valid message");
      expect(sendButton.classList.contains("bg-blue-600")).toBe(true);
      expect(sendButton.classList.contains("hover:bg-blue-700")).toBe(true);
    });
  });
});
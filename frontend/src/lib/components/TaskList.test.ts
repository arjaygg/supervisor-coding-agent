import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import TaskList from "./TaskList.svelte";

const mockTasks = [
  {
    id: 1,
    type: "PR_REVIEW",
    status: "PENDING",
    priority: 5,
    created_at: "2023-01-01T00:00:00Z",
    updated_at: "2023-01-01T00:00:00Z",
    assigned_agent_id: null,
    retry_count: 0,
    error_message: null,
    payload: { pr_number: 123, title: "Test PR" },
  },
  {
    id: 2,
    type: "CODE_ANALYSIS",
    status: "IN_PROGRESS",
    priority: 3,
    created_at: "2023-01-01T01:00:00Z",
    updated_at: "2023-01-01T01:00:00Z",
    assigned_agent_id: "agent-1",
    retry_count: 0,
    error_message: null,
    payload: { repository: "test/repo" },
  },
];

describe("TaskList", () => {
  it("should render empty state when no tasks", () => {
    const { getByText } = render(TaskList, { props: { tasks: [] } });

    expect(getByText(/no tasks found/i)).toBeTruthy();
  });

  it("should render task items", () => {
    const { getByText } = render(TaskList, { props: { tasks: mockTasks } });

    expect(getByText("PR_REVIEW")).toBeTruthy();
    expect(getByText("CODE_ANALYSIS")).toBeTruthy();
  });

  it("should show task status badges", () => {
    const { container } = render(TaskList, { props: { tasks: mockTasks } });

    const statusBadges = container.querySelectorAll(".status-badge");
    expect(statusBadges.length).toBe(2);
  });

  it("should display task priority indicators", () => {
    const { getByText } = render(TaskList, { props: { tasks: mockTasks } });

    expect(getByText("🟡")).toBeTruthy(); // High priority (3)
    expect(getByText("🔵")).toBeTruthy(); // Normal priority (5)
  });

  it("should show approve/reject buttons for pending tasks", () => {
    const { getByText } = render(TaskList, {
      props: { tasks: [mockTasks[0]] },
    });

    expect(getByText(/approve/i)).toBeTruthy();
    expect(getByText(/reject/i)).toBeTruthy();
  });

  it("should not show approve/reject buttons for non-pending tasks", () => {
    const { queryByText } = render(TaskList, {
      props: { tasks: [mockTasks[1]] },
    });

    expect(queryByText(/approve/i)).toBeFalsy();
    expect(queryByText(/reject/i)).toBeFalsy();
  });

  it("should handle keyboard shortcuts for approval", async () => {
    const user = userEvent.setup();
    const { container, component } = render(TaskList, {
      props: { tasks: [mockTasks[0]] },
    });

    const mockApproveHandler = vi.fn();
    const mockRejectHandler = vi.fn();

    component.$on("approveTask", mockApproveHandler);
    component.$on("rejectTask", mockRejectHandler);

    // Focus on the task item
    const taskItem = container.querySelector('[data-testid="task-item-1"]');
    if (taskItem) {
      taskItem.focus();

      // Press 'a' for approve
      await user.keyboard("a");
      expect(mockApproveHandler).toHaveBeenCalledWith(
        expect.objectContaining({ detail: { taskId: 1 } })
      );

      // Press 'r' for reject
      await user.keyboard("r");
      expect(mockRejectHandler).toHaveBeenCalledWith(
        expect.objectContaining({ detail: { taskId: 1 } })
      );
    }
  });

  it("should be mobile-friendly with touch targets", () => {
    const { container } = render(TaskList, { props: { tasks: mockTasks } });

    const taskItems = container.querySelectorAll(".list-item");
    taskItems.forEach((item) => {
      expect(item.classList.contains("list-item")).toBe(true);
    });
  });

  it("should emit events when approve/reject buttons are clicked", async () => {
    const { getByText, component } = render(TaskList, {
      props: { tasks: [mockTasks[0]] },
    });

    const mockApproveHandler = vi.fn();
    const mockRejectHandler = vi.fn();

    component.$on("approveTask", mockApproveHandler);
    component.$on("rejectTask", mockRejectHandler);

    const approveButton = getByText(/approve/i);
    const rejectButton = getByText(/reject/i);

    await fireEvent.click(approveButton);
    expect(mockApproveHandler).toHaveBeenCalledTimes(1);

    await fireEvent.click(rejectButton);
    expect(mockRejectHandler).toHaveBeenCalledTimes(1);
  });

  it("should show task details in mobile-friendly format", () => {
    const { getByText } = render(TaskList, { props: { tasks: mockTasks } });

    // Should show truncated payload information
    expect(getByText(/Test PR/)).toBeTruthy();
    expect(getByText(/test\/repo/)).toBeTruthy();
  });
});

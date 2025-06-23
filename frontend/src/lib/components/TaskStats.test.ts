import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/svelte";
import { get } from "svelte/store";
import TaskStats from "./TaskStats.svelte";
import { tasks } from "$lib/stores/tasks";

// Mock the tasks store
vi.mock("$lib/stores/tasks", () => {
  const mockStats = {
    total_tasks: 10,
    by_status: {
      PENDING: 3,
      IN_PROGRESS: 2,
      COMPLETED: 4,
      FAILED: 1,
    },
    by_type: {
      PR_REVIEW: 4,
      CODE_ANALYSIS: 3,
      BUG_FIX: 2,
      FEATURE: 1,
    },
    by_priority: {
      1: 1,
      3: 2,
      5: 5,
      7: 2,
    },
  };

  return {
    tasks: {
      subscribe: vi.fn((callback) => {
        callback([]);
        return () => {};
      }),
      stats: {
        subscribe: vi.fn((callback) => {
          callback(mockStats);
          return () => {};
        }),
      },
    },
  };
});

describe("TaskStats", () => {
  it("should render total tasks count", () => {
    const { getByText } = render(TaskStats);

    expect(getByText("10")).toBeTruthy();
    expect(getByText(/total tasks/i)).toBeTruthy();
  });

  it("should render status breakdown", () => {
    const { getByText } = render(TaskStats);

    expect(getByText("3")).toBeTruthy(); // Pending
    expect(getByText("2")).toBeTruthy(); // In Progress
    expect(getByText("4")).toBeTruthy(); // Completed
    expect(getByText("1")).toBeTruthy(); // Failed
  });

  it("should display status labels", () => {
    const { getByText } = render(TaskStats);

    expect(getByText(/pending/i)).toBeTruthy();
    expect(getByText(/active/i)).toBeTruthy();
    expect(getByText(/completed/i)).toBeTruthy();
    expect(getByText(/failed/i)).toBeTruthy();
  });

  it("should be responsive and mobile-friendly", () => {
    const { container } = render(TaskStats);

    const grid = container.querySelector(".grid");
    expect(grid?.classList.contains("grid-cols-2")).toBe(true);
    expect(grid?.classList.contains("md:grid-cols-4")).toBe(true);
  });

  it("should show task type distribution", () => {
    const { getByText } = render(TaskStats);

    expect(getByText(/PR Review/i)).toBeTruthy();
    expect(getByText(/Code Analysis/i)).toBeTruthy();
    expect(getByText(/Bug Fix/i)).toBeTruthy();
  });
});

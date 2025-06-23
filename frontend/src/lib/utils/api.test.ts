import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "./api";

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("API utilities", () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  describe("ApiError", () => {
    it("should create error with status and message", () => {
      const error = new ApiError(404, "Not found");
      expect(error.status).toBe(404);
      expect(error.message).toBe("Not found");
      expect(error.name).toBe("ApiError");
    });
  });

  describe("api.getTasks", () => {
    it("should fetch tasks successfully", async () => {
      const mockTasks = [
        { id: 1, type: "PR_REVIEW", status: "PENDING" },
        { id: 2, type: "CODE_ANALYSIS", status: "COMPLETED" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTasks,
      });

      const result = await api.getTasks();

      expect(mockFetch).toHaveBeenCalledWith("/api/v1/tasks", {
        headers: { "Content-Type": "application/json" },
      });
      expect(result).toEqual(mockTasks);
    });

    it("should handle query parameters", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await api.getTasks({ skip: 10, limit: 20, status: "PENDING" });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/tasks?skip=10&limit=20&status=PENDING",
        {
          headers: { "Content-Type": "application/json" },
        }
      );
    });

    it("should throw ApiError on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: "Internal server error" }),
      });

      await expect(api.getTasks()).rejects.toThrow(ApiError);
      await expect(api.getTasks()).rejects.toThrow("Internal server error");
    });
  });

  describe("api.createTask", () => {
    it("should create task successfully", async () => {
      const newTask = { id: 3, type: "BUG_FIX", status: "PENDING" };
      const taskData = {
        type: "BUG_FIX",
        payload: { issue: "test" },
        priority: 5,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => newTask,
      });

      const result = await api.createTask(taskData);

      expect(mockFetch).toHaveBeenCalledWith("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(taskData),
      });
      expect(result).toEqual(newTask);
    });
  });

  describe("api.getQuotaStatus", () => {
    it("should fetch quota status successfully", async () => {
      const quotaStatus = {
        available_agents: 2,
        total_agents: 3,
        quota_remaining: { "agent-1": 500, "agent-2": 750 },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => quotaStatus,
      });

      const result = await api.getQuotaStatus();

      expect(mockFetch).toHaveBeenCalledWith("/api/v1/agents/quota/status", {
        headers: { "Content-Type": "application/json" },
      });
      expect(result).toEqual(quotaStatus);
    });
  });
});

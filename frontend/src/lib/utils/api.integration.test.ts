import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { api } from "./api";

/**
 * Integration tests for API connectivity
 * These tests verify that the frontend can actually communicate with the backend
 *
 * Prerequisites:
 * - Backend server should be running on localhost:8000
 * - Database should be initialized
 * - Test data should be available
 */

const BACKEND_BASE_URL = "http://localhost:3000"; // Through Vite proxy
const WEBSOCKET_URL = "ws://localhost:3000/ws"; // Through Vite proxy

describe("Frontend-Backend Integration", () => {
  beforeAll(async () => {
    // Wait a bit for potential server startup
    await new Promise((resolve) => setTimeout(resolve, 1000));
  });

  describe("API Connectivity", () => {
    it("should connect to backend health endpoint", async () => {
      const health = await api.getHealth();

      expect(health).toBeDefined();
      expect(health.status).toBe("healthy");
    });

    it("should fetch detailed health information", async () => {
      const detailedHealth = await api.getDetailedHealth();

      expect(detailedHealth).toBeDefined();
      expect(detailedHealth.status).toBe("healthy");
      expect(detailedHealth.components).toBeDefined();
    });

    it("should be able to fetch tasks list", async () => {
      const tasks = await api.getTasks();

      expect(Array.isArray(tasks)).toBe(true);
      // Even if empty, should return an array
    });

    it("should be able to fetch quota status", async () => {
      const quota = await api.getQuotaStatus();

      expect(quota).toBeDefined();
      expect(typeof quota.total_agents).toBe("number");
      expect(typeof quota.available_agents).toBe("number");
    });

    it("should be able to create a task", async () => {
      const taskData = {
        type: "PR_REVIEW",
        payload: {
          repository: "test/repo",
          pr_number: 123,
          title: "Test PR",
          description: "Integration test PR",
          diff: "--- a/file.js\n+++ b/file.js\n@@ -1,1 +1,1 @@\n-old\n+new",
        },
        priority: 5,
      };

      const createdTask = await api.createTask(taskData);

      expect(createdTask).toBeDefined();
      expect(createdTask.id).toBeDefined();
      expect(createdTask.type).toBe("PR_REVIEW");
      expect(createdTask.status).toBeDefined();
    });

    it("should handle CORS properly", async () => {
      // Test that CORS headers are properly set by making a preflight request
      const response = await fetch("/api/v1/healthz", {
        method: "OPTIONS",
        headers: {
          Origin: "http://localhost:5173",
          "Access-Control-Request-Method": "GET",
          "Access-Control-Request-Headers": "Content-Type",
        },
      });

      expect(response.status).toBe(200);
      const corsHeaders = response.headers.get("Access-Control-Allow-Origin");
      expect(corsHeaders).toBeTruthy();
    });
  });

  describe("WebSocket Connectivity", () => {
    it("should be able to connect to WebSocket endpoint", async () => {
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("WebSocket connection timeout"));
        }, 5000);

        try {
          const ws = new WebSocket(WEBSOCKET_URL);

          ws.onopen = () => {
            clearTimeout(timeout);
            ws.close();
            resolve(true);
          };

          ws.onerror = (error) => {
            clearTimeout(timeout);
            reject(new Error(`WebSocket connection failed: ${error}`));
          };

          ws.onclose = (event) => {
            if (event.code !== 1000) {
              // 1000 = normal closure
              clearTimeout(timeout);
              reject(
                new Error(
                  `WebSocket closed unexpectedly: ${event.code} ${event.reason}`
                )
              );
            }
          };
        } catch (error) {
          clearTimeout(timeout);
          reject(error);
        }
      });
    }, 10000); // 10 second timeout

    it("should receive WebSocket messages for task updates", async () => {
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("No WebSocket message received within timeout"));
        }, 10000);

        try {
          const ws = new WebSocket(WEBSOCKET_URL);

          ws.onopen = () => {
            // Send a test message or wait for server-sent updates
            ws.send(JSON.stringify({ type: "ping" }));
          };

          ws.onmessage = (event) => {
            clearTimeout(timeout);
            try {
              const data = JSON.parse(event.data);
              expect(data).toBeDefined();
              ws.close();
              resolve(data);
            } catch (parseError) {
              reject(
                new Error(`Invalid WebSocket message format: ${event.data}`)
              );
            }
          };

          ws.onerror = (error) => {
            clearTimeout(timeout);
            reject(new Error(`WebSocket error: ${error}`));
          };
        } catch (error) {
          clearTimeout(timeout);
          reject(error);
        }
      });
    }, 15000);
  });

  describe("Error Handling", () => {
    it("should handle 404 errors gracefully", async () => {
      await expect(api.getTask(99999)).rejects.toThrow("Resource not found");
    });

    it("should handle network errors gracefully", async () => {
      // Mock a network error by using an invalid endpoint
      const originalFetch = global.fetch;
      global.fetch = async () => {
        throw new TypeError("Failed to fetch");
      };

      await expect(api.getHealth()).rejects.toThrow("Network error");

      // Restore original fetch
      global.fetch = originalFetch;
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { get } from "svelte/store";
import { promptTemplates } from "./promptTemplates";
import type { PromptTemplate } from "./promptTemplates";

// Mock the API
vi.mock("../utils/api", () => ({
  api: {
    getPromptTemplates: vi.fn(),
    createPromptTemplate: vi.fn(),
    updatePromptTemplate: vi.fn(),
    deletePromptTemplate: vi.fn(),
    logPromptTemplateUsage: vi.fn(),
  },
  ApiError: class extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  }
}));

import { api } from "../utils/api";

describe("promptTemplates store", () => {
  const mockTemplate: PromptTemplate = {
    id: "test-template",
    name: "Test Template",
    description: "A test template",
    template: "Hello {{name}}, your {{type}} is ready!",
    category: "Testing",
    tags: ["test", "demo"],
    type: "user",
    variables: [
      {
        name: "name",
        description: "User name",
        type: "text",
        required: true,
        placeholder: "Enter your name"
      },
      {
        name: "type",
        description: "Item type",
        type: "select",
        required: true,
        options: ["order", "package", "document"]
      }
    ],
    usage_count: 5,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchTemplates", () => {
    it("should fetch templates successfully", async () => {
      const mockResponse = {
        user_templates: [mockTemplate],
        community_templates: []
      };

      vi.mocked(api.getPromptTemplates).mockResolvedValue(mockResponse);

      await promptTemplates.fetchTemplates();

      const state = get(promptTemplates);
      expect(state.loading).toBe(false);
      expect(state.error).toBe(null);
      expect(state.userTemplates).toEqual([mockTemplate]);
      expect(state.templates.length).toBeGreaterThan(0); // Includes system templates
    });

    it("should handle fetch error gracefully", async () => {
      vi.mocked(api.getPromptTemplates).mockRejectedValue(new Error("Network error"));

      await promptTemplates.fetchTemplates();

      const state = get(promptTemplates);
      expect(state.loading).toBe(false);
      expect(state.error).toBe("Failed to fetch templates");
      expect(state.templates.length).toBeGreaterThan(0); // Should fallback to system templates
    });
  });

  describe("createTemplate", () => {
    it("should create template successfully", async () => {
      const newTemplate = { ...mockTemplate, id: "new-template" };
      vi.mocked(api.createPromptTemplate).mockResolvedValue(newTemplate);

      const result = await promptTemplates.createTemplate({
        name: newTemplate.name,
        description: newTemplate.description,
        template: newTemplate.template,
        category: newTemplate.category,
        tags: newTemplate.tags,
        variables: newTemplate.variables,
        type: "user",
        is_active: true,
      });

      expect(result).toEqual(newTemplate);
      
      const state = get(promptTemplates);
      expect(state.userTemplates).toContain(newTemplate);
      expect(state.templates).toContain(newTemplate);
    });

    it("should handle create error", async () => {
      vi.mocked(api.createPromptTemplate).mockRejectedValue(new Error("Creation failed"));

      await expect(promptTemplates.createTemplate({
        name: "Test",
        description: "Test",
        template: "Test",
        category: "Test",
        tags: [],
        variables: [],
        type: "user",
        is_active: true,
      })).rejects.toThrow();

      const state = get(promptTemplates);
      expect(state.error).toBe("Failed to create template");
    });
  });

  describe("updateTemplate", () => {
    it("should update template successfully", async () => {
      const updatedTemplate = { ...mockTemplate, name: "Updated Template" };
      vi.mocked(api.updatePromptTemplate).mockResolvedValue(updatedTemplate);

      // First add the template to state
      await promptTemplates.createTemplate({
        name: mockTemplate.name,
        description: mockTemplate.description,
        template: mockTemplate.template,
        category: mockTemplate.category,
        tags: mockTemplate.tags,
        variables: mockTemplate.variables,
        type: "user",
        is_active: true,
      });

      const result = await promptTemplates.updateTemplate(mockTemplate.id, {
        name: "Updated Template"
      });

      expect(result).toEqual(updatedTemplate);
      
      const state = get(promptTemplates);
      const updatedInState = state.templates.find(t => t.id === mockTemplate.id);
      expect(updatedInState?.name).toBe("Updated Template");
    });
  });

  describe("deleteTemplate", () => {
    it("should delete template successfully", async () => {
      vi.mocked(api.deletePromptTemplate).mockResolvedValue({ message: "Deleted" });

      // First add the template to state
      vi.mocked(api.createPromptTemplate).mockResolvedValue(mockTemplate);
      await promptTemplates.createTemplate({
        name: mockTemplate.name,
        description: mockTemplate.description,
        template: mockTemplate.template,
        category: mockTemplate.category,
        tags: mockTemplate.tags,
        variables: mockTemplate.variables,
        type: "user",
        is_active: true,
      });

      await promptTemplates.deleteTemplate(mockTemplate.id);

      const state = get(promptTemplates);
      expect(state.templates.find(t => t.id === mockTemplate.id)).toBeUndefined();
      expect(state.userTemplates.find(t => t.id === mockTemplate.id)).toBeUndefined();
    });
  });

  describe("renderTemplate", () => {
    it("should render template with variables", () => {
      const variables = {
        name: "John Doe",
        type: "order"
      };

      const rendered = promptTemplates.renderTemplate(mockTemplate, variables);
      expect(rendered).toBe("Hello John Doe, your order is ready!");
    });

    it("should handle missing variables", () => {
      const variables = {
        name: "John Doe"
        // missing 'type'
      };

      const rendered = promptTemplates.renderTemplate(mockTemplate, variables);
      expect(rendered).toBe("Hello John Doe, your  is ready!");
    });

    it("should clean up unfilled variables", () => {
      const template: PromptTemplate = {
        ...mockTemplate,
        template: "Hello {{name}}, {{unknown_var}} your {{type}}!"
      };

      const variables = {
        name: "John",
        type: "test"
      };

      const rendered = promptTemplates.renderTemplate(template, variables);
      expect(rendered).toBe("Hello John,  your test!");
    });
  });

  describe("logTemplateUsage", () => {
    it("should log template usage successfully", async () => {
      vi.mocked(api.logPromptTemplateUsage).mockResolvedValue({ message: "Logged" });
      
      // First add the template to state
      vi.mocked(api.createPromptTemplate).mockResolvedValue(mockTemplate);
      await promptTemplates.createTemplate({
        name: mockTemplate.name,
        description: mockTemplate.description,
        template: mockTemplate.template,
        category: mockTemplate.category,
        tags: mockTemplate.tags,
        variables: mockTemplate.variables,
        type: "user",
        is_active: true,
      });

      const variables = { name: "John", type: "order" };
      await promptTemplates.logTemplateUsage(mockTemplate.id, variables);

      expect(api.logPromptTemplateUsage).toHaveBeenCalledWith({
        template_id: mockTemplate.id,
        variables,
        rendered_prompt: "Hello John, your order is ready!",
      });

      const state = get(promptTemplates);
      const template = state.templates.find(t => t.id === mockTemplate.id);
      expect(template?.usage_count).toBe(mockTemplate.usage_count + 1);
    });

    it("should handle logging error gracefully", async () => {
      vi.mocked(api.logPromptTemplateUsage).mockRejectedValue(new Error("Logging failed"));
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      await promptTemplates.logTemplateUsage("non-existent", {});

      expect(consoleSpy).toHaveBeenCalledWith("Failed to log template usage:", expect.any(Error));
      consoleSpy.mockRestore();
    });
  });

  describe("utility methods", () => {
    it("should select template", () => {
      promptTemplates.selectTemplate(mockTemplate);

      const state = get(promptTemplates);
      expect(state.selectedTemplate).toEqual(mockTemplate);
    });

    it("should clear error", () => {
      // First set an error
      promptTemplates.fetchTemplates(); // This will set loading state
      
      promptTemplates.clearError();

      const state = get(promptTemplates);
      expect(state.error).toBe(null);
    });

    it("should get templates by category", async () => {
      // Add a template to state first
      vi.mocked(api.createPromptTemplate).mockResolvedValue(mockTemplate);
      await promptTemplates.createTemplate({
        name: mockTemplate.name,
        description: mockTemplate.description,
        template: mockTemplate.template,
        category: mockTemplate.category,
        tags: mockTemplate.tags,
        variables: mockTemplate.variables,
        type: "user",
        is_active: true,
      });

      const testingTemplates = promptTemplates.getTemplatesByCategory("Testing");
      expect(testingTemplates).toContain(mockTemplate);

      const nonExistentTemplates = promptTemplates.getTemplatesByCategory("NonExistent");
      expect(nonExistentTemplates).toEqual([]);
    });

    it("should search templates", async () => {
      // Add a template to state first
      vi.mocked(api.createPromptTemplate).mockResolvedValue(mockTemplate);
      await promptTemplates.createTemplate({
        name: mockTemplate.name,
        description: mockTemplate.description,
        template: mockTemplate.template,
        category: mockTemplate.category,
        tags: mockTemplate.tags,
        variables: mockTemplate.variables,
        type: "user",
        is_active: true,
      });

      // Search by name
      let results = promptTemplates.searchTemplates("Test Template");
      expect(results).toContain(mockTemplate);

      // Search by tag
      results = promptTemplates.searchTemplates("demo");
      expect(results).toContain(mockTemplate);

      // Search by category
      results = promptTemplates.searchTemplates("testing");
      expect(results).toContain(mockTemplate);

      // Search with no results
      results = promptTemplates.searchTemplates("nonexistent");
      expect(results).toEqual([]);
    });

    it("should get template by id", async () => {
      // Add a template to state first
      vi.mocked(api.createPromptTemplate).mockResolvedValue(mockTemplate);
      await promptTemplates.createTemplate({
        name: mockTemplate.name,
        description: mockTemplate.description,
        template: mockTemplate.template,
        category: mockTemplate.category,
        tags: mockTemplate.tags,
        variables: mockTemplate.variables,
        type: "user",
        is_active: true,
      });

      const found = promptTemplates.getTemplateById(mockTemplate.id);
      expect(found).toEqual(mockTemplate);

      const notFound = promptTemplates.getTemplateById("non-existent");
      expect(notFound).toBe(null);
    });
  });

  describe("default system templates", () => {
    it("should include system templates", () => {
      const state = get(promptTemplates);
      expect(state.systemTemplates.length).toBeGreaterThan(0);
      
      // Check that some expected system templates exist
      const codeReviewTemplate = state.systemTemplates.find(t => t.id === "code-review");
      expect(codeReviewTemplate).toBeDefined();
      expect(codeReviewTemplate?.type).toBe("system");
      
      const taskBreakdownTemplate = state.systemTemplates.find(t => t.id === "task-breakdown");
      expect(taskBreakdownTemplate).toBeDefined();
      expect(taskBreakdownTemplate?.type).toBe("system");
    });

    it("should have properly configured system templates", () => {
      const state = get(promptTemplates);
      const codeReviewTemplate = state.systemTemplates.find(t => t.id === "code-review");
      
      expect(codeReviewTemplate).toMatchObject({
        name: "Code Review",
        category: "Development",
        type: "system",
        is_active: true,
      });

      expect(codeReviewTemplate?.variables.length).toBeGreaterThan(0);
      expect(codeReviewTemplate?.template).toContain("{{");
    });
  });
});
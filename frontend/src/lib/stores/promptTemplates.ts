import { writable, derived, get } from "svelte/store";
import { api, ApiError } from "../utils/api";

// Types
export interface PromptTemplate {
  id: string;
  name: string;
  description: string;
  template: string;
  category: string;
  tags: string[];
  type: "system" | "user" | "community";
  variables: TemplateVariable[];
  usage_count: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  created_by?: string;
}

export interface TemplateVariable {
  name: string;
  description: string;
  type: "text" | "number" | "select" | "multiline";
  required: boolean;
  default_value?: string;
  options?: string[]; // For select type
  placeholder?: string;
}

export interface TemplateUsage {
  template_id: string;
  variables: Record<string, any>;
  rendered_prompt: string;
}

interface PromptTemplateState {
  templates: PromptTemplate[];
  userTemplates: PromptTemplate[];
  systemTemplates: PromptTemplate[];
  communityTemplates: PromptTemplate[];
  loading: boolean;
  error: string | null;
  selectedTemplate: PromptTemplate | null;
}

// Default system templates
const DEFAULT_SYSTEM_TEMPLATES: PromptTemplate[] = [
  {
    id: "code-review",
    name: "Code Review",
    description: "Comprehensive code review with security, performance, and maintainability analysis",
    template: `Please review the following {{language}} code for:

**Security Issues:**
- Look for potential vulnerabilities
- Check for unsafe operations
- Validate input handling

**Performance:**
- Identify performance bottlenecks
- Suggest optimizations
- Review algorithmic complexity

**Code Quality:**
- Check coding standards compliance
- Assess readability and maintainability
- Suggest refactoring opportunities

**Code to review:**
\`\`\`{{language}}
{{code}}
\`\`\`

{{additional_context}}`,
    category: "Development",
    tags: ["code", "review", "security", "performance"],
    type: "system",
    variables: [
      {
        name: "language",
        description: "Programming language",
        type: "select",
        required: true,
        options: ["JavaScript", "TypeScript", "Python", "Java", "C#", "Go", "Rust", "Other"],
        default_value: "TypeScript"
      },
      {
        name: "code",
        description: "Code to review",
        type: "multiline",
        required: true,
        placeholder: "Paste your code here..."
      },
      {
        name: "additional_context",
        description: "Additional context or specific areas to focus on",
        type: "multiline",
        required: false,
        placeholder: "Any specific concerns or areas you'd like me to focus on?"
      }
    ],
    usage_count: 0,
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: "task-breakdown",
    name: "Task Breakdown",
    description: "Break down complex tasks into manageable subtasks with priorities and dependencies",
    template: `Please break down the following task into manageable subtasks:

**Main Task:** {{task_title}}

**Description:** {{task_description}}

**Requirements:**
- Create a hierarchical breakdown of subtasks
- Assign priority levels (High/Medium/Low)
- Identify dependencies between tasks
- Estimate effort for each subtask
- Suggest the optimal execution order

**Context:**
- Timeline: {{timeline}}
- Team size: {{team_size}}
- Available resources: {{resources}}

{{additional_requirements}}`,
    category: "Planning",
    tags: ["project", "planning", "breakdown", "tasks"],
    type: "system",
    variables: [
      {
        name: "task_title",
        description: "Main task title",
        type: "text",
        required: true,
        placeholder: "e.g., Build user authentication system"
      },
      {
        name: "task_description",
        description: "Detailed task description",
        type: "multiline",
        required: true,
        placeholder: "Detailed description of what needs to be accomplished..."
      },
      {
        name: "timeline",
        description: "Project timeline",
        type: "text",
        required: false,
        placeholder: "e.g., 2 weeks, 1 month"
      },
      {
        name: "team_size",
        description: "Number of team members",
        type: "number",
        required: false,
        default_value: "1"
      },
      {
        name: "resources",
        description: "Available resources and constraints",
        type: "text",
        required: false,
        placeholder: "e.g., Budget, tools, existing infrastructure"
      },
      {
        name: "additional_requirements",
        description: "Additional requirements or constraints",
        type: "multiline",
        required: false,
        placeholder: "Any other specific requirements or constraints..."
      }
    ],
    usage_count: 0,
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: "bug-investigation",
    name: "Bug Investigation",
    description: "Systematic approach to investigating and debugging software issues",
    template: `I need help investigating the following bug:

**Bug Summary:** {{bug_title}}

**Description:** {{bug_description}}

**Environment:**
- OS: {{os}}
- Browser/Platform: {{platform}}
- Version: {{version}}

**Steps to Reproduce:**
{{reproduction_steps}}

**Expected Behavior:**
{{expected_behavior}}

**Actual Behavior:**
{{actual_behavior}}

**Error Messages/Logs:**
\`\`\`
{{error_logs}}
\`\`\`

**Additional Context:**
{{additional_context}}

Please help me:
1. Analyze the potential root causes
2. Suggest debugging approaches
3. Provide step-by-step investigation plan
4. Recommend fixes or workarounds`,
    category: "Development",
    tags: ["debugging", "troubleshooting", "investigation", "bug"],
    type: "system",
    variables: [
      {
        name: "bug_title",
        description: "Brief bug summary",
        type: "text",
        required: true,
        placeholder: "e.g., Login form not submitting on mobile Safari"
      },
      {
        name: "bug_description",
        description: "Detailed bug description",
        type: "multiline",
        required: true,
        placeholder: "Detailed description of the issue..."
      },
      {
        name: "os",
        description: "Operating System",
        type: "select",
        required: false,
        options: ["Windows", "macOS", "Linux", "iOS", "Android", "Other"]
      },
      {
        name: "platform",
        description: "Browser or platform",
        type: "text",
        required: false,
        placeholder: "e.g., Chrome 118, Safari 16, Node.js 18"
      },
      {
        name: "version",
        description: "Application version",
        type: "text",
        required: false,
        placeholder: "e.g., v2.1.0"
      },
      {
        name: "reproduction_steps",
        description: "Steps to reproduce the bug",
        type: "multiline",
        required: true,
        placeholder: "1. Navigate to...\n2. Click on...\n3. Enter..."
      },
      {
        name: "expected_behavior",
        description: "What should happen",
        type: "multiline",
        required: true,
        placeholder: "What you expected to happen..."
      },
      {
        name: "actual_behavior",
        description: "What actually happens",
        type: "multiline",
        required: true,
        placeholder: "What actually happens instead..."
      },
      {
        name: "error_logs",
        description: "Error messages or logs",
        type: "multiline",
        required: false,
        placeholder: "Console errors, stack traces, or log entries..."
      },
      {
        name: "additional_context",
        description: "Additional context",
        type: "multiline",
        required: false,
        placeholder: "Recent changes, related issues, etc..."
      }
    ],
    usage_count: 0,
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: "documentation-writer",
    name: "Documentation Writer",
    description: "Generate comprehensive documentation for code, APIs, or processes",
    template: `Please create {{doc_type}} documentation for:

**Subject:** {{subject}}

**Target Audience:** {{audience}}

**Documentation Type:** {{doc_type}}

**Content to Document:**
{{content}}

**Requirements:**
- Include clear examples and use cases
- Provide step-by-step instructions where applicable
- Add troubleshooting section if relevant
- Use appropriate formatting and structure
- Include code examples where helpful

**Style Guidelines:**
- Tone: {{tone}}
- Level of detail: {{detail_level}}
- Include {{sections}}

{{additional_requirements}}`,
    category: "Documentation",
    tags: ["documentation", "writing", "api", "guide"],
    type: "system",
    variables: [
      {
        name: "doc_type",
        description: "Type of documentation",
        type: "select",
        required: true,
        options: ["API Documentation", "User Guide", "Developer Guide", "Technical Specification", "Tutorial", "README", "Other"],
        default_value: "API Documentation"
      },
      {
        name: "subject",
        description: "What needs to be documented",
        type: "text",
        required: true,
        placeholder: "e.g., User Authentication API, Installation Process"
      },
      {
        name: "audience",
        description: "Target audience",
        type: "select",
        required: true,
        options: ["Developers", "End Users", "System Administrators", "Project Managers", "Mixed Audience"],
        default_value: "Developers"
      },
      {
        name: "content",
        description: "Code, process, or content to document",
        type: "multiline",
        required: true,
        placeholder: "Paste code, describe the process, or provide the content that needs documentation..."
      },
      {
        name: "tone",
        description: "Documentation tone",
        type: "select",
        required: false,
        options: ["Professional", "Friendly", "Technical", "Conversational"],
        default_value: "Professional"
      },
      {
        name: "detail_level",
        description: "Level of detail",
        type: "select",
        required: false,
        options: ["High-level overview", "Detailed explanation", "Step-by-step guide", "Reference documentation"],
        default_value: "Detailed explanation"
      },
      {
        name: "sections",
        description: "Sections to include",
        type: "text",
        required: false,
        placeholder: "e.g., examples, troubleshooting, best practices"
      },
      {
        name: "additional_requirements",
        description: "Additional requirements",
        type: "multiline",
        required: false,
        placeholder: "Any specific formatting, style, or content requirements..."
      }
    ],
    usage_count: 0,
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: "meeting-summary",
    name: "Meeting Summary",
    description: "Create structured summaries of meetings with action items and next steps",
    template: `Please create a structured summary of this meeting:

**Meeting Details:**
- Title: {{meeting_title}}
- Date: {{meeting_date}}
- Duration: {{duration}}
- Attendees: {{attendees}}

**Meeting Notes/Transcript:**
{{meeting_content}}

**Please structure the summary as:**

1. **Key Discussion Points** - Main topics covered
2. **Decisions Made** - Important decisions and their rationale
3. **Action Items** - Who does what by when
4. **Next Steps** - Follow-up meetings and deadlines
5. **Parking Lot** - Items to address later

**Focus Areas:**
{{focus_areas}}

Make the summary clear, actionable, and easy to share with stakeholders.`,
    category: "Communication",
    tags: ["meetings", "summary", "action items", "communication"],
    type: "system",
    variables: [
      {
        name: "meeting_title",
        description: "Meeting title",
        type: "text",
        required: true,
        placeholder: "e.g., Sprint Planning Meeting"
      },
      {
        name: "meeting_date",
        description: "Meeting date",
        type: "text",
        required: false,
        placeholder: "e.g., October 15, 2024"
      },
      {
        name: "duration",
        description: "Meeting duration",
        type: "text",
        required: false,
        placeholder: "e.g., 1 hour"
      },
      {
        name: "attendees",
        description: "Meeting attendees",
        type: "text",
        required: false,
        placeholder: "List of attendees..."
      },
      {
        name: "meeting_content",
        description: "Meeting notes or transcript",
        type: "multiline",
        required: true,
        placeholder: "Paste meeting notes, transcript, or key discussion points..."
      },
      {
        name: "focus_areas",
        description: "Specific areas to focus on",
        type: "text",
        required: false,
        placeholder: "e.g., action items, technical decisions, timeline changes"
      }
    ],
    usage_count: 0,
    is_active: true,
    created_at: new Date().toISOString(),
  }
];

// Create the prompt template store
function createPromptTemplateStore() {
  const { subscribe, set, update } = writable<PromptTemplateState>({
    templates: [],
    userTemplates: [],
    systemTemplates: DEFAULT_SYSTEM_TEMPLATES,
    communityTemplates: [],
    loading: false,
    error: null,
    selectedTemplate: null,
  });

  return {
    subscribe,

    // Template management
    async fetchTemplates(): Promise<void> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const data = await api.getPromptTemplates();
        
        update((state) => ({
          ...state,
          templates: [...DEFAULT_SYSTEM_TEMPLATES, ...data.user_templates, ...data.community_templates],
          userTemplates: data.user_templates || [],
          communityTemplates: data.community_templates || [],
          loading: false,
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to fetch templates";
        
        update((state) => ({
          ...state,
          templates: DEFAULT_SYSTEM_TEMPLATES, // Fallback to system templates
          loading: false,
          error: errorMessage,
        }));
      }
    },

    async createTemplate(templateData: Omit<PromptTemplate, "id" | "created_at" | "updated_at" | "usage_count">): Promise<PromptTemplate> {
      update((state) => ({ ...state, loading: true, error: null }));

      try {
        const newTemplate = await api.createPromptTemplate(templateData);

        update((state) => ({
          ...state,
          templates: [...state.templates, newTemplate],
          userTemplates: [...state.userTemplates, newTemplate],
          loading: false,
        }));

        return newTemplate;
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to create template";
        
        update((state) => ({
          ...state,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async updateTemplate(templateId: string, updates: Partial<PromptTemplate>): Promise<PromptTemplate> {
      try {
        const updatedTemplate = await api.updatePromptTemplate(templateId, updates);

        update((state) => ({
          ...state,
          templates: state.templates.map((t) => 
            t.id === templateId ? updatedTemplate : t
          ),
          userTemplates: state.userTemplates.map((t) => 
            t.id === templateId ? updatedTemplate : t
          ),
        }));

        return updatedTemplate;
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to update template";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    async deleteTemplate(templateId: string): Promise<void> {
      try {
        await api.deletePromptTemplate(templateId);

        update((state) => ({
          ...state,
          templates: state.templates.filter((t) => t.id !== templateId),
          userTemplates: state.userTemplates.filter((t) => t.id !== templateId),
        }));
      } catch (error) {
        const errorMessage = error instanceof ApiError 
          ? error.message 
          : "Failed to delete template";
        
        update((state) => ({
          ...state,
          error: errorMessage,
        }));
        throw error;
      }
    },

    // Template usage
    renderTemplate(template: PromptTemplate, variables: Record<string, any>): string {
      let rendered = template.template;

      // Replace variables in template
      Object.entries(variables).forEach(([key, value]) => {
        const regex = new RegExp(`{{${key}}}`, 'g');
        rendered = rendered.replace(regex, String(value || ''));
      });

      // Clean up any remaining unfilled variables
      rendered = rendered.replace(/{{[^}]+}}/g, '');

      return rendered;
    },

    async logTemplateUsage(templateId: string, variables: Record<string, any>): Promise<void> {
      try {
        const template = this.getTemplateById(templateId);
        if (!template) return;

        const rendered = this.renderTemplate(template, variables);
        
        await api.logPromptTemplateUsage({
          template_id: templateId,
          variables,
          rendered_prompt: rendered,
        });

        // Update usage count locally
        update((state) => ({
          ...state,
          templates: state.templates.map((t) => 
            t.id === templateId ? { ...t, usage_count: t.usage_count + 1 } : t
          ),
        }));
      } catch (error) {
        console.warn("Failed to log template usage:", error);
      }
    },

    // Template selection
    selectTemplate(template: PromptTemplate | null): void {
      update((state) => ({ ...state, selectedTemplate: template }));
    },

    // Utility methods
    getTemplateById(id: string): PromptTemplate | null {
      const state = get({ subscribe });
      return state.templates.find((t) => t.id === id) || null;
    },

    clearError(): void {
      update((state) => ({ ...state, error: null }));
    },

    // Get templates by category
    getTemplatesByCategory(category: string): PromptTemplate[] {
      const state = get({ subscribe });
      return state.templates.filter((t) => t.category === category && t.is_active);
    },

    // Search templates
    searchTemplates(query: string): PromptTemplate[] {
      const state = get({ subscribe });
      const lowerQuery = query.toLowerCase();
      
      return state.templates.filter((template) =>
        template.is_active && (
          template.name.toLowerCase().includes(lowerQuery) ||
          template.description.toLowerCase().includes(lowerQuery) ||
          template.category.toLowerCase().includes(lowerQuery) ||
          template.tags.some(tag => tag.toLowerCase().includes(lowerQuery))
        )
      );
    },
  };
}

export const promptTemplates = createPromptTemplateStore();

// Derived stores
export const activeTemplates = derived(
  promptTemplates,
  ($templates) => $templates.templates.filter(t => t.is_active)
);

export const templatesByCategory = derived(
  promptTemplates,
  ($templates) => {
    const categorized = $templates.templates
      .filter(t => t.is_active)
      .reduce((groups, template) => {
        const category = template.category || "General";
        if (!groups[category]) {
          groups[category] = [];
        }
        groups[category].push(template);
        return groups;
      }, {} as Record<string, PromptTemplate[]>);

    return categorized;
  }
);

export const selectedTemplate = derived(
  promptTemplates,
  ($templates) => $templates.selectedTemplate
);

// Initialize templates
if (typeof window !== "undefined") {
  promptTemplates.fetchTemplates();
}
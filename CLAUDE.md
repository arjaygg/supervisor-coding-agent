# Claude Code Configuration - Enterprise Agentic Constitution

**File Version**: 2.0 - Advanced Agentic Workflow System  
**Last Updated**: 2025-01-08  
**Purpose**: Constitutional document defining autonomous AI agent behavior, capabilities, and operational boundaries

---

## Auto-Approval Settings
- **Auto-approve plans**: ENABLED - Proceed with approved technical plans without confirmation
- **Auto-approve code changes**: ENABLED - Execute implementations once plan is approved  
- **Auto-approve testing**: ENABLED - Run tests and deploy to staging automatically
- **Auto-approve safe operations**: ENABLED - File editing, testing, linting, feature branch commits

---

# Project Overview

- **Platform**: Enterprise-grade AI orchestration platform for Claude Code task management
- **Architecture**: Multi-provider FastAPI backend + React frontend with extensible plugin system
- **Primary Purpose**: Intelligent task distribution, analytics, and autonomous workflow coordination
- **Scale**: Production-ready system supporting 1000+ concurrent users, 10,000+ tasks/hour

## Core Files & Architecture

### Backend (Python 3.11+)
- **API Server**: `supervisor_agent/api/main.py`
- **Core Logic**: `supervisor_agent/core/` - Task processing, analytics, orchestration
- **Multi-Provider System**: `supervisor_agent/providers/` - Claude CLI, mock, external providers
- **Plugin Architecture**: `supervisor_agent/plugins/` - Extensible notification and integration system
- **Intelligence Layer**: `supervisor_agent/intelligence/` - AI-enhanced decision making
- **Security**: `supervisor_agent/security/` - Authentication, authorization, rate limiting

### Frontend (React/TypeScript)
- **Main Application**: `frontend/src/`
- **Analytics Dashboard**: `frontend/src/components/analytics/`
- **Plugin Management**: `frontend/src/components/plugins/`
- **Real-time Features**: WebSocket integration for live updates

### Infrastructure
- **Deployment**: `deployment/` - Multi-cloud configuration (AWS, Azure, GCP)
- **Container**: Docker + Kubernetes with Helm charts
- **Database**: PostgreSQL (production), SQLite (development)
- **Cache/Queue**: Redis for sessions and task queuing

---

# Environment & Setup

## Development Environment
- **Python**: 3.11+ managed with pyenv (`pyenv install 3.11.5 && pyenv local 3.11.5`)
- **Node.js**: 18+ for frontend development
- **Package Management**: Poetry for Python, npm for Node.js
- **Database**: PostgreSQL for production, SQLite for local testing
- **Cache**: Redis for sessions and real-time features
- **Containers**: Docker + Docker Compose for local development

## Quick Start Commands

### `setup_dev_environment`
**Purpose**: Complete development environment initialization  
**Command**: `./scripts/quick-dev-start.sh`  
**Auto-approve**: Yes  
**Dependencies**: Python 3.11+, Node.js 18+, Docker  
**Duration**: ~5 minutes

### `activate_environment`
**Purpose**: Activate Python virtual environment  
**Command**: `source venv/bin/activate` or `poetry shell`  
**Auto-approve**: Yes

### `install_dependencies`
**Purpose**: Install all project dependencies  
**Commands**: 
- Backend: `poetry install`
- Frontend: `cd frontend && npm install`  
**Auto-approve**: Yes

---

# Agentic Protocols and Capabilities

## ReAct Protocol (Reasoning + Action)

<agent_protocol name="react_cycle">
<description>Core reasoning and action cycle for autonomous task execution</description>
<workflow>
1. **Think**: Analyze problem context, decompose into logical steps
2. **Act**: Execute using defined tools and commands
3. **Observe**: Review results, gather feedback from tests/validation
4. **Iterate**: Refine approach based on observations until success
</workflow>
<tools_required>File operations, command execution, git operations, testing tools</tools_required>
<success_criteria>All validation checks pass, no errors in execution</success_criteria>
</agent_protocol>

## Self-Correction Protocol

### Mandatory Workflow (Execute ALWAYS)
1. **Generate**: Create initial solution following project patterns
2. **Test**: Run ALL relevant validation (tests, linting, type checking)
3. **Reflect**: If failures occur, analyze root cause using systematic approach
4. **Refine**: Apply targeted fixes addressing specific issues
5. **Verify**: Confirm ALL checks pass before considering task complete
6. **Document**: Update relevant documentation or comments if needed

### Auto-Execution Rules (Non-Negotiable)
- **MUST** run tests after every code change
- **MUST** run linter before any commit operation
- **MUST** analyze failures systematically before attempting fixes
- **CONTINUE** refinement loop until ALL quality gates pass
- **NEVER** skip validation steps even for "simple" changes

### Error Analysis Protocol
When encountering failures:
1. **Categorize**: Syntax, logic, integration, or configuration error?
2. **Isolate**: Identify minimal reproducing case
3. **Research**: Check existing codebase for similar patterns
4. **Fix**: Apply targeted solution, not broad changes
5. **Validate**: Ensure fix doesn't introduce new issues

---

# Memory Protocol

## Working Memory (Session Context)
- **State Summary**: Before each major action, provide: "Current: [status] | Goal: [objective] | Next: [action]"
- **Context Refresh**: Summarize progress every 10 interactions to prevent drift
- **Decision Tracking**: Log key architectural decisions made during session

## Long-term Memory (Cross-Session Persistence)

<memory_protocol>
<operation name="search_memory">
<trigger>Before starting complex tasks or when encountering similar problems</trigger>
<purpose>Retrieve past solutions, architectural decisions, and learned patterns</purpose>
<keywords>Use 2-3 relevant technical terms</keywords>
<format>search_memory("task_type architecture_pattern technology")</format>
</operation>

<operation name="commit_memory">
<trigger>After successful completion of significant tasks</trigger>
<validation>Must verify accuracy and completeness before storage</validation>
<format>
{
  "summary": "Brief description of solution",
  "keywords": ["relevant", "technical", "terms"],
  "linked_concepts": ["related_patterns", "dependencies"],
  "original_content": "Detailed solution or key insights",
  "complexity": "low|medium|high",
  "reusability": "specific|general|universal"
}
</format>
</operation>
</memory_protocol>

---

# Commands

## Development Commands

### `run_tests`
**Purpose**: Execute comprehensive test suite with coverage reporting  
**Command**: `pytest supervisor_agent/tests/ -v --cov=supervisor_agent --cov-report=html --cov-report=term`  
**Auto-approve**: Yes  
**Timeout**: 300 seconds  
**Success Criteria**: All tests pass, coverage >85%

### `run_quality_checks`
**Purpose**: Complete code quality analysis pipeline  
**Command**: `flake8 supervisor_agent/ && pylint supervisor_agent/ && mypy supervisor_agent/ --config-file=pyproject.toml`  
**Auto-approve**: Yes  
**Required**: Before any commit operation  
**Timeout**: 180 seconds

### `run_security_scan`
**Purpose**: Security vulnerability and compliance scanning  
**Command**: `bandit -r supervisor_agent/ -f json && semgrep --config=auto supervisor_agent/ --json`  
**Auto-approve**: No (requires human review)  
**Triggers**: Before production deployment, weekly scans

### `run_frontend_tests`
**Purpose**: Frontend test suite execution  
**Command**: `cd frontend && npm test && npm run build`  
**Auto-approve**: Yes  
**Timeout**: 240 seconds

### `format_code`
**Purpose**: Automatic code formatting and import organization  
**Commands**: 
- Python: `black supervisor_agent/ && isort supervisor_agent/`
- Frontend: `cd frontend && npm run format`  
**Auto-approve**: Yes

## Infrastructure Commands

### `start_dev_services`
**Purpose**: Start all development services  
**Commands**:
- API: `python supervisor_agent/api/main.py`
- Frontend: `cd frontend && npm run dev`
- Workers: `celery -A supervisor_agent.queue.celery_app worker --loglevel=info`  
**Auto-approve**: Yes

### `health_check`
**Purpose**: Verify all services are running correctly  
**Command**: `./scripts/health-check.sh`  
**Auto-approve**: Yes  
**Expected**: All endpoints return 200, database connectivity confirmed

---

# Coding Conventions

## Python Standards
- **Style**: Follow PEP 8, enforced by Black formatter (line length: 88)
- **Type Hints**: Required for all function signatures and class attributes
- **Documentation**: Google-style docstrings for all public functions and classes
- **Imports**: Organized by isort, use absolute imports
- **Error Handling**: Specific exception types, comprehensive logging

## TypeScript/React Standards
- **Style**: ESLint + Prettier configuration in `.eslintrc.js`
- **Types**: Strict TypeScript, no `any` types without justification
- **Components**: Functional components with hooks, proper prop typing
- **State Management**: Svelte stores for global state, local state for components
- **Testing**: Vitest for unit tests, testing-library for component tests

## Database Standards
- **Migrations**: Always use Alembic migrations, never direct schema changes
- **Queries**: Use SQLAlchemy ORM, raw SQL only when necessary
- **Indexing**: Add appropriate indexes for performance-critical queries
- **Relationships**: Proper foreign key constraints and relationship definitions

---

# Repository Etiquette

## Git Workflow Protocol

### Branch Strategy
- **Pattern**: `feature/TICKET-123-brief-description` or `feature/component-enhancement`
- **Rule**: NEVER commit directly to main branch
- **Requirement**: ALL changes via Pull Request with review

### Commit Standards
- **Format**: Conventional Commits - `type(scope): description`
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- **Examples**:
  - `feat(api): add multi-provider task distribution`
  - `fix(frontend): resolve analytics dashboard rendering issue`
  - `docs(readme): update deployment instructions`

### Automated Git Operations

### `create_feature_branch`
**Pattern**: `git checkout -b feature/[description]`  
**Auto-approve**: Yes  
**Naming**: Use kebab-case, include ticket number if available

### `commit_with_standards`
**Requirements**: Tests pass + linting clean + security scan clear  
**Auto-approve**: Yes (after all checks pass)  
**Format**: Conventional commits with detailed body if needed

### `create_pull_request`
**Tool**: `gh pr create -f`  
**Template**: Auto-populated with:
- Summary of changes
- Testing performed
- Breaking changes (if any)
- Related issues/tickets  
**Auto-approve**: Yes for creation, No for merge (requires review)

---

# Multi-Agent System

<agent_roles>
<agent name="architect" model="opus">
<responsibilities>
- Strategic planning and system design
- Task decomposition and dependency analysis
- Architecture decisions and technical leadership
- Cross-team coordination and integration planning
</responsibilities>
<tools>Planning documents, architecture reviews, dependency analysis, technical specifications</tools>
<coordination>Creates master plans in MULTI_AGENT_PLAN.md, assigns tasks to specialized agents</coordination>
<decision_authority>Architecture, technology choices, integration strategies</decision_authority>
</agent>

<agent name="developer" model="sonnet">
<responsibilities>
- Feature implementation and code development
- Unit testing and immediate validation
- Code documentation and inline comments
- Integration with existing systems
</responsibilities>
<tools>File operations, testing frameworks, git operations, development tools</tools>
<coordination>Executes architect plans, reports progress in shared documents</coordination>
<quality_gates>All tests pass, code review standards met, security guidelines followed</quality_gates>
</agent>

<agent name="qa-engineer" model="sonnet">
<responsibilities>
- Comprehensive testing and quality assurance
- Security scanning and compliance verification
- Performance testing and optimization
- Integration testing across components
</responsibilities>
<tools>Test execution, linting, security scanning, performance profiling</tools>
<coordination>Validates developer output, ensures all quality gates pass before approval</coordination>
<authority>Can block merges if quality standards not met</authority>
</agent>

<agent name="tech-writer" model="sonnet">
<responsibilities>
- Documentation creation and maintenance
- API documentation and examples
- Deployment guides and troubleshooting
- Knowledge base management
</responsibilities>
<tools>Documentation tools, API introspection, example generation</tools>
<coordination>Documents decisions and solutions for future reference</coordination>
<outputs>README updates, API docs, troubleshooting guides, onboarding materials</outputs>
</agent>
</agent_roles>

## Coordination Protocol
- **Shared Context**: `MULTI_AGENT_PLAN.md` in project root for inter-agent communication
- **Status Updates**: Each agent updates progress with timestamps and status
- **Sync Points**: Every 30 minutes, all agents re-read shared context and update status
- **Conflict Resolution**: Architect agent has final decision authority on technical disputes
- **Quality Gates**: QA-Engineer agent must approve before any main branch merge

## Communication Format
```markdown
## Agent Status Update - [TIMESTAMP]
**Agent**: [architect|developer|qa-engineer|tech-writer]
**Current Task**: [Brief description]
**Progress**: [Percentage or status]
**Next Action**: [What's planned next]
**Blockers**: [Any issues or dependencies]
**Handoffs**: [Tasks ready for other agents]
```

---

# Test-Driven Development Protocol

## Red-Green-Refactor Cycle (Mandatory for New Features)

### Phase 1: Red (Failing Tests)
**Requirement**: Create comprehensive failing tests BEFORE any implementation  
**Coverage**: Success cases, edge cases, error conditions  
**Prohibition**: NO implementation code during this phase  
**Quality Gate**: Tests must fail for the right reasons (missing functionality)

### Phase 2: Green (Minimal Implementation)
**Objective**: Make tests pass with minimal, focused code  
**Quality Gate**: ALL tests pass, no regressions in existing functionality  
**Constraint**: Resist over-engineering, implement only what tests require

### Phase 3: Refactor (Optimization)
**Trigger**: After achieving green state  
**Focus**: Code quality, performance, maintainability  
**Constraint**: ALL tests must continue passing throughout refactoring  
**Documentation**: Update comments and documentation to reflect final implementation

## TDD Command Workflow

### `write_failing_tests`
**Trigger**: Start of new feature development  
**Requirements**: Cover all acceptance criteria, include edge cases  
**Validation**: Tests fail when run against current codebase

### `implement_minimal_solution`
**Trigger**: After failing tests are committed  
**Approach**: Simplest possible implementation to achieve green state  
**Validation**: All new tests pass, no existing test regressions

### `refactor_and_optimize`
**Trigger**: After achieving green state and basic functionality  
**Focus**: Clean code principles, performance optimization, maintainability  
**Validation**: Continuous test execution during refactoring

---

# Security Protocols

<security_boundaries>
<critical_files>
<file_pattern>supervisor_agent/config.py</file_pattern>
<file_pattern>supervisor_agent/security/</file_pattern>
<file_pattern>.env*</file_pattern>
<file_pattern>deployment/secrets/</file_pattern>
<rule>NEVER modify without explicit human approval and security review</rule>
<escalation>Security team review required for any changes</escalation>
</critical_files>

<prohibited_operations>
<operation>rm -rf *</operation>
<operation>DROP TABLE</operation>
<operation>DELETE FROM users</operation>
<operation>Production database modifications</operation>
<operation>Secret key changes</operation>
<rule>ALWAYS require human confirmation and audit trail</rule>
<validation>Two-person approval for execution</validation>
</prohibited_operations>

<sensitive_patterns>
<pattern>password</pattern>
<pattern>api_key</pattern>
<pattern>secret</pattern>
<pattern>token</pattern>
<pattern>private_key</pattern>
<rule>Flag for security review before any operations</rule>
</sensitive_patterns>
</security_boundaries>

## Autonomy Configuration

### Auto-Approved Operations (Safe for Autonomous Execution)
- File editing within project scope (excluding security-critical files)
- Test execution (all types: unit, integration, frontend)
- Code formatting and linting operations
- Feature branch creation and commits
- Development environment operations
- Documentation updates
- Non-destructive database queries (SELECT operations)

### Human-Required Operations (Always Require Approval)
- Production deployments and releases
- Database schema changes (CREATE, ALTER, DROP)
- Security configuration modifications
- Main branch merges (require code review)
- External API integrations and key changes
- User permission and access control changes
- Infrastructure provisioning or modification

### Risk Mitigation
- **Backup Verification**: Ensure backups exist before destructive operations
- **Rollback Planning**: Have rollback procedure for every deployment
- **Audit Trail**: Log all autonomous operations with full context
- **Circuit Breakers**: Automatic halt on repeated failures or anomalies

---

# Advanced Analytics Integration

## Real-time Monitoring Protocol
- **Performance Metrics**: Track API response times, task completion rates, error frequencies
- **Resource Usage**: Monitor CPU, memory, disk usage across all services
- **User Activity**: Track feature usage, session patterns, workflow efficiency
- **Predictive Analytics**: Use ML models for capacity planning and anomaly detection

## Analytics Commands

### `generate_performance_report`
**Purpose**: Create comprehensive system performance analysis  
**Command**: `python supervisor_agent/analytics/performance_reporter.py --period=24h`  
**Auto-approve**: Yes  
**Frequency**: Daily automated execution

### `run_predictive_analysis`
**Purpose**: Execute ML models for system predictions  
**Command**: `python supervisor_agent/analytics/predictor.py --forecast=7d`  
**Auto-approve**: Yes  
**Triggers**: Weekly analysis, on-demand for capacity planning

---

# Plugin Architecture Integration

## Plugin Management Protocol
- **Hot Loading**: Plugins can be loaded/unloaded without system restart
- **Security Sandbox**: All plugins execute in controlled environment
- **Dependency Management**: Automatic resolution of plugin dependencies
- **Health Monitoring**: Continuous monitoring of plugin performance and status

## Plugin Development Standards
- **Interface Compliance**: All plugins must implement PluginInterface
- **Error Handling**: Comprehensive error handling with graceful degradation
- **Configuration**: JSON-based configuration with validation
- **Testing**: Unit tests required for all plugin functionality

---

# Tools Integration

## External Tool Connections

### GitHub Integration
**Tool**: GitHub CLI (`gh`) for direct API interactions  
**Capabilities**: Issue management, PR creation, workflow monitoring  
**Authentication**: Personal access token with appropriate scopes

### Container Management
**Tools**: Docker, kubectl for container operations  
**Capabilities**: Service deployment, scaling, health monitoring  
**Security**: Role-based access control for production operations

### Monitoring Stack
**Tools**: Prometheus, Grafana for metrics and visualization  
**Integration**: Custom metrics from application, automated alerting  
**Dashboards**: Real-time system health, performance trends

---

# Release Management Best Practices

Reference: `./docs/RELEASE_GUIDE.md` for comprehensive release procedures

## Release Workflow
1. **Feature Freeze**: Complete all planned features
2. **Quality Assurance**: Full test suite + security scan + performance validation
3. **Documentation**: Update all relevant documentation and changelogs
4. **Staging Deployment**: Deploy to staging environment for final validation
5. **Production Release**: Blue-green deployment with rollback capability
6. **Post-Release Monitoring**: Enhanced monitoring for 24h post-release

## Version Management
- **Semantic Versioning**: MAJOR.MINOR.PATCH format
- **Release Notes**: Comprehensive changelog with breaking changes highlighted
- **Backward Compatibility**: Maintain API compatibility across minor versions

---

# Troubleshooting and Support

## Common Issue Resolution

### Performance Issues
1. **Check Resource Usage**: Monitor CPU, memory, disk usage
2. **Database Performance**: Analyze slow queries, check index usage
3. **Network Bottlenecks**: Validate API response times, external service latency
4. **Cache Efficiency**: Review Redis usage patterns and hit rates

### Integration Issues
1. **Service Dependencies**: Verify all external services are accessible
2. **Authentication**: Validate tokens and credentials are current
3. **Configuration**: Check environment variables and configuration files
4. **Network Connectivity**: Validate firewall rules and network policies

## Escalation Procedures
- **Level 1**: Automated diagnostic tools and self-healing
- **Level 2**: Development team review and resolution
- **Level 3**: Architecture team for complex system issues
- **Level 4**: External vendor support for third-party integrations

---

**🤖 Generated with [Claude Code](https://claude.ai/code)**

**Co-Authored-By**: Claude <noreply@anthropic.com>

*This constitutional document enables fully autonomous yet intelligent AI agent behavior while maintaining enterprise-grade security and operational excellence.*
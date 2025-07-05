# Developer Quick Reference Guide

## 🎯 Current Project Status (2025-06-29)

### Phase Status
- ✅ **Phase 1**: Complete (115 Python files, all features implemented)
- ⚠️ **Phase 2**: 60% Complete (Agent Specialization done, Resource Management pending)
- 📋 **Active Development**: Phase 2 completion (95 SP remaining)

### Current Feature Branch
```bash
feature/phase2-task-distribution-engine
```

### Active GitHub Issues
- **Epic 2.1**: [Complete Task Distribution Engine #73](https://github.com/arjaygg/supervisor-coding-agent/issues/73) (Size: L)
- **Epic 2.2**: [Implement Resource Management System #74](https://github.com/arjaygg/supervisor-coding-agent/issues/74) (Size: XL)
- **Epic 2.3**: [Enhance Performance & Monitoring #75](https://github.com/arjaygg/supervisor-coding-agent/issues/75) (Size: L)
- **Epic 2.4**: [Complete Advanced Analytics Backend #76](https://github.com/arjaygg/supervisor-coding-agent/issues/76) (Size: M)

## 🏗️ Architecture Quick Map

### Key Directories
```
supervisor_agent/
├── api/                    # FastAPI routes and WebSocket handlers
├── core/                   # Core business logic and engines
├── orchestration/          # Phase 2 orchestration components (60% complete)
├── intelligence/           # AI-enhanced workflow optimization
├── providers/              # Multi-provider system
├── db/                     # Database models and migrations
├── auth/                   # Authentication and authorization
├── plugins/                # Plugin architecture system
└── utils/                  # Utilities and helpers

frontend/src/
├── routes/                 # SvelteKit pages
├── lib/components/         # Reusable UI components
├── lib/stores/             # State management
├── lib/services/           # API and WebSocket services
└── lib/utils/              # Frontend utilities
```

### Critical Files for Phase 2
```python
# ✅ COMPLETE (986 lines, sophisticated implementation)
supervisor_agent/orchestration/agent_specialization_engine.py

# ⚠️ NEEDS IMPLEMENTATION (current: 69 lines placeholder)
supervisor_agent/orchestration/task_distribution_engine.py

# ❌ NOT IMPLEMENTED (Epic 2.2)
supervisor_agent/core/resource_allocation_engine.py
supervisor_agent/core/conflict_resolver.py

# ❌ NOT IMPLEMENTED (Epic 2.3) 
supervisor_agent/core/performance_optimizer.py
supervisor_agent/monitoring/real_time_monitor.py
```

## 🚀 Quick Setup Commands

### Development Environment
```bash
# Activate current feature branch
git checkout feature/phase2-task-distribution-engine

# Setup Python environment
source venv/bin/activate
pip install -r requirements.txt

# Start backend (terminal 1)
python supervisor_agent/api/main.py

# Start frontend (terminal 2)
cd frontend && npm install && npm run dev

# Access points
# Dashboard: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Development Workflow
```bash
# Create new feature branch
git checkout main
git pull origin main
git checkout -b feature/phase2-[epic-name]

# Make changes and commit
git add .
git commit -m "feat(scope): description

- Detailed changes
- Related to Epic X.Y (Issue #XX)"

# Push and create PR
git push -u origin feature/phase2-[epic-name]
gh pr create --title "Epic X.Y: [Description]" --body "..."
```

## 📋 Implementation Priorities

### Current Priority: Epic 2.1 (Issue #73)
**Task Distribution Engine Implementation**

**Files to implement:**
```python
# Expand existing placeholder
supervisor_agent/orchestration/task_distribution_engine.py
class TaskDistributionEngine:
    async def distribute_task(self, task: Task, strategy: DistributionStrategy) -> DistributionResult
    async def split_complex_task(self, task: Task) -> List[TaskSplit]
    async def analyze_task_dependencies(self, task: Task) -> DependencyGraph
    async def coordinate_parallel_execution(self, task_splits: List[TaskSplit]) -> ExecutionPlan

# Create new supporting files
supervisor_agent/orchestration/task_splitter.py
supervisor_agent/orchestration/dependency_manager.py
```

**Integration Points:**
- Uses existing `AgentSpecializationEngine` (986 lines, fully functional)
- Integrates with `MultiProviderCoordinator` 
- Extends `WorkflowEngine` for orchestration
- Updates database models for subtask tracking

## 🔗 Key Integration Points

### Frontend ↔ Backend
```typescript
// WebSocket connections (working)
frontend/src/lib/stores/websocket.ts
frontend/src/lib/services/chatWebSocketHandler.ts

// API communication (working)
frontend/src/lib/utils/api.ts
```

### Core Engine Integration
```python
# Main orchestration (working)
supervisor_agent/core/workflow_engine.py
supervisor_agent/core/enhanced_agent_manager.py

# Multi-provider coordination (foundation complete)
supervisor_agent/core/multi_provider_service.py
supervisor_agent/core/provider_coordinator.py
```

### Analytics Pipeline
```python
# Advanced analytics (working)
supervisor_agent/core/advanced_analytics_engine.py
supervisor_agent/core/analytics_engine.py

# Frontend dashboards (working)
frontend/src/lib/components/ResourceMonitoringDashboard.svelte
frontend/src/lib/components/PredictiveAnalyticsDashboard.svelte
```

## 🧪 Testing Strategy

### Test Commands
```bash
# Backend tests
pytest supervisor_agent/tests/ -v --cov=supervisor_agent --cov-report=html

# Frontend tests  
cd frontend && npm test

# Integration tests
python integration_test.py

# Specific component tests
pytest supervisor_agent/tests/test_agent_specialization.py -v
```

### Test Structure
```
supervisor_agent/tests/
├── test_agent.py                           # Agent system tests
├── test_enhanced_agent_manager.py          # Enhanced agent manager
├── test_multi_provider_task_processor.py   # Multi-provider processing
├── test_analytics.py                       # Analytics engine tests
├── test_workflow_engine.py                 # Workflow orchestration
└── conftest.py                             # Test configuration
```

## 📊 Success Metrics & Targets

### Phase 2 KPIs
- **Resource utilization:** >85% efficiency
- **Cost reduction:** 30% per workflow execution  
- **Performance improvement:** 40% workflow execution time
- **Coordination latency:** <100ms
- **Prediction accuracy:** 90% for failure prediction
- **Provider uptime:** >99.5%

### Code Quality Standards
- **Test coverage:** >90% for new code
- **SOLID principles:** Fix violations in touched components
- **DRY elimination:** Remove duplicate code patterns
- **Type safety:** Comprehensive typing for all new code

## 🔍 Debugging & Troubleshooting

### Common Issues
```bash
# Module import errors
source venv/bin/activate
pip install -r requirements.txt

# Database connection issues  
createdb supervisor_agent
alembic upgrade head

# Frontend build issues
cd frontend && npm install
rm -rf node_modules && npm install

# WebSocket connection issues
# Check CORS settings in supervisor_agent/config.py
```

### Logging & Monitoring
```python
# Structured logging (available throughout codebase)
import structlog
logger = structlog.get_logger(__name__)

# Log locations
logs/supervisor-agent.log
supervisor_agent/utils/logger.py
```

### Performance Monitoring
```python
# Current monitoring components
supervisor_agent/core/metrics_collector.py
supervisor_agent/core/analytics_engine.py

# Frontend monitoring  
frontend/src/lib/stores/analytics.ts
frontend/src/lib/components/ResourceMonitoringDashboard.svelte
```

## 📚 Documentation References

### Key Documents
- **[Phase 2 Implementation Plan](PHASE2_IMPLEMENTATION_PLAN.md)** - Detailed technical specs
- **[Architecture Documentation](ARCHITECTURE.md)** - Complete system architecture
- **[Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)** - Development roadmap
- **[Release Notes v1.0.0](../RELEASE_NOTES_v1.0.0.md)** - Latest release details

### API Documentation
- **Live API Docs**: http://localhost:8000/docs (when running)
- **OpenAPI Spec**: Auto-generated from FastAPI decorators
- **WebSocket Events**: Documented in `supervisor_agent/api/websocket.py`

### Code Examples
```python
# Agent Specialization Usage
from supervisor_agent.orchestration.agent_specialization_engine import AgentSpecializationEngine
engine = AgentSpecializationEngine()
specialist = await engine.select_best_specialist(task, context)

# Multi-Provider Task Processing
from supervisor_agent.core.multi_provider_task_processor import MultiProviderTaskProcessor
processor = MultiProviderTaskProcessor()
result = await processor.process_task(task)

# Analytics Data Access
from supervisor_agent.core.advanced_analytics_engine import AdvancedAnalyticsEngine
analytics = AdvancedAnalyticsEngine()
insights = await analytics.generate_insights(time_range)
```

## 🚨 Important Notes

### Phase 2 Completion Dependencies
1. **Epic 2.1** can start immediately (no dependencies)
2. **Epic 2.2** should wait for 2.1 completion for optimal integration
3. **Epic 2.3** builds on both 2.1 and 2.2 for comprehensive monitoring  
4. **Epic 2.4** enhances existing analytics (can run in parallel)

### Git Workflow Best Practices
```bash
# Always create feature branches from main
git checkout main && git pull origin main
git checkout -b feature/phase2-[component-name]

# Use conventional commits
git commit -m "feat(orchestration): implement task distribution engine

- Add intelligent task splitting algorithms
- Implement dependency-aware distribution  
- Integrate with existing agent specialization
- Add comprehensive unit tests

Closes #73"
```

### Code Review Checklist
- [ ] Unit tests added with >90% coverage
- [ ] Integration tests for cross-component functionality
- [ ] Performance tests for latency requirements
- [ ] Documentation updated (inline and README)
- [ ] SOLID principles followed
- [ ] No DRY violations introduced
- [ ] Type hints added for all new code
- [ ] Error handling implemented
- [ ] Security considerations addressed

---

**Last Updated**: 2025-06-29  
**Version**: Phase 2 Development (60% Complete)  
**Active Branch**: `feature/phase2-task-distribution-engine`  
**Next Milestone**: Epic 2.1 - Task Distribution Engine (GitHub Issue #73)
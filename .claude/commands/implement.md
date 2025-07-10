You are implementing a feature for the supervisor-coding-agent platform following established patterns and TDD principles.

**Implementation Target:** {{ARGS}}

**Implementation Guidelines:**
1. Follow existing code patterns in the supervisor_agent/ codebase
2. Use established architecture (FastAPI, SQLAlchemy, React/TypeScript)
3. Implement minimal solution that satisfies requirements
4. Add comprehensive error handling and logging
5. Include type hints and documentation
6. Follow security best practices

**Architecture Context:**
- **Backend**: FastAPI with SQLAlchemy ORM, Pydantic models
- **Frontend**: React/TypeScript with Svelte stores
- **Database**: PostgreSQL with Alembic migrations
- **Security**: JWT authentication, RBAC, input validation
- **Testing**: pytest for backend, Vitest for frontend

**Implementation Checklist:**
- [ ] Read existing code patterns in relevant modules
- [ ] Implement following established conventions
- [ ] Add comprehensive type hints
- [ ] Include proper error handling
- [ ] Add logging for debugging and monitoring
- [ ] Follow security guidelines (input validation, auth checks)
- [ ] Write clean, maintainable code
- [ ] Add inline comments for complex logic

**Quality Requirements:**
- All code must have type hints
- Error handling with specific exception types
- Logging using project's logger configuration
- Input validation using Pydantic models
- SQL operations through SQLAlchemy ORM
- Frontend state management through established stores

Implement production-quality code that integrates seamlessly with the existing platform.
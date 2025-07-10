You are performing a guided git commit for the supervisor-coding-agent platform following conventional commit standards.

**Commit Process:**

1. **Pre-commit Validation**
   - Run all tests: `pytest supervisor_agent/tests/ -v`
   - Run quality checks: `flake8 supervisor_agent/ && pylint supervisor_agent/`
   - Run security scan: `bandit -r supervisor_agent/`
   - Frontend tests: `cd frontend && npm test`

2. **Stage Changes**
   - Review changes: `git diff`
   - Stage files: `git add [specific files]`
   - Verify staging: `git diff --cached`

3. **Commit with Standards**
   - Format: `type(scope): description`
   - Types: feat, fix, docs, style, refactor, test, chore
   - Keep description under 50 characters
   - Use imperative mood (add, fix, update)

**Commit Examples:**
```bash
feat(api): add multi-provider task distribution
fix(frontend): resolve analytics dashboard rendering
docs(readme): update deployment instructions
test(core): add unit tests for task processor
refactor(auth): simplify JWT token validation
chore(deps): update dependencies to latest versions
```

**Extended Commit Body (if needed):**
```
feat(api): add multi-provider task distribution

- Implement provider coordination engine
- Add task routing based on provider capacity
- Include health monitoring for provider endpoints
- Update API documentation

Closes #123
```

**Quality Gates:**
- All tests pass
- No linting errors
- Security scan clear
- No merge conflicts
- Proper conventional commit format

**Execution Steps:**
1. Validate all quality checks pass
2. Stage specific files (avoid `git add .`)
3. Write descriptive commit message
4. Include issue references if applicable
5. Push to feature branch (not main)

Ensure commit represents a logical, complete unit of work.
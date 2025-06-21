Release Managent Best Practices and Guide
use -> ./RELEASE_GUIDE.md

# code-review-tools-available
When conducting deep code reviews, use these configured tools available in the project:

## Python/Backend Analysis Tools:
- **flake8**: Style & syntax checking (configured)
- **pylint**: Code quality analysis (configured) 
- **mypy**: Type safety analysis (configured in mypy.ini)
- **bandit**: Security vulnerability scanning
- **semgrep**: Advanced security analysis (comprehensive rule set)
- **radon**: Cyclomatic complexity & maintainability index
- **coverage.py**: Test coverage analysis with pytest
- **black**: Code formatting (Python)
- **isort**: Import sorting (Python)

## Frontend/JavaScript Analysis Tools:
- **eslint**: JavaScript/TypeScript linting (configured with @typescript-eslint)
- **prettier**: Code formatting (configured)
- **vitest**: Testing framework
- **TypeScript**: Type checking

## Universal Code Analysis Tools:
- **scc**: Code statistics, lines of code, complexity, development estimates
- **pytest**: Testing framework (configured in pytest.ini)

## Usage Commands:
### Backend:
```bash
# From project root with virtual environment activated
source venv/bin/activate

# Static analysis
flake8 supervisor_agent/
pylint supervisor_agent/
mypy supervisor_agent/ --config-file=mypy.ini
bandit -r supervisor_agent/
semgrep --config=auto supervisor_agent/
radon cc supervisor_agent/ -a
radon mi supervisor_agent/ -a

# Testing and coverage
pytest supervisor_agent/tests/ -v --cov=supervisor_agent --cov-report=html

# Code formatting
black supervisor_agent/
isort supervisor_agent/
```

### Frontend:
```bash
# From frontend/ directory
npm run lint          # ESLint + Prettier check
npm run format        # Prettier format
npm run test          # Vitest tests
npx tsc --noEmit      # TypeScript check
```

### Universal:
```bash
# From project root
scc supervisor_agent/ frontend/src/  # Code statistics
```

## Review Process:
1. Run all static analysis tools
2. Check security with bandit + semgrep  
3. Verify test coverage and passing tests
4. Analyze code complexity and maintainability
5. Ensure proper formatting and style compliance
6. Document findings with specific file:line references

See CODE_REVIEW_REPORT.md for example comprehensive analysis results.

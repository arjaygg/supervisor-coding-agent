You are creating comprehensive documentation for the supervisor-coding-agent platform.

**Documentation Target:** {{ARGS}}

**Documentation Standards:**
1. Use clear, concise language
2. Include practical examples
3. Follow existing documentation patterns
4. Keep technical accuracy paramount
5. Focus on user needs and use cases

**Documentation Types:**

### API Documentation
```python
def process_task(task_data: TaskModel) -> TaskResult:
    """Process a task using the multi-provider system.
    
    Args:
        task_data: Task configuration and parameters
        
    Returns:
        TaskResult containing execution status and output
        
    Raises:
        ValidationError: If task_data is invalid
        ProviderError: If no providers are available
        
    Example:
        >>> task = TaskModel(
        ...     prompt="Implement user authentication",
        ...     provider="claude_cli",
        ...     timeout=300
        ... )
        >>> result = process_task(task)
        >>> print(result.status)
        'completed'
    """
```

### Component Documentation
```typescript
/**
 * Analytics Dashboard Component
 * 
 * Displays real-time system metrics and performance data.
 * 
 * @param timeRange - Time period for metrics (1h, 24h, 7d)
 * @param refreshInterval - Auto-refresh interval in seconds
 * 
 * @example
 * ```tsx
 * <AnalyticsDashboard 
 *   timeRange="24h" 
 *   refreshInterval={30} 
 * />
 * ```
 */
```

### User Guide Sections
```markdown
# Feature Name

## Overview
Brief description of what this feature does and why it's useful.

## Quick Start
Step-by-step guide to get started immediately.

## Configuration
Detailed configuration options with examples.

## Examples
Practical examples showing common use cases.

## Troubleshooting
Common issues and their solutions.

## API Reference
Detailed API documentation (if applicable).
```

**Documentation Checklist:**
- [ ] Purpose and overview clearly explained
- [ ] Installation/setup instructions included
- [ ] Configuration options documented
- [ ] Practical examples provided
- [ ] Error handling and troubleshooting covered
- [ ] API reference complete (if applicable)
- [ ] Links to related documentation
- [ ] Code examples tested and working

**Quality Requirements:**
- All code examples must be tested and functional
- Screenshots/diagrams for complex UI features
- Cross-references to related documentation
- Version information for compatibility
- Contact information for support

Create documentation that enables users to successfully use the feature without additional help.
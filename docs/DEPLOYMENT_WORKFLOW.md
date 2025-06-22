# Deployment Workflow

## Overview

The deployment workflow has been updated to provide more control over when environments are created and promoted.

## PR Environment (Manual)

**Trigger**: Comment-based deployment only
- **Command**: `/deploy`
- **Purpose**: Creates temporary PR environment for testing
- **Lifecycle**: Auto-cleanup after 24 hours
- **URL**: `http://localhost:{dynamic-port}`

### Usage
1. Create or update a PR
2. Comment `/deploy` on the PR to create environment
3. Test the changes in the temporary environment
4. Comment `/deploy-to-dev` to promote to development (optional)
5. Environment auto-cleans up after 24 hours

## Development Environment (Manual Promotion)

**Trigger**: Comment-based promotion
- **Command**: `/deploy-to-dev`
- **Purpose**: Promotes changes to persistent development environment
- **Lifecycle**: Persistent, shared with team
- **URL**: `https://dev.dev-assist.example.com`

### Usage
1. Comment `/deploy-to-dev` on any PR to promote
2. PR is automatically merged to main after successful deployment
3. Feature branch is automatically deleted
4. Team is notified of the deployment

## Available Commands

| Command | Purpose | Environment | Lifecycle |
|---------|---------|-------------|-----------|
| `/deploy` | Create PR environment | Temporary | 24 hours |
| `/deploy-to-dev` | Promote to development | Persistent | Until next deployment |
| `/cleanup` | Manual cleanup of PR environment | N/A | Immediate |
| `/rollback-dev` | Rollback development environment | Persistent | Immediate |

## Workflow Benefits

1. **No automatic deployments** - Reduces resource usage
2. **Explicit control** - Teams decide when to create environments
3. **Clear progression** - PR → Testing → Development → Main
4. **Resource efficient** - Only deploy when needed
5. **Team coordination** - Clear commands for promotion

## Migration Notes

- **Previous behavior**: PR environments were created automatically on PR open/update
- **New behavior**: PR environments are created only when `/deploy` is commented
- **Promotion**: `/deploy-to-dev` must be manually triggered via comment
- **Cleanup**: PR environments still auto-cleanup after 24 hours
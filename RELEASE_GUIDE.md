# Release Management Guide

This document describes the release management process for the Supervisor Coding Agent project using automated semantic versioning with release-please.

## Overview

Our release system uses [release-please](https://github.com/googleapis/release-please) to automate:
- Semantic version bumping based on conventional commits
- Changelog generation
- Git tag creation
- GitHub release creation
- Docker image versioning

## Project Structure

This is a monorepo with independent versioning for:
- **Frontend** (`frontend/`): SvelteKit TypeScript application
- **Backend** (`supervisor_agent/`): FastAPI Python application

## Developer Workflow

### 1. Feature Development (Standard Process)

```bash
# Create feature branch
git checkout -b feature/add-task-analytics

# Make changes and commit using conventional commits
git commit -m "feat(api): add task analytics endpoint"
git commit -m "feat(frontend): add analytics dashboard"
git commit -m "test: add analytics endpoint tests"

# Push and create PR
git push origin feature/add-task-analytics
# Create PR, get review, merge to main
```

### 2. Conventional Commits

Use the conventional commit format for all commits:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Commit Types

| Type | Description | Version Impact |
|------|-------------|----------------|
| `feat` | New feature | Minor (1.1.0 → 1.2.0) |
| `fix` | Bug fix | Patch (1.1.0 → 1.1.1) |
| `feat!` or `BREAKING CHANGE:` | Breaking change | Major (1.1.0 → 2.0.0) |
| `docs` | Documentation only | No version bump |
| `style` | Code style changes | No version bump |
| `refactor` | Code refactoring | No version bump |
| `test` | Adding/updating tests | No version bump |
| `chore` | Build/tooling changes | No version bump |
| `perf` | Performance improvements | Patch |
| `ci` | CI/CD changes | No version bump |
| `build` | Build system changes | No version bump |
| `revert` | Revert previous commit | Depends on reverted commit |

#### Scopes

Use these scopes to categorize changes:

| Scope | Description |
|-------|-------------|
| `api` | Backend API changes |
| `frontend` | Frontend application changes |
| `backend` | Backend service changes |
| `core` | Core functionality changes |
| `db` | Database related changes |
| `queue` | Task queue changes |
| `auth` | Authentication/authorization |
| `config` | Configuration changes |
| `deps` | Dependency updates |
| `docker` | Docker/containerization changes |
| `ci` | CI/CD changes |
| `docs` | Documentation |
| `tests` | Test related changes |

#### Examples

```bash
# Feature commits
git commit -m "feat(api): add user authentication endpoint"
git commit -m "feat(frontend): implement task filtering"

# Bug fixes
git commit -m "fix(api): resolve database connection timeout"
git commit -m "fix(frontend): fix modal dialog closing issue"

# Breaking changes
git commit -m "feat(api)!: redesign user management API"
git commit -m "refactor(core): change task processor interface

BREAKING CHANGE: TaskProcessor.execute() now returns Promise<Result>"

# Other changes
git commit -m "docs: update API documentation"
git commit -m "chore(deps): update dependencies to latest versions"
git commit -m "test(api): add integration tests for auth endpoints"
```

### 3. Release Process

#### Automatic Release PR Creation

After features are merged to `main`, release-please automatically:

1. **Analyzes commits** since the last release
2. **Determines version bumps** for each component (frontend/backend)
3. **Creates/updates a Release PR** with:
   - Version bumps in `package.json` and `__init__.py`
   - Generated changelog entries
   - Git tag information

#### Release PR Example

```
Title: chore: release frontend 1.2.0, backend 1.1.5

Changes:
- frontend/package.json: 1.1.0 → 1.2.0
- supervisor_agent/__init__.py: 1.1.4 → 1.1.5
- frontend/CHANGELOG.md: New entries
- CHANGELOG.md: New entries
```

#### Reviewing and Merging Release PRs

1. **Review the Release PR**:
   - Check version bumps are correct
   - Verify changelog entries
   - Test the release branch if needed

2. **Merge the Release PR**:
   - This triggers automatic release creation
   - Git tags are created (`frontend-v1.2.0`, `backend-v1.1.5`)
   - GitHub releases are published
   - Docker images are built and tagged

### 4. Deployment Integration

#### Version-Aware Deployment

The deployment system automatically detects release tags:

```bash
# Development deployment (feature/branch)
docker tag: main-20250620-123456

# Release deployment (tagged commit)
docker tag: v1.2.0
```

#### Deployment Types

| Deployment Type | Trigger | Docker Tag Format |
|----------------|---------|-------------------|
| Development | Branch/commit | `{branch}-{timestamp}` |
| Frontend Release | `frontend-v*` tag | `v{version}` |
| Backend Release | `backend-v*` tag | `v{version}` |
| Application Release | `v*` tag | `v{version}` |

#### Environment Version Tracking

Each deployment includes version metadata:

```json
{
  "deployment_id": "deploy-20250620-123456-a1b2c3d4",
  "deployment_type": "frontend-release",
  "is_release": true,
  "versions": {
    "frontend": "1.2.0",
    "backend": "1.1.5"
  },
  "images": {
    "api": "asia-southeast1-docker.pkg.dev/project/dev-assist/api:v1.2.0",
    "frontend": "asia-southeast1-docker.pkg.dev/project/dev-assist/frontend:v1.2.0"
  }
}
```

## Release Strategies

### Independent Component Releases

Components can be released independently:

```bash
# Only frontend changes
feat(frontend): add new dashboard → frontend v1.2.0 release

# Only backend changes  
fix(api): resolve memory leak → backend v1.1.6 release

# Both components changed
feat(frontend): add analytics
feat(api): add analytics endpoint
→ frontend v1.3.0 + backend v1.2.0 releases
```

### Coordinated Releases

For major releases affecting both components:

```bash
# Create coordinated changes
feat(api)!: redesign task management API
feat(frontend)!: update UI for new task API

BREAKING CHANGE: Task API endpoints have changed
→ frontend v2.0.0 + backend v2.0.0 releases
```

## Rollback Process

### Using Git Tags

```bash
# List recent releases
git tag --sort=-version:refname | head -5

# Deploy specific version
gh workflow run "🚀 Promote to Development" \
  --field branch=main \
  --ref frontend-v1.1.0
```

### Using Docker Tags

```bash
# Rollback to previous version
docker tag asia-southeast1-docker.pkg.dev/project/dev-assist/frontend:v1.1.0 \
           asia-southeast1-docker.pkg.dev/project/dev-assist/frontend:latest
```

## Hotfix Process

For critical fixes requiring immediate release:

### Option 1: Direct to Main (Emergency)

```bash
git checkout main
git commit -m "fix(api)!: patch critical security vulnerability"
git push origin main
# → release-please creates immediate Release PR
```

### Option 2: Hotfix Branch (Preferred)

```bash
git checkout -b hotfix/critical-security-fix
git commit -m "fix(api)!: patch critical security vulnerability"
git push origin hotfix/critical-security-fix
# → Create PR → Fast review → Merge → Release PR created
```

## Troubleshooting

### Release PR Not Created

**Issue**: Commits merged but no Release PR appears

**Solutions**:
1. Check commit message format (must be conventional)
2. Verify commits include changes that trigger version bumps
3. Check release-please action logs in GitHub Actions

### Wrong Version Bump

**Issue**: Version bump is incorrect

**Solutions**:
1. Check commit types (`feat` vs `fix` vs `docs`)
2. Verify breaking change notation (`!` or `BREAKING CHANGE:`)
3. Edit Release PR to adjust versions manually if needed

### Missing Components in Release

**Issue**: Only one component released when both should be

**Solutions**:
1. Ensure commits use correct scopes (`api` vs `frontend`)
2. Check that changes actually affect the missing component
3. Verify `.release-please-config.json` configuration

## Best Practices

### Commit Messages

- ✅ Use imperative mood: "add feature" not "added feature"
- ✅ Keep first line under 100 characters
- ✅ Use body for context when needed
- ✅ Reference issues: "fixes #123"

### Release Timing

- 🗓️ **Regular releases**: Weekly or bi-weekly
- 🚨 **Hotfix releases**: As needed for critical issues
- 📅 **Major releases**: Quarterly with proper communication

### Version Strategy

- 🎯 **Semantic versioning**: Follow semver.org strictly
- 🔄 **Independent components**: Allow different versions
- 📦 **Docker images**: Always tag with semantic versions
- 🏷️ **Git tags**: Use component prefixes for clarity

## Configuration Files

### `.release-please-config.json`
```json
{
  "packages": {
    "frontend": {
      "package-name": "supervisor-agent-dashboard",
      "component": "frontend",
      "release-type": "node"
    },
    "supervisor_agent": {
      "package-name": "supervisor-agent",
      "component": "backend", 
      "release-type": "python"
    }
  }
}
```

### `.release-please-manifest.json`
```json
{
  "frontend": "1.0.0",
  "supervisor_agent": "1.0.0"
}
```

## Support

For questions about the release process:
1. Check this guide first
2. Review [release-please documentation](https://github.com/googleapis/release-please)
3. Ask in team chat or create an issue
4. Review recent Release PRs for examples